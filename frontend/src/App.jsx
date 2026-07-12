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
import RecordingPage from './components/RecordingPage';
import SummaryReview from './components/SummaryReview';
import ChooseAction from './components/ChooseAction';
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
  // Carried from the recording step to the review step (speak → review flow):
  // the raw transcript and the AI-drafted summary the user will edit/approve.
  const [transcript, setTranscript] = useState('');
  const [summaryText, setSummaryText] = useState('');
  // The summary the choose-action step will send (what /:id/send needs).
  // Set on save (review step) or from History's send button; cleared when
  // the user navigates out of the flow so no stale id lingers.
  const [savedSummaryId, setSavedSummaryId] = useState(null);
  // True while ChooseAction has a send in flight — freezes BottomNav so the
  // request's outcome can't be lost to a mid-send navigation.
  const [navLocked, setNavLocked] = useState(false);

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

  // The one navigation path handed to child screens: leaving for anywhere
  // but the choose-action flow drops the pending summary id, so no stale id
  // lingers behind a later visit.
  const navigate = (next) => {
    if (next !== 'choose-action') setSavedSummaryId(null);
    setView(next);
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

  // The speak → review → choose-action flow hands per-flow state between
  // steps (transcript, then the saved summary's id), which the uniform VIEWS
  // map (user/onNavigate only) can't express — so those three screens render
  // explicitly instead of living in the map.
  let primaryScreen;
  if (view === 'recording') {
    primaryScreen = (
      <RecordingPage
        onBack={() => setView('home')}
        onContinue={({ transcript: nextTranscript, summaryText: nextSummary }) => {
          setTranscript(nextTranscript);
          setSummaryText(nextSummary);
          setView('review');
        }}
      />
    );
  } else if (view === 'review') {
    primaryScreen = (
      <SummaryReview
        user={user}
        transcript={transcript}
        summaryText={summaryText}
        onSaved={(id) => {
          setSavedSummaryId(id);
          setView('choose-action');
        }}
        onNavigate={navigate}
      />
    );
  } else if (view === 'choose-action' && savedSummaryId != null) {
    // The null guard is defensive: a refresh mid-flow resets view to 'home'
    // anyway, and the saved summary is always waiting under History.
    primaryScreen = (
      <ChooseAction
        summaryId={savedSummaryId}
        onNavigate={navigate}
        onBusyChange={setNavLocked}
      />
    );
  } else {
    primaryScreen = (
      <CurrentView
        user={user}
        onNavigate={navigate}
        // History's per-summary send button re-enters the choose-action
        // flow with that summary's id (ignored by the other views).
        onSendSummary={(id) => {
          setSavedSummaryId(id);
          setView('choose-action');
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">J.W.T</span>
        <button type="button" onClick={handleLogout}>Log out</button>
      </header>

      <div className="app-content">
        {/* Contacts get one read-only screen; primaries get the view switcher. */}
        {isPrimary ? primaryScreen : <ContactDashboard user={user} />}
      </div>

      {isPrimary && <BottomNav active={view} onNavigate={navigate} disabled={navLocked} />}
    </div>
  );
}
