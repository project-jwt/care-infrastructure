// Adapters for spec §Account. All require a valid JWT
// (handleFetch attaches it automatically).

import { handleFetch } from './fetch-helpers';

// Who am I? App.jsx calls this on mount to restore the session from a stored token.
export const getMe = () => handleFetch('/api/users/me');

// fields: any of { fullName, email, password } — only the ones sent get updated.
export const updateMe = (fields) =>
  handleFetch('/api/users/me', { method: 'PATCH', body: JSON.stringify(fields) });

// Flips hasCompletedSetup to true (used by the SetupTutorial ticket).
export const markSetupComplete = () =>
  handleFetch('/api/users/me/setup', { method: 'PATCH' });

// Permanently deletes the account. `password` is re-supplied as confirmation
// (the backend re-checks it and 403s on mismatch). On success the account and,
// via DB cascade, its summaries and contact links are gone; the caller should
// then clear the token and return to the logged-out screen. Returns 204 (no
// body), so data is null on success.
export const deleteMe = (password) =>
  handleFetch('/api/users/me', {
    method: 'DELETE',
    body: JSON.stringify({ password }),
  });
