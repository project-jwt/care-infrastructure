// Adapters for spec §Trusted Contacts (primary only). All require a valid
// JWT (handleFetch attaches it automatically); the backend rejects contact
// accounts with 403.

import { handleFetch } from './fetch-helpers';

// The current user's trusted contacts:
// [{ linkId, contactId, fullName, email, nickname, relationship }]
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
