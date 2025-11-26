import { useEffect, useState } from 'react';

interface ScrollSpyOptions {
  rootMargin?: string;
  threshold?: number;
}

export default function useScrollSpy(sectionIds: string[], options: ScrollSpyOptions = {}) {
  const [activeId, setActiveId] = useState(sectionIds[0] ?? '');
  const { rootMargin = '-45% 0px -45% 0px', threshold = 0.2 } = options;
  const idsKey = sectionIds.join('|');

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const sections = sectionIds
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => Boolean(el));

    if (!sections.length) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        });
      },
      {
        rootMargin,
        threshold
      }
    );

    sections.forEach((section) => observer.observe(section));

    return () => {
      sections.forEach((section) => observer.unobserve(section));
      observer.disconnect();
    };
  }, [idsKey, rootMargin, threshold, sectionIds]);

  return activeId;
}
