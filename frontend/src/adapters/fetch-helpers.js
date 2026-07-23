// Shared fetch wrapper — every adapter goes through handleFetch so JWT
// injection and error shaping live in exactly one place.

const TOKEN_KEY = 'token';

// The only functions allowed to touch localStorage for the JWT.
// Components never read/write the token directly — they go through adapters.
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

// Returns { data, error } so callers never need try/catch.
// Exactly one of the two is non-null.
//   data  -> parsed JSON body on 2xx (null for empty bodies)
//   error -> { status, message } on non-2xx or network failure
export const handleFetch = async (url, options = {}) => {
  const headers = { ...options.headers };

  // Backend routes behind get_current_user expect: Authorization: Bearer <jwt>
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  // Only JSON bodies in this app; header only set when a body exists.
  if (options.body) headers['Content-Type'] = 'application/json';

  try {
    const response = await fetch(url, { ...options, headers });

    // Parse separately from the fetch: a non-JSON body (e.g. a plain-text
    // 500 from a proxy) must not be mistaken for a network failure — the
    // real HTTP status is preserved either way. Empty bodies parse to null.
    let body = null;
    try {
      const text = await response.text();
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }

    if (!response.ok) {
      // server/main.py shapes every error as { message }.
      return {
        data: null,
        error: { status: response.status, message: body?.message || 'Something went wrong' },
      };
    }

    return { data: body, error: null };
  } catch {
    // fetch only throws on network problems (server down, no connection).
    return { data: null, error: { status: 0, message: 'Could not reach the server' } };
  }
};

// Fetches a binary body (an image's bytes) with the JWT attached, returning
// { data: Blob, error }. Images live behind auth, so an <img src> to the
// endpoint would 401 — callers turn the Blob into an object URL instead.
export const getBlob = async (url) => {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const response = await fetch(url, { headers });
    if (!response.ok) {
      return { data: null, error: { status: response.status, message: 'Could not load image' } };
    }
    return { data: await response.blob(), error: null };
  } catch {
    return { data: null, error: { status: 0, message: 'Could not reach the server' } };
  }
};
