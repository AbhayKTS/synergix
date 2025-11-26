import { CSSProperties, useMemo, useState } from 'react';
import clsx from 'clsx';
import NavItem from './NavItem';
import useScrollSpy from '@/hooks/useScrollSpy';
import {
  ToriiIcon,
  ScrollIcon,
  SparkIcon,
  OracleEyeIcon,
  CoinIcon,
  BookIcon,
  KatanaMailIcon
} from '@/icons';

const links = [
  { id: 'home', label: 'Home', icon: ToriiIcon },
  { id: 'about', label: 'About', icon: ScrollIcon },
  { id: 'features', label: 'Features', icon: SparkIcon },
  { id: 'oracle', label: 'Oracle Engine', icon: OracleEyeIcon },
  { id: 'token', label: 'Token', icon: CoinIcon },
  { id: 'docs', label: 'Documentation', icon: BookIcon },
  { id: 'contact', label: 'Contact', icon: KatanaMailIcon }
];

export default function Header() {
  const sectionIds = useMemo(() => links.map((link) => link.id), []);
  const activeId = useScrollSpy(sectionIds, { rootMargin: '-45% 0px -45% 0px' });
  const emberSeeds = useMemo(
    () =>
      Array.from({ length: 12 }, (_, index) => ({
        delay: index * 0.75,
        x: Math.random()
      })),
    []
  );
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleToggle = () => setMobileOpen((prev) => !prev);
  const handleNavigate = () => setMobileOpen(false);

  return (
    <header className="nav-header" aria-label="Primary navigation">
      <div className="nav-fog" aria-hidden />
      <div className="nav-fog nav-fog--reverse" aria-hidden />
      {emberSeeds.map((seed, index) => (
        <span
          key={`ember-${index}`}
          className="nav-ember"
          aria-hidden
          style={{ animationDelay: `${seed.delay}s`, '--rand-x': seed.x.toString() } as CSSProperties}
        />
      ))}
      <div className="mx-auto flex w-full max-w-screen-xl items-center justify-between gap-6 px-4 py-3 lg:px-8 lg:py-4">
        <div className="flex flex-1 items-center gap-4 text-white">
          <div className="leading-tight">
            <p className="text-[11px] uppercase tracking-[0.65em] text-white/60 md:text-[12px]">Oracle Path</p>
            <p className="text-xl font-semibold tracking-[0.08em] md:text-2xl">Samurai Network</p>
          </div>
          <span className="hidden h-px flex-1 rounded-full bg-gradient-to-r from-white/20 via-white/10 to-transparent md:block" aria-hidden />
        </div>

        <nav className="hidden flex-shrink-0 items-center justify-end gap-6 md:flex">
          {links.map(({ id, label, icon: Icon }) => (
            <NavItem
              key={id}
              icon={<Icon className="h-5 w-5" />}
              label={label}
              target={`#${id}`}
              isActive={activeId === id}
            />
          ))}
        </nav>

        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.3em] text-white/70 transition hover:border-red-500/50 hover:text-white md:hidden"
          onClick={handleToggle}
          aria-expanded={mobileOpen}
          aria-controls="samurai-mobile-nav"
        >
          Menu
          <span className="relative h-4 w-4">
            <span className={clsx('absolute inset-x-0 top-0 h-0.5 bg-white transition', mobileOpen ? 'translate-y-2 rotate-45' : '')} />
            <span className={clsx('absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 bg-white transition', mobileOpen ? 'opacity-0' : 'opacity-70')} />
            <span className={clsx('absolute inset-x-0 bottom-0 h-0.5 bg-white transition', mobileOpen ? '-translate-y-2 -rotate-45' : '')} />
          </span>
        </button>
      </div>

      <div
        id="samurai-mobile-nav"
        className={clsx(
          'nav-mobile-panel md:hidden',
          mobileOpen ? 'pointer-events-auto translate-y-0 opacity-100' : 'pointer-events-none -translate-y-3 opacity-0'
        )}
      >
        {links.map(({ id, label, icon: Icon }) => (
          <NavItem
            key={`mobile-${id}`}
            icon={<Icon className="h-5 w-5" />}
            label={label}
            target={`#${id}`}
            isActive={activeId === id}
            onNavigate={handleNavigate}
            compact
          />
        ))}
      </div>
    </header>
  );
}
