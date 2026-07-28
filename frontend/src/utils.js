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
