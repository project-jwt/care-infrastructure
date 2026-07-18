// HelplinePage — the pre-loaded numbers a user can call for scam help
// (spec §MVP 4, wireframe "Helpline — AARP one-tap call").
//
// Read-only screen, no modes: one card per helpline with a single filled
// Call button — a tel: link, so on a phone it opens the dialer in one tap.
// On a desktop the number is written out in the button itself, big enough
// to read and dial from any phone.
//
// Reached two ways: BottomNav "Helpline", and ChooseAction's "Call for help".
// Rendered from App's VIEWS map, so props are { user, onNavigate } — only
// onNavigate('home') is used, to back out to the home screen (BottomNav has
// no Home item — the wireframe caps it at 3). The token scopes the request.

import { useEffect, useState } from 'react';
import { listHelplines } from '../adapters/helplines-adapters';
import './HelplinePage.css';

// "877-908-3360" -> "tel:+18779083360". All MVP helplines are US numbers,
// so the +1 prefix is assumed.
const telHref = (phone) => `tel:+1${phone.replace(/\D/g, '')}`;

export default function HelplinePage({ onNavigate }) {
  const [items, setItems] = useState(null); // null = still loading
  const [loadError, setLoadError] = useState(null);

  // Named (not inline in the effect) so the load-error Try Again button can
  // re-run it. Resetting to the loading state first makes the retry visible.
  const load = async () => {
    setItems(null);
    setLoadError(null);
    const { data, error } = await listHelplines();
    if (error) setLoadError("We couldn't load the helplines.");
    else setItems(data);
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="helpline-page">
      <button
        type="button"
        className="helpline-page__back"
        onClick={() => onNavigate('home')}
      >
        &larr; Home
      </button>
      <h1 className="helpline-page__heading">Get help with a scam</h1>

      {/* Always-mounted live region for the transient states (same pattern
          as the F5 screens) — a live region that mounts already holding text
          is never announced, so the element must exist before the message. */}
      <p className="helpline-page__status" role="status" aria-live="polite">
        {loadError || (items === null ? 'Loading…' : '')}
      </p>
      {loadError && (
        <button type="button" className="helpline-page__retry" onClick={load}>
          Try again
        </button>
      )}
      {items !== null && items.length === 0 && (
        <p className="helpline-page__hint">
          There are no helplines to show right now. Please try again later.
        </p>
      )}

      {items !== null && items.length > 0 && (
        <ul className="helpline-page__list">
          {items.map((h) => (
            <li key={h.id} className="helpline-page__card">
              <h2 className="helpline-page__name">{h.name}</h2>
              {h.description && (
                <p className="helpline-page__description">{h.description}</p>
              )}
              {h.hours && <p className="helpline-page__hours">Open {h.hours}</p>}
              {/* The one primary action: an anchor styled as the filled
                  button, with the number in the label as the desktop
                  fallback (readable + dialable from any phone). */}
              <a className="helpline-page__call" href={telHref(h.phone)}>
                Call {h.phone}
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
