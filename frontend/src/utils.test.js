// Tests for displayName — the nickname/name/email fallback chain.
//
// The email fallback exists because an INVITED contact has no fullName: they
// haven't registered, so nobody has typed their name. Without it, an invite
// with no nickname renders as an empty row.
//
// Run: npm test (node --test, no framework needed)

import test from 'node:test';
import assert from 'node:assert/strict';
import { displayName } from './utils.js';

test('prefers the nickname the primary chose', () => {
  assert.equal(
    displayName({ nickname: 'Mom', fullName: 'Eleanor P.', email: 'e@x.com' }),
    'Mom'
  );
});

test('falls back to the registered full name', () => {
  assert.equal(
    displayName({ nickname: null, fullName: 'Eleanor P.', email: 'e@x.com' }),
    'Eleanor P.'
  );
});

test('falls back to the email for an invited contact with no nickname', () => {
  assert.equal(
    displayName({ status: 'invited', nickname: null, fullName: null, email: 'e@x.com' }),
    'e@x.com'
  );
});

test('an invited contact with a nickname still shows the nickname', () => {
  assert.equal(
    displayName({ status: 'invited', nickname: 'Kid', fullName: null, email: 'e@x.com' }),
    'Kid'
  );
});
