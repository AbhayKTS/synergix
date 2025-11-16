#!/usr/bin/env python3
"""In-memory FastAPI task queue for the oracle pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import List

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("task_queue")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

app = FastAPI(title="Oracle Task Queue", version="1.0")


class QueueTask(BaseModel):
    contract_address: str = Field(..., description="Target contract address to assess")
    source_code: str | None = Field(default=None, description="Full Solidity source code")
    bytecode: str | None = Field(default=None, description="Optional compiled bytecode")

    @field_validator("contract_address")
    @classmethod
    def validate_contract_address(cls, value: str) -> str:
        cleaned = value.strip() if isinstance(value, str) else value
        if not cleaned:
            raise ValueError("contract_address is required")
        return cleaned

    @model_validator(mode="after")
    def ensure_payload(self) -> "QueueTask":
        if self.source_code is None and self.bytecode is None:
            raise ValueError("Provide source_code or bytecode for each task")
        return self


class CompletionRequest(BaseModel):
    contract_address: str = Field(..., description="Completed contract address")

    @field_validator("contract_address")
    @classmethod
    def validate_complete_address(cls, value: str) -> str:
        cleaned = value.strip() if isinstance(value, str) else value
        if not cleaned:
            raise ValueError("contract_address is required")
        return cleaned


TASK_QUEUE: List[QueueTask] = []
QUEUE_LOCK = asyncio.Lock()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "pending": len(TASK_QUEUE)}


@app.get("/pending")
async def list_pending() -> List[dict]:
    async with QUEUE_LOCK:
        return [task.model_dump() for task in TASK_QUEUE]


@app.post("/enqueue")
async def enqueue(task: QueueTask) -> dict:
    async with QUEUE_LOCK:
        TASK_QUEUE.append(task)
        logger.info("Enqueued task for %s (pending=%d)", task.contract_address, len(TASK_QUEUE))
        return {"status": "queued", "pending": len(TASK_QUEUE)}


@app.post("/mark-complete")
async def mark_complete(payload: CompletionRequest) -> dict:
    async with QUEUE_LOCK:
        before = len(TASK_QUEUE)
        TASK_QUEUE[:] = [task for task in TASK_QUEUE if task.contract_address.lower() != payload.contract_address.lower()]
        after = len(TASK_QUEUE)
        removed = before - after
        logger.info("Marked %s as complete (removed=%d, pending=%d)", payload.contract_address, removed, after)
        return {"status": "completed", "pending": after}


if __name__ == "__main__":
    uvicorn.run("task_queue:app", host="0.0.0.0", port=9000, reload=True)
