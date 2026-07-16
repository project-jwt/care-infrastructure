// Adapters for spec §Summaries (primary only). All require a valid JWT
// (handleFetch attaches it automatically); the backend rejects contacts
// with 403.

import { getToken, handleFetch } from './fetch-helpers';

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

// Emails the summary to trusted contacts and records each successful send.
// Returns { summaryId, sentTo: [{ contactId, sentAt }], failed: [{ contactId }] }
// — failed is non-empty on a partial send (retry just those ids). Errors:
// 404 summary not found (or not the caller's), 403 a contactId is not a
// trusted contact, 502 EVERY email failed (nothing recorded), 422 empty
// contactIds.
export const sendSummary = (id, contactIds) =>
  handleFetch(`/api/summaries/${id}/send`, {
    method: 'POST',
    body: JSON.stringify({ contactIds }),
  });
