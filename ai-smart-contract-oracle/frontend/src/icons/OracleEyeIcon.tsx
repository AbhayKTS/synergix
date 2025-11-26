import { SVGProps } from 'react';

export default function OracleEyeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M6 24s8-12 18-12 18 12 18 12-8 12-18 12S6 24 6 24z" />
      <circle cx={24} cy={24} r={5} />
      <path d="M24 13v-6" />
      <path d="m18 14-3-5" />
      <path d="m30 14 3-5" />
    </svg>
  );
}
