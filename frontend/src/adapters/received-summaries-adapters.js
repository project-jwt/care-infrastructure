// Adapters for spec §Contact Dashboard (contact only). Requires a valid JWT
// (handleFetch attaches it automatically); the backend rejects primaries
// with 403.

import { handleFetch } from './fetch-helpers';

// Everything that has been sent to the logged-in contact, newest send first:
// [{ summaryId, summaryText, sentAt, from: { id, fullName } }]. The token
// scopes the list — a contact only ever sees what was addressed to them.
export const listReceivedSummaries = () => handleFetch('/api/received-summaries');
