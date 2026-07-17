// Tests for isMobileDevice — the routing switch that sends phones/tablets to
// the record-and-transcribe speech path (mobile Web Speech implementations
// ignore continuous mode and drop undelivered words on abort).
//
// Run: npm test (node --test, no framework needed)

import test from 'node:test';
import assert from 'node:assert/strict';
import { isMobileDevice } from './device.js';

const IPHONE_SAFARI =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const ANDROID_CHROME =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36';
const MAC_CHROME =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const WINDOWS_CHROME =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
// iPadOS 13+ masquerades as desktop Safari; only maxTouchPoints reveals it.
const IPAD_DESKTOP_MODE =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15';

test('iPhone Safari is mobile', () => {
  assert.equal(isMobileDevice({ userAgent: IPHONE_SAFARI, maxTouchPoints: 5 }), true);
});

test('Android Chrome is mobile', () => {
  assert.equal(isMobileDevice({ userAgent: ANDROID_CHROME, maxTouchPoints: 5 }), true);
});

test('desktop Mac Chrome is not mobile', () => {
  assert.equal(isMobileDevice({ userAgent: MAC_CHROME, maxTouchPoints: 0 }), false);
});

test('desktop Windows Chrome is not mobile', () => {
  assert.equal(isMobileDevice({ userAgent: WINDOWS_CHROME, maxTouchPoints: 0 }), false);
});

test('iPad in desktop mode (Mac UA + touch screen) is mobile', () => {
  assert.equal(isMobileDevice({ userAgent: IPAD_DESKTOP_MODE, maxTouchPoints: 5 }), true);
});

test('no navigator (SSR) is not mobile', () => {
  assert.equal(isMobileDevice(undefined), false);
});
