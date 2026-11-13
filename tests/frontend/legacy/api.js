(function attachClearSpendApi(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.ClearSpendApi = api;
}(typeof globalThis !== 'undefined' ? globalThis : window, () => {
  class ApiError extends Error {
    constructor(message, { status = 0, payload = null, url = '' } = {}) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.payload = payload;
      this.url = url;
    }
  }

  async function requestJson(url, options = {}, fallbackMessage = 'Could not load local data') {
    const response = await fetch(url, options);
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new ApiError(fallbackMessage, { status: response.status, url });
    }
    if (!response.ok) {
      throw new ApiError(payload?.error || fallbackMessage, {
        status: response.status,
        payload,
        url,
      });
    }
    return payload;
  }

  function getJson(url, fallbackMessage) {
    return requestJson(url, { cache: 'no-store' }, fallbackMessage);
  }

  function postJson(url, body, fallbackMessage) {
    return requestJson(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }, fallbackMessage);
  }

  function postForm(url, body, fallbackMessage) {
    return requestJson(url, { method: 'POST', body }, fallbackMessage);
  }

  return { ApiError, getJson, postJson, postForm, requestJson };
}));
