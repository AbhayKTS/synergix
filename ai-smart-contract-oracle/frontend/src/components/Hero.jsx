import React from 'react';
import VisualStage from './VisualStage';

const Hero = () => {
  return (
  <section id="home" className="relative w-full min-h-screen flex items-center overflow-hidden bg-[#0d0d0d] text-white">
      {/* Background Elements */}
      <div className="absolute inset-0 z-0">
        {/* Dark gradient base */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-[#1a1a20] via-[#0d0d0d] to-black" />
        
        {/* Red accent glow */}
        <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-red-900/20 to-transparent blur-3xl" />
        
        {/* Fog Animation Layers */}
        <div className="absolute inset-0 opacity-30 pointer-events-none overflow-hidden">
           <div className="absolute top-1/2 left-0 w-[200%] h-64 bg-gradient-to-r from-transparent via-gray-800/20 to-transparent blur-3xl animate-[fog-flow_25s_linear_infinite]" />
           <div className="absolute bottom-0 left-0 w-[200%] h-48 bg-gradient-to-r from-transparent via-gray-700/10 to-transparent blur-2xl animate-[fog-flow_35s_linear_infinite_reverse]" />
        </div>
      </div>

      <div className="container mx-auto px-6 z-10 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center h-full pt-20">
        {/* Left Content */}
        <div className="space-y-8 relative">
          {/* Decorative vertical line */}
          <div className="absolute -left-6 top-0 bottom-0 w-[1px] bg-gradient-to-b from-transparent via-red-600/50 to-transparent hidden lg:block" />

          <div className="inline-flex items-center gap-2 px-4 py-1 border border-red-500/30 rounded-full bg-red-900/10 backdrop-blur-sm">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-red-400 text-xs tracking-[0.2em] uppercase font-semibold">AI-Powered Oracle</span>
          </div>
          
          <h1 className="text-6xl md:text-7xl lg:text-8xl font-bold leading-none tracking-tighter">
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-gray-100 via-gray-300 to-gray-500 drop-shadow-lg">
              THE BLADE
            </span>
            <span className="block text-red-600 drop-shadow-[0_0_25px_rgba(220,38,38,0.6)] font-serif italic">
              OF TRUTH
            </span>
          </h1>
          
          <p className="text-xl text-gray-400 max-w-lg leading-relaxed font-light border-l-2 border-red-600/50 pl-6">
            Severing uncertainty with precision. The first decentralized oracle powered by combat-tested AI models.
          </p>

          <div className="flex flex-wrap gap-6 pt-4">
            <button
              className="group relative px-10 py-4 rounded-full bg-gradient-to-r from-red-700 via-red-600 to-purple-700 text-white font-bold tracking-[0.3em] uppercase overflow-hidden transition-all transform hover:scale-105 shadow-[0_0_30px_rgba(220,38,38,0.45)]"
              onClick={() => {
                if (typeof window === 'undefined') return;
                const target = document.getElementById('oracle');
                target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
            >
              <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-[shimmer_1s_infinite]" />
              <span className="relative z-10 tracking-[0.35em]">GET STARTED</span>
            </button>
          </div>
          
          {/* Glassmorphic Stats Panel */}
          <div className="grid grid-cols-3 gap-6 p-6 rounded-xl bg-[#111116]/60 border border-white/5 backdrop-blur-xl mt-12 shadow-2xl">
            <div className="text-center lg:text-left">
              <div className="text-3xl font-bold text-white font-mono">2.4s</div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">Latency</div>
            </div>
            <div className="text-center lg:text-left border-l border-white/5 pl-6">
              <div className="text-3xl font-bold text-red-500 font-mono">99.9%</div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">Accuracy</div>
            </div>
            <div className="text-center lg:text-left border-l border-white/5 pl-6">
              <div className="text-3xl font-bold text-white font-mono">$4.2B</div>
              <div className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">Secured</div>
            </div>
          </div>
        </div>

        {/* Right Visuals */}
        <div className="relative h-full min-h-[600px] flex items-center justify-center perspective-1000">
           <VisualStage />
        </div>
      </div>
    </section>
  );
};

export default Hero;
