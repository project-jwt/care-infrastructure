// Primary user's home — the single "Speak Now" action (spec §MVP 2).
// Kept deliberately minimal: the full home screen belongs to its own ticket;
// this just makes the speak → review flow reachable.
// props: onNavigate(view) = App's view setter (per the App shell convention).

export default function PrimaryHome({ onNavigate }) {
  return (
    <div className="home-page">
      <h1>Welcome</h1>
      <p>Press the button and tell us what&rsquo;s going on.</p>
      <button
        type="button"
        className="speak-now"
        onClick={() => onNavigate('recording')}
      >
        Speak Now
      </button>
    </div>
  );
}
