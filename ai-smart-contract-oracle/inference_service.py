#!/usr/bin/env python3
"""FastAPI inference service that powers the oracle pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from feature_extractor import extract_from_bytecode, extract_from_source

logger = logging.getLogger("inference_service")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

MODEL_VERSION = "1.0"
MODEL_PATH = Path("model/security_model.xgb")
SCALER_PATH = Path("model/scaler.pkl")
FEATURE_LIST_PATH = Path("datasets/feature_list.json")
FALLBACK_SCORE = 50
FALLBACK_CATEGORY = 1

MODEL: Optional[XGBClassifier] = None
SCALER: Optional[StandardScaler] = None
FEATURE_NAMES: List[str] = []

app = FastAPI(title="Smart Contract Inference Service", version=MODEL_VERSION)


class InferenceRequest(BaseModel):
    """Incoming payload for /infer."""

    source_code: str | None = Field(default=None, description="Solidity source code to analyze")
    bytecode: str | None = Field(default=None, description="Optional EVM bytecode fallback")
    contract_address: str | None = Field(default=None, description="Optional contract metadata")

    @field_validator("source_code", mode="before")
    @classmethod
    def normalize_source(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def ensure_payload(self) -> "InferenceRequest":
        if self.source_code is None and self.bytecode is None:
            raise ValueError("Provide source_code or bytecode for inference")
        return self


def load_feature_names(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature list not found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("feature_list.json must contain a list of feature names")
    return [str(name) for name in data]


def load_artifacts() -> None:
    global MODEL, SCALER, FEATURE_NAMES

    logger.info("Loading model artifacts")
    model = XGBClassifier()
    model.load_model(str(MODEL_PATH))
    scaler = joblib.load(SCALER_PATH)
    if not isinstance(scaler, StandardScaler):
        raise TypeError("The loaded scaler is not a sklearn StandardScaler instance")
    feature_names = load_feature_names(FEATURE_LIST_PATH)

    MODEL = model
    SCALER = scaler
    FEATURE_NAMES = feature_names
    logger.info("Model artifacts loaded (%d features)", len(FEATURE_NAMES))


def ensure_artifacts_ready() -> None:
    if MODEL is None or SCALER is None or not FEATURE_NAMES:
        raise RuntimeError("Model artifacts are not loaded")


def derive_features(request: InferenceRequest) -> Dict[str, float]:
    if request.source_code:
        return extract_from_source(request.source_code)
    if request.bytecode:
        return extract_from_bytecode(request.bytecode)
    raise ValueError("No source_code or bytecode provided")


def vectorize_features(features: Dict[str, float]) -> np.ndarray:
    ensure_artifacts_ready()
    return np.array([[float(features.get(name, 0.0)) for name in FEATURE_NAMES]], dtype=float)


def predict_score(vector: np.ndarray) -> float:
    ensure_artifacts_ready()
    scaled = SCALER.transform(vector)
    probs = MODEL.predict_proba(scaled)
    score = float(probs[0][1] * 100.0)
    return max(0.0, min(score, 100.0))


def categorize_score(score: float) -> int:
    if score < 33:
        return 0
    if score < 66:
        return 1
    return 2


def fallback_response(reason: Optional[str] = None) -> Dict[str, Any]:
    message = "Fallback inference used"
    if reason:
        message = f"Fallback inference used: {reason}"
    return {
        "risk_score": FALLBACK_SCORE,
        "risk_category": FALLBACK_CATEGORY,
        "explanation": message,
    }


@app.on_event("startup")
async def on_startup() -> None:
    try:
        load_artifacts()
    except Exception as exc:  # pragma: no cover
        logger.warning("Model artifacts not available, falling back to dummy responses: %s", exc)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "artifacts_loaded": MODEL is not None}


@app.get("/model-info")
def model_info() -> Dict[str, Any]:
    if MODEL is None or SCALER is None or not FEATURE_NAMES:
        raise HTTPException(status_code=503, detail="Model artifacts are not loaded")
    return {
        "model_type": MODEL.__class__.__name__,
        "scaler_type": SCALER.__class__.__name__,
        "feature_count": len(FEATURE_NAMES),
        "model_version": MODEL_VERSION,
    }


@app.post("/infer")
async def infer(request: InferenceRequest) -> Dict[str, Any]:
    try:
        features = derive_features(request)
        vector = vectorize_features(features)
        score = predict_score(vector)
        category = categorize_score(score)
        return {
            "risk_score": int(round(score)),
            "risk_category": category,
            "explanation": "Model-generated security assessment",
        }
    except Exception as exc:
        logger.exception("Inference failed, returning fallback response: %s", exc)
        return fallback_response(str(exc))


if __name__ == "__main__":
    uvicorn.run("inference_service:app", host="0.0.0.0", port=8000, reload=False)
    



    






