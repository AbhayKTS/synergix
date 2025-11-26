import { SVGProps } from 'react';

export default function ToriiIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M10 12h28" />
      <path d="M16 18h16" />
      <path d="M14 12 12 6h6l6 6" />
      <path d="M34 12 36 6h-6l-6 6" />
      <path d="M16 18v22" />
      <path d="M32 18v22" />
    </svg>
  );
}
