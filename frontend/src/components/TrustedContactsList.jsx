// TrustedContactsList — the trusted people summaries can be sent to, with
// add / edit / remove (spec §MVP 5).
//
// One component, five modes, same shape as PastSummaries so the flow stays
// a single mental thread:
//   list           -> everyone on the list (GET /api/contacts)
//   add            -> add by email (POST /api/contacts); the person must
//                     already have a Contact account — the backend's 404
//                     becomes "ask them to sign up first"
//   detail         -> one contact's card, with the edit/remove entry points
//   edit           -> nickname + relationship only (PATCH /api/contacts/:linkId)
//   confirm-delete -> Remove is TWO presses, never one (DELETE /api/contacts/:linkId)
//
// Every row is keyed by linkId (the primary↔contact link), not the contact's
// user id — the contract's PATCH/DELETE take the linkId.
//
// Rendered from App's VIEWS map, so props are { user, onNavigate } — neither
// is needed here (the token scopes every request to the logged-in user).

import { useEffect, useState } from 'react';
import {
  addContact,
  deleteContact,
  listContacts,
  updateContact,
} from '../adapters/contacts-adapters';
import './TrustedContactsList.css';

// What the list calls a person: their nickname if one was set, else their
// registered full name.
const displayName = (c) => c.nickname || c.fullName;

