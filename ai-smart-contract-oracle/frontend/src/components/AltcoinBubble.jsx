import React from 'react';

const AltcoinBubble = ({ symbol, color, delay, x, y, scale }) => {
  return (
    <div 
      className="absolute rounded-full flex items-center justify-center backdrop-blur-md border border-white/10 shadow-lg transition-all duration-1000"
      style={{
        width: `${scale * 60}px`,
        height: `${scale * 60}px`,
        backgroundColor: `${color}30`, // Low opacity
        left: `${x}%`,
        top: `${y}%`,
        animation: `float-bubble ${3 + Math.random() * 2}s ease-in-out infinite`,
        animationDelay: `${delay}s`,
        boxShadow: `0 0 15px ${color}40`,
        zIndex: Math.floor(scale * 10)
      }}
    >
      <span className="font-bold text-white drop-shadow-md select-none" style={{ fontSize: `${scale * 0.9}rem` }}>
        {symbol}
      </span>
    </div>
  );
};

export default AltcoinBubble;
