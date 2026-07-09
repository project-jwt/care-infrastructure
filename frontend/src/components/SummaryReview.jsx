// SummaryReview — editable review of the AI-drafted summary, then save
// (spec §MVP 3: "the user can edit the summary before or after it is sent").
//
// The summary arrives from RecordingPage in the user's own words. They read
// it, fix anything, and press the one primary action — which calls
// POST /api/summaries (saveSummary) with the raw transcript riding along so
// the History detail view can show it later. A saved confirmation replaces
// the form; ChooseAction (send to contact / call helpline) is a later ticket
// and picks up from here.
//
// Props:
//   transcript  — raw speech-to-text words (optional in the save contract)
//   summaryText — the AI draft handed up from RecordingPage
//   onNavigate(view) — App's view switcher

import { useState } from 'react';
import { saveSummary } from '../adapters/summaries-adapters';
import './SummaryReview.css';

export default function SummaryReview({ transcript, summaryText, onNavigate }) {
  // The textarea is the single source of truth — initialized with the AI
  // draft, then the user's edits win. A textarea (not rendered HTML) keeps
  // the \n\n paragraph breaks visible and editable as real blank lines.
  const [text, setText] = useState(summaryText || '');
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const canSave = !isSaving && text.trim().length > 0;

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    const { error } = await saveSummary({
      transcript: transcript || null, // '' -> null: the contract's "no transcript"
      summaryText: text.trim(),
    });
    setIsSaving(false);
    if (error) {
      // Plain language, no blame, recoverable — same voice as RecordingPage.
      setSaveError("We couldn't save your summary just now. Please try again.");
      return;
    }
    setSaved(true);
  }

  // After a successful save the form is gone — one clear next step, no way
  // to double-save the same summary.
  if (saved) {
    return (
      <main className="summary-review">
        <h1 className="summary-review__heading">Saved</h1>
        <p className="summary-review__hint">
          Your summary is safe. You can find it any time under History.
        </p>
        <button
          type="button"
          className="summary-review__save"
          onClick={() => onNavigate('home')}
        >
          Back to home
        </button>
      </main>
    );
  }

  return (
    <main className="summary-review">
      {/* Restarts the speak flow — RecordingPage mounts fresh. */}
      <button
        type="button"
        className="summary-review__back"
        onClick={() => onNavigate('recording')}
      >
        &larr; Start over
      </button>

      <h1 className="summary-review__heading">Here&rsquo;s what we wrote</h1>
      <p className="summary-review__hint">
        Read it over &mdash; you can change any of the words. When it looks
        right, press the button below.
      </p>

      <label className="summary-review__label" htmlFor="summary">
        Your summary:
      </label>
      <textarea
        id="summary"
        className="summary-review__text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        readOnly={isSaving}
        rows={10}
      />

      {/* Reserved line so the layout doesn't jump when a status appears. */}
      <p className="summary-review__status" role="status" aria-live="polite">
        {isSaving ? 'Saving…' : saveError || ''}
      </p>

      {/* The one primary action on this screen (design rules). */}
      <button
        type="button"
        className="summary-review__save"
        onClick={handleSave}
        disabled={!canSave}
      >
        {isSaving ? 'Saving…' : 'Looks good — save it'}
      </button>
    </main>
  );
}
