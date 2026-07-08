// RecordingPage — speech-to-text capture screen (spec §MVP 2, ticket F2).
//
// Scope (capture only): one Speak button, a live editable transcript, and a
// plain-language typing fallback. The clarifying-question loop / draftSummary
// call belongs to a later ticket — this screen just collects the transcript
// and hands it up through onContinue.
//
// Props:
//   onContinue(transcript) — required; called with the trimmed transcript
//                            when the user presses Continue (review step).
//   onBack()               — optional; renders a back button when provided.

import { useState } from 'react';
import useSpeechRecognition from '../hooks/useSpeechRecognition';
import './RecordingPage.css';

export default function RecordingPage({ onContinue, onBack }) {
  // The transcript is the single source of truth — always editable between
  // recordings, and what Continue hands to the review step.
  const [transcript, setTranscript] = useState('');
  const { isSupported, isListening, interimText, micDenied, error, start, stop } =
    useSpeechRecognition();

  // Fallback mode kicks in when the browser lacks the API (e.g. Firefox) or
  // the user blocked the microphone — typing takes over, flow never blocks.
  const speechAvailable = isSupported && !micDenied;
  const canContinue = !isListening && transcript.trim().length > 0;

  // One button, two jobs: start when idle, stop when listening. Each
  // finalized phrase is APPENDED (with a space) rather than replacing the
  // text, so pressing Speak again adds to what's already there —
  // continuous: false ends a session after every pause.
  function handleSpeakClick() {
    if (isListening) {
      stop();
    } else {
      start((finalText) => {
        setTranscript((t) => (t ? `${t} ` : '') + finalText);
      });
    }
  }

  // While listening, show committed text + the live interim guess so words
  // appear as they're spoken. When idle, show just the committed transcript.
  const displayedText = isListening
    ? transcript + (interimText ? `${transcript ? ' ' : ''}${interimText}` : '')
    : transcript;

  // Status line under the Speak button (aria-live announces it to
  // screen readers without stealing focus).
  let status = '';
  if (isListening) status = 'Listening…';
  else if (error) status = error;

  return (
    <main className="recording-page">
      {onBack && (
        <button type="button" className="recording-page__back" onClick={onBack}>
          &larr; Back
        </button>
      )}

      <h1 className="recording-page__heading">Tell us what&rsquo;s going on</h1>

      {speechAvailable ? (
        <>
          <p className="recording-page__hint">
            Press the button and speak. You can fix the words after.
          </p>
          {/* The one primary action on this screen (design rules). */}
          <button
            type="button"
            className={`recording-page__speak${isListening ? ' recording-page__speak--listening' : ''}`}
            onClick={handleSpeakClick}
            aria-pressed={isListening}
          >
            <span className="recording-page__speak-icon" aria-hidden="true">
              {isListening ? '■' : '🎙'}
            </span>
            {isListening ? 'Stop' : 'Speak'}
          </button>
          <p className="recording-page__status" role="status" aria-live="polite">
            {status}
          </p>
        </>
      ) : (
        // Plain-language fallback notice — calm, no jargon, no blame.
        <p className="recording-page__fallback-notice">
          {micDenied
            ? "We don't have permission to use your microphone."
            : "Talking isn't available on this browser."}{' '}
          No problem &mdash; you can type instead. Tap the box below and tell us
          what&rsquo;s going on.
        </p>
      )}

      {/* The textarea IS the edit surface — words stream in live while
          listening (read-only so incoming results can't clobber an edit),
          then it becomes fully editable the moment recording stops. */}
      <label className="recording-page__label" htmlFor="transcript">
        Your words:
      </label>
      <textarea
        id="transcript"
        className="recording-page__transcript"
        value={displayedText}
        onChange={(e) => setTranscript(e.target.value)}
        readOnly={isListening}
        rows={8}
        placeholder={
          speechAvailable
            ? 'Your words will show up here.'
            : 'Type what happened here.'
        }
      />

      {/* Disabled until there's something to send and the mic is off. */}
      <button
        type="button"
        className="recording-page__continue"
        onClick={() => onContinue(transcript.trim())}
        disabled={!canContinue}
      >
        Continue
      </button>
    </main>
  );
}
