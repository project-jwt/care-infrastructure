// Tiny display helpers shared across screens — one home so the sender and
// the recipient never render the same fact two different ways.

// "2026-07-09T23:09:50Z" -> "July 9, 2026" — plain dates, no timestamps.
export const formatDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

// What we call a person: their nickname if one was set, else their registered
// full name, else their email — an INVITED contact has no fullName yet, so
// without the last step a nickname-less invite renders as a blank row.
export const displayName = (c) => c.nickname || c.fullName || c.email;

// GET /api/contacts returns two row shapes in one list, told apart by `status`:
// an "active" row is a real link (linkId/contactId/fullName set), an "invited"
// row is a pending invitation (inviteId/invitedAt set, the others null).
export const isInvited = (c) => c.status === 'invited';

// A stable React key for either shape. Neither id alone is safe: an invited
// row's linkId is null (so every invite would collide on the same null key and
// React would mis-reconcile them), and the two ids come from independent
// sequences, so a link and an invite can share a number. Prefixing keeps them
// in separate namespaces.
export const rowKey = (c) => (isInvited(c) ? `i${c.inviteId}` : `l${c.linkId}`);
