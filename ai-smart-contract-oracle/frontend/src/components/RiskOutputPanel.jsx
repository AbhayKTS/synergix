import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, Radio, Link2 } from 'lucide-react';
import { ipfsToHttp } from '@/utils/ipfs';

const categoryPalette = {
  0: { label: 'Safe', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  1: { label: 'Caution', color: 'text-amber-300', bg: 'bg-amber-300/10' },
  2: { label: 'Danger', color: 'text-red-400', bg: 'bg-red-400/10' }
};

export default function RiskOutputPanel({ riskData, isPolling }) {
  const palette = categoryPalette[riskData?.category ?? 0];
  const ipfsLink = ipfsToHttp(riskData?.ipfsCid);
  const timestamp = riskData?.timestamp ? new Date(riskData.timestamp * 1000) : null;
  const aggregatedScore = typeof riskData?.aggregatedScore === 'number' ? riskData.aggregatedScore : null;
  const normalizedScore = aggregatedScore !== null ? Math.max(0, Math.min(aggregatedScore, 100)) : 0;
  const confidencePercent = typeof riskData?.confidence === 'number' ? Math.round(riskData.confidence * 100) : null;
  const attackVectors = riskData?.attackVectors ?? [];
  const intelFeed = riskData?.intelFeed ?? [];
  const consensusCopy = riskData?.modelConsensus || 'Oracle council syncing';

  return (
    <div className="glass-panel relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-black/40 via-[#0b0b11]/70 to-black/80 p-6">
      <div className="pointer-events-none absolute inset-0 opacity-60" style={{
        background: 'radial-gradient(circle at 20% 20%, rgba(234,46,73,0.2), transparent 55%)'
      }} />
      <div className="pointer-events-none absolute inset-0 opacity-50" style={{
        background: 'radial-gradient(circle at 80% 30%, rgba(112,52,255,0.22), transparent 55%)'
      }} />
      <div className="relative">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs tracking-[0.4em] text-white/50">ORACLE STATUS</p>
          <h3 className="font-serif text-2xl text-white">Real-Time Verdict Stream</h3>
        </div>
        <div className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs uppercase ${palette.bg} ${palette.color}`}>
          <Radio size={16} className={isPolling ? 'animate-pulse' : ''} />
          Polling
        </div>
      </div>
      <div className="katana-divider" />
      <div className="grid gap-6 lg:grid-cols-2">
        <motion.div
          className="glass-panel rounded-2xl border border-white/10 bg-black/50 p-5"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <p className="text-sm text-white/60">Risk Score</p>
          <AnimatePresence mode="wait">
            <motion.p
              key={riskData?.aggregatedScore ?? 'pending'}
              className="text-6xl font-semibold tracking-tight text-white"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
            >
              {riskData?.aggregatedScore ?? '--'}
            </motion.p>
          </AnimatePresence>
          <p className={`mt-2 inline-flex items-center gap-2 rounded-full px-4 py-1 text-sm ${palette.bg} ${palette.color}`}>
            <ShieldAlert size={18} />
            {palette.label}
          </p>
          {aggregatedScore !== null && (
            <div className="mt-4 h-2 w-full rounded-full border border-white/10 bg-black/60">
              <div
                className="h-full rounded-full bg-gradient-to-r from-katana via-amber-400 to-neon"
                style={{ width: `${normalizedScore}%` }}
              />
            </div>
          )}
        </motion.div>
        <div className="space-y-4 text-sm text-white/70">
          <div className="flex items-center justify-between rounded-2xl border border-white/5 bg-black/30 p-4">
            <span>Oracle Submissions</span>
            <strong className="text-xl text-white">{riskData?.numSubmittingOracles ?? '--'}</strong>
          </div>
          <div className="flex items-center justify-between rounded-2xl border border-white/5 bg-black/30 p-4">
            <span>Finalized</span>
            <strong className="text-xl text-white">{riskData?.finalized ? 'Yes' : 'Pending'}</strong>
          </div>
          <div className="rounded-2xl border border-white/5 bg-black/30 p-4">
            <p className="text-white/60">Timestamp</p>
            <p className="text-white">{timestamp ? timestamp.toLocaleString() : 'Awaiting verdict'}</p>
          </div>
          <div className="rounded-2xl border border-white/5 bg-black/30 p-4">
            <p className="text-white/60">Evidence</p>
            {ipfsLink ? (
              <a href={ipfsLink} className="inline-flex items-center gap-2 text-neon" target="_blank" rel="noreferrer">
                <Link2 size={16} /> View IPFS dossier
              </a>
            ) : (
              <p className="text-white/40">Oracle has not published IPFS evidence yet.</p>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-white/5 bg-black/40 p-4">
              <p className="text-white/60">Signal Confidence</p>
              <p className="text-2xl font-semibold text-white">{confidencePercent ? `${confidencePercent}%` : 'Calibrating'}</p>
              {confidencePercent && (
                <div className="mt-3 h-1.5 rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-red-400"
                    style={{ width: `${confidencePercent}%` }}
                  />
                </div>
              )}
            </div>
            <div className="rounded-2xl border border-white/5 bg-black/40 p-4">
              <p className="text-white/60">Council Consensus</p>
              <p className="text-xl font-semibold text-white">{consensusCopy}</p>
              <p className="text-xs uppercase tracking-[0.3em] text-white/40">model agreement</p>
            </div>
          </div>
          <div className="rounded-2xl border border-white/5 bg-black/30 p-4">
            <p className="text-white/60">Dominant Attack Vectors</p>
            {attackVectors.length ? (
              <div className="mt-3 space-y-2">
                {attackVectors.map((vector) => (
                  <div key={vector.label} className="flex items-center justify-between rounded-xl border border-white/5 bg-black/50 px-3 py-2">
                    <span className="text-white/80">{vector.label}</span>
                    <span className="text-white font-semibold">{vector.weight}%</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-white/40">Awaiting vector telemetry.</p>
            )}
          </div>
          <div className="rounded-2xl border border-white/5 bg-black/30 p-4">
            <p className="text-white/60">Intelligence Feed</p>
            {intelFeed.length ? (
              <div className="mt-3 space-y-3">
                {intelFeed.map((item, index) => (
                  <div key={`${item.type}-${index}`} className="rounded-xl border border-white/5 bg-black/60 px-3 py-2">
                    <span
                      className={`mb-1 inline-flex rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.3em] ${
                        item.type === 'critical' ? 'bg-red-500/20 text-red-300' : item.type === 'notice' ? 'bg-amber-400/20 text-amber-200' : 'bg-white/10 text-white/70'
                      }`}
                    >
                      {item.type}
                    </span>
                    <p className="text-white/80">{item.message}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-white/40">Oracle auditors syncing logs.</p>
            )}
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
