// isMobileDevice — should this device avoid the live Web Speech path?
//
// Mobile browsers ship a Web Speech API that looks usable (the constructor
// exists) but breaks the assumptions the live path depends on: continuous
// mode is ignored (the session ends at the first pause — Chromium #40324711,
// and iOS behaves the same), and results are often delivered only after the
// session ends, so aborting on Stop discards the user's words. On these
// devices RecordingPage prefers the record-and-transcribe path instead.
//
// Takes the navigator (or a stand-in for tests); defaults to the global one.

export function isMobileDevice(
  nav = typeof navigator !== 'undefined' ? navigator : undefined,
) {
  if (!nav) return false;
  const ua = nav.userAgent || '';
  if (/iPhone|iPad|iPod|Android/i.test(ua)) return true;
  // iPadOS 13+ reports a desktop Mac UA; a Mac with a multi-touch screen
  // is an iPad.
  if (/Macintosh/i.test(ua) && (nav.maxTouchPoints || 0) > 1) return true;
  return false;
}
