// App — top-level auth state + role-based view switching (no router; a
// `view` string decides which screen renders).
//
// How teammates plug a new screen in:
//   1. Add your component to the VIEWS map below with a view name.
//   2. Navigate to it from anywhere via the onNavigate prop (or BottomNav).
//   3. Need the logged-in user? Take it as a prop and pass it where App
//      renders your view.

import { useEffect, useState } from 'react';
import { getToken } from './adapters/fetch-helpers';
import { logout } from './adapters/auth-adapters';
import { getMe } from './adapters/users-adapters';
import LoginRegisterPage from './components/LoginRegisterPage';
import BottomNav from './components/BottomNav';
import PrimaryHome from './components/PrimaryHome';
import ContactDashboard from './components/ContactDashboard';
import PastSummaries from './components/PastSummaries';
import TrustedContactsList from './components/TrustedContactsList';
import HelplinePage from './components/HelplinePage';

// Primary user's screens, keyed by view name. BottomNav points at
// history/contacts/helpline; 'home' is the landing view after login.
const VIEWS = {
  home: PrimaryHome,
  history: PastSummaries,
  contacts: TrustedContactsList,
  helpline: HelplinePage,
};

export default function App() {
  const [user, setUser] = useState(null); // null = logged out
  const [checking, setChecking] = useState(true); // true while validating a stored token
  const [view, setView] = useState('home');

  // On first load: if a token survived a refresh, ask the backend who it
  // belongs to. Only an explicit rejection (401/403 = expired, forged, user
  // deleted) clears the token — a network blip or server error keeps it, so
  // a valid session isn't lost to a temporary outage.
  useEffect(() => {
    const restoreSession = async () => {
      if (!getToken()) {
        setChecking(false);
        return;
      }
      const { data, error } = await getMe();
      if (error) {
        if (error.status === 401 || error.status === 403) logout();
      } else {
        setUser(data);
      }
      setChecking(false);
    };
    restoreSession();
  }, []);

  const handleAuth = (loggedInUser) => {
    setUser(loggedInUser);
    setView('home');
  };

  const handleLogout = () => {
    logout(); // clears the stored token
    setUser(null);
    setView('home');
  };

  // Don't flash the login page while we're still checking the stored token.
  if (checking) return <div className="app-loading">Loading…</div>;

  if (!user) return <LoginRegisterPage onAuth={handleAuth} />;

  const isPrimary = user.role === 'primary';
  const CurrentView = VIEWS[view] ?? PrimaryHome;

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">J.W.T</span>
        <button type="button" onClick={handleLogout}>Log out</button>
      </header>

      <div className="app-content">
        {/* Contacts get one read-only screen; primaries get the view switcher. */}
        {isPrimary ? <CurrentView user={user} onNavigate={setView} /> : <ContactDashboard user={user} />}
      </div>

      {isPrimary && <BottomNav active={view} onNavigate={setView} />}
    </div>
  );
}
