export const THEME_STORAGE_KEY = 'clearspend-color-theme';

export const themes = [
  { id: 'current', name: 'Current violet', description: 'The ClearSpend baseline', colors: ['#6658e8', '#41b98c', '#e6a14b'] },
  { id: 'forest', name: 'Forest & lime', description: 'Natural and reassuring', colors: ['#2c654d', '#7da96d', '#d9944d'] },
  { id: 'midnight', name: 'Midnight & aqua', description: 'Focused dark cockpit', colors: ['#56e3ba', '#f5de58', '#ff8d64'] },
  { id: 'clay', name: 'Clay & sky', description: 'Warm with cool contrast', colors: ['#ad4b35', '#3f8ba2', '#e5a04b'] },
  { id: 'plum', name: 'Plum & apricot', description: 'Expressive and personal', colors: ['#733f73', '#d78362', '#e4a84e'] },
  { id: 'ocean', name: 'Ocean & mint', description: 'Clean and refreshing', colors: ['#087f8c', '#38a376', '#ee9669'] },
  { id: 'rose', name: 'Rose & gold', description: 'Warm personal finance', colors: ['#a33f5d', '#c18a2d', '#6e9bc8'] },
  { id: 'cobalt', name: 'Cobalt & lemon', description: 'Crisp and energetic', colors: ['#285ed1', '#2b9973', '#db9b24'] },
  { id: 'sage', name: 'Sage & terracotta', description: 'Muted and grounded', colors: ['#64765a', '#b76445', '#c49844'] },
  { id: 'graphite', name: 'Graphite & amber', description: 'Restrained dark mode', colors: ['#e0a53b', '#6ac1a2', '#e67755'] },
  { id: 'navy', name: 'Navy & coral', description: 'Bold dark contrast', colors: ['#ff806c', '#5ed2b1', '#f2c75b'] },
  { id: 'sand', name: 'Sand & teal', description: 'Soft Mediterranean warmth', colors: ['#147d78', '#678b4f', '#d18149'] },
] as const;

export type ThemeId = typeof themes[number]['id'];

export function isThemeId(value: string | null): value is ThemeId {
  return themes.some((theme) => theme.id === value);
}

export function readStoredTheme(storage: Pick<Storage, 'getItem'> | null = typeof localStorage === 'undefined' ? null : localStorage): ThemeId {
  if (!storage) return 'current';
  try {
    const stored = storage.getItem(THEME_STORAGE_KEY);
    return isThemeId(stored) ? stored : 'current';
  } catch {
    return 'current';
  }
}

export function applyTheme(theme: ThemeId, root: Pick<HTMLElement, 'dataset'> = document.documentElement): void {
  root.dataset.clearspendTheme = theme;
}

export function storeTheme(theme: ThemeId, storage: Pick<Storage, 'setItem'> | null = typeof localStorage === 'undefined' ? null : localStorage): void {
  if (!storage) return;
  try { storage.setItem(THEME_STORAGE_KEY, theme); } catch { /* Keep the in-memory preference. */ }
}