export default function TrustedContactsList() {
  const [items, setItems] = useState(null); // null = still loading
  const [loadError, setLoadError] = useState(null);

  const [mode, setMode] = useState('list'); // list | add | detail | edit | confirm-delete
  const [selected, setSelected] = useState(null); // the open contact (full link record)
  const [isBusy, setIsBusy] = useState(false); // a request is in flight
  const [actionError, setActionError] = useState(null);

  // Add form fields (email only exists here; edit can't change it).
  const [addEmail, setAddEmail] = useState('');
  // Nickname + relationship are shared by the add and edit forms — they're
  // seeded from '' (add) or the selected contact (edit) on entry.
  const [nickname, setNickname] = useState('');
  const [relationship, setRelationship] = useState('');

  useEffect(() => {
    const load = async () => {
      const { data, error } = await listContacts();
      if (error) setLoadError("We couldn't load your contacts. Please try again.");
      else setItems(data);
    };
    load();
  }, []);

  const openAdd = () => {
    setAddEmail('');
    setNickname('');
    setRelationship('');
    setActionError(null);
    setMode('add');
  };

  const openDetail = (contact) => {
    setSelected(contact);
    setActionError(null);
    setMode('detail');
  };

  const openEdit = () => {
    setNickname(selected.nickname || '');
    setRelationship(selected.relationship || '');
    setActionError(null);
    setMode('edit');
  };

  const backToList = () => {
    setSelected(null);
    setActionError(null);
    setMode('list');
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    setIsBusy(true);
    setActionError(null);
    const { data, error } = await addContact({
      contactEmail: addEmail.trim(),
      // Blank optional fields stay unset rather than becoming ''.
      nickname: nickname.trim() || undefined,
      relationship: relationship.trim() || undefined,
    });
    setIsBusy(false);
    if (error) {
      if (error.status === 404) {
        // The deliberate "no account with that email" 404 (see the backend's
        // privacy note) — the fix is on their side, so say so kindly.
        setActionError(
          "We couldn't find that email. Ask them to sign up first — then you can add them here."
        );
      } else if (error.status === 409) {
        setActionError('This person is already on your list.');
      } else {
        setActionError("We couldn't add this contact. Please try again.");
      }
      return;
    }
    setItems((list) => [...list, data]);
    setMode('list');
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    setIsBusy(true);
    setActionError(null);
    // Both fields always sent: the form shows both, so a cleared box means
    // "remove it" (null), not "leave it alone".
    const { data, error } = await updateContact(selected.linkId, {
      nickname: nickname.trim() || null,
      relationship: relationship.trim() || null,
    });
    setIsBusy(false);
    if (error) {
      setActionError("We couldn't save your changes. Please try again.");
      return;
    }
    setSelected(data);
    // Keep the list in sync without refetching.
    setItems((list) => list.map((c) => (c.linkId === data.linkId ? data : c)));
    setMode('detail');
  };

  const handleDelete = async () => {
    setIsBusy(true);
    setActionError(null);
    const { error } = await deleteContact(selected.linkId);
    setIsBusy(false);
    if (error) {
      setActionError("We couldn't remove this contact. Please try again.");
      setMode('detail');
      return;
    }
    setItems((list) => list.filter((c) => c.linkId !== selected.linkId));
    setSelected(null);
    setMode('list');
  };

  // ── list mode (also loading / error / empty) ──────────────────────────────

  if (mode === 'list') {
    return (
      <main className="trusted-contacts">
        <h1 className="trusted-contacts__heading">Your trusted contacts</h1>

        {items === null && !loadError && (
          <p className="trusted-contacts__hint">Loading&hellip;</p>
        )}
        {loadError && <p className="trusted-contacts__error">{loadError}</p>}
        {items !== null && items.length === 0 && (
          <p className="trusted-contacts__hint">
            No one here yet. Add the people you trust, and you can send them
            your summaries.
          </p>
        )}

        {items !== null && items.length > 0 && (
          <ul className="trusted-contacts__list">
            {items.map((c) => (
              <li key={c.linkId}>
                {/* The whole card is the tap target — no tiny icons. */}
                <button
                  type="button"
                  className="trusted-contacts__item"
                  onClick={() => openDetail(c)}
                  disabled={isBusy}
                >
                  <span className="trusted-contacts__item-name">{displayName(c)}</span>
                  {c.relationship && (
                    <span className="trusted-contacts__item-relationship">
                      {c.relationship}
                    </span>
                  )}
                  <span className="trusted-contacts__item-email">{c.email}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <p className="trusted-contacts__status" role="status" aria-live="polite">
          {actionError || ''}
        </p>

        {items !== null && (
          <button type="button" className="trusted-contacts__primary" onClick={openAdd}>
            Add a contact
          </button>
        )}
      </main>
    );
  }

  // ── add mode ──────────────────────────────────────────────────────────────

  if (mode === 'add') {
    return (
      <main className="trusted-contacts">
        <button type="button" className="trusted-contacts__back" onClick={backToList}>
          &larr; Cancel
        </button>
        <h1 className="trusted-contacts__heading">Add a contact</h1>
        <p className="trusted-contacts__hint">
          They need their own account first. Once they have signed up, enter
          the email they used.
        </p>

        <form className="trusted-contacts__form" onSubmit={handleAdd}>
          <label className="trusted-contacts__label" htmlFor="contact-email">
            Their email:
          </label>
          <input
            id="contact-email"
            className="trusted-contacts__input"
            type="email"
            value={addEmail}
            onChange={(e) => setAddEmail(e.target.value)}
            readOnly={isBusy}
            required
          />

          <label className="trusted-contacts__label" htmlFor="contact-nickname">
            What you call them (optional):
          </label>
          <input
            id="contact-nickname"
            className="trusted-contacts__input"
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            readOnly={isBusy}
          />

          <label className="trusted-contacts__label" htmlFor="contact-relationship">
            Who they are to you (optional):
          </label>
          <input
            id="contact-relationship"
            className="trusted-contacts__input"
            type="text"
            placeholder="Daughter, neighbor, friend…"
            value={relationship}
            onChange={(e) => setRelationship(e.target.value)}
            readOnly={isBusy}
          />

          <p className="trusted-contacts__status" role="status" aria-live="polite">
            {isBusy ? 'Adding…' : actionError || ''}
          </p>

          <button
            type="submit"
            className="trusted-contacts__primary"
            disabled={isBusy || addEmail.trim().length === 0}
          >
            {isBusy ? 'Adding…' : 'Add this person'}
          </button>
        </form>
      </main>
    );
  }

  // ── edit mode ─────────────────────────────────────────────────────────────

  if (mode === 'edit') {
    return (
      <main className="trusted-contacts">
        <button
          type="button"
          className="trusted-contacts__back"
          onClick={() => setMode('detail')}
        >
          &larr; Cancel
        </button>
        <h1 className="trusted-contacts__heading">{selected.fullName}</h1>
        <p className="trusted-contacts__hint">{selected.email}</p>

        <form className="trusted-contacts__form" onSubmit={handleSaveEdit}>
          <label className="trusted-contacts__label" htmlFor="edit-nickname">
            What you call them:
          </label>
          <input
            id="edit-nickname"
            className="trusted-contacts__input"
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            readOnly={isBusy}
          />

          <label className="trusted-contacts__label" htmlFor="edit-relationship">
            Who they are to you:
          </label>
          <input
            id="edit-relationship"
            className="trusted-contacts__input"
            type="text"
            placeholder="Daughter, neighbor, friend…"
            value={relationship}
            onChange={(e) => setRelationship(e.target.value)}
            readOnly={isBusy}
          />

          <p className="trusted-contacts__status" role="status" aria-live="polite">
            {isBusy ? 'Saving…' : actionError || ''}
          </p>

          <button type="submit" className="trusted-contacts__primary" disabled={isBusy}>
            {isBusy ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </main>
    );
  }

  // ── detail + confirm-delete modes ─────────────────────────────────────────

  return (
    <main className="trusted-contacts">
      <button type="button" className="trusted-contacts__back" onClick={backToList}>
        &larr; All contacts
      </button>

      <h1 className="trusted-contacts__heading">{displayName(selected)}</h1>

      <dl className="trusted-contacts__facts">
        <dt>Name</dt>
        <dd>{selected.fullName}</dd>
        <dt>Email</dt>
        <dd>{selected.email}</dd>
        {selected.nickname && (
          <>
            <dt>You call them</dt>
            <dd>{selected.nickname}</dd>
          </>
        )}
        {selected.relationship && (
          <>
            <dt>Who they are</dt>
            <dd>{selected.relationship}</dd>
          </>
        )}
      </dl>

      <p className="trusted-contacts__status" role="status" aria-live="polite">
        {isBusy ? 'One moment…' : actionError || ''}
      </p>

      {mode === 'confirm-delete' ? (
        <>
          <p className="trusted-contacts__confirm">
            Remove {displayName(selected)} from your list? They will no longer
            receive your summaries.
          </p>
          <button
            type="button"
            className="trusted-contacts__danger"
            onClick={handleDelete}
            disabled={isBusy}
          >
            Yes, remove them
          </button>
          <button
            type="button"
            className="trusted-contacts__secondary"
            onClick={() => setMode('detail')}
            disabled={isBusy}
          >
            No, keep them
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            className="trusted-contacts__primary"
            onClick={openEdit}
            disabled={isBusy}
          >
            Change nickname or relationship
          </button>
          <button
            type="button"
            className="trusted-contacts__secondary"
            onClick={() => setMode('confirm-delete')}
            disabled={isBusy}
          >
            Remove this contact
          </button>
        </>
      )}
    </main>
  );
}
