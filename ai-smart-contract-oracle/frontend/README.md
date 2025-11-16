AI Smart Contract Oracle - Frontend Dashboard

This is a Vite + React frontend dashboard for the AI Smart Contract Oracle project.

Features:
- Search contract address
- Risk score gauge (Recharts)
- Color-coded verdict badge
- Expandable sections showing AI feature breakdown, static analysis, and IPFS evidence
- Wallet integration using Wagmi + RainbowKit
- Live event listener for RiskAlertIssued events to auto-refresh UI

Quick start:
1. cd frontend
2. npm install
3. npm run dev

Environment variables (optional):
- VITE_API_URL - API gateway base URL (default http://127.0.0.1:8080)
- VITE_ORACLE_CONTRACT - Oracle contract address (for event listening)

Notes:
- This scaffold focuses on UI components and event listening. For production, wire in the RainbowKit ConnectButton UI and secure the backend endpoints.
