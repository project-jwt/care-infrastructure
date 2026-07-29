// Tests for displayName — the nickname/name/email fallback chain.
//
// The email fallback exists because an INVITED contact has no fullName: they
// haven't registered, so nobody has typed their name. Without it, an invite
// with no nickname renders as an empty row.
//
// Run: npm test (node --test, no framework needed)

import test from 'node:test';
import assert from 'node:assert/strict';
import { displayName, isInvited, rowKey } from './utils.js';

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

// isInvited / rowKey — shared by TrustedContactsList and ChooseAction, which
// both render the two-shape /api/contacts list.

test('isInvited tells the two row shapes apart', () => {
  assert.equal(isInvited({ status: 'invited' }), true);
  assert.equal(isInvited({ status: 'active' }), false);
});

test('rowKey namespaces the two id sequences so they cannot collide', () => {
  // A link and an invite can share a number — they come from separate
  // sequences — so the raw ids must not be used as keys directly.
  assert.notEqual(
    rowKey({ status: 'active', linkId: 7, inviteId: null }),
    rowKey({ status: 'invited', inviteId: 7, linkId: null })
  );
});

test('rowKey gives distinct keys to two invited rows', () => {
  // The bug this exists to prevent: an invited row's linkId is null, so keying
  // on linkId alone made every invite collide on the same null key.
  assert.notEqual(
    rowKey({ status: 'invited', inviteId: 1, linkId: null }),
    rowKey({ status: 'invited', inviteId: 2, linkId: null })
  );
});
