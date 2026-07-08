// Adapters for spec §Account. All three require a valid JWT
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
