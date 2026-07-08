// Adapters for spec §Auth. Register/login persist the JWT on success so
// components only deal with the user object, never the token itself.

import { handleFetch, setToken, clearToken } from './fetch-helpers';

// Both endpoints return { token, user } — store the token, hand back { user, error }.
const authenticate = async (path, body) => {
  const { data, error } = await handleFetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  if (error) return { user: null, error };

  setToken(data.token);
  return { user: data.user, error: null };
};

// role must be 'primary' or 'contact' (backend rejects anything else with 422).
export const register = ({ email, password, fullName, role }) =>
  authenticate('/api/auth/register', { email, password, fullName, role });

export const login = ({ email, password }) =>
  authenticate('/api/auth/login', { email, password });

// Purely client-side: the server doesn't track sessions, so "logging out"
// is just forgetting the token.
export const logout = () => clearToken();
