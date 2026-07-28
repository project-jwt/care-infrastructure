// Adapters for spec §Trusted Contacts (primary only). All require a valid
// JWT (handleFetch attaches it automatically); the backend rejects contact
// accounts with 403.

import { handleFetch } from './fetch-helpers';

// [{ status, linkId, contactId, fullName, email, nickname, relationship,
//    inviteId, invitedAt }]
// status "active" = a real link (linkId/contactId/fullName set); status
// "invited" = someone invited who hasn't registered (inviteId/invitedAt set,
// fullName null). Active rows come first.
export const listContacts = () => handleFetch('/api/contacts');

// Adds a contact by email — the person must already have a Contact account.
// 404 when there's no such account (the UI turns this into "ask them to
// sign up first"), 409 when they're already on the list.
export const addContact = ({ contactEmail, nickname, relationship }) =>
  handleFetch('/api/contacts', {
    method: 'POST',
    body: JSON.stringify({ contactEmail, nickname, relationship }),
  });

// Updates nickname / relationship. Only the keys present in `fields` are
// touched — the backend tells "omitted" apart from "set to null".
export const updateContact = (linkId, fields) =>
  handleFetch(`/api/contacts/${linkId}`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });

export const deleteContact = (linkId) =>
  handleFetch(`/api/contacts/${linkId}`, { method: 'DELETE' });

// ── pending invitations ──────────────────────────────────────────────────────
// Keyed by inviteId, NOT linkId — an invited person has no link yet, and the
// two are independent id sequences.

export const updateInvite = (inviteId, fields) =>
  handleFetch(`/api/contacts/invites/${inviteId}`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  });

// 429 when the hourly cooldown hasn't elapsed.
export const resendInvite = (inviteId) =>
  handleFetch(`/api/contacts/invites/${inviteId}/resend`, { method: 'POST' });

export const cancelInvite = (inviteId) =>
  handleFetch(`/api/contacts/invites/${inviteId}`, { method: 'DELETE' });
