## Samurai Oracle Frontend

Cyberpunk samurai-inspired dashboard built with **Next.js + Tailwind CSS + Framer Motion + Three.js** to drive the AI Oracle pipeline.

### ✨ Features
- Wallet connect (MetaMask / ethers v6)
- Contract enqueue flow → POST `http://127.0.0.1:9000/enqueue`
- Animated 3D ETH coin + particle background
- Glassmorphic risk dashboard with live polling of `getFinalRisk`
- IPFS evidence link rendering + oracle submission stats

### 🏎 Quick start
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` once the task queue, inference API, Hardhat node, and oracle node are online.

### 🔧 Environment variables

Set these in a `.env.local` file (optional – sensible defaults target the local Hardhat stack):

```
NEXT_PUBLIC_QUEUE_URL=http://127.0.0.1:9000/enqueue
NEXT_PUBLIC_ORACLE_CONTRACT=0x5FbDB2315678afecb367f032d93F642f64180aa3
NEXT_PUBLIC_RPC_URL=http://127.0.0.1:8545
```

### 🧱 Project structure

```
src/
 ├─ pages/
 │   ├─ _app.js
 │   └─ index.jsx
 ├─ components/
 │   ├─ SamuraiHeader.jsx
 │   ├─ WalletConnect.jsx
 │   ├─ ContractInputCard.jsx
 │   ├─ RiskOutputPanel.jsx
 │   ├─ ParticleBackground.jsx
 │   └─ ThreeCoin.jsx
 ├─ abi/AIOracleAggregator.json
 ├─ web3/web3Client.js
 ├─ utils/ipfs.js
 └─ styles/globals.css
```

### 🚀 Workflow
1. Connect wallet (optional for read-only but required for future tx signing).
2. Enter a contract + optional Solidity source and click **Summon Oracle**.
3. Backend enqueues the job (`task_queue.py`).
4. Oracle node processes and submits results to `AIOracleAggregator`.
5. Dashboard polls `getFinalRisk` every 5 seconds and animates updates.

> Let this interface slice through uncertainty like a katana through silk.
