#!/usr/bin/env python3
"""Feature extraction utilities for Solidity sources and EVM bytecode.

This module exposes two entry points:

```
extract_from_source(source_code: str) -> Dict[str, float]
extract_from_bytecode(bytecode: str) -> Dict[str, float]
```

Both functions return flat dictionaries containing numeric feature values that
are immediately consumable by downstream ML pipelines (dataset builder,
training, inference). The implementation favours resiliency: every feature is
guarded with defaults, all errors are logged, and extraction continues even if
Slither or bytecode parsing fails mid-way.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

try:  # pragma: no cover - optional dependency
    from slither.slither import Slither  # type: ignore[import]

    SLITHER_AVAILABLE = True
except Exception:  # pragma: no cover - best-effort fallback
    SLITHER_AVAILABLE = False

__all__ = ["extract_from_source", "extract_from_bytecode"]

LOW_LEVEL_CALLS = {"call", "delegatecall", "callcode", "staticcall"}
DANGEROUS_OPCODES = {"DELEGATECALL", "SELFDESTRUCT", "CALL", "CALLCODE"}
HALTING_OPCODES = {"STOP", "RETURN", "REVERT", "INVALID", "SELFDESTRUCT"}

OPCODE_TABLE: Dict[int, str] = {
    0x00: "STOP",
    0x01: "ADD",
    0x02: "MUL",
    0x03: "SUB",
    0x04: "DIV",
    0x05: "SDIV",
    0x06: "MOD",
    0x07: "SMOD",
    0x08: "ADDMOD",
    0x09: "MULMOD",
    0x0a: "EXP",
    0x0b: "SIGNEXTEND",
    0x10: "LT",
    0x11: "GT",
    0x12: "SLT",
    0x13: "SGT",
    0x14: "EQ",
    0x15: "ISZERO",
    0x16: "AND",
    0x17: "OR",
    0x18: "XOR",
    0x19: "NOT",
    0x1a: "BYTE",
    0x20: "SHA3",
    0x30: "ADDRESS",
    0x31: "BALANCE",
    0x32: "ORIGIN",
    0x33: "CALLER",
    0x34: "CALLVALUE",
    0x35: "CALLDATALOAD",
    0x36: "CALLDATASIZE",
    0x37: "CALLDATACOPY",
    0x38: "CODESIZE",
    0x39: "CODECOPY",
    0x3a: "GASPRICE",
    0x3b: "EXTCODESIZE",
    0x3c: "EXTCODECOPY",
    0x3d: "RETURNDATASIZE",
    0x3e: "RETURNDATACOPY",
    0x40: "BLOCKHASH",
    0x41: "COINBASE",
    0x42: "TIMESTAMP",
    0x43: "NUMBER",
    0x44: "DIFFICULTY",
    0x45: "GASLIMIT",
    0x50: "POP",
    0x51: "MLOAD",
    0x52: "MSTORE",
    0x53: "MSTORE8",
    0x54: "SLOAD",
    0x55: "SSTORE",
    0x56: "JUMP",
    0x57: "JUMPI",
    0x58: "PC",
    0x59: "MSIZE",
    0x5a: "GAS",
    0x5b: "JUMPDEST",
    0xf0: "CREATE",
    0xf1: "CALL",
    0xf2: "CALLCODE",
    0xf3: "RETURN",
    0xf4: "DELEGATECALL",
    0xf5: "CREATE2",
    0xfa: "STATICCALL",
    0xfd: "REVERT",
    0xfe: "INVALID",
    0xff: "SELFDESTRUCT",
}
for i in range(0x60, 0x80):
    OPCODE_TABLE[i] = f"PUSH{i - 0x5f}"
for i in range(0x80, 0x90):
    OPCODE_TABLE[i] = f"DUP{i - 0x7f}"
for i in range(0x90, 0xa0):
    OPCODE_TABLE[i] = f"SWAP{i - 0x8f}"
for i in range(0xa0, 0xa5):
    OPCODE_TABLE[i] = f"LOG{i - 0x9f}"

OPCODE_FEATURE_NAMES = sorted(set(OPCODE_TABLE.values()))

BASE_FEATURE_KEYS = [
    "num_functions_total",
    "num_functions_public",
    "num_functions_external",
    "num_functions_internal",
    "num_functions_private",
    "num_modifiers_total",
    "has_modifier_onlyowner",
    "has_modifier_nonreentrant",
    "num_external_calls",
    "num_low_level_calls",
    "cyclomatic_complexity",
    "num_state_variables",
    "num_inherited_contracts",
    "reentrancy_detected",
    "balance_usage",
    "inline_assembly_usage",
    "bytecode_length",
    "num_opcodes_total",
    "num_jumps",
    "num_jumpi",
    "num_jumpdest",
    "push_pop_ratio",
    "call_depth_estimate",
    "storage_write_count",
    "storage_read_count",
    "unreachable_code_detected",
    "dangerous_opcode_delegatecall",
    "dangerous_opcode_selfdestruct",
    "dangerous_opcode_call",
    "dangerous_opcode_callcode",
]

VISIBILITY_KEYS = {
    "public": "num_functions_public",
    "external": "num_functions_external",
    "internal": "num_functions_internal",
    "private": "num_functions_private",
}

VISIBILITY_REGEX = re.compile(
    r"function\s+\w+\s*\([^)]*\)\s*(public|external|internal|private)"
)
LOW_LEVEL_CALL_PATTERN = re.compile(r"\.(call|delegatecall|callcode|staticcall)\s*\(", re.IGNORECASE)
GENERIC_EXTERNAL_CALL_PATTERN = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)


def _init_feature_dict() -> Dict[str, float]:
    """Create a feature dict seeded with default zero values."""

    features: Dict[str, float] = {key: 0.0 for key in BASE_FEATURE_KEYS}
    for name in OPCODE_FEATURE_NAMES:
        features[f"opcode_{name.lower()}"] = 0.0
    return features


def _normalize_bytecode(bytecode: str) -> str:
    cleaned = re.sub(r"0x|\s+", "", bytecode or "")
    if len(cleaned) % 2 == 1:
        cleaned = "0" + cleaned
    return cleaned.lower()


def extract_modifiers(contract: Any) -> Dict[str, int]:
    """Return modifier counts and critical modifier presence for a contract."""

    result = {
        "num_modifiers_total": 0,
        "has_modifier_onlyowner": 0,
        "has_modifier_nonreentrant": 0,
    }
    if contract is None:
        return result
    try:
        modifiers = list(getattr(contract, "modifiers", []) or [])
        result["num_modifiers_total"] = len(modifiers)
        for modifier in modifiers:
            name = (getattr(modifier, "name", "") or "").lower()
            if name == "onlyowner":
                result["has_modifier_onlyowner"] = 1
            if name == "nonreentrant":
                result["has_modifier_nonreentrant"] = 1
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Failed to read modifiers: %s", exc)

    try:
        for function in getattr(contract, "functions", []) or []:
            for modifier in getattr(function, "modifiers", []) or []:
                name = (getattr(modifier, "name", "") or "").lower()
                if name == "onlyowner":
                    result["has_modifier_onlyowner"] = 1
                if name == "nonreentrant":
                    result["has_modifier_nonreentrant"] = 1
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to inspect function modifiers: %s", exc)
    return result


def compute_complexity(functions: Iterable[Any], source_code: str) -> float:
    """Aggregate cyclomatic complexity with regex fallbacks."""

    complexity = 0.0
    for func in functions or []:
        value = getattr(func, "complexity", None)
        if value is None:
            value = getattr(func, "cyclomatic_complexity", None)
        if value is None:
            continue
        try:
            complexity += float(value)
        except (TypeError, ValueError):
            continue

    if complexity == 0.0 and source_code:
        branch_hits = re.findall(r"\b(if|for|while|case|require|assert)\b", source_code)
        complexity = float(len(branch_hits) + 1) if branch_hits else 1.0
    return complexity


def count_external_calls(source_code: str) -> Tuple[int, int]:
    """Count external call patterns and low-level calls from raw source text."""

    low_level = len(LOW_LEVEL_CALL_PATTERN.findall(source_code))
    high_level = 0
    for match in GENERIC_EXTERNAL_CALL_PATTERN.finditer(source_code):
        target = match.group(1)
        if target in {"this", "super", "msg", "address", "type"}:
            continue
        high_level += 1
    return high_level + low_level, low_level


def detect_reentrancy_patterns(source_code: str) -> int:
    """Return 1 if classic reentrancy anti-patterns are detected in the source."""

    if not source_code:
        return 0
    external_call = re.search(
        r"(call\.value|\.call\s*\(|\.delegatecall\s*\(|\.send\s*\(|\.transfer\s*\()",
        source_code,
    )
    state_update = re.search(
        r"(sstore\s*\(|\bstorage\b|\b_mapping\b|\b[a-zA-Z_][\w\[\]\.]*(\+|-|=))",
        source_code,
    )
    non_guarded = not re.search(r"\bnonReentrant\b|ReentrancyGuard", source_code)
    if external_call and state_update and non_guarded:
        return 1
    return 0


def _has_unreachable_code(opcodes: Sequence[str]) -> bool:
    unreachable = False
    dead_zone = False
    for opcode in opcodes:
        if opcode in HALTING_OPCODES:
            dead_zone = True
            continue
        if opcode == "JUMPDEST":
            dead_zone = False
            continue
        if dead_zone:
            unreachable = True
            break
    return unreachable


def extract_opcodes(bytecode: str) -> Tuple[Dict[str, int], Dict[str, float]]:
    """Parse bytecode into opcode counts and aggregate statistics."""

    cleaned = _normalize_bytecode(bytecode)
    if not cleaned:
        return {}, {
            "bytecode_length": 0.0,
            "num_jumps": 0.0,
            "num_jumpi": 0.0,
            "num_jumpdest": 0.0,
            "num_push": 0.0,
            "num_pop": 0.0,
            "push_pop_ratio": 0.0,
            "call_depth_estimate": 0.0,
            "storage_write_count": 0.0,
            "storage_read_count": 0.0,
            "unreachable_code_detected": 0.0,
            "num_opcodes_total": 0.0,
        }

    counts: Counter[str] = Counter()
    sequence: List[str] = []
    i = 0
    while i < len(cleaned):
        chunk = cleaned[i : i + 2]
        try:
            opcode_int = int(chunk, 16)
        except ValueError:
            break
        name = OPCODE_TABLE.get(opcode_int, f"OP_{opcode_int:02X}")
        counts[name] += 1
        sequence.append(name)
        i += 2
        if 0x60 <= opcode_int <= 0x7F:
            push_bytes = opcode_int - 0x5F
            i += push_bytes * 2

    num_push = sum(count for name, count in counts.items() if name.startswith("PUSH"))
    num_pop = counts.get("POP", 0)
    num_calls = sum(counts.get(op, 0) for op in {"CALL", "DELEGATECALL", "CALLCODE", "STATICCALL"})
    push_pop_ratio = num_push / max(num_pop, 1)

    current_depth = 0
    max_depth = 0
    for name in sequence:
        if name in {"CALL", "DELEGATECALL", "CALLCODE", "STATICCALL"}:
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif name in HALTING_OPCODES or name == "JUMPDEST":
            current_depth = 0
        else:
            current_depth = max(current_depth - 1, 0)

    stats = {
        "bytecode_length": float(len(cleaned) // 2),
        "num_jumps": float(counts.get("JUMP", 0)),
        "num_jumpi": float(counts.get("JUMPI", 0)),
        "num_jumpdest": float(counts.get("JUMPDEST", 0)),
        "num_push": float(num_push),
        "num_pop": float(num_pop),
        "push_pop_ratio": float(push_pop_ratio),
        "call_depth_estimate": float(max_depth or num_calls),
        "storage_write_count": float(counts.get("SSTORE", 0)),
        "storage_read_count": float(counts.get("SLOAD", 0)),
        "unreachable_code_detected": float(int(_has_unreachable_code(sequence))),
        "num_opcodes_total": float(sum(counts.values())),
    }
    return dict(counts), stats


def _apply_opcode_features(features: Dict[str, float], opcode_counts: Dict[str, int], stats: Dict[str, float]) -> None:
    for key, value in stats.items():
        if key in features:
            features[key] = value
    features["bytecode_length"] = stats.get("bytecode_length", 0.0)
    features["num_opcodes_total"] = stats.get("num_opcodes_total", 0.0)
    features["push_pop_ratio"] = stats.get("push_pop_ratio", 0.0)
    features["call_depth_estimate"] = stats.get("call_depth_estimate", 0.0)
    features["storage_write_count"] = stats.get("storage_write_count", 0.0)
    features["storage_read_count"] = stats.get("storage_read_count", 0.0)
    features["unreachable_code_detected"] = stats.get("unreachable_code_detected", 0.0)

    for name in OPCODE_FEATURE_NAMES:
        features[f"opcode_{name.lower()}"] = float(opcode_counts.get(name, 0))
    for name, count in opcode_counts.items():
        key = f"opcode_{name.lower()}"
        if key not in features:
            features[key] = float(count)

    for dangerous in DANGEROUS_OPCODES:
        features[f"dangerous_opcode_{dangerous.lower()}"] = float(opcode_counts.get(dangerous, 0))
    features["num_low_level_calls"] = float(sum(opcode_counts.get(op.upper(), 0) for op in LOW_LEVEL_CALLS))
    features["num_external_calls"] = features["num_low_level_calls"]
    features["num_jumps"] = stats.get("num_jumps", 0.0)
    features["num_jumpi"] = stats.get("num_jumpi", 0.0)
    features["num_jumpdest"] = stats.get("num_jumpdest", 0.0)


def _build_slither(source_code: str) -> Optional[Slither]:
    if not SLITHER_AVAILABLE:
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".sol", delete=False, encoding="utf-8") as tmp:
            tmp.write(source_code)
            tmp.flush()
            tmp_path = tmp.name
        return Slither(tmp_path)
    except Exception as exc:  # pragma: no cover
        logger.debug("Slither parsing failed: %s", exc)
        return None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _populate_slither_metrics(slither_obj: Slither, source_code: str, features: Dict[str, float]) -> None:
    try:
        for contract in getattr(slither_obj, "contracts", []) or []:
            functions = [fn for fn in getattr(contract, "functions", []) or [] if not getattr(fn, "is_constructor", False)]
            features["num_functions_total"] += len(functions)
            for fn in functions:
                visibility = (getattr(fn, "visibility", "") or "").lower()
                key = VISIBILITY_KEYS.get(visibility)
                if key:
                    features[key] += 1
            features["cyclomatic_complexity"] += compute_complexity(functions, source_code)
            features["num_state_variables"] += len(getattr(contract, "state_variables", []) or [])
            inheritance = getattr(contract, "inheritance", []) or []
            if inheritance:
                features["num_inherited_contracts"] += max(len(inheritance) - 1, 0)

            modifier_data = extract_modifiers(contract)
            features["num_modifiers_total"] += modifier_data["num_modifiers_total"]
            if modifier_data["has_modifier_onlyowner"]:
                features["has_modifier_onlyowner"] = 1.0
            if modifier_data["has_modifier_nonreentrant"]:
                features["has_modifier_nonreentrant"] = 1.0
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to collect Slither metrics: %s", exc)


def _apply_regex_fallbacks(source_code: str, features: Dict[str, float]) -> None:
    matches = VISIBILITY_REGEX.findall(source_code)
    if matches:
        totals = Counter(match.lower() for match in matches)
        for vis, key in VISIBILITY_KEYS.items():
            features[key] = max(features[key], float(totals.get(vis, 0)))
        features["num_functions_total"] = max(
            features["num_functions_total"], float(len(matches))
        )

    modifier_defs = len(re.findall(r"\bmodifier\s+\w+", source_code))
    features["num_modifiers_total"] = max(features["num_modifiers_total"], float(modifier_defs))
    if re.search(r"\bonlyOwner\b", source_code):
        features["has_modifier_onlyowner"] = 1.0
    if re.search(r"\bnonReentrant\b", source_code):
        features["has_modifier_nonreentrant"] = 1.0

    total_external, low_level = count_external_calls(source_code)
    features["num_external_calls"] = max(features["num_external_calls"], float(total_external))
    features["num_low_level_calls"] = max(features["num_low_level_calls"], float(low_level))

    features["reentrancy_detected"] = float(detect_reentrancy_patterns(source_code))
    if re.search(r"\bbalance\b|msg\.value", source_code):
        features["balance_usage"] = 1.0
    if re.search(r"\bassembly\s*\{", source_code):
        features["inline_assembly_usage"] = 1.0


def _finalize(features: Dict[str, float]) -> Dict[str, float]:
    return {key: float(value) for key, value in features.items()}


def extract_from_source(source_code: str) -> Dict[str, float]:
    """Extract ML-friendly features from Solidity source code."""

    features = _init_feature_dict()
    if not source_code or not source_code.strip():
        return features

    try:
        slither_obj = _build_slither(source_code)
        if slither_obj:
            _populate_slither_metrics(slither_obj, source_code, features)
    except Exception as exc:  # pragma: no cover
        logger.debug("Source extraction failure: %s", exc)

    _apply_regex_fallbacks(source_code, features)
    return _finalize(features)


def extract_from_bytecode(bytecode: str) -> Dict[str, float]:
    """Extract ML-friendly features directly from compiled EVM bytecode."""

    features = _init_feature_dict()
    if not bytecode:
        return features

    try:
        opcode_counts, stats = extract_opcodes(bytecode)
        _apply_opcode_features(features, opcode_counts, stats)
    except Exception as exc:  # pragma: no cover
        logger.debug("Bytecode extraction failure: %s", exc)
    return _finalize(features)


def _read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract features from Solidity or bytecode")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="Path to Solidity source file (.sol)")
    group.add_argument("--bytecode-file", help="Path to bytecode file containing hex string")
    group.add_argument("--hex", help="Raw bytecode hex string")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    result: Dict[str, float]
    if args.source:
        if not os.path.exists(args.source):
            raise SystemExit(f"Source file not found: {args.source}")
        result = extract_from_source(_read_file(args.source))
    elif args.bytecode_file:
        if not os.path.exists(args.bytecode_file):
            raise SystemExit(f"Bytecode file not found: {args.bytecode_file}")
        result = extract_from_bytecode(_read_file(args.bytecode_file))
    else:
        result = extract_from_bytecode(args.hex or "")

    dump = json.dumps(result, indent=2 if args.pretty else None)
    print(dump)


if __name__ == "__main__":
    main()
