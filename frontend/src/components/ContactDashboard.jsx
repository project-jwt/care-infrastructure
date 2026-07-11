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

import { useEffect, useState } from 'react';
import { listReceivedSummaries } from '../adapters/received-summaries-adapters';
import './ContactDashboard.css';

// "2026-07-09T23:09:50Z" -> "July 9, 2026" — plain dates, no timestamps.
const formatDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

export default function ContactDashboard() {
  const [items, setItems] = useState(null); // null = still loading
  const [loadError, setLoadError] = useState(null);
  const [selected, setSelected] = useState(null); // open summary, null = list mode

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

        {/* pre-wrap keeps the summary's own line and paragraph breaks. */}
        <p className="contact-dashboard__text">{selected.summaryText}</p>
      </main>
    );
  }

  // ── list mode (also loading / error / empty) ──────────────────────────────

  return (
    <main className="contact-dashboard">
      <h1 className="contact-dashboard__heading">Summaries sent to you</h1>

      {items === null && !loadError && (
        <p className="contact-dashboard__hint">Loading&hellip;</p>
      )}
      {loadError && (
        <>
          <p className="contact-dashboard__error">{loadError}</p>
          <button type="button" className="contact-dashboard__primary" onClick={load}>
            Try again
          </button>
        </>
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
            <li key={s.summaryId}>
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
