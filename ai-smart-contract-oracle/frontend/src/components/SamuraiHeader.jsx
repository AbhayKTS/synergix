import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, ShieldHalf, Coins, ArrowRightCircle } from 'lucide-react';

const tokenLabels = [
  'BTC', 'ETH', 'USDT', 'XRP', 'BNB', 'USDC', 'SOL', 'TRX', 'STETH', 'DOGE', 'ADA', 'USDE', 'WBTC', 'BCH', 'HYPE',
  'WBETH', 'WETH', 'ZEC', 'LINK', 'XLM', 'XMR', 'LTC', 'HBAR', 'sUSDe', 'AVAX', 'DAI', 'SUI', 'SHIB', 'UNI', 'TON',
  'WLFI', 'RNDR', 'DOT', 'MNT', 'TAO', 'AAVE', 'sUSDS', 'BGB', 'NEAR', 'ICP', 'OKB', 'ETC', 'PI', 'JITOSOL'
];

const ORBIT_PRESETS = {
  desktop: {
    coreSize: 320,
    clearance: 38,
    ringSpacing: 62,
    sizeRange: [42, 60],
    durationBase: 18,
    orbitPadding: 18,
    ringCount: 3
  },
  tablet: {
    coreSize: 288,
    clearance: 32,
    ringSpacing: 56,
    sizeRange: [38, 54],
    durationBase: 16,
    orbitPadding: 16,
    ringCount: 3
  },
  mobile: {
    coreSize: 240,
    clearance: 26,
    ringSpacing: 48,
    sizeRange: [30, 44],
    durationBase: 14,
    orbitPadding: 12,
    ringCount: 2
  }
};

const goldenNoise = (seed) => {
  const sin = Math.sin(seed * 937.999);
  return sin - Math.floor(sin);
};

// Deterministically distribute tokens in concentric orbits that never trespass into the coin boundary.
const buildSigils = (mode = 'desktop') => {
  const settings = ORBIT_PRESETS[mode] || ORBIT_PRESETS.desktop;
  const { coreSize, clearance, ringSpacing, sizeRange, durationBase, orbitPadding, ringCount } = settings;
  const [minSize, maxSize] = sizeRange;
  const coreRadius = coreSize / 2;
  const baseRadius = coreRadius + clearance + maxSize / 2 + orbitPadding;
  const totalTokens = tokenLabels.length;

  const rings = Array.from({ length: ringCount }, (_, ringIndex) => {
    const radius = baseRadius + ringIndex * ringSpacing;
    const circumference = 2 * Math.PI * radius;
    const averageSpacing = ((minSize + maxSize) / 2) * 1.32;
    const capacity = Math.max(8 + ringIndex * 2, Math.floor(circumference / averageSpacing));
    return { radius, capacity, ringIndex };
  });

  const ringCounts = [];
  let assigned = 0;
  rings.forEach((ring, index) => {
    const remainingTokens = totalTokens - assigned;
    const remainingRings = ringCount - index;
    const ideal = Math.ceil(remainingTokens / Math.max(1, remainingRings));
    const count = Math.max(0, Math.min(ring.capacity, ideal));
    ringCounts.push(count);
    assigned += count;
  });

  let leftover = totalTokens - assigned;
  while (leftover > 0) {
    let distributed = false;
    for (let i = 0; i < ringCount && leftover > 0; i += 1) {
      if (ringCounts[i] < rings[i].capacity) {
        ringCounts[i] += 1;
        leftover -= 1;
        distributed = true;
      }
    }
    if (!distributed) break;
  }

  const items = [];
  let labelIndex = 0;

  rings.forEach((ring, ringIdx) => {
    const count = ringCounts[ringIdx];
    if (!count) return;

    const angleStep = (Math.PI * 2) / count;
    const baseOffset = goldenNoise(ringIdx + 5) * Math.PI * 2;

    for (let slot = 0; slot < count && labelIndex < totalTokens; slot += 1) {
      const label = tokenLabels[labelIndex];
      const variance = goldenNoise(labelIndex + 17);
      const varianceSecondary = goldenNoise(labelIndex + 29);
      const varianceTertiary = goldenNoise(labelIndex + 41);
      const size = minSize + variance * (maxSize - minSize);
      const angle = baseOffset + slot * angleStep + (varianceSecondary - 0.5) * 0.22;

      const minDistance = coreRadius + size / 2 + clearance;
      const safeRange = Math.max(6, ring.radius - minDistance);
      const drift = Math.min(safeRange, 12 + varianceTertiary * 12);
      const tangentAngle = angle + Math.PI / 2;
      const radialPhase = varianceSecondary * Math.PI * 2;

      const steps = [0, 0.25, 0.5, 0.75, 1];
      const framePositions = steps.map((progress) => {
        const radialShift = Math.sin(progress * Math.PI * 2 + radialPhase) * drift * 0.4;
        const tangential = Math.cos(progress * Math.PI * 2 + radialPhase) * drift;
        const x = Math.cos(angle) * (ring.radius + radialShift) + Math.cos(tangentAngle) * tangential * 0.55;
        const y = Math.sin(angle) * (ring.radius + radialShift) + Math.sin(tangentAngle) * tangential * 0.55;
        return { x, y };
      });

      const opacity = 0.58 + variance * 0.28;
      const glow = 0.25 + varianceSecondary * 0.3;
      const duration = durationBase + ringIdx * 2.6 + varianceSecondary * 3.8;
      const delay = variance * 3.5;

      items.push({
        label,
        size,
        path: {
          x: framePositions.map((frame) => frame.x),
          y: framePositions.map((frame) => frame.y)
        },
        opacity,
        glow,
        duration,
        delay,
        ring: ringIdx
      });

      labelIndex += 1;
    }
  });

  return items;
};

