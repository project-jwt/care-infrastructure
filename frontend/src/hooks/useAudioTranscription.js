// useAudioTranscription — record the mic with MediaRecorder, then send the
// clip to the backend to be transcribed (Deepgram). This is the fallback path
// for browsers where the Web Speech API doesn't work — above all iOS, where
// Safari's speech recognition is unreliable and Chrome/Firefox lack it
// entirely. MediaRecorder + getUserMedia, by contrast, work on iOS 14.3+.
//
// Interface mirrors useSpeechRecognition where it can, so RecordingPage can
// treat the two similarly:
//   isSupported    — MediaRecorder + getUserMedia available
//   isRecording    — mic actively capturing
//   isTranscribing — clip uploaded, waiting on the transcript
//   micDenied      — user blocked the mic (permanent fallback to typing)
//   error          — plain-language message for recoverable problems
//   start()        — begin recording
//   stop(onResult) — stop, upload, then onResult(transcript) once it's back

import { useEffect, useRef, useState } from 'react';
import { transcribeAudio } from '../adapters/summaries-adapters';

const isSupported =
  typeof window !== 'undefined' &&
  typeof MediaRecorder !== 'undefined' &&
  !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

export default function useAudioTranscription() {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [micDenied, setMicDenied] = useState(false);
  const [error, setError] = useState(null);

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const onResultRef = useRef(null);

  // Release the mic so its indicator turns off and the device isn't held.
  function releaseStream() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }

  // Kill any live recording if the user navigates away mid-capture.
  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      releaseStream();
    };
  }, []);

  async function start() {
    if (!isSupported || isRecording) return;
    setError(null);

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      // NotAllowedError/SecurityError = blocked permission -> permanent
      // fallback to typing. Anything else is a recoverable "try again".
      if (e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')) {
        setMicDenied(true);
      } else {
        setError("We couldn't use your microphone. You can type instead.");
      }
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
    };

    // Fires after stop() — the final chunk is in by now. Assemble, release the
    // mic, then upload for transcription.
    recorder.onstop = async () => {
      releaseStream();
      const type = recorder.mimeType || (chunksRef.current[0] && chunksRef.current[0].type) || 'audio/webm';
      const blob = new Blob(chunksRef.current, { type });
      chunksRef.current = [];
      recorderRef.current = null;

      if (!blob.size) {
        setIsTranscribing(false);
        setError("We didn't catch any audio. Please try again, or type instead.");
        return;
      }

      const { data, error: apiError } = await transcribeAudio(blob);
      setIsTranscribing(false);
      if (apiError || !data) {
        setError("We couldn't turn your recording into words. You can type instead.");
        return;
      }
      const text = (data.transcript || '').trim();
      if (!text) {
        setError("We didn't catch any words. Please try again, or type instead.");
        return;
      }
      if (onResultRef.current) onResultRef.current(text);
    };

    recorderRef.current = recorder;
    recorder.start();
    setIsRecording(true);
  }

  function stop(onResult) {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;
    onResultRef.current = onResult;
    // Flip UI state up front, not from an event — the actual transcript
    // arrives asynchronously via onstop.
    setIsRecording(false);
    setIsTranscribing(true);
    recorder.stop();
  }

  return { isSupported, isRecording, isTranscribing, micDenied, error, start, stop };
}
