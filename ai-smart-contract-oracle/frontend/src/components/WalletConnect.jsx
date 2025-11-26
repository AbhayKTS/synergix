import { motion } from 'framer-motion';
import { Wallet } from 'lucide-react';
import { shortenAddress } from '@/web3/web3Client';

export default function WalletConnect({ address, onConnect, isConnecting }) {
  const buttonLabel = address ? 'Samurai Linked' : 'Connect Wallet';
  return (
    <motion.div
      className="glass-panel flex flex-col gap-5 rounded-3xl border border-white/10 bg-gradient-to-br from-black/50 via-black/30 to-white/10 p-6"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-white/60">Wallet Link</p>
          <p className="font-serif text-2xl text-white">Summon Your Samurai Identity</p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[0.65rem] uppercase tracking-[0.4em] text-white/50">
          Web3 Ready
        </span>
      </div>
      <button
        type="button"
        onClick={onConnect}
        disabled={!!address || isConnecting}
        className="group inline-flex items-center justify-center gap-3 rounded-full border border-white/10 bg-gradient-to-r from-katana/80 to-neon/60 px-6 py-3 font-semibold tracking-wide text-white shadow-neon-ring transition duration-300 hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-70"
      >
        <Wallet className="text-white drop-shadow" />
        {isConnecting ? 'Linking...' : buttonLabel}
      </button>
      {address && (
        <div className="rounded-2xl border border-white/5 bg-black/40 p-4 text-sm">
          <p className="text-white/50">Connected as</p>
          <p className="font-mono text-lg text-white">{shortenAddress(address)}</p>
        </div>
      )}
    </motion.div>
  );
}
