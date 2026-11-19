export const THEME_STORAGE_KEY = 'clearspend-color-theme';
export const THEME_STORAGE_VERSION = 1;
export const DEFAULT_THEME_ID = 'current';

export const themes = [
  { id: 'current', name: 'Current violet', description: 'The ClearSpend baseline', scheme: 'light', colors: ['#6658e8', '#41b98c', '#e6a14b'] },
  { id: 'clay', name: 'Clay & sky', description: 'Warm with cool contrast', scheme: 'light', colors: ['#9f402c', '#33788d', '#ad681c'] },
  { id: 'plum', name: 'Plum & apricot', description: 'Expressive and personal', scheme: 'light', colors: ['#733f73', '#b96243', '#a87217'] },
  { id: 'rose', name: 'Rose & gold', description: 'Warm personal finance', scheme: 'light', colors: ['#963650', '#9e6d17', '#537da6'] },
  { id: 'graphite', name: 'Graphite & amber', description: 'Restrained dark mode', scheme: 'dark', colors: ['#e0a53b', '#6ac1a2', '#e67755'] },
  { id: 'navy', name: 'Navy & coral', description: 'Bold dark contrast', scheme: 'dark', colors: ['#ff806c', '#5ed2b1', '#f2c75b'] },
  { id: 'steel', name: 'Steel & electric', description: 'Technical high contrast', scheme: 'dark', colors: ['#67a8ff', '#65d0c0', '#f0bd63'] },
  { id: 'ruby', name: 'Ruby night', description: 'Confident dark color', scheme: 'dark', colors: ['#ff6f91', '#74c7ec', '#f2c45e'] },
] as const;

export type ThemeId = typeof themes[number]['id'];
export type ThemeScheme = typeof themes[number]['scheme'];
export type ThemeDefinition = typeof themes[number];

interface StoredThemePreference {
  version: typeof THEME_STORAGE_VERSION;
  theme: ThemeId;
}

type ThemeStorageReader = Pick<Storage, 'getItem'>;
type ThemeStorageWriter = Pick<Storage, 'setItem'>;
type ThemeRoot = Pick<HTMLElement, 'dataset' | 'style'>;

export function isThemeId(value: unknown): value is ThemeId {
  return typeof value === 'string' && themes.some((theme) => theme.id === value);
}

export function themeDefinition(theme: ThemeId): ThemeDefinition {
  return themes.find((candidate) => candidate.id === theme) ?? themes[0];
}

function decodeStoredTheme(value: string | null): ThemeId {
  if (!value) return DEFAULT_THEME_ID;
  if (isThemeId(value)) return value;
  try {
    const candidate = JSON.parse(value) as Partial<StoredThemePreference> | null;
    return candidate?.version === THEME_STORAGE_VERSION && isThemeId(candidate.theme)
      ? candidate.theme
      : DEFAULT_THEME_ID;
  } catch {
    return DEFAULT_THEME_ID;
  }
}

export function readStoredTheme(
  storage: ThemeStorageReader | null = typeof localStorage === 'undefined' ? null : localStorage,
): ThemeId {
  if (!storage) return DEFAULT_THEME_ID;
  try { return decodeStoredTheme(storage.getItem(THEME_STORAGE_KEY)); }
  catch { return DEFAULT_THEME_ID; }
}

export function applyTheme(
  theme: ThemeId,
  root: ThemeRoot = document.documentElement,
): void {
  const definition = themeDefinition(theme);
  root.dataset.clearspendTheme = definition.id;
  root.style.colorScheme = definition.scheme;
}

export function storeTheme(
  theme: ThemeId,
  storage: ThemeStorageWriter | null = typeof localStorage === 'undefined' ? null : localStorage,
): void {
  if (!storage) return;
  const preference: StoredThemePreference = { version: THEME_STORAGE_VERSION, theme };
  try { storage.setItem(THEME_STORAGE_KEY, JSON.stringify(preference)); }
  catch { /* Keep the in-memory preference. */ }
}
