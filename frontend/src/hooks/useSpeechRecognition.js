// useSpeechRecognition — wraps the browser Web Speech API behind a small
// React hook so RecordingPage stays pure UI.
//
// Behavior:
//   lang 'en-US', continuous: true, interimResults: true. continuous:true keeps
//   the session open across natural pauses — it ends only when the user presses
//   Stop (or a safety cap), instead of cutting off the moment they take a breath.
//
// Returned shape:
//   isSupported  — false when the browser has no SpeechRecognition (e.g. Firefox)
//   isListening  — true while the mic is actively capturing
//   interimText  — in-progress words, updated live as the user speaks
//   micDenied    — true once the user blocks mic permission (permanent fallback)
//   error        — plain-language message for recoverable problems
//   start(onFinal) — begin listening; onFinal(text) fires with each committed phrase
//   stop()       — end the session; commits whatever was said, even mid-phrase

import { useEffect, useRef, useState } from 'react';

// Chrome/Safari still ship this API under the `webkit` prefix.
const SpeechRecognitionImpl =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : undefined;

// Safety cap on one recording so a mic left hot (user walked away without
// pressing Stop) can't run forever. Generous enough not to cut off someone
// describing a problem; the trailing words are committed before it fires.
const MAX_RECORDING_MS = 90000;

export default function useSpeechRecognition() {
  const isSupported = Boolean(SpeechRecognitionImpl);

  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [micDenied, setMicDenied] = useState(false);
  const [error, setError] = useState(null);

  // Holds the active recognition instance between renders.
  const recognitionRef = useRef(null);
  // Watchdog timer (see MAX_RECORDING_MS) — also the iOS freeze guard, since a
  // session that never fires onend can't leave the UI stuck once this resets it.
  const timeoutRef = useRef(null);
  // The onFinal callback and the latest not-yet-finalized interim words, so
  // stop() can commit what the user was mid-saying instead of dropping it.
  const onFinalRef = useRef(null);
  const pendingInterimRef = useRef('');

  // Force the UI back to idle. Called from stop(), the watchdog, onerror, and
  // onend — NOT only from onend, because iOS Safari often never fires onend,
  // which used to leave isListening stuck true forever.
  function resetToIdle() {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsListening(false);
    setInterimText('');
  }

  // Commit any trailing interim words the browser hasn't finalized yet. Clears
  // the ref so it's idempotent — it can never double-commit the same words,
  // no matter how many of stop()/watchdog/onerror/onend call it.
  function commitPendingInterim() {
    const pending = pendingInterimRef.current.trim();
    pendingInterimRef.current = '';
    if (pending && onFinalRef.current) onFinalRef.current(pending);
  }

  // If the user leaves the page mid-recording, kill the session so the mic
  // doesn't stay hot. abort() (vs stop()) discards pending results.
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (recognitionRef.current) recognitionRef.current.abort();
    };
  }, []);

  // Safari misbehaves when a recognition instance is restarted, so each
  // start() builds a fresh one instead of reusing.
  function start(onFinal) {
    if (!isSupported || isListening) return;
    onFinalRef.current = onFinal;
    pendingInterimRef.current = '';

    const recognition = new SpeechRecognitionImpl();
    recognition.lang = 'en-US';
    recognition.continuous = true;      // ride through pauses; the user ends it
    recognition.interimResults = true;

    // Fires repeatedly while speaking. Finalized phrases commit immediately;
    // the interim tail is stashed so stop() can commit it too.
    recognition.onresult = (event) => {
      let finalText = '';
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) finalText += result[0].transcript;
        else interim += result[0].transcript;
      }
      // Final and interim are disjoint segments (interim is the tail past the
      // finalized ones), so committing both never overlaps.
      if (finalText && onFinalRef.current) onFinalRef.current(finalText.trim());
      pendingInterimRef.current = interim;
      setInterimText(interim);
    };

    // Map browser error codes to plain-language messages (design rule:
    // no jargon). Only a permission block flips the page into fallback mode.
    recognition.onerror = (event) => {
      if (recognitionRef.current !== recognition) return; // superseded session
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setMicDenied(true);
      } else if (event.error === 'no-speech') {
        setError("We didn't hear anything. Try again.");
      } else if (event.error === 'audio-capture') {
        setError("We couldn't find a microphone on this device.");
      } else if (event.error !== 'aborted') {
        setError('Something went wrong with the microphone. You can type instead.');
      }
      commitPendingInterim(); // don't lose words to an error mid-speech
      resetToIdle();
    };

    recognition.onend = () => {
      if (recognitionRef.current !== recognition) return; // a newer session won
      recognitionRef.current = null;
      commitPendingInterim(); // safety if the browser ends on its own
      resetToIdle();
    };

    // Re-entry safety: with the optimistic resetToIdle() in stop(), isListening
    // can be false while an old session is still alive. Abort it before
    // starting a fresh one so we never double-capture.
    if (recognitionRef.current) recognitionRef.current.abort();
    recognitionRef.current = recognition;
    setError(null);
    setIsListening(true);
    recognition.start();

    timeoutRef.current = setTimeout(() => {
      commitPendingInterim();
      if (recognitionRef.current) recognitionRef.current.abort();
      resetToIdle();
    }, MAX_RECORDING_MS);
  }

  // Commit the trailing interim ourselves, THEN abort (not stop) so the browser
  // doesn't also finalize the same words and double them. This is what saves
  // what the user said when they press Stop mid-phrase.
  function stop() {
    commitPendingInterim();
    if (recognitionRef.current) recognitionRef.current.abort();
    resetToIdle();
  }

  return { isSupported, isListening, interimText, micDenied, error, start, stop };
}
