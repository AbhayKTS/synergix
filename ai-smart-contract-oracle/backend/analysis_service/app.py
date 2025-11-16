import os
import sys
import hashlib
import json
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Ensure project root is importable so we can import feature_extractor and model artifacts
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from feature_extractor import extract_from_bytecode, summarize_features

# XGBoost model loading
try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

# Web3 for fetching bytecode
try:
    from web3 import Web3
except Exception:
    Web3 = None

app = FastAPI(title='AI Smart Contract Analysis Service')

# Config (can be overridden via environment variables)
SEPOLIA_RPC = os.environ.get('SEPOLIA_RPC', 'https://sepolia.infura.io/v3/YOUR-PROJECT-ID')
MODEL_PATH = os.environ.get('MODEL_PATH', os.path.join(ROOT, 'model', 'security_model.xgb'))
FEATURE_IMPORTANCE_PATH = os.environ.get('FEATURE_IMPORTANCE_PATH', os.path.join(ROOT, 'model', 'feature_importance.json'))

# Load feature importance (if present) to determine feature ordering
if os.path.exists(FEATURE_IMPORTANCE_PATH):
    try:
        with open(FEATURE_IMPORTANCE_PATH, 'r', encoding='utf-8') as f:
            FEATURE_IMPORTANCE = json.load(f)
            FEATURE_ORDER = list(FEATURE_IMPORTANCE.keys())
    except Exception:
        FEATURE_IMPORTANCE = {}
        FEATURE_ORDER = []
else:
    FEATURE_IMPORTANCE = {}
    FEATURE_ORDER = []

# Load model if available
MODEL = None
if XGBClassifier is not None and os.path.exists(MODEL_PATH):
    try:
        MODEL = XGBClassifier()
        MODEL.load_model(MODEL_PATH)
    except Exception:
        MODEL = None

# Setup Web3 provider
W3 = None
if Web3 is not None:
    try:
        W3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC))
    except Exception:
        W3 = None


class AnalyzeRequest(BaseModel):
    contract_address: str


def normalize_address(addr: str) -> str:
    if not Web3:
        return addr
    try:
        return Web3.toChecksumAddress(addr)
    except Exception:
        return addr


def fetch_bytecode_from_chain(contract_address: str) -> str:
    """Fetch deployed bytecode for an address via Web3. Returns hex string starting with 0x."""
    if W3 is None:
        raise RuntimeError('Web3 is not available or not configured')
    checksum = normalize_address(contract_address)
    try:
        code = W3.eth.get_code(checksum)
        # code may be HexBytes or bytes
        try:
            hexstr = code.hex()
            if not hexstr.startswith('0x'):
                hexstr = '0x' + hexstr
        except Exception:
            # fallback
            hexstr = '0x' + code.hex() if hasattr(code, 'hex') else str(code)
        return hexstr
    except Exception as e:
        raise RuntimeError(f'Error fetching bytecode from chain: {e}')


def flatten_features(feat: Dict[str, Any]) -> Dict[str, float]:
    """Convert extractor features into a flat numeric dictionary of feature_name->value.

    Naming conventions:
      - opcode frequencies: op_<OPNAME>
      - bytecode_length_bytes
      - num_external_calls
      - vis_public / vis_external / vis_internal
      - mod_onlyOwner / mod_nonReentrant
      - jumps / jumpi / jumpdest / branch_keywords
    """
    out = {}
    # opcode frequencies
    opcode_freq = feat.get('opcode_frequency') or {}
    for k, v in opcode_freq.items():
        key = f'op_{k}'
        out[key] = float(v)

    # basic numeric
    for key in ['bytecode_length_bytes', 'num_external_calls']:
        val = feat.get(key)
        out[key] = float(val) if (val is not None) else 0.0

    # function visibility
    fv = feat.get('function_visibility') or {}
    out['vis_public'] = float(fv.get('public') or 0)
    out['vis_external'] = float(fv.get('external') or 0)
    out['vis_internal'] = float(fv.get('internal') or 0)

    # modifiers
    mu = feat.get('modifier_usage') or {}
    out['mod_onlyOwner'] = float(mu.get('onlyOwner') or 0)
    out['mod_nonReentrant'] = float(mu.get('nonReentrant') or 0)

    # control flow
    cf = feat.get('control_flow') or {}
    out['jumps'] = float(cf.get('num_jumps') or 0)
    out['jumpi'] = float(cf.get('num_jumpi') or 0)
    out['jumpdest'] = float(cf.get('num_jumpdest') or 0)
    out['branch_keywords'] = float(cf.get('branch_keywords') or 0)

    return out


