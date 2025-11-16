"""
FastAPI API Gateway

Features:
- Caches latest risk results in Redis (optional; falls back to in-memory cache)
- GET /risk/{contractAddress} -> returns latest risk result (fast)
- GET /history/{contractAddress} -> returns on-chain history (AssessmentSubmitted events and RiskAlertIssued)
- Fetches final risk from chain using Web3; if none or not finalized, falls back to backend analysis service (/analyze)

Configuration via environment variables:
- SEPOLIA_RPC (default placeholder)
- ORACLE_CONTRACT_ADDRESS (address of deployed AIOracleAggregator)
- ANALYSIS_SERVICE_URL (http://host:port) used if no cached/on-chain final result
- REDIS_URL (optional) e.g. redis://localhost:6379/0
- CACHE_TTL (seconds) default 300

Dependencies:
  pip install fastapi uvicorn web3 httpx redis asyncio
  # For async redis (optional): pip install aioredis

"""

import os
import json
import asyncio
import logging
from typing import Optional, Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Try to import redis clients
try:
    import aioredis
    AIREDIS_AVAILABLE = True
except Exception:
    aioredis = None
    AIREDIS_AVAILABLE = False

try:
    import redis as redis_sync
    REDIS_SYNC_AVAILABLE = True
except Exception:
    redis_sync = None
    REDIS_SYNC_AVAILABLE = False

import httpx
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_gateway")

# Config
SEPOLIA_RPC = os.environ.get('SEPOLIA_RPC', 'https://sepolia.infura.io/v3/YOUR-PROJECT-ID')
ORACLE_CONTRACT_ADDRESS = os.environ.get('ORACLE_CONTRACT_ADDRESS')
ANALYSIS_SERVICE_URL = os.environ.get('ANALYSIS_SERVICE_URL', 'http://127.0.0.1:8000')
REDIS_URL = os.environ.get('REDIS_URL')
CACHE_TTL = int(os.environ.get('CACHE_TTL', '300'))

# Minimal ABI for the AIOracleAggregator (getTargetState + events)
ORACLE_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "target", "type": "address"}
        ],
        "name": "getTargetState",
        "outputs": [
            {"internalType": "uint16", "name": "total", "type": "uint16"},
            {"internalType": "uint16", "name": "cntSafe", "type": "uint16"},
            {"internalType": "uint16", "name": "cntCaution", "type": "uint16"},
            {"internalType": "uint16", "name": "cntDanger", "type": "uint16"},
            {"internalType": "bool", "name": "finalized", "type": "bool"},
            {"internalType": "uint8", "name": "finalCategory", "type": "uint8"},
            {"internalType": "uint256", "name": "finalScore", "type": "uint256"},
            {"internalType": "string", "name": "finalIpfsCid", "type": "string"},
            {"internalType": "uint40", "name": "finalTimestamp", "type": "uint40"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "target", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "oracle", "type": "address"},
            {"indexed": False, "internalType": "uint8", "name": "category", "type": "uint8"},
            {"indexed": False, "internalType": "uint256", "name": "score", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "ipfsCid", "type": "string"}
        ],
        "name": "AssessmentSubmitted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "target", "type": "address"},
            {"indexed": False, "internalType": "uint8", "name": "category", "type": "uint8"},
            {"indexed": False, "internalType": "uint256", "name": "score", "type": "uint256"},
            {"indexed": False, "internalType": "string", "name": "ipfsCid", "type": "string"}
        ],
        "name": "RiskAlertIssued",
        "type": "event"
    }
]

# FastAPI app
app = FastAPI(title="AI Smart Contract Oracle API Gateway")

# Global connections (initialized on startup)
W3: Optional[Web3] = None
CONTRACT = None
redis = None
memory_cache: Dict[str, Dict[str, Any]] = {}  # key -> {'value':..., 'expiry': ts}


class RiskResponse(BaseModel):
    risk_score: Optional[float]
    risk_label: Optional[str]
    ipfs_cid: Optional[str]
    source: str  # 'onchain' | 'analysis_service'
    details: Optional[Dict[str, Any]]


