import assert from 'node:assert/strict';
import test from 'node:test';
import { applyTheme, isThemeId, readStoredTheme, storeTheme, THEME_STORAGE_KEY, themes } from '../src/features/theme/theme.ts';

test('theme catalogue has unique supported ids', () => {
  assert.equal(themes.length, 12);
  assert.equal(new Set(themes.map((theme) => theme.id)).size, themes.length);
  assert.ok(themes.every((theme) => theme.colors.length === 3));
  assert.equal(isThemeId('midnight'), true);
  assert.equal(isThemeId('unknown'), false);
});

test('theme preference falls back safely and applies to the root dataset', () => {
  assert.equal(readStoredTheme({ getItem: () => 'forest' }), 'forest');
  assert.equal(readStoredTheme({ getItem: () => 'not-a-theme' }), 'current');
  assert.equal(readStoredTheme({ getItem: () => { throw new Error('blocked'); } }), 'current');

  const root = { dataset: {} as DOMStringMap };
  applyTheme('navy', root);
  assert.equal(root.dataset.clearspendTheme, 'navy');
});

test('theme preference is stored under the stable browser key', () => {
  let stored: [string, string] | undefined;
  storeTheme('sand', { setItem: (key, value) => { stored = [key, value]; } });
  assert.deepEqual(stored, [THEME_STORAGE_KEY, 'sand']);
  assert.doesNotThrow(() => storeTheme('sand', { setItem: () => { throw new Error('blocked'); } }));
});
