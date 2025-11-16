#!/usr/bin/env python3
"""FastAPI microservice for smart-contract security inference."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import shap
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, root_validator
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from feature_extractor import extract_from_bytecode, extract_from_source

try:  # Optional Web3 support for future enhancements
    from web3 import Web3  # type: ignore
except Exception:  # pragma: no cover
    Web3 = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

MODEL_VERSION = "1.0"
MODEL_PATH = Path("model/security_model.xgb")
SCALER_PATH = Path("model/scaler.pkl")
FEATURE_LIST_PATH = Path("datasets/feature_list.json")
DEFAULT_TRAINING_DATE = "2025-11-01T00:00:00Z"

MODEL: Optional[XGBClassifier] = None
SCALER: Optional[StandardScaler] = None
EXPLAINER: Optional[shap.TreeExplainer] = None
FEATURE_NAMES: List[str] = []

app = FastAPI(title="Smart Contract Inference Service", version=MODEL_VERSION)


class InferenceRequest(BaseModel):
    """Input payload for /predict."""

    source_code: Optional[str] = None
    bytecode: Optional[str] = None
    contract_address: Optional[str] = None

    @root_validator(skip_on_failure=True)
    def validate_inputs(cls, values: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        if not any(values.get(field) for field in ("source_code", "bytecode", "contract_address")):
            raise ValueError("Provide at least one of source_code, bytecode, or contract_address")
        return values


class InferenceError(Exception):
    """Custom exception for controlled inference failures."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def load_feature_names(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature list not found at {path}")
    feature_list = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(feature_list, list):
        raise ValueError("feature_list.json must contain a list of feature names")
    return [str(name) for name in feature_list]


def load_model(model_path: Path, scaler_path: Path, feature_list_path: Path) -> None:
    """Load model, scaler, feature names, and SHAP explainer into global scope."""

    global MODEL, SCALER, EXPLAINER, FEATURE_NAMES

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}")
    if not scaler_path.exists():
        raise FileNotFoundError(f"Scaler file not found at {scaler_path}")

    logger.info("Loading model from %s", model_path)
    model = XGBClassifier()
    model.load_model(str(model_path))

    logger.info("Loading scaler from %s", scaler_path)
    scaler = joblib.load(scaler_path)
    if not isinstance(scaler, StandardScaler):
        raise TypeError("Loaded scaler is not an instance of StandardScaler")

    feature_names = load_feature_names(feature_list_path)

    logger.info("Initializing SHAP TreeExplainer")
    explainer = shap.TreeExplainer(model)

    MODEL = model
    SCALER = scaler
    FEATURE_NAMES = feature_names
    EXPLAINER = explainer
    logger.info("Inference service ready")


