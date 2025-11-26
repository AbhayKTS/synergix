import { SVGProps } from 'react';

export default function SparkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M24 6 26.5 17.5 38 20 26.5 22.5 24 34 21.5 22.5 10 20l11.5-2.5L24 6z" />
      <circle cx={24} cy={24} r={16} strokeDasharray="4 6" />
    </svg>
  );
}