@app.on_event("startup")
async def startup_event():
    global W3, CONTRACT, redis
    # Setup Web3
    W3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC))
    # Some testnets need PoA middleware
    try:
        W3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    if ORACLE_CONTRACT_ADDRESS:
        try:
            CONTRACT = W3.eth.contract(address=W3.toChecksumAddress(ORACLE_CONTRACT_ADDRESS), abi=ORACLE_ABI)
            logger.info('Contract initialized at %s', ORACLE_CONTRACT_ADDRESS)
        except Exception as e:
            logger.warning('Could not init contract: %s', e)
            CONTRACT = None
    else:
        logger.warning('ORACLE_CONTRACT_ADDRESS not set; on-chain fetch disabled')
        CONTRACT = None

    # Setup Redis if available
    if REDIS_URL:
        if AIREDIS_AVAILABLE:
            try:
                redis = await aioredis.from_url(REDIS_URL)
                logger.info('Connected to Redis (aioredis)')
            except Exception as e:
                logger.warning('aioredis connection failed: %s', e)
                redis = None
        elif REDIS_SYNC_AVAILABLE:
            try:
                # fallback to sync redis client (will be used in threadpool)
                redis = redis_sync.from_url(REDIS_URL)
                logger.info('Connected to Redis (sync)')
            except Exception as e:
                logger.warning('redis-py connection failed: %s', e)
                redis = None
        else:
            logger.warning('Redis requested but no client available; using in-memory cache')
            redis = None
    else:
        logger.info('No REDIS_URL provided; using in-memory cache')
        redis = None


# ---- Caching helpers ----
async def get_cached(key: str) -> Optional[Dict[str, Any]]:
    # Try Redis (aioredis)
    if redis is not None and AIREDIS_AVAILABLE and isinstance(redis, aioredis.Redis):
        try:
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning('Redis get failed: %s', e)
    # Try sync redis (used via thread)
    if redis is not None and REDIS_SYNC_AVAILABLE and not AIREDIS_AVAILABLE:
        try:
            def _get():
                val = redis.get(key)
                return val
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, _get)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning('sync Redis get failed: %s', e)
    # In-memory
    entry = memory_cache.get(key)
    if entry:
        if entry['expiry'] >= asyncio.get_event_loop().time():
            return entry['value']
        else:
            # expired
            memory_cache.pop(key, None)
    return None


async def set_cached(key: str, value: Dict[str, Any], ttl: int = CACHE_TTL) -> None:
    if redis is not None and AIREDIS_AVAILABLE and isinstance(redis, aioredis.Redis):
        try:
            await redis.set(key, json.dumps(value), ex=ttl)
            return
        except Exception as e:
            logger.warning('Redis set failed: %s', e)
    if redis is not None and REDIS_SYNC_AVAILABLE and not AIREDIS_AVAILABLE:
        try:
            def _set():
                redis.set(key, json.dumps(value), ex=ttl)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _set)
            return
        except Exception as e:
            logger.warning('sync Redis set failed: %s', e)
    # fallback to in-memory
    memory_cache[key] = {'value': value, 'expiry': asyncio.get_event_loop().time() + ttl}


# ---- On-chain fetch ----
async def fetch_onchain_result(target: str) -> Optional[RiskResponse]:
    """Call contract.getTargetState(target) and return RiskResponse if finalized."""
    if CONTRACT is None:
        return None
    try:
        # web3 is sync; run in executor
        def _call():
            return CONTRACT.functions.getTargetState(Web3.toChecksumAddress(target)).call()
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(None, _call)
        # res: (total, cntSafe, cntCaution, cntDanger, finalized, finalCategory, finalScore, finalIpfsCid, finalTimestamp)
        total, cntSafe, cntCaution, cntDanger, finalized, finalCategory, finalScore, finalIpfsCid, finalTimestamp = res
        if not finalized:
            return None
        # normalize finalScore: if <=100 treat as percentage
        risk_score = None
        try:
            if finalScore <= 100:
                risk_score = float(finalScore) / 100.0
            else:
                risk_score = float(finalScore)
        except Exception:
            risk_score = None
        label_map = {1: 'safe', 2: 'caution', 3: 'dangerous'}
        label = label_map.get(int(finalCategory), None)
        response = RiskResponse(
            risk_score=risk_score,
            risk_label=label,
            ipfs_cid=finalIpfsCid,
            source='onchain',
            details={
                'total': int(total),
                'cntSafe': int(cntSafe),
                'cntCaution': int(cntCaution),
                'cntDanger': int(cntDanger),
                'finalTimestamp': int(finalTimestamp)
            }
        )
        return response.dict()
    except Exception as e:
        logger.warning('On-chain fetch failed: %s', e)
        return None


