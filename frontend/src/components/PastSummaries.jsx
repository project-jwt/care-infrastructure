// PastSummaries — list of saved summaries with detail / edit / delete
// (spec §MVP 3, wireframe screen 7).
//
// One component, four modes, so the flow stays a single mental thread:
//   list           -> everything saved, newest first (GET /api/summaries)
//   detail         -> one summary + original spoken words (GET /api/summaries/:id)
//   edit           -> textarea over the summary text (PATCH /api/summaries/:id)
//   confirm-delete -> Delete is TWO presses, never one (DELETE /api/summaries/:id)
//
// Rendered from App's VIEWS map, so props are { user, onNavigate,
// onSendSummary }. onNavigate('home') backs the list out to the home screen
// (BottomNav has no Home item — the wireframe caps it at 3). onSendSummary(id)
// hands the open summary's id back to App, which re-enters the choose-action
// send flow — the send path for anyone who saved before adding contacts (or
// who just wants to re-send an old summary).

import { useEffect, useState } from 'react';
import {
  deleteSummary,
  getSummary,
  getSummaryRecipients,
  listSummaries,
  updateSummary,
} from '../adapters/summaries-adapters';
import { displayName, formatDate } from '../utils';
import './PastSummaries.css';

export default function PastSummaries({ onNavigate, onSendSummary }) {
  const [items, setItems] = useState(null); // null = still loading
  const [loadError, setLoadError] = useState(null);

  // Detail state: which summary is open, and what mode the screen is in.
  const [mode, setMode] = useState('list'); // list | detail | edit | confirm-delete
  const [selected, setSelected] = useState(null); // full record incl. transcript
  const [editText, setEditText] = useState('');
  const [isBusy, setIsBusy] = useState(false); // a request is in flight
  const [actionError, setActionError] = useState(null);

  // "Sent to" receipt for the open summary. null = still loading; [] = never
  // sent; recipientsError = the receipt call failed (the summary still shows).
  const [recipients, setRecipients] = useState(null);
  const [recipientsError, setRecipientsError] = useState(false);

  useEffect(() => {
    const load = async () => {
      const { data, error } = await listSummaries();
      if (error) setLoadError("We couldn't load your summaries. Please try again.");
      else setItems(data);
    };
    load();
  }, []);

  const openDetail = async (id) => {
    setActionError(null);
    setIsBusy(true);
    // The list shape has no transcript (kept light on purpose) — the detail
    // endpoint returns it, so "what you said" can be shown alongside.
    const { data, error } = await getSummary(id);
    setIsBusy(false);
    if (error) {
      setActionError("We couldn't open that summary. Please try again.");
      return;
    }
    setSelected(data);
    setMode('detail');

    // Load the "sent to" receipt separately — a failure here must not stop the
    // summary + transcript from rendering.
    setRecipients(null);
    setRecipientsError(false);
    const { data: recs, error: recErr } = await getSummaryRecipients(id);
    if (recErr) setRecipientsError(true);
    else setRecipients(recs);
  };

  const handleSaveEdit = async () => {
    setIsBusy(true);
    setActionError(null);
    const { data, error } = await updateSummary(selected.id, editText.trim());
    setIsBusy(false);
    if (error) {
      setActionError("We couldn't save your changes. Please try again.");
      return;
    }
    setSelected(data);
    // Keep the list in sync without refetching.
    setItems((list) => list.map((s) => (s.id === data.id ? { ...s, ...data } : s)));
    setMode('detail');
  };

  const handleDelete = async () => {
    setIsBusy(true);
    setActionError(null);
    const { error } = await deleteSummary(selected.id);
    setIsBusy(false);
    if (error) {
      setActionError("We couldn't delete that summary. Please try again.");
      setMode('detail');
      return;
    }
    setItems((list) => list.filter((s) => s.id !== selected.id));
    setSelected(null);
    setMode('list');
  };

  const backToList = () => {
    setSelected(null);
    setActionError(null);
    setMode('list');
  };

  // ── list mode (also loading / error / empty) ──────────────────────────────

  if (mode === 'list') {
    return (
      <main className="past-summaries">
        <button
          type="button"
          className="past-summaries__back"
          onClick={() => onNavigate('home')}
        >
          &larr; Home
        </button>
        <h1 className="past-summaries__heading">Your summaries</h1>

        {items === null && !loadError && (
          <p className="past-summaries__hint">Loading&hellip;</p>
        )}
        {loadError && <p className="past-summaries__error">{loadError}</p>}
        {items !== null && items.length === 0 && (
          <p className="past-summaries__hint">
            Nothing here yet. When you save a summary, it will show up on this
            page.
          </p>
        )}

        {items !== null && items.length > 0 && (
          <ul className="past-summaries__list">
            {items.map((s) => (
              <li key={s.id}>
                {/* The whole card is the tap target — no tiny icons. */}
                <button
                  type="button"
                  className="past-summaries__item"
                  onClick={() => openDetail(s.id)}
                  disabled={isBusy}
                >
                  <span className="past-summaries__item-date">{formatDate(s.createdAt)}</span>
                  <span className="past-summaries__item-preview">
                    {s.summaryText.split('\n')[0]}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <p className="past-summaries__status" role="status" aria-live="polite">
          {actionError || ''}
        </p>
      </main>
    );
  }

  // ── edit mode ─────────────────────────────────────────────────────────────

  if (mode === 'edit') {
    return (
      <main className="past-summaries">
        <button type="button" className="past-summaries__back" onClick={() => setMode('detail')}>
          &larr; Cancel
        </button>
        <h1 className="past-summaries__heading">Change your summary</h1>

        <label className="past-summaries__label" htmlFor="edit-summary">
          Your summary:
        </label>
        <textarea
          id="edit-summary"
          className="past-summaries__textarea"
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          readOnly={isBusy}
          rows={10}
        />

        <p className="past-summaries__status" role="status" aria-live="polite">
          {isBusy ? 'Saving…' : actionError || ''}
        </p>

        <button
          type="button"
          className="past-summaries__primary"
          onClick={handleSaveEdit}
          disabled={isBusy || editText.trim().length === 0}
        >
          {isBusy ? 'Saving…' : 'Save changes'}
        </button>
      </main>
    );
  }

  // ── detail + confirm-delete modes ─────────────────────────────────────────

  return (
    <main className="past-summaries">
      <button type="button" className="past-summaries__back" onClick={backToList}>
        &larr; All summaries
      </button>

      <h1 className="past-summaries__heading">{formatDate(selected.createdAt)}</h1>

      {/* pre-line keeps the \n\n paragraph breaks visible. */}
      <p className="past-summaries__text">{selected.summaryText}</p>

      {selected.transcript && (
        <details className="past-summaries__transcript">
          <summary className="past-summaries__transcript-toggle">
            <span className="past-summaries__transcript-chevron" aria-hidden="true">
              &#9656;
            </span>
            <span>Tap to read what you said</span>
          </summary>
          <p className="past-summaries__transcript-body">{selected.transcript}</p>
        </details>
      )}

      {/* Sent to — who this summary was delivered to (the sender's receipt). */}
      <section className="past-summaries__sent-to" aria-labelledby="sent-to-h">
        <h2 id="sent-to-h" className="past-summaries__sent-to-heading">Sent to</h2>
        {recipientsError && (
          <p className="past-summaries__hint">We couldn&apos;t load who this was sent to.</p>
        )}
        {!recipientsError && recipients === null && (
          <p className="past-summaries__hint">Loading&hellip;</p>
        )}
        {!recipientsError && recipients !== null && recipients.length === 0 && (
          <p className="past-summaries__hint">Not sent yet.</p>
        )}
        {!recipientsError && recipients !== null && recipients.length > 0 && (
          <ul className="past-summaries__recipients">
            {recipients.map((r, i) => (
              <li key={i} className="past-summaries__recipient">
                <span className="past-summaries__recipient-name">
                  {/* The name the sender saved them under ("Mom"), same as
                      everywhere else — falls back to "Deleted user" once the
                      contact and its link are gone (both names null). */}
                  {displayName(r) || 'Deleted user'}
                </span>
                <span className="past-summaries__recipient-date">{formatDate(r.sentAt)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="past-summaries__status" role="status" aria-live="polite">
        {isBusy ? 'One moment…' : actionError || ''}
      </p>

      {mode === 'confirm-delete' ? (
        <>
          <p className="past-summaries__confirm">
            Delete this summary? It cannot be brought back.
          </p>
          <button
            type="button"
            className="past-summaries__danger"
            onClick={handleDelete}
            disabled={isBusy}
          >
            Yes, delete it
          </button>
          <button
            type="button"
            className="past-summaries__secondary"
            onClick={() => setMode('detail')}
            disabled={isBusy}
          >
            No, keep it
          </button>
        </>
      ) : (
        <>
          {/* Send stays the filled, dominant action — same rule as the
              choose screen. */}
          <button
            type="button"
            className="past-summaries__primary"
            onClick={() => onSendSummary(selected.id)}
            disabled={isBusy}
          >
            Send to my trusted contacts
          </button>
          <button
            type="button"
            className="past-summaries__secondary"
            onClick={() => {
              setEditText(selected.summaryText);
              setMode('edit');
            }}
            disabled={isBusy}
          >
            Change the words
          </button>
          <button
            type="button"
            className="past-summaries__secondary"
            onClick={() => setMode('confirm-delete')}
            disabled={isBusy}
          >
            Delete this summary
          </button>
        </>
      )}
    </main>
  );
}
