import { SVGProps } from 'react';

export default function CoinIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx={24} cy={24} r={14} />
      <circle cx={24} cy={24} r={9} strokeDasharray="4 3" />
      <path d="M22 19h5l-2 5h3l-5 8 1-6h-3l4-7z" strokeLinejoin="bevel" />
    </svg>
  );
}