# ---- Analysis service fallback ----
async def call_analysis_service(target: str) -> Optional[RiskResponse]:
    url = f"{ANALYSIS_SERVICE_URL.rstrip('/')}/analyze"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json={"contract_address": target})
            if r.status_code != 200:
                logger.warning('Analysis service returned %s: %s', r.status_code, r.text)
                return None
            data = r.json()
            # expected keys: risk_score, risk_label, ipfs_cid, feature_details
            rr = RiskResponse(
                risk_score=data.get('risk_score'),
                risk_label=data.get('risk_label'),
                ipfs_cid=data.get('ipfs_cid'),
                source='analysis_service',
                details=data.get('feature_details')
            )
            return rr.dict()
    except Exception as e:
        logger.warning('Analysis service call failed: %s', e)
        return None


# ---- History fetch (events) ----
async def fetch_history_from_chain(target: str, from_block: int = 0, to_block: Optional[int] = None) -> Dict[str, Any]:
    if CONTRACT is None:
        raise HTTPException(status_code=500, detail='On-chain contract not configured')
    if to_block is None:
        try:
            to_block = W3.eth.block_number
        except Exception:
            to_block = 'latest'
    try:
        # build topic for the indexed target
        target_topic = Web3.keccak(hexstr=Web3.toChecksumAddress(target).lower()).hex() if False else None
        # We'll use contract.events to create filters and fetch logs
        loop = asyncio.get_running_loop()
        def _get_logs():
            logs_assess = CONTRACT.events.AssessmentSubmitted().getLogs(fromBlock=from_block, toBlock=to_block, argument_filters={'target': Web3.toChecksumAddress(target)})
            logs_alerts = CONTRACT.events.RiskAlertIssued().getLogs(fromBlock=from_block, toBlock=to_block, argument_filters={'target': Web3.toChecksumAddress(target)})
            return logs_assess, logs_alerts
        logs_assess, logs_alerts = await loop.run_in_executor(None, _get_logs)
        # normalize logs
        assessments = []
        for ev in logs_assess:
            # ev args: target, oracle, category, score, ipfsCid
            a = {
                'oracle': ev['args']['oracle'],
                'category': int(ev['args']['category']),
                'score': int(ev['args']['score']),
                'ipfs_cid': ev['args']['ipfsCid'],
                'blockNumber': ev['blockNumber'],
                'transactionHash': ev['transactionHash'].hex()
            }
            assessments.append(a)
        alerts = []
        for ev in logs_alerts:
            alert = {
                'category': int(ev['args']['category']),
                'score': int(ev['args']['score']),
                'ipfs_cid': ev['args']['ipfsCid'],
                'blockNumber': ev['blockNumber'],
                'transactionHash': ev['transactionHash'].hex()
            }
            alerts.append(alert)
        return {'assessments': assessments, 'alerts': alerts}
    except Exception as e:
        logger.warning('fetch_history failed: %s', e)
        raise HTTPException(status_code=500, detail=f'History fetch failed: {e}')


# --- Routes ---
@app.get('/risk/{contract_address}', response_model=RiskResponse)
async def get_risk(contract_address: str):
    key = f'risk:{contract_address.lower()}'

    # 1) Try cache
    cached = await get_cached(key)
    if cached:
        return cached

    # 2) Try on-chain
    onchain = await fetch_onchain_result(contract_address)
    if onchain:
        await set_cached(key, onchain)
        return onchain

    # 3) Fallback to analysis service
    analysis = await call_analysis_service(contract_address)
    if analysis:
        await set_cached(key, analysis)
        return analysis

    raise HTTPException(status_code=404, detail='No risk data available')


@app.get('/history/{contract_address}')
async def get_history(contract_address: str, from_block: int = 0, to_block: Optional[int] = None):
    return await fetch_history_from_chain(contract_address, from_block=from_block, to_block=to_block)


# Health
@app.get('/health')
async def health():
    return {"status": "ok"}