def error_response(message: str, details: Optional[str] = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    payload = {
        "error": True,
        "message": message,
        "details": details,
    }
    return JSONResponse(status_code=status_code, content=payload)


def extract_features(payload: InferenceRequest) -> Dict[str, float]:
    """Derive numerical features from source or bytecode."""

    if payload.source_code:
        return extract_from_source(payload.source_code)
    if payload.bytecode:
        return extract_from_bytecode(payload.bytecode)
    raise InferenceError("Bytecode fetch not implemented in this MVP.", details="Provide source_code or bytecode directly.")


def preprocess_features(features: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Align features with training schema and scale them."""

    if MODEL is None or SCALER is None or not FEATURE_NAMES:
        raise InferenceError("Model artifacts not loaded")

    raw_vector = np.array([[float(features.get(name, 0.0)) for name in FEATURE_NAMES]], dtype=float)
    scaled_vector = SCALER.transform(raw_vector)
    raw_feature_map = {name: float(raw_vector[0, idx]) for idx, name in enumerate(FEATURE_NAMES)}
    return raw_vector, scaled_vector, raw_feature_map


def run_inference(scaled_vector: np.ndarray) -> float:
    """Run model prediction and return unsafe probability."""

    if MODEL is None:
        raise InferenceError("Model not loaded")
    probs = MODEL.predict_proba(scaled_vector)
    return float(probs[0, 1])


def risk_label(score: float) -> str:
    if score < 0.3:
        return "safe"
    if score < 0.7:
        return "caution"
    return "danger"


def _format_importance_entries(shap_values: Sequence[float], raw_features: Dict[str, float]) -> List[Dict[str, float]]:
    entries = []
    for name, impact in zip(FEATURE_NAMES, shap_values):
        entries.append(
            {
                "feature": name,
                "value": raw_features.get(name, 0.0),
                "impact": float(impact),
            }
        )
    positives = sorted((e for e in entries if e["impact"] >= 0), key=lambda item: item["impact"], reverse=True)[:10]
    negatives = sorted((e for e in entries if e["impact"] < 0), key=lambda item: item["impact"])[:10]
    return positives + negatives


def compute_shap(scaled_vector: np.ndarray, raw_features: Dict[str, float]) -> List[Dict[str, float]]:
    """Compute SHAP explanations for the provided sample."""

    if EXPLAINER is None:
        raise InferenceError("SHAP explainer not initialized")
    shap_values = EXPLAINER.shap_values(scaled_vector)
    if isinstance(shap_values, list):
        shap_sample = shap_values[1][0] if len(shap_values) > 1 else shap_values[0][0]
    else:
        shap_sample = shap_values[0]
    return _format_importance_entries(shap_sample, raw_features)


@app.on_event("startup")
async def on_startup() -> None:  # pragma: no cover - FastAPI lifecycle
    try:
        load_model(MODEL_PATH, SCALER_PATH, FEATURE_LIST_PATH)
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to load inference artifacts: %s", exc)
        raise


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/model-info")
def model_info() -> Dict[str, object]:
    if MODEL is None or SCALER is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "model_type": MODEL.__class__.__name__,
        "scaler_type": SCALER.__class__.__name__,
        "feature_count": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
        "training_date": DEFAULT_TRAINING_DATE,
        "model_version": MODEL_VERSION,
    }


@app.post("/predict")
async def predict(payload: InferenceRequest, request: Request) -> JSONResponse:
    start_time = time.perf_counter()
    logger.info("Prediction request received from %s", request.client.host if request.client else "unknown")

    if payload.contract_address and not (payload.source_code or payload.bytecode):
        return error_response("Bytecode fetch not implemented in this MVP.")

    try:
        feature_start = time.perf_counter()
        features = extract_features(payload)
        feature_duration = time.perf_counter() - feature_start
        logger.info("Feature extraction took %.4f seconds", feature_duration)

        preprocess_start = time.perf_counter()
        raw_vector, scaled_vector, raw_features = preprocess_features(features)
        preprocess_duration = time.perf_counter() - preprocess_start
        logger.info("Feature preprocessing took %.4f seconds", preprocess_duration)

        inference_start = time.perf_counter()
        score = run_inference(scaled_vector)
        inference_duration = time.perf_counter() - inference_start
        logger.info("Model inference took %.4f seconds", inference_duration)

        shap_start = time.perf_counter()
        top_factors = compute_shap(scaled_vector, raw_features)
        shap_duration = time.perf_counter() - shap_start
        logger.info("SHAP computation took %.4f seconds", shap_duration)

        features_used = int(np.count_nonzero(raw_vector))
        response = {
            "risk_score": score,
            "risk_label": risk_label(score),
            "features_used": features_used,
            "top_risk_factors": top_factors,
            "raw_features": raw_features,
            "model_version": MODEL_VERSION,
            "explanation_method": "SHAP TreeExplainer",
        }
        total_duration = time.perf_counter() - start_time
        logger.info("Total request time %.4f seconds", total_duration)
        return JSONResponse(content=response)
    except InferenceError as exc:
        logger.warning("Inference error: %s", exc.message)
        return error_response(exc.message, exc.details)
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected inference failure: %s", exc)
        return error_response("Unexpected server error", str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    uvicorn.run("inference_service:app", host="0.0.0.0", port=8000, reload=True)
