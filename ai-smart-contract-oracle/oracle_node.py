#!/usr/bin/env python3
"""Decentralized oracle node (HTTP-queue variant).

This version polls an off-chain HTTP queue (CONFIG.pending_url) to fetch tasks,
calls the inference service, signs results, and submits transactions to the
AIOracleAggregator contract on the local Hardhat node.

Place this file at the project root (same folder as .env), ensure:
 - smart_contracts/oracle_aggregator_abi.json exists
 - .env contains ETH_RPC_URL, ORACLE_PRIVATE_KEY, ORACLE_ADDRESS, ORACLE_CONTRACT_ADDRESS, INFERENCE_URL, etc.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import AsyncRetrying, RetryError, retry, stop_after_attempt, wait_fixed
from web3 import HTTPProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

# --- Logging setup ---
logger = logging.getLogger("oracle_node")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

# --- Constants ---
ABI_PATH = Path("smart_contracts/oracle_aggregator_abi.json")
MODEL_VERSION = "1.0"
DEFAULT_PENDING_URL = "http://127.0.0.1:9000/pending"
DEFAULT_MARK_COMPLETE_URL = "http://127.0.0.1:9000/mark-complete"

app = FastAPI(title="Oracle Node (HTTP Queue)", version=MODEL_VERSION)


# --- Config model ---
class OracleConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    oracle_private_key: str = Field(..., validation_alias="ORACLE_PRIVATE_KEY")
    eth_rpc_url: str = Field(..., validation_alias="ETH_RPC_URL")
    oracle_address: str = Field(..., validation_alias="ORACLE_ADDRESS")
    contract_address: str = Field(..., validation_alias="ORACLE_CONTRACT_ADDRESS")
    inference_url: str = Field(..., validation_alias="INFERENCE_URL")
    poll_interval: float = Field(5.0, validation_alias="POLL_INTERVAL")
    pending_url: Optional[str] = Field(DEFAULT_PENDING_URL, validation_alias="PENDING_TASK_URL")
    mark_complete_url: Optional[str] = Field(DEFAULT_MARK_COMPLETE_URL, validation_alias="MARK_COMPLETE_URL")

    @field_validator("poll_interval", mode="before")
    @classmethod
    def validate_poll_interval(cls, value: Any) -> float:
        try:
            return float(value)
        except Exception as exc:  # pragma: no cover
            raise ValueError("POLL_INTERVAL must be numeric") from exc

    @field_validator("oracle_private_key", mode="before")
    @classmethod
    def normalize_private_key(cls, value: str) -> str:
        if value is None:
            raise ValueError("ORACLE_PRIVATE_KEY is required")
        stripped = value.strip()
        return stripped if stripped.startswith("0x") else f"0x{stripped}"


# --- Pydantic models for tasks & status ---
class TaskPayload(BaseModel):
    contract_address: str
    source_code: Optional[str] = None
    bytecode: Optional[str] = None

    @field_validator("contract_address", mode="before")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        if not value:
            raise ValueError("contract_address is required")
        return value.strip()

    @model_validator(mode="after")
    @classmethod
    def ensure_payload(cls, data: "TaskPayload") -> "TaskPayload":
        if not data.source_code and not data.bytecode:
            raise ValueError("Task requires source_code or bytecode")
        return data


class OracleStatus(BaseModel):
    last_tx_hash: Optional[str] = None
    last_score: Optional[float] = None
    last_signature: Optional[str] = None
    last_contract_address: Optional[str] = None
    last_category: Optional[int] = None


# --- Global handles (populated at startup) ---
CONFIG: Optional[OracleConfig] = None
WEB3: Optional[Web3] = None
CONTRACT = None
ACCOUNT = None
HTTP_CLIENT: Optional[httpx.AsyncClient] = None
POLL_TASK: Optional[asyncio.Task] = None
STATUS = OracleStatus()


# --- Custom exception for clarity ---
class OracleError(Exception):
    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


# --- Utilities ---
def load_env() -> OracleConfig:
    """Load environment variables using python-dotenv and Pydantic settings."""
    load_dotenv()
    config = OracleConfig()
    logger.info("Environment loaded for oracle at %s", config.oracle_address)
    return config


def load_contract(web3: Web3, contract_address: str) -> Any:
    if not ABI_PATH.exists():
        raise FileNotFoundError(f"Contract ABI not found at {ABI_PATH}")
    abi_text = ABI_PATH.read_text(encoding="utf-8")
    try:
        abi = json.loads(abi_text)
    except Exception as exc:
        raise ValueError(f"Failed to parse ABI at {ABI_PATH}: {exc}") from exc
    checksum_address = Web3.to_checksum_address(contract_address)
    return web3.eth.contract(address=checksum_address, abi=abi)


async def call_inference_service(task: TaskPayload) -> Dict[str, Any]:
    """Call the inference service (CONFIG.inference_url) with retrying."""
    if CONFIG is None or HTTP_CLIENT is None:
        raise OracleError("Service not initialized")
    if not task.source_code and not task.bytecode:
        raise OracleError("Task payload missing analyzable content")
    payload = {
        "source_code": task.source_code,
        "bytecode": task.bytecode,
        "contract_address": task.contract_address,
    }
    logger.info("Calling inference service for %s", task.contract_address)
    try:
        retryer = AsyncRetrying(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
        async for attempt in retryer:
            with attempt:
                response = await HTTP_CLIENT.post(CONFIG.inference_url, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                if "risk_score" not in data:
                    raise OracleError("Inference response missing risk_score")
                return data
    except RetryError as exc:
        raise OracleError("Inference service unreachable", str(exc)) from exc
    except httpx.HTTPError as exc:
        raise OracleError("Inference request failed", str(exc)) from exc


def sign_message(contract_address: str, risk_score: float, ipfs_cid: str = "") -> Tuple[str, bytes]:
    if ACCOUNT is None:
        raise OracleError("Account not initialized")
    raw_message = f"{contract_address}|{risk_score}|{ipfs_cid}"
    message = encode_defunct(text=raw_message)
    signed = ACCOUNT.sign_message(message)
    signature_hex = signed.signature.hex()
    return signature_hex, signed.signature


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), reraise=True)
def submit_to_blockchain(
    contract_address: str,
    risk_score: float,
    ipfs_cid: str = "",
) -> str:
    """Submit the assessment to the on-chain AIOracleAggregator contract."""
    if WEB3 is None or CONTRACT is None or ACCOUNT is None or CONFIG is None:
        raise OracleError("Blockchain client not initialized")

    checksum_target = Web3.to_checksum_address(contract_address)
    score_int = int(max(min(risk_score, 100.0), 0.0))

    tx = CONTRACT.functions.submitAssessment(
        checksum_target,
        score_int,
        ipfs_cid,
    ).build_transaction(
        {
            "from": Web3.to_checksum_address(CONFIG.oracle_address),
            "nonce": WEB3.eth.get_transaction_count(Web3.to_checksum_address(CONFIG.oracle_address)),
            "gas": 500000,
            "gasPrice": WEB3.eth.gas_price,
            "chainId": WEB3.eth.chain_id,
        }
    )
    signed_tx = WEB3.eth.account.sign_transaction(tx, private_key=ACCOUNT.key)
    raw_tx = getattr(signed_tx, "rawTransaction", None) or getattr(signed_tx, "raw_transaction", None)
    if raw_tx is None:
        raise OracleError("Signed transaction missing raw bytes")
    tx_hash = WEB3.eth.send_raw_transaction(raw_tx)
    logger.info("Submitted transaction %s", tx_hash.hex())
    return tx_hash.hex()


# --- Task queue interactions (HTTP) ---
async def fetch_pending_tasks() -> List[TaskPayload]:
    """Fetch pending tasks from the configured HTTP pending_url.

    The pending endpoint is expected to return either:
      - a JSON array of task objects
      - or a JSON object containing {"tasks": [...]}
    """
    if CONFIG is None or HTTP_CLIENT is None or not CONFIG.pending_url:
        logger.debug("No pending_url configured or HTTP client missing")
        return []
    try:
        retryer = AsyncRetrying(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
        async for attempt in retryer:
            with attempt:
                logger.debug("Fetching pending tasks from %s", CONFIG.pending_url)
                response = await HTTP_CLIENT.get(CONFIG.pending_url, timeout=15)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    tasks_data = payload
                elif isinstance(payload, dict) and "tasks" in payload and isinstance(payload["tasks"], list):
                    tasks_data = payload["tasks"]
                else:
                    # fallback: maybe it's an array under a key like "pending"
                    tasks_data = payload.get("pending", []) if isinstance(payload, dict) else []
                tasks = []
                for t in tasks_data:
                    # tolerate keys: contract_address, ipfsCid, source_code, bytecode
                    try:
                        tasks.append(TaskPayload(**t))
                    except Exception as exc:
                        logger.warning("Skipping invalid task payload %s: %s", t, exc)
                return tasks
    except RetryError as exc:
        logger.warning("Pending-task endpoint unreachable: %s", exc)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to fetch pending tasks: %s", exc)
    return []


async def mark_task_complete(contract_address: str, tx_hash: str) -> None:
    """Tell the task queue the task was completed (POST to mark_complete_url)."""
    if CONFIG is None or HTTP_CLIENT is None or not CONFIG.mark_complete_url:
        logger.debug("mark_complete_url not configured, not marking")
        return
    payload = {"contract_address": contract_address, "tx_hash": tx_hash}
    try:
        retryer = AsyncRetrying(stop=stop_after_attempt(3), wait=wait_fixed(2), reraise=True)
        async for attempt in retryer:
            with attempt:
                response = await HTTP_CLIENT.post(CONFIG.mark_complete_url, json=payload, timeout=10)
                response.raise_for_status()
                logger.info("Marked task complete for %s", contract_address)
                return
    except RetryError as exc:
        logger.warning("Failed to mark task complete: %s", exc)
    except Exception as exc:
        logger.exception("Error while marking task complete: %s", exc)


# --- Task processing ---
async def process_task(task: TaskPayload) -> Dict[str, Any]:
    if not task.contract_address:
        raise OracleError("contract_address is required")
    start_time = time.perf_counter()

    # Call inference
    inference = await call_inference_service(task)
    try:
        risk_score = float(inference.get("risk_score", 0.0))
    except Exception:
        risk_score = 0.0
    risk_score = max(min(risk_score, 100.0), 0.0)
    risk_category = inference.get("risk_category")

    signature_hex, _ = sign_message(task.contract_address, risk_score)

    tx_hash = await asyncio.to_thread(submit_to_blockchain, task.contract_address, risk_score)

    # Mark completed on the queue
    await mark_task_complete(task.contract_address, tx_hash)

    # Update status
    STATUS.last_tx_hash = tx_hash
    STATUS.last_score = risk_score
    STATUS.last_signature = signature_hex
    STATUS.last_contract_address = task.contract_address
    STATUS.last_category = int(risk_category) if isinstance(risk_category, (int, float)) else None

    duration = time.perf_counter() - start_time
    logger.info("Processed task for %s in %.2fs (tx=%s)", task.contract_address, duration, tx_hash)
    return {
        "tx_hash": tx_hash,
        "risk_score": risk_score,
        "signature": signature_hex,
        "contract_address": task.contract_address,
    "risk_category": risk_category,
    }


async def poll_tasks() -> None:
    if CONFIG is None:
        logger.error("CONFIG missing; poll loop exiting")
        return
    logger.info("Starting polling loop with %.1fs interval", CONFIG.poll_interval)
    while True:
        try:
            tasks = await fetch_pending_tasks()
            if tasks:
                logger.info("Fetched %d pending task(s)", len(tasks))
            for task in tasks:
                try:
                    await process_task(task)
                except Exception as exc:  # pragma: no cover
                    logger.exception("Failed to process task %s: %s", getattr(task, "contract_address", "?"), exc)
        except Exception as exc:
            logger.exception("Polling loop error: %s", exc)
        await asyncio.sleep(CONFIG.poll_interval)


# --- FastAPI helpers ---
def json_error(message: str, details: Optional[str] = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": True, "message": message, "details": details})


@app.on_event("startup")
async def on_startup() -> None:
    global CONFIG, WEB3, CONTRACT, ACCOUNT, HTTP_CLIENT, POLL_TASK
    try:
        CONFIG = load_env()
    except Exception as exc:
        logger.exception("Failed to load environment/config: %s", exc)
        raise

    # HTTP client used for inference + task queue
    HTTP_CLIENT = httpx.AsyncClient(timeout=30.0)

    # Web3 setup
    try:
        WEB3 = Web3(HTTPProvider(CONFIG.eth_rpc_url))
        # keep ExtraDataToPOAMiddleware for local chains like Hardhat/Ganache if needed
        WEB3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    except Exception as exc:
        logger.exception("Failed to initialize Web3: %s", exc)
        raise

    # Load contract ABI and instantiate contract
    try:
        CONTRACT = load_contract(WEB3, CONFIG.contract_address)
    except Exception as exc:
        logger.exception("Failed to load contract: %s", exc)
        raise

    # Load account from private key
    try:
        ACCOUNT = Account.from_key(CONFIG.oracle_private_key)
    except Exception as exc:
        logger.exception("Failed to initialize account from private key: %s", exc)
        raise

    # Start the polling loop
    POLL_TASK = asyncio.create_task(poll_tasks())
    logger.info("Oracle node initialized for %s", CONFIG.oracle_address)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global HTTP_CLIENT, POLL_TASK
    if POLL_TASK:
        POLL_TASK.cancel()
        try:
            await POLL_TASK
        except Exception:
            pass
    if HTTP_CLIENT:
        await HTTP_CLIENT.aclose()


@app.get("/health")
async def health() -> Dict[str, Any]:
    if CONFIG is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return {"status": "ok", "node": CONFIG.oracle_address}


@app.get("/status")
async def status_endpoint() -> Dict[str, Any]:
    return STATUS.dict()


@app.post("/submit-task")
async def submit_task(task: TaskPayload, request: Request) -> JSONResponse:
    logger.info("Manual task submission from %s", request.client.host if request.client else "unknown")
    try:
        result = await process_task(task)
        return JSONResponse(content=result)
    except OracleError as exc:
        return json_error(exc.message, exc.details)
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error during manual submission: %s", exc)
        return json_error("Unexpected server error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- Run directly for local development ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("oracle_node:app", host="0.0.0.0", port=8100, reload=True)
