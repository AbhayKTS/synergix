#!/usr/bin/env python3
"""Decentralized oracle node for on-chain AI risk submissions."""

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
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import AsyncRetrying, RetryError, retry, stop_after_attempt, wait_fixed
from web3 import HTTPProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

ABI_PATH = Path("smart_contracts/oracle_aggregator_abi.json")
MODEL_VERSION = "1.0"
DEFAULT_PENDING_URL = "http://localhost:9000/pending"
DEFAULT_MARK_COMPLETE_URL = "http://localhost:9000/mark-complete"

app = FastAPI(title="Oracle Node", version=MODEL_VERSION)


class OracleConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    oracle_private_key: str = Field(..., validation_alias="ORACLE_PRIVATE_KEY")
    eth_rpc_url: str = Field(..., validation_alias="ETH_RPC_URL")
    oracle_address: str = Field(..., validation_alias="ORACLE_ADDRESS")
    contract_address: str = Field(..., validation_alias="ORACLE_CONTRACT_ADDRESS")
    inference_url: str = Field(..., validation_alias="INFERENCE_URL")
    poll_interval: float = Field(5.0, validation_alias="POLL_INTERVAL")
    pending_url: Optional[str] = Field(DEFAULT_PENDING_URL, validation_alias="PENDING_TASK_URL")
    mark_complete_url: Optional[str] = Field(DEFAULT_MARK_COMPLETE_URL, validation_alias="MARK_COMPLETE_URL")

    @validator("poll_interval", pre=True)
    def validate_poll_interval(cls, value: Any) -> float:
        try:
            return float(value)
        except Exception as exc:  # pragma: no cover
            raise ValueError("POLL_INTERVAL must be numeric") from exc


class TaskPayload(BaseModel):
    contract_address: str
    source_code: Optional[str] = None
    bytecode: Optional[str] = None
    ipfsCid: Optional[str] = None


class OracleStatus(BaseModel):
    last_tx_hash: Optional[str] = None
    last_score: Optional[float] = None
    last_signature: Optional[str] = None
    last_contract_address: Optional[str] = None


CONFIG: Optional[OracleConfig] = None
WEB3: Optional[Web3] = None
CONTRACT = None
ACCOUNT = None
HTTP_CLIENT: Optional[httpx.AsyncClient] = None
POLL_TASK: Optional[asyncio.Task] = None
STATUS = OracleStatus()


