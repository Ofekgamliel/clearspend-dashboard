import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = (relativePath: string) => readFileSync(new URL(relativePath, import.meta.url), 'utf8');

const featureStyles = [
  ['events', '../src/features/events/events.css', '.events-panel-preview'],
  ['transactions', '../src/features/transactions/transactions.css', '.transactions-panel'],
  ['recurring', '../src/features/recurring/recurring.css', '.recurring-panel-preview'],
  ['observations', '../src/features/observations/observations.css', '.observations-panel-preview'],
  ['imports', '../src/features/imports/imports.css', '.import-manager-head'],
  ['merchants', '../src/features/merchants/merchants.css', '.merchant-manager-summary'],
] as const;

test('feature stylesheets are present and imported by the application entry point', () => {
  const entryPoint = source('../src/main.ts');

  for (const [feature, path, representativeSelector] of featureStyles) {
    assert.match(entryPoint, new RegExp(`['"]\\./features/${feature}/${feature}\\.css['"]`));
    assert.ok(source(path).includes(representativeSelector));
  }
});

test('extracted feature selectors do not return to the global stylesheet', () => {
  const globalStyles = source('../src/style.css');
  const featureSelector = /^\s*\.(?:events?|business-trip|transactions?|recurring|observations?|imports?|merchants?)(?:[-_a-zA-Z]|\b)/m;

  assert.doesNotMatch(globalStyles, featureSelector);
});

test('control typography does not mix inherit into a font shorthand', () => {
  const controlStyles = [
    '../src/shared/ui/UiButton.vue',
    '../src/shared/ui/UiInput.vue',
    '../src/shared/ui/UiSelect.vue',
    '../src/features/merchants/merchants.css',
    '../src/features/imports/imports.css',
  ];
  const mixedInheritShorthand = /font\s*:\s*(?!inherit\s*(?:[;}]))[^;}]*\binherit\b/;

  for (const path of controlStyles) assert.doesNotMatch(source(path), mixedInheritShorthand);
});

test('feature-owned presentation consumes semantic theme tokens instead of literal colors', () => {
  const literalColor = /#[0-9a-f]{3,8}\b|rgba?\s*\(/i;
  const themedSources = [
    ...featureStyles.map(([, path]) => path),
    '../src/features/events/EventsPanel.vue',
    '../src/features/observations/model.ts',
    '../src/features/trend/TrendPanel.vue',
  ];

  for (const path of themedSources) assert.doesNotMatch(source(path), literalColor, `${path} contains a fixed UI color`);
});
