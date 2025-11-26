import { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import axios from 'axios';
import { motion } from 'framer-motion';

import Hero from '@/components/Hero';
import Header from '@/components/nav/Header';
import WalletConnect from '@/components/WalletConnect';
import ContractInputCard from '@/components/ContractInputCard';
import RiskOutputPanel from '@/components/RiskOutputPanel';
import ParticleBackground from '@/components/ParticleBackground';
import { connectWallet, fetchFinalRisk } from '@/web3/web3Client';



const QUEUE_URL = process.env.NEXT_PUBLIC_QUEUE_URL || 'http://127.0.0.1:9000/enqueue';
const POLL_INTERVAL = 5000;
const USE_MOCK_RISK = process.env.NEXT_PUBLIC_USE_MOCK_RISK !== 'false';
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export default function HomePage() {
  const [walletAddress, setWalletAddress] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [contractAddress, setContractAddress] = useState('');
  const [sourceCode, setSourceCode] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [riskData, setRiskData] = useState(null);
  const [activeTarget, setActiveTarget] = useState('');
  const [isPolling, setIsPolling] = useState(false);

  const petals = useMemo(() => Array.from({ length: 12 }), []);

  const handleConnect = async () => {
    try {
      setIsConnecting(true);
      const { address } = await connectWallet();
      setWalletAddress(address);
    } catch (error) {
      console.error(error);
      setStatusMessage(error.message || 'Wallet connection failed.');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleSubmit = async () => {
    const normalizedAddress = contractAddress.trim();
    if (!normalizedAddress) {
      setStatusMessage('Enter a contract address first.');
      return;
    }
    try {
      setIsSubmitting(true);
      setRiskData(null);
      setActiveTarget('');

      const requestSuffix = normalizedAddress.replace(/^0x/i, '').slice(0, 6).toUpperCase() || 'SAMURI';

      if (USE_MOCK_RISK) {
        setStatusMessage(`Request RQ-${requestSuffix} acknowledged — validator clans syncing (mock).`);
        await sleep(900);
        setStatusMessage('Simulated dispatch complete. Polling for finalized verdict.');
        setActiveTarget(normalizedAddress);
        return;
      }

      setStatusMessage('Dispatching assessment request to the queue...');
      await axios.post(QUEUE_URL, {
        contract_address: normalizedAddress,
        source_code: sourceCode || undefined
      });
      setStatusMessage(`Request RQ-${requestSuffix} sent — Oracle dispatching. Polling for finalized verdict.`);
      setActiveTarget(normalizedAddress);
    } catch (error) {
      console.error(error);
      const fallbackMessage = USE_MOCK_RISK ? 'Mock request hiccup. Try summoning once more.' : 'Unable to enqueue task.';
      setStatusMessage(error.response?.data?.message || fallbackMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    if (!activeTarget) return undefined;
    let isMounted = true;
    let intervalId;

    const poll = async () => {
      try {
        setIsPolling(true);
        const result = await fetchFinalRisk(activeTarget);
        if (isMounted) {
          setRiskData(result);
        }
      } catch (error) {
        console.error('Polling error', error);
      }
    };

    poll();
    intervalId = setInterval(poll, POLL_INTERVAL);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
      setIsPolling(false);
    };
  }, [activeTarget]);

  return (
    <>
      <Head>
        <title>Samurai Oracle Dashboard</title>
      </Head>
  <ParticleBackground />
  <Header />
      <main className="relative mx-auto max-w-6xl space-y-12 px-4 py-12">
        {petals.map((_, index) => (
          <span
            key={index}
            className="sakura-petal"
            style={{
              left: `${(index / petals.length) * 100}%`,
              animationDelay: `${index * 0.8}s`
            }}
          />
        ))}
  <Hero />
        <motion.div
          className="relative overflow-hidden rounded-[28px] border-2 border-emerald-400/60 bg-gradient-to-r from-emerald-950/70 via-purple-900/50 to-black/80 p-6 text-white shadow-[0_18px_40px_rgba(16,185,129,0.35)] backdrop-blur"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <span className="pointer-events-none absolute inset-x-4 top-0 h-1 rounded-full bg-gradient-to-r from-emerald-400 via-rose-400 to-purple-400 opacity-70" />
          <div className="relative flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-500/25 text-2xl">⚠️</span>
              <div>
                <p className="text-xs uppercase tracking-[0.55em] text-emerald-200">Prototype Disclosure</p>
                <h4 className="text-lg font-semibold tracking-wide text-white">Backend under construction · mock verdicts displayed</h4>
              </div>
            </div>
            <span className="rounded-full border border-white/20 px-4 py-1 text-xs uppercase tracking-[0.3em] text-white/70">Demo mode</span>
          </div>
          <p className="relative mt-3 text-sm leading-relaxed text-white/85">
            Prototype Mode: Backend services are still under development. Risk analysis results shown here are mock outputs. Once the backend is complete, it will be integrated with the
            frontend and real analysis will be generated along with evidence. User authentication will also be required before performing any analysis.
          </p>
        </motion.div>
        <motion.section
          id="about"
          className="glass-panel relative overflow-hidden rounded-[32px] border border-white/5 bg-gradient-to-br from-black/60 via-[#130912]/70 to-black/80 p-8"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8 }}
        >
          <div className="pointer-events-none absolute inset-0 opacity-20">
            <div className="absolute -top-10 right-0 h-48 w-48 rounded-full bg-red-500/30 blur-[120px]" />
            <div className="absolute bottom-0 left-0 h-56 w-56 rounded-full bg-indigo-500/20 blur-[100px]" />
          </div>
          <div className="relative space-y-4">
            <p className="text-xs uppercase tracking-[0.5em] text-red-400">About</p>
            <h2 className="text-3xl font-serif text-white md:text-4xl">Forged in vigilance, tempered by AI</h2>
            <p className="text-base text-white/70 md:text-lg">
              Samurai Oracle unifies predictive AI, zero-knowledge proofs, and encrypted relayers into a single risk pipeline. Every verdict
              is etched by validator clans who shadow duel exploit patterns across chains.
            </p>
          </div>
        </motion.section>
        <motion.section
          id="features"
          className="grid gap-6 rounded-[32px] border border-white/5 bg-gradient-to-br from-white/5 via-black/30 to-black/60 p-6 shadow-inner lg:grid-cols-3"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.7 }}
        >
          {[
            {
              title: 'Enqueue Contract',
              description: 'Ship ABI or Solidity for rapid risk inference. Samurai relays orchestrate the payload across validator shards.'
            },
            {
              title: 'AI Consensus Sweep',
              description: 'Predictive models, fuzzers, and on-chain heuristics collaborate to surface vulnerabilities before exploitation.'
            },
            {
              title: 'Verdict & Evidence',
              description: 'Receive finalized scores, oracle attestations, and IPFS dossiers signed by the network council.'
            }
          ].map((item) => (
            <div
              key={item.title}
              className="glass-panel flex flex-col gap-2 rounded-3xl border border-white/10 bg-black/50 p-5"
            >
              <p className="text-xs uppercase tracking-[0.4em] text-white/50">Workflow</p>
              <h4 className="font-serif text-xl text-white">{item.title}</h4>
              <p className="text-sm text-white/60">{item.description}</p>
            </div>
          ))}
        </motion.section>
        <section id="oracle" className="grid gap-8 lg:grid-cols-[1fr_1fr]">
          <WalletConnect address={walletAddress} onConnect={handleConnect} isConnecting={isConnecting} />
          <ContractInputCard
            contractAddress={contractAddress}
            sourceCode={sourceCode}
            onAddressChange={setContractAddress}
            onSourceCodeChange={setSourceCode}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
            statusMessage={statusMessage}
          />
        </section>
        <motion.section
          id="token"
          className="rounded-[32px] border border-white/5 bg-gradient-to-br from-[#12040f]/80 via-black/60 to-black/80 p-8"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.7 }}
        >
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-red-400">Katana Token</p>
              <h3 className="text-3xl font-serif text-white">Liquidity for verdict finality</h3>
              <p className="text-white/70">Staked validators collateralize verdicts and earn oracle routing fees per block.</p>
            </div>
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: 'Staked', value: '68M KTN' },
                { label: 'APY', value: '14.3%' },
                { label: 'Burns', value: '12.2K' }
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-white/10 bg-white/5 p-4 text-center">
                  <p className="text-sm uppercase tracking-[0.2em] text-white/40">{item.label}</p>
                  <p className="text-2xl font-bold text-white">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.section>

        <motion.section
          id="docs"
          className="rounded-[32px] border border-white/5 bg-black/40 p-1"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.7 }}
        >
          <RiskOutputPanel riskData={riskData} isPolling={isPolling} />
        </motion.section>

        <motion.section
          id="contact"
          className="rounded-[32px] border border-white/5 bg-gradient-to-r from-black/70 via-[#14070d]/80 to-black/70 p-8"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.7 }}
        >
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-red-400">Contact</p>
              <h3 className="text-3xl font-serif text-white">Summon the oracle council</h3>
              <p className="text-white/70">Ping us for integrations, validator onboarding, or press briefings.</p>
            </div>
            <div className="flex flex-wrap gap-4">
              <a
                href="mailto:abhay88998@gmail.com"
                className="rounded-full border border-white/10 px-6 py-3 text-sm uppercase tracking-[0.3em] text-white/80 transition hover:border-red-500/70 hover:text-white"
              >
                Email
              </a>
              <a
                href="https://t.me/samurai-oracle"
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-white/10 px-6 py-3 text-sm uppercase tracking-[0.3em] text-white/80 transition hover:border-red-500/70 hover:text-white"
              >
                Telegram
              </a>
            </div>
          </div>
        </motion.section>
      </main>
    </>
  );
}
