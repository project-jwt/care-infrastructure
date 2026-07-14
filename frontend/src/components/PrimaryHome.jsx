// Primary user's home — big-button screen per the wireframe (spec §MVP 2).
// Speak Now is the single dominant action (starts the speak → review flow);
// below it, one big button into each of the three BottomNav flows.
// props: user = logged-in user, onNavigate(view) = App's view setter.

import './PrimaryHome.css';

// Same views BottomNav points at, but as full-width on-screen buttons —
// easier targets for the 65+ audience than the small fixed nav alone.
const FLOWS = [
  { view: 'history', label: 'Past Summaries' },
  { view: 'contacts', label: 'Trusted Contacts' },
  { view: 'helpline', label: 'Helpline' },
];

export default function PrimaryHome({ user, onNavigate }) {
  const firstName = user?.fullName?.trim().split(/\s+/)[0];

  return (
    <main className="primary-home">
      <h1 className="primary-home__heading">
        {firstName ? `Welcome, ${firstName}` : 'Welcome'}
      </h1>
      <p className="primary-home__hint">
        Press the button and tell us what&rsquo;s going on.
      </p>

      <button
        type="button"
        className="primary-home__speak"
        onClick={() => onNavigate('recording')}
      >
        Speak Now
      </button>

      {/* Labelled so screen readers can tell these apart from the bottom nav. */}
      <nav className="primary-home__flows" aria-label="Home shortcuts">
        {FLOWS.map(({ view, label }) => (
          <button
            key={view}
            type="button"
            className="primary-home__flow"
            onClick={() => onNavigate(view)}
          >
            {label}
          </button>
        ))}
      </nav>
    </main>
  );
}
