// RecordingPage — speech-to-text capture + clarifying-question loop
// (spec §MVP 2).
//
// Flow: the user speaks (or types) their problem, Continue sends the
// transcript to POST /api/summaries/draft. If the AI needs more detail it
// returns questions — each is asked one at a time using the same speak/type
// input — and the answers are sent back with the transcript until the AI
// returns a finished summary, which is handed up through onContinue.
//
// Two ways to speak, chosen per device (see inputMode below):
//   'live'   — the browser's Web Speech API (desktop Chrome, Android): the
//              words stream in as you talk, free and instant.
//   'record' — record the mic and transcribe server-side (iOS, where the Web
//              Speech API is unreliable/absent): you speak, then the words
//              appear once the recording is transcribed.
//   'type'   — no working mic path: the textarea is the only input.
//
// Props:
//   onContinue({ transcript, summaryText }) — required; called when the AI
//                                             summary is ready (review step).
//   onBack()                                — optional; renders a back button.

import { useState } from 'react';
import useSpeechRecognition from '../hooks/useSpeechRecognition';
import useAudioTranscription from '../hooks/useAudioTranscription';
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

  // Two input engines; which one this device uses is decided below.
  const speech = useSpeechRecognition();
  const audio = useAudioTranscription();

  // Prefer the live Web Speech API where it works. Only fall to recording when
  // it doesn't (iOS) — that keeps the free, instant path on the browsers that
  // support it and spends a transcription call only where it's actually needed.
  const speechLive = speech.isSupported && !speech.micDenied;
  const canRecord = !speechLive && audio.isSupported && !audio.micDenied;
  const inputMode = speechLive ? 'live' : canRecord ? 'record' : 'type';

  const isCapturing = speech.isListening || audio.isRecording; // mic is hot
  const isTranscribing = audio.isTranscribing; // clip uploaded, words pending

  // The same textarea serves both steps — it edits the transcript while
  // capturing and the current answer while clarifying.
  const currentText = step === 'capture' ? transcript : answerText;
  const setCurrentText = step === 'capture' ? setTranscript : setAnswerText;

  const canContinue =
    !isCapturing && !isTranscribing && !isDrafting && currentText.trim().length > 0;

  // Append (with a space) rather than replace, so each spoken phrase adds to
  // what's already there.
  const appendText = (finalText) =>
    setCurrentText((t) => (t ? `${t} ` : '') + finalText);

  // The one primary mic action: start when idle, stop when active. Routes to
  // whichever engine this device is using.
  function handleMicClick() {
    if (inputMode === 'live') {
      if (speech.isListening) speech.stop();
      else speech.start(appendText);
    } else if (inputMode === 'record') {
      if (audio.isRecording) audio.stop(appendText);
      else audio.start();
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

  // In live mode, show committed text + the live interim guess so words appear
  // as they're spoken. Recording mode has no interim stream — the words arrive
  // all at once after transcription — so it just shows the committed text.
  const displayedText =
    speech.isListening && speech.interimText
      ? `${currentText}${currentText ? ' ' : ''}${speech.interimText}`
      : currentText;

  // Status line under the mic button (aria-live announces it to screen readers
  // without stealing focus).
  let status = '';
  if (isDrafting) status = 'One moment — putting your words together…';
  else if (isTranscribing) status = 'Turning your recording into words…';
  else if (speech.isListening) status = 'Listening…';
  else if (audio.isRecording) status = 'Recording… press Stop when you finish.';
  else if (draftError) status = draftError;
  else if (speech.error) status = speech.error;
  else if (audio.error) status = audio.error;

  // Mic button copy differs per engine: 'Speak' streams live; 'Record' captures
  // then transcribes on Stop.
  const micIdleLabel = inputMode === 'record' ? 'Record' : 'Speak';
  const busy = isDrafting || isTranscribing;

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

      {inputMode !== 'type' ? (
        <>
          <p className="recording-page__hint">
            Press the button and speak. You can fix the words after.
          </p>
          {/* The one primary action on this screen (design rules). */}
          <button
            type="button"
            className={`recording-page__speak${isCapturing ? ' recording-page__speak--listening' : ''}`}
            onClick={handleMicClick}
            aria-pressed={isCapturing}
            disabled={busy}
          >
            <span className="recording-page__speak-icon" aria-hidden="true">
              {isCapturing ? '■' : '🎙'}
            </span>
            {isCapturing ? 'Stop' : micIdleLabel}
          </button>
        </>
      ) : (
        // Plain-language fallback notice — calm, no jargon, no blame.
        <p className="recording-page__fallback-notice">
          {speech.micDenied || audio.micDenied
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
          then it becomes fully editable the moment capture stops. */}
      <label className="recording-page__label" htmlFor="transcript">
        {step === 'capture' ? 'Your words:' : 'Your answer:'}
      </label>
      <textarea
        id="transcript"
        className="recording-page__transcript"
        value={displayedText}
        onChange={(e) => setCurrentText(e.target.value)}
        readOnly={isCapturing || isTranscribing || isDrafting}
        rows={8}
        placeholder={
          inputMode === 'type'
            ? 'Type what happened here.'
            : 'Your words will show up here.'
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
