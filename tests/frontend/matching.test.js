const test = require('node:test');
const assert = require('node:assert/strict');

const {
  displayMatchScore,
  normalizeIdentityText,
  rankDisplayIdentities,
  strongDisplayIdentitySuggestion,
} = require('../../dist/matching.js');

const identity = (displayName, transactions, aliases = []) => ({
  display_name: displayName,
  transactions,
  alias_names: aliases,
});

test('normalizes punctuation, Hebrew marks, case, and standalone branch numbers', () => {
  assert.equal(normalizeIdentityText('  SUPER-PHARM 147 '), 'super pharm');
  assert.equal(normalizeIdentityText('חָנוּת-147'), 'חנות');
});

test('preserves the existing exact, containment, token-overlap, and no-match scores', () => {
  assert.equal(displayMatchScore('Alpha Market', 'alpha market'), 100);
  assert.ok(displayMatchScore('Alpha Market Branch', 'Alpha Market') >= 80);
  assert.ok(displayMatchScore('Alpha Coffee Market', 'Alpha Market Place') > 0);
  assert.equal(displayMatchScore('Alpha', 'Beta'), 0);
});

test('scores aliases as well as the canonical display name', () => {
  const matches = rankDisplayIdentities('Corner Shop Branch', [
    identity('Unrelated', 40, ['Corner Shop']),
    identity('Corner Cafe', 50),
  ]);
  assert.equal(matches[0].item.display_name, 'Unrelated');
  assert.ok(matches[0].score >= 80);
});

test('uses transaction count only as a tie breaker', () => {
  const matches = rankDisplayIdentities('Same Name', [
    identity('Same Name', 2),
    identity('Same Name', 20),
  ]);
  assert.equal(matches[0].item.transactions, 20);
});

test('suggests only a strong and unambiguous identity', () => {
  const strong = identity('Corner Shop', 20);
  assert.equal(strongDisplayIdentitySuggestion('Corner Shop 147', [strong, identity('Other', 100)]), strong);
  assert.equal(strongDisplayIdentitySuggestion('Corner Shop', [strong, identity('Corner Shop', 5)]), null);
  assert.equal(strongDisplayIdentitySuggestion('Unknown Merchant', [strong]), null);
});
