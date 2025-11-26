import React from 'react';
import SpinningCoin from './SpinningCoin';
import AltcoinBubble from './AltcoinBubble';

const VisualStage = () => {
  // Bubbles positioned to not overlap with the center coin
  const bubbles = [
    { symbol: 'ETH', color: '#627EEA', x: 10, y: 20, scale: 1.2, delay: 0 },
    { symbol: 'BTC', color: '#F7931A', x: 85, y: 15, scale: 1.0, delay: 1 },
    { symbol: 'SOL', color: '#14F195', x: 5, y: 70, scale: 0.9, delay: 2 },
    { symbol: 'LINK', color: '#2A5ADA', x: 80, y: 65, scale: 1.1, delay: 0.5 },
    { symbol: 'DOT', color: '#E6007A', x: 45, y: 85, scale: 0.8, delay: 1.5 },
    { symbol: 'AVAX', color: '#E84142', x: 50, y: 5, scale: 0.7, delay: 2.5 },
  ];

  return (
    <div className="relative w-full h-[600px] flex items-center justify-center overflow-visible">
      {/* Glow behind coin */}
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-red-600/20 rounded-full blur-[100px]" />
      
      {/* Coin */}
      <div className="z-20 transform scale-125 hover:scale-135 transition-transform duration-500">
        <SpinningCoin />
      </div>

      {/* Bubbles */}
      {bubbles.map((b, i) => (
        <AltcoinBubble key={i} {...b} />
      ))}
      
      {/* Embers overlay */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
         {[...Array(15)].map((_, i) => (
           <div 
             key={i}
             className="absolute w-1 h-1 bg-orange-500 rounded-full blur-[1px]"
             style={{
               left: `${Math.random() * 100}%`,
               animation: `ember-rise ${3 + Math.random() * 4}s linear infinite`,
               animationDelay: `${Math.random() * 5}s`,
               opacity: 0
             }}
           />
         ))}
      </div>
    </div>
  );
};

export default VisualStage;
