export const API_GATEWAY_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8080'
export const ORACLE_CONTRACT_ADDRESS = import.meta.env.VITE_ORACLE_CONTRACT || ''
export const ORACLE_ABI = [
  {
    "anonymous": false,
    "inputs": [
      {"indexed": true, "internalType": "address", "name": "target", "type": "address"},
      {"indexed": true, "internalType": "address", "name": "oracle", "type": "address"},
      {"indexed": false, "internalType": "uint8", "name": "category", "type": "uint8"},
      {"indexed": false, "internalType": "uint256", "name": "score", "type": "uint256"},
      {"indexed": false, "internalType": "string", "name": "ipfsCid", "type": "string"}
    ],
    "name": "AssessmentSubmitted",
    "type": "event"
  },
  {
    "anonymous": false,
    "inputs": [
      {"indexed": true, "internalType": "address", "name": "target", "type": "address"},
      {"indexed": false, "internalType": "uint8", "name": "category", "type": "uint8"},
      {"indexed": false, "internalType": "uint256", "name": "score", "type": "uint256"},
      {"indexed": false, "internalType": "string", "name": "ipfsCid", "type": "string"}
    ],
    "name": "RiskAlertIssued",
    "type": "event"
  }
]