export default function SamuraiHeader({ ThreeCoin: ThreeCoinComponent }) {
  const [sigilState, setSigilState] = useState({ mode: 'desktop', items: buildSigils('desktop') });

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const detectMode = () => {
      const width = window.innerWidth;
      if (width < 640) return 'mobile';
      if (width < 1024) return 'tablet';
      return 'desktop';
    };

    const updateLayout = () => {
      const nextMode = detectMode();
      setSigilState((current) => {
        if (current.mode === nextMode) return current;
        return { mode: nextMode, items: buildSigils(nextMode) };
      });
    };

    updateLayout();
    window.addEventListener('resize', updateLayout);
    return () => window.removeEventListener('resize', updateLayout);
  }, []);

  const sigils = sigilState.items;

  return (
    <section className="relative overflow-hidden rounded-[36px] border border-white/5 bg-black/30 p-10 shadow-katana-glow">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_20%,rgba(234,46,73,0.22),transparent_60%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_88%_25%,rgba(112,52,255,0.28),transparent_55%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent opacity-50" />
      <div className="pointer-events-none absolute -left-24 top-1/2 hidden h-72 w-72 -translate-y-1/2 rounded-full border border-katana/10 blur-md lg:block" />
      <div className="relative grid gap-12 lg:grid-cols-2">
        <div className="space-y-8">
          <motion.p
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1 text-[0.7rem] tracking-[0.35em] text-frost"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <Sparkles size={16} className="text-katana" />
            SAMURAI ORACLE NETWORK
          </motion.p>
          <motion.h1
            className="font-serif text-4xl leading-tight text-white drop-shadow-xl md:text-5xl lg:text-6xl"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.8 }}
          >
            Decentralized AI Oracle —{' '}
            <span className="bg-gradient-to-r from-katana via-white to-neon bg-clip-text text-transparent">Predict</span>
            {' '}Smart Contract Exploits Before They Strike.
          </motion.h1>
          <motion.p
            className="max-w-xl text-base text-white/70 md:text-lg"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.8 }}
          >
            Fueled by predictive AI and katana-grade cryptography. Submit contracts, summon oracle nodes, and read
            on-chain verdicts in real time—all wrapped in glassmorphic cyber-samurai elegance.
          </motion.p>
          <motion.div
            className="flex flex-col gap-3 sm:flex-row"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45, duration: 0.8 }}
          >
            <a
              href="#oracle-controls"
              className="group inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-gradient-to-r from-katana to-neon px-6 py-3 text-sm font-semibold tracking-wide text-white shadow-neon-ring transition hover:scale-[1.01]"
            >
              Begin Assessment
              <ArrowRightCircle size={18} className="transition group-hover:translate-x-1" />
            </a>
            <a
              href="https://samurai-oracle.gitbook.io/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-white/70 transition hover:border-neon/60 hover:text-white"
            >
              View Protocol Runbook
            </a>
          </motion.div>
          <div className="katana-divider" />
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { icon: ShieldHalf, label: 'AI Risk Sentinel', value: 'Proactive' },
              { icon: Coins, label: 'Chain Ready', value: 'Hardhat L2' },
              { icon: Sparkles, label: 'Response', value: '< 5s Poll' }
            ].map((item) => (
              <motion.div
                key={item.label}
                className="glass-panel flex flex-col gap-1 rounded-2xl border border-white/10 p-4 text-sm backdrop-blur"
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
              >
                <item.icon className="text-neon" size={22} />
                <span className="text-white/60">{item.label}</span>
                <span className="text-lg font-semibold text-white">{item.value}</span>
              </motion.div>
            ))}
          </div>
        </div>
        <div className="relative flex min-h-[600px] w-full items-center justify-center overflow-visible">
          <div
            className="pointer-events-none absolute inset-0 opacity-65"
            style={{
              background: 'radial-gradient(circle at 50% 50%, rgba(112,52,255,0.32), transparent 68%)'
            }}
          />
          <motion.div
            className="pointer-events-none absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-katana/18 via-transparent to-neon/12 blur-[170px]"
            initial={{ opacity: 0.06 }}
            animate={{ opacity: [0.08, 0.2, 0.08] }}
            transition={{ duration: 10, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
          />
          <motion.div
            className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10"
            initial={{ opacity: 0.12, scale: 0.94 }}
            animate={{ opacity: [0.1, 0.24, 0.1], scale: [0.97, 1.03, 0.97] }}
            transition={{ duration: 8, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
          />
          <div className="relative z-20 flex h-[320px] w-[320px] items-center justify-center">
            {ThreeCoinComponent ? <ThreeCoinComponent /> : null}
          </div>
          {sigils.map((sigil) => (
            <motion.div
              key={sigil.label}
              className="crypto-sigil absolute left-1/2 top-1/2 flex items-center justify-center border text-[0.65rem] font-semibold uppercase tracking-widest text-white/85 backdrop-blur-xl"
              style={{
                width: `${sigil.size}px`,
                height: `${sigil.size}px`,
                marginLeft: `-${sigil.size / 2}px`,
                marginTop: `-${sigil.size / 2}px`,
                opacity: sigil.opacity,
                boxShadow: `0 0 ${18 + sigil.ring * 6}px rgba(112, 52, 255, ${0.2 + sigil.glow}), inset 0 0 ${12 + sigil.ring * 4}px rgba(234, 46, 73, ${0.16 + sigil.glow / 1.9})`,
                borderColor: `rgba(255, 255, 255, ${0.12 + sigil.glow / 2})`,
                background: 'radial-gradient(circle at 35% 30%, rgba(255,255,255,0.26), rgba(112,52,255,0.18) 55%, rgba(234,46,73,0.18) 100%)',
                willChange: 'transform, opacity'
              }}
              initial={{
                x: sigil.path.x[0],
                y: sigil.path.y[0],
                opacity: 0,
                scale: 0.86
              }}
              animate={{
                x: sigil.path.x,
                y: sigil.path.y,
                opacity: [sigil.opacity * 0.25, sigil.opacity, sigil.opacity * 0.45, sigil.opacity, sigil.opacity * 0.35],
                scale: [0.98, 1.06, 1, 1.03, 0.99],
                rotate: sigil.ring % 2 === 0 ? [0, 2.4, -1.4, 1, 0] : [0, -2, 1.6, -1, 0]
              }}
              transition={{
                duration: sigil.duration,
                repeat: Infinity,
                repeatType: 'mirror',
                ease: 'easeInOut',
                delay: sigil.delay
              }}
              whileHover={{ scale: 1.18, filter: 'brightness(1.2)' }}
            >
              <span className="relative z-[1] drop-shadow-lg">{sigil.label}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
