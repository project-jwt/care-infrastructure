// Adapters for spec §Contact Dashboard (contact only). Requires a valid JWT
// (handleFetch attaches it automatically); the backend rejects primaries
// with 403.

import { getBlob, handleFetch } from './fetch-helpers';

// Everything that has been sent to the logged-in contact, newest send first:
// [{ summaryId, summaryText, sentAt, from: { id, fullName }, images: [...] }].
// The token scopes the list — a contact only ever sees what was addressed to
// them. Each image is metadata only; fetch its bytes with the helper below.
export const listReceivedSummaries = () => handleFetch('/api/received-summaries');

// The bytes of one photo on a received summary, as a Blob. Authorized only if
// the summary was sent to this contact (else 404). Caller makes an object URL.
export const getReceivedSummaryImageBlob = (summaryId, imageId) =>
  getBlob(`/api/received-summaries/${summaryId}/images/${imageId}/raw`);
