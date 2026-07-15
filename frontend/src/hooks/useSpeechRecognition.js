// useSpeechRecognition — wraps the browser Web Speech API behind a small
// React hook so RecordingPage stays pure UI.
//
// Spec values (Part II — Core Technologies):
//   lang: 'en-US', continuous: false, interimResults: true
//
// Returned shape:
//   isSupported  — false when the browser has no SpeechRecognition (e.g. Firefox)
//   isListening  — true while the mic is actively capturing
//   interimText  — in-progress words, updated live as the user speaks
//   micDenied    — true once the user blocks mic permission (permanent fallback)
//   error        — plain-language message for recoverable problems (no speech, no mic)
//   start(onFinal) — begin listening; onFinal(text) fires with each finalized phrase
//   stop()       — end the session manually (browser also auto-ends after a pause)

import { useEffect, useRef, useState } from 'react';

// Chrome/Safari still ship this API under the `webkit` prefix.
const SpeechRecognitionImpl =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : undefined;

export default function useSpeechRecognition() {
  const isSupported = Boolean(SpeechRecognitionImpl);

  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [micDenied, setMicDenied] = useState(false);
  const [error, setError] = useState(null);

  // Holds the active recognition instance between renders.
  const recognitionRef = useRef(null);
  // Watchdog timer: iOS Safari can leave a session open with no onend/onresult
  // ever firing, which would freeze the whole screen (the UI gates on
  // isListening). This forces the UI back to idle after a hard cap.
  const timeoutRef = useRef(null);

  // Force the UI back to idle. Called from stop(), onerror, and the watchdog —
  // NOT only from onend, because iOS Safari often never fires onend after a
  // stop() or an error, which used to leave isListening stuck true forever.
  function resetToIdle() {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsListening(false);
    setInterimText('');
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

    const recognition = new SpeechRecognitionImpl();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = true;

    // Fires repeatedly while speaking. Results split into two buckets:
    // finalized phrases (committed to the transcript via onFinal) and
    // interim guesses (shown live, replaced on every event).
    recognition.onresult = (event) => {
      let finalText = '';
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      if (finalText) onFinal(finalText.trim());
      setInterimText(interim);
    };

    // Map browser error codes to plain-language messages (design rule:
    // no jargon). Only a permission block flips the page into fallback mode.
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setMicDenied(true);
      } else if (event.error === 'no-speech') {
        setError("We didn't hear anything. Try again.");
      } else if (event.error === 'audio-capture') {
        setError("We couldn't find a microphone on this device.");
      } else if (event.error !== 'aborted') {
        setError('Something went wrong with the microphone. You can type instead.');
      }
      // Always free the UI on error — iOS Safari may not fire onend afterwards.
      resetToIdle();
    };

    // With continuous: false the browser ends the session on its own after a
    // pause in speech — this handler resets the UI whether the user pressed
    // Stop or simply stopped talking.
    recognition.onend = () => {
      recognitionRef.current = null;
      resetToIdle();
    };

    // Re-entry safety: with the optimistic resetToIdle() in stop(), isListening
    // can be false while an old iOS session is still alive. Abort it before
    // starting a fresh one so we never double-capture.
    if (recognitionRef.current) recognitionRef.current.abort();
    recognitionRef.current = recognition;
    setError(null);
    setIsListening(true);
    recognition.start();

    // Hard cap so a session that never ends on its own (iOS) can't freeze the
    // screen. onFinal has already committed any finalized phrases by then.
    timeoutRef.current = setTimeout(() => {
      if (recognitionRef.current) recognitionRef.current.abort();
      resetToIdle();
    }, 20000);
  }

  // stop() (not abort) so any phrase still being processed flushes through
  // onresult first. But free the UI immediately rather than waiting for onend —
  // on iOS Safari that event often never arrives, which left Stop unable to
  // end the session and froze the page.
  function stop() {
    if (recognitionRef.current) recognitionRef.current.stop();
    resetToIdle();
  }

  return { isSupported, isListening, interimText, micDenied, error, start, stop };
}
