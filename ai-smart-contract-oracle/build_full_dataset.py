"""build_full_dataset
=================================
Automates the creation of a unified smart contract security dataset by:
- Downloading multiple public datasets
- Cleaning and deduplicating Solidity sources
- Inferring safety labels
- Extracting program features
- Merging everything into train/test CSV files ready for ML training

Run:
    python build_full_dataset.py
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from zipfile import ZipFile

import pandas as pd
import requests
from sklearn.model_selection import train_test_split
from tqdm import tqdm

from feature_extractor import extract_from_bytecode, extract_from_source

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG: Dict[str, Any] = {
    "raw_dir": Path("datasets/raw"),
    "output_dir": Path("datasets"),
    "train_path": Path("datasets/training_data.csv"),
    "test_path": Path("datasets/test_data.csv"),
    "metadata_path": Path("datasets/metadata.json"),
    "feature_list_path": Path("datasets/feature_list.json"),
    "test_size": 0.2,
    "random_state": 42,
    "proxy_markers": [
        "TransparentUpgradeableProxy",
        "UUPSUpgradeable",
        "ERC1967Proxy",
        "ProxyAdmin",
        "delegatecallImplementation",
    ],
    "safe_datasets": {
        "openzeppelin",
        "sanctuary",
        "audited",
    },
    "unsafe_datasets": {
        "smartbugs",
        "solidifi",
        "swc",
        "dasp",
        "reentrancy",
        "exploits",
    },
    "bytecode_suffixes": {".hex", ".bin"},
    "datasets": [
        {
            "name": "smartbugs",
            "repo": "smartbugs/smartbugs",
            "branch": "master",
            "subfolder": "smartbugs/dataset",
            "file_patterns": ["**/*.sol"],
        },
        {
            "name": "solidifi",
            "repo": "solidifi/solidi-fi",
            "branch": "master",
            "subfolder": "dataset",
            "file_patterns": ["**/*.sol"],
        },
        {
            "name": "swc",
            "repo": "SmartContractWeakness/SWC-registry",
            "branch": "master",
            "subfolder": "test_cases",
            "file_patterns": ["**/*.sol"],
        },
        {
            "name": "dasp",
            "repo": "DASP-Datasets/DASP-Datasets",
            "branch": "master",
            "subfolder": "",
            "file_patterns": ["**/*.sol"],
        },
        {
            "name": "reentrancy",
            "repo": "zhou-xiaojia/ReentrancyBenchmarks",
            "branch": "master",
            "subfolder": "",
            "file_patterns": ["**/*.sol"],
        },
        {
            "name": "sanctuary",
            "repo": "tintinweb/smart-contract-sanctuary",
            "branch": "main",
            "subfolder": "verified-contracts",
            "file_patterns": ["**/*.sol", "**/*.eth"],
        },
        {
            "name": "openzeppelin",
            "repo": "OpenZeppelin/openzeppelin-contracts",
            "branch": "master",
            "subfolder": "contracts",
            "file_patterns": ["**/*.sol"],
        },
    ],
}

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------
@dataclass
class ContractEntry:
    dataset: str
    path: Path


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def github_zip_url(repo: str, branch: str) -> str:
    return f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"


def ensure_directories(config: Dict[str, Any]) -> None:
    config["raw_dir"].mkdir(parents=True, exist_ok=True)
    config["output_dir"].mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1: downloads
# ---------------------------------------------------------------------------
def download_repos(config: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Path]]:
    """Download dataset archives if not already present."""

    archives: List[Tuple[Dict[str, Any], Path]] = []
    for dataset in config["datasets"]:
        dest_dir = config["raw_dir"] / dataset["name"]
        if dest_dir.exists() and any(dest_dir.iterdir()):
            logging.info("Dataset '%s' already present; skipping download", dataset["name"])
            continue

        archive_path = config["raw_dir"] / f"{dataset['name']}.zip"
        if archive_path.exists():
            logging.info("Archive for '%s' already exists", dataset["name"])
        else:
            url = github_zip_url(dataset["repo"], dataset["branch"])
            logging.info("Downloading %s", url)
            download_file(url, archive_path)
        archives.append((dataset, archive_path))
    return archives


def download_file(url: str, dest: Path, chunk_size: int = 1 << 20) -> None:
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    with dest.open("wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc=f"Downloading {dest.name}"
    ) as bar:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                bar.update(len(chunk))


# ---------------------------------------------------------------------------
# Step 2: extraction
# ---------------------------------------------------------------------------
def extract_archives(config: Dict[str, Any], archives: Sequence[Tuple[Dict[str, Any], Path]]) -> None:
    for dataset, archive in archives:
        dest_dir = config["raw_dir"] / dataset["name"]
        if dest_dir.exists() and any(dest_dir.iterdir()):
            continue
        with tempfile.TemporaryDirectory() as tmpdir:
            logging.info("Extracting %s", archive)
            with ZipFile(archive) as zf:
                zf.extractall(tmpdir)
            tmp_root = Path(tmpdir)
            extracted_root = next((p for p in tmp_root.iterdir() if p.is_dir()), tmp_root)
            subfolder = Path(dataset["subfolder"]) if dataset["subfolder"] else Path()
            source_dir = extracted_root / subfolder if subfolder else extracted_root
            if not source_dir.exists():
                logging.warning("Subfolder %s not found in %s", subfolder, dataset["name"])
                source_dir = extracted_root
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(source_dir, dest_dir)
        archive.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Step 3: load contract files
# ---------------------------------------------------------------------------
def load_contract_files(config: Dict[str, Any]) -> List[ContractEntry]:
    entries: List[ContractEntry] = []
    for dataset in config["datasets"]:
        base_dir = config["raw_dir"] / dataset["name"]
        if not base_dir.exists():
            logging.warning("Dataset '%s' missing; skipping", dataset["name"])
            continue
        patterns = dataset.get("file_patterns", ["**/*.sol"])
        for pattern in patterns:
            for file_path in base_dir.glob(pattern):
                if file_path.is_file():
                    entries.append(ContractEntry(dataset=dataset["name"], path=file_path))
    logging.info("Loaded %d candidate contract files", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Step 4: cleaning
# ---------------------------------------------------------------------------
def clean_contract_source(path: Path, config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    suffix = path.suffix.lower()
    solidity_suffixes = {".sol", ".eth"}
    if suffix not in solidity_suffixes.union(config["bytecode_suffixes"]):
        return None, None

    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if suffix in config["bytecode_suffixes"]:
        if not text:
            return None, None
        return text, sha256(text.encode()).hexdigest()

    text_no_spdx = re.sub(r"^\s*//\s*SPDX-License-Identifier:.*$", "", text, flags=re.MULTILINE)
    text_no_comments = re.sub(r"/\*.*?\*/", "", text_no_spdx, flags=re.DOTALL)
    text_no_comments = re.sub(r"//.*", "", text_no_comments)
    cleaned = "\n".join(line.rstrip() for line in text_no_comments.splitlines() if line.strip())
    if not cleaned:
        return None, None
    if any(marker in cleaned for marker in config["proxy_markers"]):
        return None, None
    return cleaned, sha256(cleaned.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Step 5: labeling
# ---------------------------------------------------------------------------
def classify_label_from_path(path: Path, dataset_name: str, config: Dict[str, Any]) -> int:
    dataset_name = dataset_name.lower()
    if dataset_name in config["safe_datasets"]:
        return 0
    if dataset_name in config["unsafe_datasets"]:
        return 1
    path_str = str(path).lower()
    if any(token in path_str for token in ("audited", "safe")):
        return 0
    if any(token in path_str for token in ("exploit", "hack", "vulnerable", "attack")):
        return 1
    # default to unsafe to be conservative
    return 1


# ---------------------------------------------------------------------------
# Step 6: feature extraction
# ---------------------------------------------------------------------------
def extract_features(
    cleaned_source: Optional[str],
    raw_path: Path,
    label: int,
) -> Optional[Dict[str, Any]]:
    try:
        if cleaned_source and raw_path.suffix.lower() in {".sol", ".eth"}:
            features = extract_from_source(cleaned_source)
        else:
            bytecode = cleaned_source if cleaned_source and raw_path.suffix.lower() in CONFIG["bytecode_suffixes"] else raw_path.read_text(encoding="utf-8", errors="ignore")
            features = extract_from_bytecode(bytecode)
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Feature extraction failed for %s: %s", raw_path, exc)
        return None

    features = features or {}
    features["contract_path"] = str(raw_path)
    features["label"] = label
    return features


# ---------------------------------------------------------------------------
# Step 7: merge & save
# ---------------------------------------------------------------------------
def merge_and_save(rows: List[Dict[str, Any]], config: Dict[str, Any], dataset_counts: Dict[str, int]) -> None:
    if not rows:
        raise RuntimeError("No data rows generated; aborting save.")

    flattened_rows = [flatten_dict(row) for row in rows]
    df = pd.DataFrame(flattened_rows)
    feature_cols = [col for col in df.columns if col not in {"contract_path", "label"}]

    train_df, test_df = train_test_split(
        df,
        test_size=config["test_size"],
        random_state=config["random_state"],
        stratify=df["label"],
    )

    train_df.to_csv(config["train_path"], index=False)
    test_df.to_csv(config["test_path"], index=False)

    metadata = {
        "total_rows": int(len(df)),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "per_dataset_counts": dataset_counts,
    }
    config["metadata_path"].write_text(json.dumps(metadata, indent=2))
    config["feature_list_path"].write_text(json.dumps(feature_cols, indent=2))
    logging.info("Saved %d rows (train=%d, test=%d)", len(df), len(train_df), len(test_df))


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def flatten_dict(data: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key, sep=sep))
        else:
            items[new_key] = normalize_value(value)
    return items


def normalize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return value


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ensure_directories(CONFIG)

    archives = download_repos(CONFIG)
    extract_archives(CONFIG, archives)

    entries = load_contract_files(CONFIG)
    duplicate_hashes: set[str] = set()
    rows: List[Dict[str, Any]] = []

    metadata_counts: Dict[str, int] = {}
    for entry in tqdm(entries, desc="Processing contracts"):
        dataset = entry.dataset
        metadata_counts.setdefault(dataset, 0)
        label = classify_label_from_path(entry.path, dataset, CONFIG)
        cleaned, signature = clean_contract_source(entry.path, CONFIG)
        if not cleaned or not signature:
            continue
        if signature in duplicate_hashes:
            continue
        duplicate_hashes.add(signature)
        features = extract_features(cleaned, entry.path, label)
        if not features:
            continue
        rows.append(features)
        metadata_counts[dataset] += 1

    for dataset in CONFIG["datasets"]:
        metadata_counts.setdefault(dataset["name"], 0)

    merge_and_save(rows, CONFIG, metadata_counts)


if __name__ == "__main__":
    main()
