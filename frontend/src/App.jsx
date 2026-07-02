// TODO: top-level auth state + role-based routing.
// - Check for an existing JWT in localStorage on mount, call getMe.
// - If unauthenticated, render <LoginRegisterPage />.
// - If role === 'primary', render the primary flow (Home / Recording / Review / etc.).
// - If role === 'contact', render <ContactDashboard />.

export default function App() {
  return <div>TODO: App</div>;
}
