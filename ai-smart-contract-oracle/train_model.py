#!/usr/bin/env python3
"""Train an XGBoost model to detect vulnerable Solidity contracts."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


DEFAULT_DATASET = Path("datasets/training_data.csv")
DEFAULT_MODEL_PATH = Path("model/security_model.xgb")
DEFAULT_SCALER_PATH = Path("model/scaler.pkl")
DEFAULT_METRICS_PATH = Path("model/metrics.json")
DEFAULT_CONFUSION_PATH = Path("model/confusion_matrix.png")
DEFAULT_FEATURE_IMPORTANCE_PATH = Path("model/feature_importance.json")


def load_dataset(dataset_path: Path) -> pd.DataFrame:
    """Load dataset from disk and validate schema."""

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    df = pd.read_csv(dataset_path)
    if "label" not in df.columns:
        raise ValueError("Dataset must contain a 'label' column")
    return df


def preprocess(
    df: pd.DataFrame,
    test_size: float,
    random_state: int,
    scaler_path: Path,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Split dataset, scale features, and persist the scaler."""

    feature_names = [col for col in df.columns if col != "label"]
    if not feature_names:
        raise ValueError("No feature columns found.")

    X = df[feature_names].values.astype(float)
    y = df["label"].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    scaler_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, scaler_path)
    logging.info("Saved scaler to %s", scaler_path)

    return X_train_scaled, X_test_scaled, y_train, y_test, feature_names


def compute_scale_pos_weight(labels: np.ndarray) -> float:
    """Return imbalance ratio for XGBoost's scale_pos_weight."""

    unique, counts = np.unique(labels, return_counts=True)
    distribution = dict(zip(unique.tolist(), counts.tolist()))
    neg = float(distribution.get(0, 0))
    pos = float(distribution.get(1, 0))
    if pos == 0:
        logging.warning("No positive samples detected; defaulting scale_pos_weight to 1.0")
        return 1.0
    return neg / pos if pos else 1.0


def log_class_distribution(labels: np.ndarray) -> None:
    """Log the class balance for transparency."""

    unique, counts = np.unique(labels, return_counts=True)
    dist = {int(k): int(v) for k, v in zip(unique, counts)}
    logging.info("Class distribution (before training): %s", dist)


def train_model(X_train: np.ndarray, y_train: np.ndarray, scale_pos_weight: float) -> XGBClassifier:
    """Train the configured XGBoost classifier."""

    model = XGBClassifier(
        max_depth=8,
        learning_rate=0.05,
        n_estimators=500,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=-1,
        use_label_encoder=False,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: XGBClassifier,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> Tuple[Dict[str, float], np.ndarray]:
    """Compute evaluation metrics and return confusion matrix."""

    preds = model.predict(X_test)
    probas = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probas))
        if len(np.unique(y_test)) > 1
        else 0.0,
    }
    cm = confusion_matrix(y_test, preds)
    return metrics, cm


def save_model(model: XGBClassifier, model_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(model_path)
    logging.info("Saved model to %s", model_path)


def save_metrics(metrics: Dict[str, float], metrics_path: Path) -> None:
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    logging.info("Saved metrics to %s", metrics_path)


def save_confusion_matrix(cm: np.ndarray, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(cm, cmap="Blues")
    ax.set_title("Confusion Matrix")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    tick_marks = np.arange(2)
    ax.set_xticks(tick_marks)
    ax.set_yticks(tick_marks)
    ax.set_xticklabels(["Safe", "Unsafe"])
    ax.set_yticklabels(["Safe", "Unsafe"])

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="black")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    logging.info("Saved confusion matrix plot to %s", output_path)


def _format_importance(
    scores: Dict[str, float], feature_names: Sequence[str]
) -> Dict[str, float]:
    formatted: Dict[str, float] = {}
    for key, value in scores.items():
        if key.startswith("f") and key[1:].isdigit():
            idx = int(key[1:])
            if 0 <= idx < len(feature_names):
                formatted[feature_names[idx]] = float(value)
                continue
        formatted[key] = float(value)
    return formatted


def save_feature_importance(
    model: XGBClassifier,
    feature_names: Sequence[str],
    output_path: Path,
) -> None:
    booster = model.get_booster()
    importance = {
        "gain": _format_importance(booster.get_score(importance_type="gain"), feature_names),
        "weight": _format_importance(
            booster.get_score(importance_type="weight"), feature_names
        ),
        "cover": _format_importance(booster.get_score(importance_type="cover"), feature_names),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(importance, fh, indent=2)
    logging.info("Saved feature importances to %s", output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train smart-contract risk classifier")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to the training dataset CSV",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="File to store the trained model",
    )
    parser.add_argument(
        "--scaler-out",
        type=Path,
        default=DEFAULT_SCALER_PATH,
        help="File to store the fitted StandardScaler",
    )
    parser.add_argument(
        "--metrics-out",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="JSON file to store evaluation metrics",
    )
    parser.add_argument(
        "--confusion-out",
        type=Path,
        default=DEFAULT_CONFUSION_PATH,
        help="PNG file for the confusion matrix",
    )
    parser.add_argument(
        "--feature-importance-out",
        type=Path,
        default=DEFAULT_FEATURE_IMPORTANCE_PATH,
        help="JSON file for feature importance stats",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test split size (default 0.2)",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Seed for reproducible splits",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def main() -> None:
    configure_logging()
    args = parse_args()

    logging.info("Loading dataset from %s", args.dataset)
    df = load_dataset(args.dataset)

    X_train, X_test, y_train, y_test, feature_names = preprocess(
        df,
        test_size=args.test_size,
        random_state=args.random_state,
        scaler_path=args.scaler_out,
    )

    log_class_distribution(y_train)
    scale_pos_weight = compute_scale_pos_weight(y_train)
    logging.info("scale_pos_weight set to %.4f", scale_pos_weight)

    logging.info("Training XGBoost model...")
    model = train_model(X_train, y_train, scale_pos_weight)

    logging.info("Evaluating model...")
    metrics, cm = evaluate_model(model, X_test, y_test)

    print(json.dumps(metrics, indent=2))

    save_model(model, args.model_out)
    save_metrics(metrics, args.metrics_out)
    save_confusion_matrix(cm, args.confusion_out)
    save_feature_importance(model, feature_names, args.feature_importance_out)

    logging.info("Training pipeline completed successfully.")


if __name__ == "__main__":
    main()
