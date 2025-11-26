import React from 'react';
import clsx from 'clsx';

type NavItemProps = {
  icon: React.ReactNode;
  label: string;
  target: string;
  isActive?: boolean;
  onNavigate?: () => void;
  compact?: boolean;
};

export default function NavItem({ icon, label, target, isActive = false, onNavigate, compact = false }: NavItemProps) {
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const id = target.replace('#', '');
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    onNavigate?.();
  };

  return (
    <a
      href={target}
      onClick={handleClick}
      className={clsx(
        'nav-item relative flex items-center overflow-hidden rounded-2xl px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/80',
        compact ? 'w-full gap-3 justify-start px-3 py-2 text-[11px]' : 'gap-2 text-sm',
        isActive ? 'nav-item-active' : 'nav-item-inactive'
      )}
      aria-label={label}
      aria-current={isActive ? 'true' : undefined}
    >
      <span className="nav-item-icon flex h-5 w-5 items-center justify-center" aria-hidden>
        {icon}
      </span>
      <span
        className={clsx(
          'nav-item-label transition-colors duration-300',
          compact ? 'flex-1 text-left tracking-[0.3em] text-white/80' : 'block'
        )}
      >
        {label}
      </span>
    </a>
  );
}
