#!/usr/bin/env python3
"""
oracle_node.py

Watches the analysis queue directory (`backend/queue`) for new result JSON files.
For each new result, it signs the payload with a configured private key and submits
it to a configured smart contract function:

  submitAssessment(address contractAddress, uint256 score, string ipfsCid, bytes signature)

Helper functions:
- load_private_key(): load key from env or file
- sign_message(): produce an Ethereum-compatible signature over the assessment
- submit_to_chain(): build, sign, and send the transaction

Configuration via environment variables:
- QUEUE_DIR (default: backend/queue)
- PROCESSED_DIR (default: backend/queue/processed)
- FAILED_DIR (default: backend/queue/failed)
- ORACLE_CONTRACT_ADDRESS (required): address of the contract exposing submitAssessment
- SEPOLIA_RPC (default placeholder): RPC endpoint
- PRIVATE_KEY or PRIVATE_KEY_FILE: private key hex or path to file
- POLL_INTERVAL (seconds, default 5)

"""

import os
import sys
import time
import json
import logging
from typing import Tuple

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# External deps
try:
    from web3 import Web3
    from web3.exceptions import TransactionNotFound
    from eth_account import Account
    from eth_account.messages import encode_defunct
except Exception:
    Web3 = None
    Account = None

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger('oracle_node')

# Config
QUEUE_DIR = os.environ.get('QUEUE_DIR', os.path.join(ROOT, 'backend', 'queue'))
PROCESSED_DIR = os.environ.get('PROCESSED_DIR', os.path.join(QUEUE_DIR, 'processed'))
FAILED_DIR = os.environ.get('FAILED_DIR', os.path.join(QUEUE_DIR, 'failed'))
ORACLE_CONTRACT_ADDRESS = os.environ.get('ORACLE_CONTRACT_ADDRESS')  # required
SEPOLIA_RPC = os.environ.get('SEPOLIA_RPC', 'https://sepolia.infura.io/v3/YOUR-PROJECT-ID')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
PRIVATE_KEY_FILE = os.environ.get('PRIVATE_KEY_FILE')
POLL_INTERVAL = float(os.environ.get('POLL_INTERVAL', '5'))
CHAIN_ID = os.environ.get('CHAIN_ID')  # optional, will try to query from node

# Minimal ABI for submitAssessment(contractAddress,uint256,string,bytes)
ORACLE_ABI = [
    {
        'inputs': [
            {'internalType': 'address', 'name': 'contractAddress', 'type': 'address'},
            {'internalType': 'uint256', 'name': 'score', 'type': 'uint256'},
            {'internalType': 'string', 'name': 'ipfsCid', 'type': 'string'},
            {'internalType': 'bytes', 'name': 'signature', 'type': 'bytes'},
        ],
        'name': 'submitAssessment',
        'outputs': [],
        'stateMutability': 'nonpayable',
        'type': 'function'
    }
]


def ensure_dirs():
    os.makedirs(QUEUE_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)


def load_private_key() -> str:
    """Load the private key hex string either directly from env PRIVATE_KEY or from PRIVATE_KEY_FILE.

    Returns the hex string starting with 0x.
    """
    if PRIVATE_KEY:
        pk = PRIVATE_KEY.strip()
        if not pk.startswith('0x'):
            pk = '0x' + pk
        return pk
    if PRIVATE_KEY_FILE and os.path.exists(PRIVATE_KEY_FILE):
        with open(PRIVATE_KEY_FILE, 'r', encoding='utf-8') as f:
            pk = f.read().strip()
            if not pk.startswith('0x'):
                pk = '0x' + pk
            return pk
    raise RuntimeError('Private key not configured. Set PRIVATE_KEY or PRIVATE_KEY_FILE environment variable.')


def sign_message(private_key: str, contract_address: str, score_int: int, ipfs_cid: str) -> str:
    """Sign the assessment payload and return the signature hex string (0x...).

    We compute keccak256(abi.encodePacked(address,uint256,string)) using Web3.solidityKeccak
    and then sign the hash using eth-account encode_defunct for compatibility with personal_sign.
    """
    if Web3 is None or Account is None:
        raise RuntimeError('web3 and eth_account must be installed')

    # Ensure checksum address
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC))
    try:
        checksum = w3.toChecksumAddress(contract_address)
    except Exception:
        checksum = contract_address

    # solidityKeccak expects types and values
    hash_bytes = w3.solidityKeccak(['address', 'uint256', 'string'], [checksum, int(score_int), ipfs_cid])
    # encode as defunct message for signing
    message = encode_defunct(hexstr=hash_bytes.hex())
    signed = Account.sign_message(message, private_key=private_key)
    sig_hex = signed.signature.hex()
    return sig_hex


