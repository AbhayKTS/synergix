import { ethers } from 'ethers';
import aggregatorArtifact from '@/abi/AIOracleAggregator.json';

const CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_ORACLE_CONTRACT || '0x5FbDB2315678afecb367f032d93F642f64180aa3';
const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL || 'http://127.0.0.1:8545';

const abi = aggregatorArtifact.abi;
const USE_MOCK_RISK = process.env.NEXT_PUBLIC_USE_MOCK_RISK !== 'false';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const vectorPool = [
  'Liquidity Drain',
  'Reentrancy',
  'Price Oracle Drift',
  'Delegatecall Shadow',
  'Unchecked Call Return',
  'Arithmetic Underflow',
  'Governance Hijack'
];

const consensusPool = ['Unanimous', 'Supermajority', 'Split Council'];

const generateMockRisk = (targetAddress) => {
  const addressFragment = (targetAddress || '').replace(/^0x/i, '').padEnd(8, '0').slice(0, 8);
  const seed = parseInt(addressFragment || '0', 16);
  const jitter = Math.floor((Date.now() / 5000) % 7);
  const baseScore = 18 + (seed % 63); // keep it between ~18-80
  const aggregatedScore = Math.max(12, Math.min(96, baseScore + jitter));
  const category = aggregatedScore < 35 ? 0 : aggregatedScore < 70 ? 1 : 2;
  const timestamp = Math.floor(Date.now() / 1000) - (seed % 3600);
  const confidence = 0.68 + ((seed % 23) / 100); // 68% - 91%
  const consensusIndex = seed % consensusPool.length;

  const weights = [
    (seed % 40) + 30,
    ((seed >> 3) % 35) + 20,
    ((seed >> 5) % 25) + 15
  ];
  const weightSum = weights.reduce((sum, value) => sum + value, 0);
  const attackVectors = weights.map((weight, idx) => ({
    label: vectorPool[(seed + idx * 3) % vectorPool.length],
    weight: Math.round((weight / weightSum) * 100)
  }));

  const intelFeed = [
    {
      type: category === 2 ? 'critical' : 'notice',
      message:
        category === 2
          ? 'Validator shard detected correlated liquidation vectors across testnet pools.'
          : 'State diffs align with reference implementation — no drift detected.'
    },
    {
      type: 'info',
      message: `MEV replay window ${(seed % 9) + 1} blocks — anomaly ${seed % 2 ? 'absent' : 'muted'}.`
    }
  ];

  return {
    aggregatedScore,
    category,
    ipfsCid: `QmMockedRiskCid${(seed % 1000).toString().padStart(3, '0')}`,
    timestamp,
    numSubmittingOracles: 3 + (seed % 4),
    finalized: true,
    confidence,
    modelConsensus: consensusPool[consensusIndex],
    attackVectors,
    intelFeed
  };
};

export const shortenAddress = (address) => {
  if (!address || address.length < 10) return address || '';
  return `${address.slice(0, 6)}···${address.slice(-4)}`;
};

export const getBrowserProvider = () => {
  if (typeof window === 'undefined' || !window.ethereum) {
    throw new Error('MetaMask not detected. Install it to sign oracle summons.');
  }
  return new ethers.BrowserProvider(window.ethereum);
};

export const connectWallet = async () => {
  const provider = getBrowserProvider();
  await provider.send('eth_requestAccounts', []);
  const signer = await provider.getSigner();
  const address = await signer.getAddress();
  return { address, provider, signer };
};

export const getReadOnlyProvider = () => {
  return new ethers.JsonRpcProvider(RPC_URL);
};

export const getContract = (providerOrSigner) => {
  if (!providerOrSigner) {
    throw new Error('Provider or signer is required to instantiate the oracle contract');
  }
  return new ethers.Contract(CONTRACT_ADDRESS, abi, providerOrSigner);
};

export const fetchFinalRisk = async (targetAddress, providerOverride) => {
  if (!targetAddress) return null;

  if (USE_MOCK_RISK) {
    await sleep(800);
    return generateMockRisk(targetAddress);
  }

  const provider = providerOverride || getReadOnlyProvider();
  const contract = getContract(provider);
  const result = await contract.getFinalRisk(targetAddress);
  return {
    aggregatedScore: Number(result[0]),
    category: Number(result[1]),
    ipfsCid: result[2],
    timestamp: Number(result[3]),
    numSubmittingOracles: Number(result[4]),
    finalized: Boolean(result[5])
  };
};
