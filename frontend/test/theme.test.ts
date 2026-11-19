import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  applyTheme,
  DEFAULT_THEME_ID,
  isThemeId,
  readStoredTheme,
  storeTheme,
  THEME_STORAGE_KEY,
  themes,
} from '../src/features/theme/theme.ts';

test('theme registry has stable unique identifiers and light or dark schemes', () => {
  assert.equal(new Set(themes.map((theme) => theme.id)).size, themes.length);
  assert.ok(themes.some((theme) => theme.scheme === 'light'));
  assert.ok(themes.some((theme) => theme.scheme === 'dark'));
  for (const theme of themes) {
    assert.equal(isThemeId(theme.id), true);
    assert.equal(theme.colors.length, 3);
  }
});

test('stored theme preference supports versioned and legacy values', () => {
  assert.equal(readStoredTheme({ getItem: () => JSON.stringify({ version: 1, theme: 'graphite' }) }), 'graphite');
  assert.equal(readStoredTheme({ getItem: () => 'plum' }), 'plum');
  assert.equal(readStoredTheme({ getItem: () => 'forest' }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => 'midnight' }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => 'espresso' }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => JSON.stringify({ version: 1, theme: 'sand' }) }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => JSON.stringify({ version: 99, theme: 'graphite' }) }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => 'removed-theme' }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => '{not-json' }), DEFAULT_THEME_ID);
  assert.equal(readStoredTheme({ getItem: () => { throw new Error('unavailable'); } }), DEFAULT_THEME_ID);
});

test('storing a theme writes the versioned preference and tolerates failures', () => {
  let storedKey = '';
  let storedValue = '';
  storeTheme('navy', { setItem: (key, value) => { storedKey = key; storedValue = value; } });
  assert.equal(storedKey, THEME_STORAGE_KEY);
  assert.deepEqual(JSON.parse(storedValue), { version: 1, theme: 'navy' });
  assert.doesNotThrow(() => storeTheme('current', { setItem: () => { throw new Error('unavailable'); } }));
});

test('applying a theme updates both its root identifier and native color scheme', () => {
  const root = { dataset: {}, style: { colorScheme: '' } } as unknown as Pick<HTMLElement, 'dataset' | 'style'>;
  applyTheme('graphite', root);
  assert.equal(root.dataset.clearspendTheme, 'graphite');
  assert.equal(root.style.colorScheme, 'dark');
  applyTheme('clay', root);
  assert.equal(root.style.colorScheme, 'light');
});

test('every registered non-default palette defines the complete foundation contract', () => {
  const css = readFileSync(new URL('../src/shared/theme/palettes.css', import.meta.url), 'utf8');
  const foundation = readFileSync(new URL('../src/shared/theme/tokens.css', import.meta.url), 'utf8');
  const required = [...foundation.matchAll(/^\s*(--theme-[a-z0-9-]+):/gm)].map((match) => match[1]);
  assert.ok(required.length > 20);

  for (const theme of themes.filter((candidate) => candidate.id !== DEFAULT_THEME_ID)) {
    const start = css.indexOf(`:root[data-clearspend-theme="${theme.id}"]`);
    assert.notEqual(start, -1, `missing ${theme.id} palette`);
    const block = css.slice(start, css.indexOf('}', start) + 1);
    assert.match(block, new RegExp(`color-scheme:\\s*${theme.scheme}`));
    for (const token of required) assert.ok(block.includes(`${token}:`), `${theme.id} is missing ${token}`);
  }
});

test('the pre-render bootstrap recognizes every registered theme and both schemes', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  assert.match(html, /<meta name="color-scheme" content="light dark">/);
  for (const theme of themes) assert.ok(html.includes(`'${theme.id}'`), `bootstrap is missing ${theme.id}`);
  for (const theme of themes.filter((candidate) => candidate.scheme === 'dark')) {
    assert.ok(html.includes(`'${theme.id}'`), `bootstrap dark scheme is missing ${theme.id}`);
  }
});
