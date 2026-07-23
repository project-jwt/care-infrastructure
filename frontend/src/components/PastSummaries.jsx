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

import { useEffect, useRef, useState } from 'react';
import {
  deleteSummary,
  deleteSummaryImage,
  getSummary,
  getSummaryImageBlob,
  getSummaryRecipients,
  listSummaries,
  listSummaryImages,
  updateSummary,
  uploadSummaryImage,
} from '../adapters/summaries-adapters';
import { formatDate } from '../utils';
import './PastSummaries.css';

const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // keep in step with the server cap
const MAX_IMAGES = 2;

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

  // Photos on the open summary. images: null = loading, [] = none, else the
  // metadata list. imageUrls maps imageId -> object URL of its bytes. The
  // created object URLs are tracked in a ref so they can be revoked on cleanup.
  const [images, setImages] = useState(null);
  const [imageUrls, setImageUrls] = useState({});
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState(null);
  const objectUrls = useRef([]);

  const revokeImageUrls = () => {
    objectUrls.current.forEach((u) => URL.revokeObjectURL(u));
    objectUrls.current = [];
  };

  // Revoke any outstanding object URLs when the screen unmounts.
  useEffect(() => revokeImageUrls, []);

  useEffect(() => {
    const load = async () => {
      const { data, error } = await listSummaries();
      if (error) setLoadError("We couldn't load your summaries. Please try again.");
      else setItems(data);
    };
    load();
  }, []);

  // Fetch a summary's photo metadata, then each one's bytes as an object URL.
  // Revokes any URLs from a previously-open summary first.
  const loadImages = async (id) => {
    revokeImageUrls();
    setImageUrls({});
    setImages(null);
    setImageError(null);
    const { data, error } = await listSummaryImages(id);
    if (error) {
      setImageError("We couldn't load the photos on this summary.");
      setImages([]);
      return;
    }
    setImages(data);
    const urls = {};
    for (const img of data) {
      const { data: blob } = await getSummaryImageBlob(id, img.id);
      if (blob) {
        const url = URL.createObjectURL(blob);
        urls[img.id] = url;
        objectUrls.current.push(url);
      }
    }
    setImageUrls(urls);
  };

  const handleAddPhoto = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // let the same file be re-picked after an error
    if (!file) return;
    setImageError(null);
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setImageError('Please choose a JPEG, PNG, or WebP photo.');
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError('That photo is too large. Please choose one under 10 MB.');
      return;
    }
    setImageBusy(true);
    const { error } = await uploadSummaryImage(selected.id, file);
    setImageBusy(false);
    if (error) {
      setImageError(
        error.status === 409
          ? `You can attach at most ${MAX_IMAGES} photos.`
          : "We couldn't add that photo. Please try again.",
      );
      return;
    }
    await loadImages(selected.id);
  };

  const handleRemovePhoto = async (imageId) => {
    setImageBusy(true);
    setImageError(null);
    const { error } = await deleteSummaryImage(selected.id, imageId);
    setImageBusy(false);
    if (error) {
      setImageError("We couldn't remove that photo. Please try again.");
      return;
    }
    await loadImages(selected.id);
  };

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

    // Photos load independently too — a failure shows a hint, never blocks.
    loadImages(id);
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
    revokeImageUrls();
    setImages(null);
    setImageUrls({});
    setImageError(null);
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
          <summary>What you said at the time</summary>
          <p>{selected.transcript}</p>
        </details>
      )}

      {/* Photos — attachments that go out with the summary when it's sent. */}
      <section className="past-summaries__photos" aria-labelledby="photos-h">
        <h2 id="photos-h" className="past-summaries__photos-heading">Photos</h2>

        {images === null && (
          <p className="past-summaries__hint">Loading&hellip;</p>
        )}
        {images !== null && images.length === 0 && (
          <p className="past-summaries__hint">
            No photos yet. Add one and it will be sent along with this summary.
          </p>
        )}
        {images !== null && images.length > 0 && (
          <ul className="past-summaries__photo-list">
            {images.map((img) => (
              <li key={img.id} className="past-summaries__photo">
                {imageUrls[img.id] ? (
                  <img
                    className="past-summaries__photo-img"
                    src={imageUrls[img.id]}
                    alt={img.filename || 'Attached photo'}
                  />
                ) : (
                  <span className="past-summaries__photo-fallback">
                    Couldn&apos;t load photo
                  </span>
                )}
                {mode === 'detail' && (
                  <button
                    type="button"
                    className="past-summaries__photo-remove"
                    onClick={() => handleRemovePhoto(img.id)}
                    disabled={imageBusy}
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {mode === 'detail' && images !== null && images.length < MAX_IMAGES && (
          <label className="past-summaries__photo-add">
            {imageBusy ? 'Adding…' : 'Add a photo'}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="past-summaries__photo-input"
              onChange={handleAddPhoto}
              disabled={imageBusy}
            />
          </label>
        )}

        {imageError && <p className="past-summaries__error">{imageError}</p>}
      </section>

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
                  {r.fullName ?? 'Deleted user'}
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
