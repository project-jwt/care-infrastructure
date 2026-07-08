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

    // 204s and empty bodies have nothing to parse.
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;

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