def submit_to_chain(private_key: str, oracle_contract_address: str, target_contract_address: str, score_int: int, ipfs_cid: str, signature_hex: str) -> str:
    """Submit the signed assessment to the on-chain oracle contract and return tx hash hex.

    Requires SEPOLIA_RPC and ORACLE_ABI. Handles nonce, gas estimation, signing and broadcasting.
    """
    if Web3 is None:
        raise RuntimeError('web3 is not installed')

    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC))
    if not w3.isConnected():
        raise RuntimeError('Failed to connect to RPC provider')

    # Load contract
    try:
        oracle_addr = w3.toChecksumAddress(oracle_contract_address)
    except Exception:
        oracle_addr = oracle_contract_address
    contract = w3.eth.contract(address=oracle_addr, abi=ORACLE_ABI)

    # Derive account from private key
    acct = Account.from_key(private_key)
    sender = acct.address

    # Prepare args: bytes signature needs to be bytes, convert from hex
    sig_bytes = bytes.fromhex(signature_hex[2:] if signature_hex.startswith('0x') else signature_hex)

    # Convert to score uint256 - already provided
    tx = None
    try:
        # Build transaction
        txn = contract.functions.submitAssessment(target_contract_address, int(score_int), ipfs_cid, sig_bytes).buildTransaction({
            'from': sender,
            'nonce': w3.eth.get_transaction_count(sender),
            'gasPrice': w3.eth.gas_price,
        })
        # Estimate gas if not present
        try:
            gas_est = w3.eth.estimate_gas({
                'to': oracle_addr,
                'from': sender,
                'data': txn['data']
            })
            txn['gas'] = int(gas_est * 1.2)
        except Exception:
            txn['gas'] = 300000

        # Chain ID
        try:
            txn['chainId'] = int(CHAIN_ID) if CHAIN_ID else w3.eth.chain_id
        except Exception:
            txn['chainId'] = w3.eth.chain_id

        # Sign
        signed_txn = Account.sign_transaction(txn, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        logger.info(f'Submitted tx {tx_hash_hex} for contract {target_contract_address}')
        return tx_hash_hex
    except Exception as e:
        raise RuntimeError(f'Transaction submission failed: {e}')


def process_file(filepath: str, private_key: str) -> Tuple[bool, str]:
    """Process a single JSON result file: sign and submit. Returns (success, message_or_txhash)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return False, f'Failed to load JSON: {e}'

    # Expected fields: contract_address, risk_score (float or int), ipfs_cid
    contract_address = data.get('contract_address') or data.get('contractAddress')
    score = data.get('risk_score') or data.get('score') or data.get('combined_score')
    ipfs_cid = data.get('ipfs_cid') or data.get('ipfsCid')

    if not contract_address or score is None or not ipfs_cid:
        return False, 'Missing required fields (contract_address, risk_score, ipfs_cid) in JSON'

    # Determine integer score for on-chain uint256. If score in [0,1], scale to 0-100; otherwise try cast to int.
    try:
        s_float = float(score)
        if 0.0 <= s_float <= 1.0:
            score_int = int(round(s_float * 100))
        else:
            score_int = int(round(s_float))
    except Exception:
        return False, 'Invalid score value'

    # Sign the message
    try:
        sig_hex = sign_message(private_key, contract_address, score_int, ipfs_cid)
    except Exception as e:
        return False, f'Signing failed: {e}'

    # Submit to chain
    oracle_addr = os.environ.get('ORACLE_CONTRACT_ADDRESS')
    if not oracle_addr:
        return False, 'ORACLE_CONTRACT_ADDRESS not configured in environment'

    try:
        tx_hash = submit_to_chain(private_key, oracle_addr, contract_address, score_int, ipfs_cid, sig_hex)
        return True, tx_hash
    except Exception as e:
        return False, f'Submission failed: {e}'


def watch_loop():
    ensure_dirs()
    private_key = load_private_key()
    logger.info('Oracle node started. Watching queue: %s', QUEUE_DIR)

    while True:
        try:
            files = [f for f in os.listdir(QUEUE_DIR) if f.lower().endswith('.json')]
            files = sorted(files)  # process in alphabetical/creation order
            for fname in files:
                path = os.path.join(QUEUE_DIR, fname)
                # skip directories and processed/failed dirs
                if os.path.isdir(path):
                    continue
                logger.info('Processing file: %s', path)
                success, msg = process_file(path, private_key)
                if success:
                    logger.info('Processed successfully: %s -> tx %s', fname, msg)
                    # move to processed
                    dest = os.path.join(PROCESSED_DIR, fname)
                    os.replace(path, dest)
                else:
                    logger.error('Failed to process %s: %s', fname, msg)
                    # move to failed with .err suffix
                    dest = os.path.join(FAILED_DIR, fname)
                    # attach error info next to file
                    errpath = dest + '.error.txt'
                    try:
                        with open(errpath, 'w', encoding='utf-8') as ef:
                            ef.write(str(msg))
                    except Exception:
                        pass
                    try:
                        os.replace(path, dest)
                    except Exception:
                        # if replace fails, attempt to remove original
                        try:
                            os.remove(path)
                        except Exception:
                            pass
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info('Shutting down oracle node (keyboard interrupt)')
            break
        except Exception as e:
            logger.exception('Unexpected error in watch loop: %s', e)
            time.sleep(POLL_INTERVAL)


def main():
    try:
        watch_loop()
    except Exception as e:
        logger.exception('Oracle node terminated with error: %s', e)


if __name__ == '__main__':
    main()
