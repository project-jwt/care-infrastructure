// Adapters for spec §Summaries (primary only). All require a valid JWT
// (handleFetch attaches it automatically); the backend rejects contacts
// with 403.

import { handleFetch } from './fetch-helpers';

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

// Emails the summary to trusted contacts and records each send. Returns
// { summaryId, sentTo: [{ contactId, sentAt }] }. Errors: 404 summary not
// found (or not the caller's), 403 a contactId is not a trusted contact,
// 502 the email service failed (nothing recorded), 422 empty contactIds.
export const sendSummary = (id, contactIds) =>
  handleFetch(`/api/summaries/${id}/send`, {
    method: 'POST',
    body: JSON.stringify({ contactIds }),
  });
