#!/usr/bin/env python3
"""Utility script to generate placeholder ML artifacts for local testing."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

FEATURES = [
    "opcode_balance",
    "opcode_calls",
    "opcode_storage",
    "bytecode_length",
    "complexity_score",
]


def main() -> None:
    rng = np.random.default_rng(42)
    X = rng.random((200, len(FEATURES)))
    y = (0.6 * X[:, 0] + 0.4 * X[:, 1] + 0.2 * X[:, 2] > 0.5).astype(int)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = XGBClassifier(
        n_estimators=25,
        max_depth=4,
        learning_rate=0.3,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        eval_metric="logloss",
    )
    model.fit(X_scaled, y)

    model_dir = Path("model")
    data_dir = Path("datasets")
    model_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    model.save_model(model_dir / "security_model.xgb")
    joblib.dump(scaler, model_dir / "scaler.pkl")
    (data_dir / "feature_list.json").write_text(json.dumps(FEATURES, indent=2))

    print("Artifacts generated:")
    print(f" - model/security_model.xgb")
    print(f" - model/scaler.pkl")
    print(f" - datasets/feature_list.json")


if __name__ == "__main__":
    main()
