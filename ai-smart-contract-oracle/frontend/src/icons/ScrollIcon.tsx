import { SVGProps } from 'react';

export default function ScrollIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M15 12h18a4 4 0 0 1 4 4v18a4 4 0 0 1-4 4H17" />
      <path d="M15 12a4 4 0 0 0-4 4v18a4 4 0 0 0 4 4h2" />
      <path d="M18 20h12" />
      <path d="M18 26h10" />
    </svg>
  );
}
