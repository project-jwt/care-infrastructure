// Bottom navigation — Speak plus the three flows. The wireframe capped the
// nav at 3 items (History, Contacts, Helpline); the team added the landing
// tab as a 4th so users always have a visible way back (spec design-rule
// deviation, agreed 2026-07-14). The landing view ('home') is now the
// speak/record screen, so the tab reads "Speak". Shown only to primary
// users; the contact view is a single screen. props: active = current view
// name, onNavigate(view) = App's view setter, disabled = freeze all items (a
// request is in flight on the current screen, and navigating away would lose
// its outcome).

const NAV_ITEMS = [
  { view: 'home', label: 'Speak' },
  { view: 'history', label: 'History' },
  { view: 'contacts', label: 'Contacts' },
  { view: 'helpline', label: 'Helpline' },
];

export default function BottomNav({ active, onNavigate, disabled = false }) {
  return (
    <nav className="bottom-nav">
      {NAV_ITEMS.map(({ view, label }) => (
        <button
          key={view}
          type="button"
          className={active === view ? 'active' : ''}
          onClick={() => onNavigate(view)}
          disabled={disabled}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
