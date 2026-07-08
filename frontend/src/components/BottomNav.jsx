// Bottom navigation — exactly 3 items per the wireframe (History, Contacts,
// Helpline). Shown only to primary users; the contact view is a single screen.
// props: active = current view name, onNavigate(view) = App's view setter.

const NAV_ITEMS = [
  { view: 'history', label: 'History' },
  { view: 'contacts', label: 'Contacts' },
  { view: 'helpline', label: 'Helpline' },
];

export default function BottomNav({ active, onNavigate }) {
  return (
    <nav className="bottom-nav">
      {NAV_ITEMS.map(({ view, label }) => (
        <button
          key={view}
          type="button"
          className={active === view ? 'active' : ''}
          onClick={() => onNavigate(view)}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
