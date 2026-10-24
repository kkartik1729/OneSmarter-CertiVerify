import { useState } from 'react';
export type Theme = 'dark' | 'light';
const KEY = 'cv-theme'; // only a UI preference is stored
export const initTheme = () => {
  let t: Theme = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') {
      t = saved;
    }
  } catch {
    /* storage unavailable */
  }
  document.documentElement.dataset.theme = t;
  if (t === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
};

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains('dark') || document.documentElement.dataset.theme === 'dark'
      ? 'dark'
      : 'light'
  );

  const toggle = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    if (next === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* ignore */
    }
    setTheme(next);
  };

  return { theme, toggle };
}
