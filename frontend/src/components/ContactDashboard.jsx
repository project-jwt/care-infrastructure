// ContactDashboard — the one read-only screen a trusted contact sees:
// everything that has been sent to them, newest first (spec §MVP 1,
// Contact Dashboard; GET /api/received-summaries).
//
// One component, two modes, same shape as PastSummaries but read-only:
//   list   -> sender + date + first-line preview per card
//   detail -> the full summary text (already in the list payload — the
//             API returns full summaryText, so opening a card needs no
//             second request)
//
// App renders this whenever user.role === 'contact'; props are { user },
// which isn't needed here (the token scopes the request to the logged-in
// contact).

import { useEffect, useRef, useState } from 'react';
import {
  getReceivedSummaryImageBlob,
  listReceivedSummaries,
} from '../adapters/received-summaries-adapters';
import { formatDate } from '../utils';
import './ContactDashboard.css';

export default function ContactDashboard() {
  const [items, setItems] = useState(null); // null = still loading
  const [loadError, setLoadError] = useState(null);
  const [selected, setSelected] = useState(null); // open summary, null = list mode

  // Object URLs for the open summary's photos (imageId -> URL), tracked in a
  // ref so they can be revoked when the summary changes or the screen unmounts.
  const [imageUrls, setImageUrls] = useState({});
  const objectUrls = useRef([]);
  const revokeImageUrls = () => {
    objectUrls.current.forEach((u) => URL.revokeObjectURL(u));
    objectUrls.current = [];
  };

  // Named (not inline in the effect) so the load-error Try Again button can
  // re-run it. Resetting to the loading state first makes the retry visible.
  const load = async () => {
    setItems(null);
    setLoadError(null);
    const { data, error } = await listReceivedSummaries();
    if (error) setLoadError("We couldn't load your summaries.");
    else setItems(data);
  };

  useEffect(() => {
    load();
  }, []);

  // When a summary opens, fetch its photos' bytes (each behind auth) and turn
  // them into object URLs. Revokes the previous set first; the list-item
  // payload already carries the image metadata.
  useEffect(() => {
    let cancelled = false;
    revokeImageUrls();
    setImageUrls({});
    if (selected?.images?.length) {
      (async () => {
        const urls = {};
        for (const img of selected.images) {
          const { data: blob } = await getReceivedSummaryImageBlob(selected.summaryId, img.id);
          if (blob && !cancelled) {
            const url = URL.createObjectURL(blob);
            urls[img.id] = url;
            objectUrls.current.push(url);
          }
        }
        if (!cancelled) setImageUrls(urls);
      })();
    }
    return () => {
      cancelled = true;
    };
  }, [selected]);

  // Revoke any outstanding URLs when the screen unmounts.
  useEffect(() => revokeImageUrls, []);

  // ── detail mode ───────────────────────────────────────────────────────────

  if (selected) {
    return (
      <main className="contact-dashboard">
        <button
          type="button"
          className="contact-dashboard__back"
          onClick={() => setSelected(null)}
        >
          &larr; All summaries
        </button>

        <h1 className="contact-dashboard__heading">
          From {selected.from.fullName}
        </h1>
        <p className="contact-dashboard__date">{formatDate(selected.sentAt)}</p>

        {/* pre-line — the same rendering History gives the sender, so both
            sides see identical layout of identical text. */}
        <p className="contact-dashboard__text">{selected.summaryText}</p>

        {/* Photos the sender attached — read-only on this side. */}
        {selected.images?.length > 0 && (
          <section className="contact-dashboard__photos" aria-labelledby="cd-photos-h">
            <h2 id="cd-photos-h" className="contact-dashboard__photos-heading">Photos</h2>
            <ul className="contact-dashboard__photo-list">
              {selected.images.map((img) => (
                <li key={img.id} className="contact-dashboard__photo">
                  {imageUrls[img.id] ? (
                    <img
                      className="contact-dashboard__photo-img"
                      src={imageUrls[img.id]}
                      alt={img.filename || 'Attached photo'}
                    />
                  ) : (
                    <span className="contact-dashboard__photo-fallback">Loading photo&hellip;</span>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    );
  }

  // ── list mode (also loading / error / empty) ──────────────────────────────

  return (
    <main className="contact-dashboard">
      <h1 className="contact-dashboard__heading">Summaries sent to you</h1>

      {/* Always-mounted live region for the transient states — a live region
          that mounts already holding text is never announced, so the element
          has to exist before the message does. */}
      <p className="contact-dashboard__status" role="status" aria-live="polite">
        {loadError || (items === null ? 'Loading…' : '')}
      </p>
      {loadError && (
        <button type="button" className="contact-dashboard__primary" onClick={load}>
          Try again
        </button>
      )}
      {items !== null && items.length === 0 && (
        <p className="contact-dashboard__hint">
          Nothing here yet. When someone sends you a summary, it will show up
          on this page.
        </p>
      )}

      {items !== null && items.length > 0 && (
        <ul className="contact-dashboard__list">
          {items.map((s) => (
            // The backend deliberately allows re-sending the same summary, so
            // summaryId alone can repeat — the timestamp disambiguates.
            <li key={`${s.summaryId}-${s.sentAt}`}>
              {/* The whole card is the tap target — no tiny icons. */}
              <button
                type="button"
                className="contact-dashboard__item"
                onClick={() => setSelected(s)}
              >
                <span className="contact-dashboard__item-sender">
                  From {s.from.fullName}
                </span>
                <span className="contact-dashboard__item-date">{formatDate(s.sentAt)}</span>
                <span className="contact-dashboard__item-preview">
                  {s.summaryText.split('\n')[0]}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