def build_feature_vector(flat: Dict[str, float], feature_order: list) -> list:
    """Return a feature vector (list) ordered by feature_order. Missing features -> 0.0.

    If feature_order is empty, use sorted keys from flat dict to produce consistent ordering.
    """
    if not feature_order:
        feature_order = sorted(flat.keys())
    vec = [float(flat.get(k, 0.0)) for k in feature_order]
    return vec, feature_order


def run_model_inference(flat_features: Dict[str, float]) -> Dict[str, Any]:
    """Run model inference and return score and optional details."""
    if MODEL is None:
        # If no model available, return placeholder
        return {'model_score': None, 'model_prob': None}

    vec, used_order = build_feature_vector(flat_features, FEATURE_ORDER)
    # XGBoost expects 2D array
    try:
        probs = MODEL.predict_proba([vec])
        # probs shape (1, 2) assuming binary classification and label 1 is dangerous
        prob_danger = float(probs[0][1])
    except Exception:
        # fallback to predict (0 or 1)
        pred = MODEL.predict([vec])[0]
        prob_danger = float(pred)

    return {'model_score': prob_danger, 'feature_order': used_order}


def compute_static_analysis_score(features: Dict[str, Any]) -> float:
    """Heuristic static analysis score based on features as a placeholder for Slither.

    Returns a score between 0 and 1 where higher means more risky.
    """
    score = 0.0
    # high-risk opcodes
    opcode_freq = features.get('opcode_frequency') or {}
    if opcode_freq.get('DELEGATECALL', 0) > 0:
        score += 0.35
    if opcode_freq.get('SELFDESTRUCT', 0) > 0:
        score += 0.4
    # CALL presence
    if opcode_freq.get('CALL', 0) > 0:
        score += 0.2 * min(1.0, opcode_freq.get('CALL', 0) / 5.0)

    # control flow complexity increases risk moderately
    cf = features.get('control_flow') or {}
    jumps = cf.get('num_jumps') or 0
    jumpi = cf.get('num_jumpi') or 0
    branches = cf.get('branch_keywords') or 0
    complexity = (jumps + jumpi) * 0.01 + branches * 0.02
    score += min(0.2, complexity)

    # fewer protections reduce safety: absence of onlyOwner and nonReentrant counts as small increase in risk
    mu = features.get('modifier_usage') or {}
    if mu.get('onlyOwner', 0) == 0:
        score += 0.05
    if mu.get('nonReentrant', 0) == 0:
        score += 0.03

    # clamp to [0,1]
    return max(0.0, min(1.0, score))


def combine_scores(model_score: float, static_score: float, model_weight: float = 0.7) -> float:
    """Combine model and static analysis scores using weighted average."""
    if model_score is None:
        # rely purely on static
        return static_score
    if static_score is None:
        return model_score
    return float(model_weight * model_score + (1.0 - model_weight) * static_score)


def upload_report_to_ipfs(report: Dict[str, Any]) -> str:
    """Placeholder IPFS upload: when Pinata credentials are provided, one could implement
    the HTTP upload here. For now we return a deterministic placeholder CID computed from the report.
    """
    j = json.dumps(report, sort_keys=True).encode('utf-8')
    h = hashlib.sha256(j).hexdigest()
    # create a fake CID-like string
    return f'placeholder-{h}'


@app.post('/analyze')
async def analyze(req: AnalyzeRequest):
    addr = req.contract_address
    if not addr:
        raise HTTPException(status_code=400, detail='contract_address is required')

    # Step 1: fetch bytecode
    try:
        bytecode = fetch_bytecode_from_chain(addr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to fetch bytecode: {e}')

    # Step 2: extract features using feature_extractor
    try:
        features = extract_from_bytecode(bytecode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Feature extraction failed: {e}')

    # Step 3: run model inference
    flat = flatten_features(features)
    model_res = run_model_inference(flat)
    model_score = model_res.get('model_score')

    # Step 4: compute static analysis score (placeholder for Slither)
    static_score = compute_static_analysis_score(features)

    # Combine
    combined = combine_scores(model_score if model_score is not None else None, static_score)

    # Risk label mapping
    if combined < 0.3:
        label = 'safe'
    elif combined < 0.7:
        label = 'caution'
    else:
        label = 'dangerous'

    # Prepare detailed report
    report = {
        'contract_address': addr,
        'model_score': model_score,
        'static_score': static_score,
        'combined_score': combined,
        'risk_label': label,
        'features': {
            'flattened': flat,
            'raw': features,
        }
    }

    # Step 5: upload to IPFS (placeholder)
    cid = upload_report_to_ipfs(report)

    # Step 6: return
    return {
        'risk_score': combined,
        'risk_label': label,
        'ipfs_cid': cid,
        'feature_details': report['features'],
    }
