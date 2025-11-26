import React from 'react';
import Image from 'next/image';

const SpinningCoin = () => {
  return (
    <div className="relative w-64 h-64 perspective-1000">
      <div className="w-full h-full relative preserve-3d animate-[coin-spin_10s_linear_infinite]">
        {/* Front Face */}
        <div className="absolute inset-0 backface-hidden rounded-full overflow-hidden border-4 border-yellow-600 shadow-[0_0_50px_rgba(234,179,8,0.4)] bg-black">
          <Image 
            src="/images/samurai-coin.jpg" 
            alt="Samurai Coin Front" 
            fill
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/20 to-transparent opacity-50" />
        </div>
        {/* Back Face */}
        <div className="absolute inset-0 backface-hidden rounded-full overflow-hidden border-4 border-yellow-600 shadow-[0_0_50px_rgba(234,179,8,0.4)] bg-black" style={{ transform: 'rotateY(180deg)' }}>
          <Image 
            src="/images/samurai-coin.jpg" 
            alt="Samurai Coin Back" 
            fill
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/20 to-transparent opacity-50" />
        </div>
      </div>
    </div>
  );
};

export default SpinningCoin;