class OracleError(Exception):
    """Custom exception for oracle operations."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def load_env() -> OracleConfig:
    """Load environment variables using python-dotenv and Pydantic settings."""

    load_dotenv()
    config = OracleConfig()
    logger.info("Environment loaded for oracle at %s", config.oracle_address)
    return config


def load_contract(web3: Web3, contract_address: str) -> Any:
    if not ABI_PATH.exists():
        raise FileNotFoundError(f"Contract ABI not found at {ABI_PATH}")
    abi = json.loads(ABI_PATH.read_text(encoding="utf-8"))
    checksum_address = Web3.to_checksum_address(contract_address)
    return web3.eth.contract(address=checksum_address, abi=abi)


async def call_inference_service(task: TaskPayload) -> Dict[str, Any]:
    if CONFIG is None or HTTP_CLIENT is None:
        raise OracleError("Service not initialized")
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
                return response.json()
    except RetryError as exc:
        raise OracleError("Inference service unreachable", str(exc)) from exc


def sign_message(contract_address: str, risk_score: float, ipfs_cid: str) -> Tuple[str, bytes]:
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
    ipfs_cid: str,
) -> str:
    if WEB3 is None or CONTRACT is None or ACCOUNT is None or CONFIG is None:
        raise OracleError("Blockchain client not initialized")

    checksum_target = Web3.to_checksum_address(contract_address)
    score_int = int(max(min(risk_score, 1.0), 0.0) * 100)
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
    raw_tx = getattr(signed_tx, "rawTransaction", None)
    if raw_tx is None:
        raw_tx = getattr(signed_tx, "raw_transaction", None)
    if raw_tx is None:
        raise OracleError("Signed transaction missing raw bytes")
    tx_hash = WEB3.eth.send_raw_transaction(raw_tx)
    logger.info("Submitted transaction %s", tx_hash.hex())
    return tx_hash.hex()


async def fetch_pending_tasks() -> List[TaskPayload]:
    """Fetch pending tasks directly from the smart contract (recommended)."""
    if WEB3 is None or CONTRACT is None:
        return []

    try:
        # Call the smart contract to get pending contract addresses
        pending = CONTRACT.functions.getPendingTasks().call()

        tasks = []
        for addr in pending:
            tasks.append(TaskPayload(contract_address=addr))

        if pending:
            logger.info("Fetched %d pending tasks from blockchain", len(tasks))

        return tasks

    except Exception as exc:
        logger.exception("Failed to fetch pending tasks from blockchain: %s", exc)
        return []



async def mark_task_complete(contract_address: str, tx_hash: str) -> None:
    if CONFIG is None or HTTP_CLIENT is None or not CONFIG.mark_complete_url:
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


async def process_task(task: TaskPayload) -> Dict[str, Any]:
    if not task.contract_address:
        raise OracleError("contract_address is required")
    start_time = time.perf_counter()
    inference = await call_inference_service(task)
    risk_score = float(inference.get("risk_score", 0.0))
    ipfs_cid = task.ipfsCid or inference.get("ipfsCid", "")
    signature_hex, _ = sign_message(task.contract_address, risk_score, ipfs_cid)
    tx_hash = await asyncio.to_thread(submit_to_blockchain, task.contract_address, risk_score, ipfs_cid)
    await mark_task_complete(task.contract_address, tx_hash)
    STATUS.last_tx_hash = tx_hash
    STATUS.last_score = risk_score
    STATUS.last_signature = signature_hex
    STATUS.last_contract_address = task.contract_address
    duration = time.perf_counter() - start_time
    logger.info("Processed task for %s in %.2fs", task.contract_address, duration)
    return {
        "tx_hash": tx_hash,
        "risk_score": risk_score,
        "signature": signature_hex,
        "contract_address": task.contract_address,
        "ipfsCid": ipfs_cid,
    }


async def poll_tasks() -> None:
    if CONFIG is None:
        return
    logger.info("Starting polling loop with %.1fs interval", CONFIG.poll_interval)
    while True:
        try:
            tasks = await fetch_pending_tasks()
            for task in tasks:
                try:
                    await process_task(task)
                except Exception as exc:  # pragma: no cover
                    logger.exception("Failed to process task %s: %s", task.contract_address, exc)
        except Exception as exc:  # pragma: no cover
            logger.exception("Polling loop error: %s", exc)
        await asyncio.sleep(CONFIG.poll_interval)


def json_error(message: str, details: Optional[str] = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": True, "message": message, "details": details})


@app.on_event("startup")
async def on_startup() -> None:  # pragma: no cover - framework lifecycle
    global CONFIG, WEB3, CONTRACT, ACCOUNT, HTTP_CLIENT, POLL_TASK
    CONFIG = load_env()
    HTTP_CLIENT = httpx.AsyncClient(timeout=30.0)
    WEB3 = Web3(HTTPProvider(CONFIG.eth_rpc_url))
    WEB3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    CONTRACT = load_contract(WEB3, CONFIG.contract_address)
    ACCOUNT = Account.from_key(CONFIG.oracle_private_key)
    POLL_TASK = asyncio.create_task(poll_tasks())
    logger.info("Oracle node initialized for %s", CONFIG.oracle_address)


@app.on_event("shutdown")
async def on_shutdown() -> None:  # pragma: no cover
    global HTTP_CLIENT, POLL_TASK
    if POLL_TASK:
        POLL_TASK.cancel()
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("oracle_node:app", host="0.0.0.0", port=8100, reload=True)
