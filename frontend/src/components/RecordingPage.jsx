// RecordingPage — speech-to-text capture + clarifying-question loop
// (spec §MVP 2).
//
// Flow: the user speaks (or types) their problem, Continue sends the
// transcript to POST /api/summaries/draft. If the AI needs more detail it
// returns questions — each is asked one at a time using the same speak/type
// input — and the answers are sent back with the transcript until the AI
// returns a finished summary, which is handed up through onContinue.
//
// Props:
//   onContinue({ transcript, summaryText }) — required; called when the AI
//                                             summary is ready (review step).
//   onBack()                                — optional; renders a back button.

import { useState } from 'react';
import useSpeechRecognition from '../hooks/useSpeechRecognition';
import { draftSummary } from '../adapters/summaries-adapters';
import './RecordingPage.css';

export default function RecordingPage({ onContinue, onBack }) {
  // 'capture' = describing the problem; 'clarify' = answering AI questions.
  const [step, setStep] = useState('capture');
  const [transcript, setTranscript] = useState('');

  // Clarifying-question round: the questions, which one is showing, the
  // answers collected so far, and the answer currently being composed.
  const [questions, setQuestions] = useState([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [answerText, setAnswerText] = useState('');

  const [isDrafting, setIsDrafting] = useState(false); // waiting on the AI
  const [draftError, setDraftError] = useState(null);

  const { isSupported, isListening, interimText, micDenied, error, start, stop } =
    useSpeechRecognition();

  // Fallback mode kicks in when the browser lacks the API (e.g. Firefox) or
  // the user blocked the microphone — typing takes over, flow never blocks.
  const speechAvailable = isSupported && !micDenied;

  // The same textarea serves both steps — it edits the transcript while
  // capturing and the current answer while clarifying.
  const currentText = step === 'capture' ? transcript : answerText;
  const setCurrentText = step === 'capture' ? setTranscript : setAnswerText;

  const canContinue = !isListening && !isDrafting && currentText.trim().length > 0;

  // One button, two jobs: start when idle, stop when listening. Each
  // finalized phrase is APPENDED (with a space) rather than replacing the
  // text, so pressing Speak again adds to what's already there —
  // continuous: false ends a session after every pause.
  function handleSpeakClick() {
    if (isListening) {
      stop();
    } else {
      start((finalText) => {
        setCurrentText((t) => (t ? `${t} ` : '') + finalText);
      });
    }
  }

  // One round trip to the AI. Called from the capture step and again after
  // each clarifying round; loops until the AI stops asking.
  async function submitDraft(answersSoFar) {
    setIsDrafting(true);
    setDraftError(null);
    const { data, error: apiError } = await draftSummary({
      transcript: transcript.trim(),
      answers: answersSoFar,
    });
    setIsDrafting(false);

    if (apiError) {
      setDraftError("We couldn't put your words together just now. Please try again.");
      return;
    }
    if (data.needsClarification) {
      setQuestions(data.questions);
      setQuestionIndex(0);
      setAnswerText('');
      setStep('clarify');
      return;
    }
    onContinue({ transcript: transcript.trim(), summaryText: data.summaryText });
  }

  function handleContinue() {
    if (step === 'capture') {
      submitDraft(answers);
      return;
    }
    // Record the current answer, then either show the next question or send
    // the whole round back to the AI.
    const updatedAnswers = [
      ...answers,
      { question: questions[questionIndex], answer: answerText.trim() },
    ];
    setAnswers(updatedAnswers);
    setAnswerText('');
    if (questionIndex + 1 < questions.length) {
      setQuestionIndex(questionIndex + 1);
    } else {
      submitDraft(updatedAnswers);
    }
  }

  // While listening, show committed text + the live interim guess so words
  // appear as they're spoken. When idle, show just the committed text.
  const displayedText = isListening
    ? currentText + (interimText ? `${currentText ? ' ' : ''}${interimText}` : '')
    : currentText;

  // Status line under the Speak button (aria-live announces it to
  // screen readers without stealing focus).
  let status = '';
  if (isDrafting) status = 'One moment — putting your words together…';
  else if (isListening) status = 'Listening…';
  else if (draftError) status = draftError;
  else if (error) status = error;

  return (
    <main className="recording-page">
      {onBack && (
        <button type="button" className="recording-page__back" onClick={onBack}>
          &larr; Back
        </button>
      )}

      {step === 'capture' ? (
        <h1 className="recording-page__heading">Tell us what&rsquo;s going on</h1>
      ) : (
        <>
          <h1 className="recording-page__heading">One more question</h1>
          <p className="recording-page__question">{questions[questionIndex]}</p>
        </>
      )}

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
            disabled={isDrafting}
          >
            <span className="recording-page__speak-icon" aria-hidden="true">
              {isListening ? '■' : '🎙'}
            </span>
            {isListening ? 'Stop' : 'Speak'}
          </button>
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

      <p className="recording-page__status" role="status" aria-live="polite">
        {status}
      </p>

      {/* The textarea IS the edit surface — words stream in live while
          listening (read-only so incoming results can't clobber an edit),
          then it becomes fully editable the moment recording stops. */}
      <label className="recording-page__label" htmlFor="transcript">
        {step === 'capture' ? 'Your words:' : 'Your answer:'}
      </label>
      <textarea
        id="transcript"
        className="recording-page__transcript"
        value={displayedText}
        onChange={(e) => setCurrentText(e.target.value)}
        readOnly={isListening || isDrafting}
        rows={8}
        placeholder={
          speechAvailable
            ? 'Your words will show up here.'
            : 'Type what happened here.'
        }
      />

      {/* Disabled until there's something to send and nothing is in flight. */}
      <button
        type="button"
        className="recording-page__continue"
        onClick={handleContinue}
        disabled={!canContinue}
      >
        {isDrafting ? 'Working…' : 'Continue'}
      </button>
    </main>
  );
}
