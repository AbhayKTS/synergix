import { useEffect, useRef } from 'react';

const PETAL_COUNT = 12;

export default function ParticleBackground() {
  const canvasRef = useRef(null);
  const petals = useRef([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrame;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const resetPetal = (petal) => {
      petal.x = Math.random() * canvas.width;
      petal.y = -10;
  petal.size = 4 + Math.random() * 6;
  petal.speed = 0.6 + Math.random() * 1.1;
  petal.swing = Math.random() * 1.6;
    };

    petals.current = Array.from({ length: PETAL_COUNT }).map(() => {
      const petal = {};
      resetPetal(petal);
      petal.y = Math.random() * canvas.height;
      return petal;
    });

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      petals.current.forEach((petal) => {
        petal.y += petal.speed;
        petal.x += Math.sin(petal.y * 0.01) * petal.swing;
        if (petal.y > canvas.height + 10) {
          resetPetal(petal);
        }
  const gradient = ctx.createRadialGradient(petal.x, petal.y, petal.size * 0.12, petal.x, petal.y, petal.size);
  gradient.addColorStop(0, 'rgba(233,233,233,0.65)');
  gradient.addColorStop(1, 'rgba(234,46,73,0.12)');
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.ellipse(petal.x, petal.y, petal.size, petal.size * 0.7, Math.PI / 4, 0, Math.PI * 2);
        ctx.fill();
      });
      animationFrame = requestAnimationFrame(render);
    };

    resize();
    render();
    window.addEventListener('resize', resize);
    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
  className="pointer-events-none fixed inset-0 -z-10 opacity-35"
      aria-hidden
    />
  );
}
