(function attachClearSpendMatching(root, factory) {
  const matching = factory();
  if (typeof module === 'object' && module.exports) module.exports = matching;
  root.ClearSpendMatching = matching;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  function normalizeIdentityText(value) {
    return String(value || '')
      .normalize('NFKD')
      .toLocaleLowerCase()
      .replace(/[\u0591-\u05c7]/g, '')
      .replace(/[^\p{L}\p{N}]+/gu, ' ')
      .replace(/\b\d+\b/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function displayMatchScore(query, candidate) {
    const wanted = normalizeIdentityText(query);
    const existing = normalizeIdentityText(candidate);
    if (!wanted) return 1;
    if (!existing) return 0;
    if (wanted === existing) return 100;
    if (wanted.includes(existing) || existing.includes(wanted)) {
      return 80 + (Math.min(existing.length, wanted.length) / Math.max(existing.length, wanted.length) * 10);
    }
    const wantedTokens = new Set(wanted.split(' ').filter(Boolean));
    const existingTokens = new Set(existing.split(' ').filter(Boolean));
    const overlap = [...wantedTokens].filter(token => existingTokens.has(token)).length;
    if (!overlap) return 0;
    return overlap / wantedTokens.size * 55 + overlap / existingTokens.size * 25;
  }

  function scoreDisplayIdentity(query, identity) {
    const candidates = [identity.display_name, ...(identity.alias_names || [])];
    return {
      item: identity,
      score: Math.max(...candidates.map(candidate => displayMatchScore(query, candidate))),
    };
  }

  function rankDisplayIdentities(query, identities) {
    return (identities || [])
      .map(identity => scoreDisplayIdentity(query, identity))
      .sort((left, right) => right.score - left.score
        || Number(right.item.transactions || 0) - Number(left.item.transactions || 0));
  }

  function strongDisplayIdentitySuggestion(query, identities) {
    const matches = rankDisplayIdentities(query, identities);
    const best = matches[0];
    const runnerUp = matches[1];
    if (!best || best.score < 80) return null;
    if (runnerUp && best.score - runnerUp.score < 20) return null;
    return best.item;
  }

  return {
    displayMatchScore,
    normalizeIdentityText,
    rankDisplayIdentities,
    scoreDisplayIdentity,
    strongDisplayIdentitySuggestion,
  };
}));
