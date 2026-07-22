// ProfilePage — the account dashboard (spec §Account). One screen, reachable
// from the header for BOTH roles, exposing the account CRUD a user can perform
// on themselves:
//   Read   — name, email, role shown at the top
//   Update — edit name/email, and change password (PATCH /users/me)
//   Delete — password-confirmed, irreversible account deletion (DELETE /users/me)
//
// It owns only form state; the source-of-truth user lives in App and is
// refreshed via onUpdated after a successful save. onDeleted hands control back
// to App to clear the session. onBack returns to the previous screen.

import { useState } from 'react';
import { updateMe, deleteMe } from '../adapters/users-adapters';
import './ProfilePage.css';

const ROLE_LABELS = { primary: 'Primary account', contact: 'Trusted contact' };

export default function ProfilePage({ user, onUpdated, onBack, onDeleted }) {
  // --- Update: name + email ---
  const [fullName, setFullName] = useState(user.fullName);
  const [email, setEmail] = useState(user.email);
  const [savingDetails, setSavingDetails] = useState(false);
  const [detailsStatus, setDetailsStatus] = useState(null); // { ok, message }

  // --- Update: password (separate form; never prefilled) ---
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordStatus, setPasswordStatus] = useState(null);

  // --- Delete: two-step, password-confirmed ---
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const handleDetailsSave = async (event) => {
    event.preventDefault();
    // Only send what actually changed, so PATCHing the name never re-submits
    // (and re-validates) an unchanged email.
    const fields = {};
    if (fullName !== user.fullName) fields.fullName = fullName;
    if (email !== user.email) fields.email = email;
    if (Object.keys(fields).length === 0) {
      setDetailsStatus({ ok: true, message: 'Nothing to update.' });
      return;
    }

    setSavingDetails(true);
    setDetailsStatus(null);
    const { data, error } = await updateMe(fields);
    setSavingDetails(false);

    if (error) {
      // e.g. 409 "Email already registered"
      setDetailsStatus({ ok: false, message: error.message });
      return;
    }
    onUpdated(data); // lift the fresh user up so App stays in sync
    setDetailsStatus({ ok: true, message: 'Saved.' });
  };

  const handlePasswordSave = async (event) => {
    event.preventDefault();
    if (newPassword.length < 8) {
      setPasswordStatus({ ok: false, message: 'Password must be at least 8 characters.' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordStatus({ ok: false, message: 'The two passwords don’t match.' });
      return;
    }

    setSavingPassword(true);
    setPasswordStatus(null);
    const { error } = await updateMe({ password: newPassword });
    setSavingPassword(false);

    if (error) {
      setPasswordStatus({ ok: false, message: error.message });
      return;
    }
    setNewPassword('');
    setConfirmPassword('');
    setPasswordStatus({ ok: true, message: 'Password updated.' });
  };

  const handleDelete = async (event) => {
    event.preventDefault();
    setDeleting(true);
    setDeleteError(null);
    const { error } = await deleteMe(deletePassword);
    setDeleting(false);

    if (error) {
      // 403 "Incorrect password" is the expected case; anything else shows
      // its own message too.
      setDeleteError(error.message);
      return;
    }
    onDeleted(); // App clears the token and returns to the logged-out screen
  };

  return (
    <main className="profile">
      <button type="button" className="profile__back" onClick={onBack}>
        &larr; Back
      </button>

      <h1 className="profile__heading">Your account</h1>

      {/* Read: current account at a glance */}
      <section className="profile__card" aria-labelledby="profile-account-h">
        <h2 id="profile-account-h" className="profile__card-title">Account</h2>
        <dl className="profile__facts">
          <div className="profile__fact">
            <dt>Name</dt>
            <dd>{user.fullName}</dd>
          </div>
          <div className="profile__fact">
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div className="profile__fact">
            <dt>Account type</dt>
            <dd>{ROLE_LABELS[user.role] ?? user.role}</dd>
          </div>
        </dl>
      </section>

      {/* Update: name + email */}
      <section className="profile__card" aria-labelledby="profile-details-h">
        <h2 id="profile-details-h" className="profile__card-title">Edit details</h2>
        <form className="profile__form" onSubmit={handleDetailsSave}>
          <label className="profile__label">
            Full name
            <input
              className="profile__input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              required
            />
          </label>
          <label className="profile__label">
            Email
            <input
              className="profile__input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <button type="submit" className="profile__save" disabled={savingDetails}>
            {savingDetails ? 'Saving…' : 'Save changes'}
          </button>
          {detailsStatus && (
            <p
              className={detailsStatus.ok ? 'profile__status' : 'profile__status profile__status--error'}
              role={detailsStatus.ok ? 'status' : 'alert'}
            >
              {detailsStatus.message}
            </p>
          )}
        </form>
      </section>

      {/* Update: password */}
      <section className="profile__card" aria-labelledby="profile-pw-h">
        <h2 id="profile-pw-h" className="profile__card-title">Change password</h2>
        <form className="profile__form" onSubmit={handlePasswordSave}>
          <label className="profile__label">
            New password
            <input
              className="profile__input"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <label className="profile__label">
            Confirm new password
            <input
              className="profile__input"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <button type="submit" className="profile__save" disabled={savingPassword}>
            {savingPassword ? 'Updating…' : 'Update password'}
          </button>
          {passwordStatus && (
            <p
              className={passwordStatus.ok ? 'profile__status' : 'profile__status profile__status--error'}
              role={passwordStatus.ok ? 'status' : 'alert'}
            >
              {passwordStatus.message}
            </p>
          )}
        </form>
      </section>

      {/* Delete: irreversible, password-confirmed */}
      <section className="profile__card profile__card--danger" aria-labelledby="profile-danger-h">
        <h2 id="profile-danger-h" className="profile__card-title">Delete account</h2>
        <p className="profile__danger-note">
          This permanently deletes your account and everything in it. It cannot
          be undone.
        </p>

        {!deleteOpen ? (
          <button
            type="button"
            className="profile__danger-btn"
            onClick={() => setDeleteOpen(true)}
          >
            Delete my account
          </button>
        ) : (
          <form className="profile__form" onSubmit={handleDelete}>
            <label className="profile__label">
              Enter your password to confirm
              <input
                className="profile__input"
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                autoComplete="current-password"
                required
                autoFocus
              />
            </label>
            {deleteError && (
              <p className="profile__status profile__status--error" role="alert">
                {deleteError}
              </p>
            )}
            <div className="profile__danger-actions">
              <button
                type="button"
                className="profile__cancel"
                onClick={() => {
                  setDeleteOpen(false);
                  setDeletePassword('');
                  setDeleteError(null);
                }}
                disabled={deleting}
              >
                Cancel
              </button>
              <button type="submit" className="profile__danger-btn" disabled={deleting}>
                {deleting ? 'Deleting…' : 'Permanently delete'}
              </button>
            </div>
          </form>
        )}
      </section>
    </main>
  );
}
