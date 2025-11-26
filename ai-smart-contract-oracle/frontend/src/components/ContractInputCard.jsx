import { useRef } from 'react';
import { motion } from 'framer-motion';
import { FileCode2, SendHorizonal } from 'lucide-react';

export default function ContractInputCard({
  contractAddress,
  sourceCode,
  onAddressChange,
  onSourceCodeChange,
  onSubmit,
  isSubmitting,
  statusMessage
}) {
  const fileInputRef = useRef(null);

  const handleFileUpload = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      onSourceCodeChange(e.target.result.toString());
    };
    reader.readAsText(file);
  };

  return (
    <motion.div
      className="glass-panel rounded-3xl border border-white/10 bg-gradient-to-br from-black/50 via-[#111116]/60 to-black/80 p-6"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.6 }}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs tracking-[0.5em] text-white/50">CONTRACT ANALYZER</p>
          <h3 className="font-serif text-2xl text-white">Summon the Oracle</h3>
        </div>
        <div className="crypto-sigil flex h-12 w-12 items-center justify-center border border-white/10 text-white/70">
          <FileCode2 />
        </div>
      </div>
      <div className="katana-divider" />
      <form
        className="space-y-5"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="space-y-2">
          <label className="text-sm uppercase tracking-[0.4em] text-white/60">Contract Address</label>
          <input
            type="text"
            required
            value={contractAddress}
            onChange={(event) => onAddressChange(event.target.value)}
            placeholder="0x…"
            className="w-full rounded-2xl border border-white/10 bg-black/40 px-4 py-3 text-white outline-none transition focus:border-katana"
          />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <textarea
            value={sourceCode}
            onChange={(event) => onSourceCodeChange(event.target.value)}
            placeholder="Optional Solidity source code"
            className="h-44 w-full rounded-2xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white/90 outline-none transition focus:border-neon"
          />
          <div className="flex flex-col gap-3 rounded-2xl border border-dashed border-white/20 bg-black/20 p-4 text-sm text-white/70">
            <p>Upload a .sol contract to auto-populate the oracle payload. Source remains local—no server storage.</p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.4em] text-white/80 hover:border-neon"
            >
              Choose File
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".sol,.txt"
              onChange={handleFileUpload}
              className="hidden"
            />
          </div>
        </div>
        <motion.button
          type="submit"
          whileTap={{ scale: 0.98 }}
          className="group flex w-full items-center justify-center gap-3 rounded-full border border-white/10 bg-gradient-to-r from-katana to-neon px-6 py-4 text-lg font-semibold text-white shadow-neon-ring"
          disabled={isSubmitting}
        >
          <span>{isSubmitting ? 'Dispatching...' : 'Analyze Smart Contract → Summon Oracle'}</span>
          <SendHorizonal className="transition group-hover:translate-x-1" />
        </motion.button>
      </form>
      {statusMessage && (
        <p className="mt-4 rounded-2xl border border-white/10 bg-black/60 px-4 py-3 text-sm text-white/70">{statusMessage}</p>
      )}
    </motion.div>
  );
}
