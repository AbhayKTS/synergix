import { SVGProps } from 'react';

export default function BookIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 10h14a6 6 0 0 1 6 6v22h-16a6 6 0 0 0-6-6V10z" />
      <path d="M32 16a6 6 0 0 1 6 6v16a4 4 0 0 1-4 4h-18" />
      <path d="M18 16h8" />
      <path d="M18 22h6" />
    </svg>
  );
}
