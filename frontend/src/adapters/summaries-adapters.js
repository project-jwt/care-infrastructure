// Adapters for spec §Summaries (primary only). All require a valid JWT
// (handleFetch attaches it automatically); the backend rejects contacts
// with 403.

import { getBlob, getToken, handleFetch } from './fetch-helpers';

// Uploads a recorded audio clip to be transcribed server-side (Deepgram),
// for browsers without a working Web Speech API (iOS). Returns
// { data: { transcript }, error }. Not routed through handleFetch because
// that helper is JSON-only — audio is multipart/form-data, and the browser
// must set the Content-Type (with its boundary) itself, so we don't set it.
export const transcribeAudio = async (blob) => {
  const form = new FormData();
  // Filename + type help the backend/Deepgram detect the audio format.
  const ext = (blob.type.split('/')[1] || 'webm').split(';')[0];
  form.append('audio', blob, `recording.${ext}`);

  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  try {
    const response = await fetch('/api/summaries/transcribe', {
      method: 'POST',
      headers,
      body: form,
    });
    let body = null;
    try {
      const text = await response.text();
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    if (!response.ok) {
      return {
        data: null,
        error: { status: response.status, message: body?.message || 'Something went wrong' },
      };
    }
    return { data: body, error: null };
  } catch {
    return { data: null, error: { status: 0, message: 'Could not reach the server' } };
  }
};

// Runs the transcript (plus any answers to earlier clarifying questions)
// through the AI. Returns either { needsClarification: true, questions }
// or { needsClarification: false, summaryText }. Saves nothing.
export const draftSummary = ({ transcript, answers = [] }) =>
  handleFetch('/api/summaries/draft', {
    method: 'POST',
    body: JSON.stringify({ transcript, answers }),
  });

// Saves a finalized summary. transcript is optional per the contract.
export const saveSummary = ({ transcript, summaryText }) =>
  handleFetch('/api/summaries', {
    method: 'POST',
    body: JSON.stringify({ transcript, summaryText }),
  });

// All of the current user's summaries, newest first (no transcripts — the
// list shape stays light).
export const listSummaries = () => handleFetch('/api/summaries');

// One summary, transcript included.
export const getSummary = (id) => handleFetch(`/api/summaries/${id}`);

// Edits the summary text, before or after it has been sent.
export const updateSummary = (id, summaryText) =>
  handleFetch(`/api/summaries/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ summaryText }),
  });

export const deleteSummary = (id) =>
  handleFetch(`/api/summaries/${id}`, { method: 'DELETE' });

// Who this summary was sent to, oldest send first (the sender's receipt):
// [{ contactId, fullName, sentAt }]. A recipient who deleted their account
// comes back with contactId/fullName null (render as "Deleted user"). 404 if
// the summary isn't the caller's; [] if it was never sent.
export const getSummaryRecipients = (id) =>
  handleFetch(`/api/summaries/${id}/recipients`);

// Emails the summary to trusted contacts and records each send. Returns
// { summaryId, sentTo: [{ contactId, sentAt }] }. Errors: 404 summary not
// found (or not the caller's), 403 a contactId is not a trusted contact,
// 502 the email service failed (nothing recorded), 422 empty contactIds.
export const sendSummary = (id, contactIds) =>
  handleFetch(`/api/summaries/${id}/send`, {
    method: 'POST',
    body: JSON.stringify({ contactIds }),
  });

// ── Image attachments ─────────────────────────────────────────────────────

// A summary's photos as metadata (no bytes), oldest first:
// [{ id, filename, contentType, byteSize, createdAt }].
export const listSummaryImages = (id) =>
  handleFetch(`/api/summaries/${id}/images`);

// Uploads one photo (multipart, like transcribeAudio — the browser must set
// the multipart Content-Type/boundary, so we don't route through handleFetch).
// Returns { data: ImageOut, error }. Errors: 413 too big, 415 wrong type,
// 409 already at the 2-photo limit, 404 not the caller's summary.
export const uploadSummaryImage = async (id, file) => {
  const form = new FormData();
  form.append('image', file, file.name);

  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  try {
    const response = await fetch(`/api/summaries/${id}/images`, {
      method: 'POST',
      headers,
      body: form,
    });
    let body = null;
    try {
      const text = await response.text();
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    if (!response.ok) {
      return {
        data: null,
        error: { status: response.status, message: body?.message || 'Something went wrong' },
      };
    }
    return { data: body, error: null };
  } catch {
    return { data: null, error: { status: 0, message: 'Could not reach the server' } };
  }
};

// The bytes of one photo, as a Blob (caller makes an object URL for <img>).
export const getSummaryImageBlob = (id, imageId) =>
  getBlob(`/api/summaries/${id}/images/${imageId}/raw`);

export const deleteSummaryImage = (id, imageId) =>
  handleFetch(`/api/summaries/${id}/images/${imageId}`, { method: 'DELETE' });
