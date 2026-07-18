// SetupTutorial — first-login walkthrough (spec §MVP 6). Renders as a fixed
// overlay on top of the real home screen so the highlight ring and arrows
// point at the actual buttons, not mockups. App shows it while
// user.hasCompletedSetup is false; "Get started" calls markSetupComplete()
// and App flips the flag locally, so it never shows again.
//
// No Skip/Escape dismissal on purpose: the tour is seven short steps, and a
// dismissed-but-incomplete state would only re-show it next login anyway.
// props: onComplete() = App's callback that flips hasCompletedSetup locally.

import { useLayoutEffect, useRef, useState } from 'react';
import { markSetupComplete } from '../adapters/users-adapters';
import './SetupTutorial.css';

// Each step highlights one real element (target = CSS selector) or none
// (target = null → centered card over a full dim). The three flow steps point
// at the home screen's big shortcut buttons rather than the small nav tabs —
// the tour teaches the targets the 65+ audience will actually tap. Steps may
// also carry a label: among the target's matches, the button whose text
// equals the label wins, so reordering FLOWS can't silently repoint a step.
const STEPS = [
  {
    id: 'welcome',
    target: null,
    title: 'Welcome to J.W.T',
    body: 'This app helps you share how you’re doing with the people who care about you. Let’s take a quick look around.',
  },
  {
    id: 'speak',
    target: '.primary-home__speak',
    placement: 'below',
    title: 'Tell us what’s going on',
    body: 'Tap the big Speak Now button and just talk. The app listens and writes a short summary you can check before sharing.',
  },
  {
    id: 'history',
    target: '.primary-home__flow',
    label: 'Past Summaries',
    placement: 'above',
    title: 'Look back anytime',
    body: 'Tap Past Summaries to read the updates you’ve shared before.',
  },
  {
    id: 'contacts',
    target: '.primary-home__flow',
    label: 'Trusted Contacts',
    placement: 'above',
    title: 'Your trusted people',
    body: 'Tap Trusted Contacts to see the family and friends who receive your updates.',
  },
  {
    id: 'helpline',
    target: '.primary-home__flow',
    label: 'Helpline',
    placement: 'above',
    title: 'Help is always here',
    body: 'If you ever need to talk to someone right away, tap Helpline.',
  },
  {
    id: 'nav',
    target: '.bottom-nav',
    placement: 'above',
    title: 'Find your way around',
    body: 'This bar stays with you on every screen. Tap Home any time to come back here.',
  },
  {
    id: 'finish',
    target: null,
    title: 'You’re all set',
    body: 'That’s everything. You won’t see this tour again.',
  },
];

// The element a step points at: first match of its selector, or — when the
// step has a label — the match whose visible text equals it.
const findTarget = (step) => {
  if (!step.target) return null;
  const matches = [...document.querySelectorAll(step.target)];
  if (step.label) {
    return matches.find((el) => el.textContent.trim() === step.label) ?? null;
  }
  return matches[0] ?? null;
};

const HIGHLIGHT_PAD = 6; // px the ring extends past the target on each side
const CARD_GAP = 20; // px between the target and the card (arrow lives here)

export default function SetupTutorial({ onComplete }) {
  const [stepIndex, setStepIndex] = useState(0);
  // Viewport rect of the current step's target; null = no target found, so
  // the card centers over a plain dim and the tour stays completable even
  // if a selector stops matching.
  const [rect, setRect] = useState(null);
  const [saving, setSaving] = useState(false);
  const cardRef = useRef(null);
  const nextButtonRef = useRef(null);

  const step = STEPS[stepIndex];
  const isLast = stepIndex === STEPS.length - 1;

  useLayoutEffect(() => {
    const measure = () => {
      const el = findTarget(step);
      setRect(el ? el.getBoundingClientRect() : null);
    };
    measure();
    // Moving focus into the freshly-labelled dialog also announces the new
    // step to screen readers, so no aria-live region is needed.
    nextButtonRef.current?.focus();
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true); // .app-content can scroll on short viewports
    return () => {
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [step]);

  const finish = async () => {
    setSaving(true); // disables the button — no double PATCH
    const { error } = await markSetupComplete();
    // Close even on error: the flag just stays false and the tour re-shows
    // next login, which beats leaving the user stuck on an undismissable modal.
    if (error) console.error('Could not save setup completion:', error);
    onComplete();
  };

  // Both targets (home buttons, bottom nav) and the card render in viewport
  // coordinates, so getBoundingClientRect maps straight to position: fixed.
  let highlightStyle;
  let cardStyle;
  let placement = 'center';
  if (rect) {
    placement = step.placement;
    highlightStyle = {
      top: rect.top - HIGHLIGHT_PAD,
      left: rect.left - HIGHLIGHT_PAD,
      width: rect.width + HIGHLIGHT_PAD * 2,
      height: rect.height + HIGHLIGHT_PAD * 2,
    };
    // The card is inset 16px each side and capped at 420px, centered — mirror
    // that math to aim the arrow at the target's center, clamped onto the card.
    const cardWidth = Math.min(420, window.innerWidth - 32);
    const cardLeft = (window.innerWidth - cardWidth) / 2;
    const arrowX = Math.min(
      Math.max(rect.left + rect.width / 2 - cardLeft, 24),
      cardWidth - 24,
    );
    cardStyle = { '--arrow-x': `${arrowX}px` };
    if (placement === 'below') {
      cardStyle.top = rect.bottom + CARD_GAP;
    } else {
      cardStyle.bottom = window.innerHeight - rect.top + CARD_GAP;
    }
  }

  // Minimal focus trap: Tab wraps across the card's two buttons. The overlay
  // already blocks pointer events everywhere else.
  const trapFocus = (event) => {
    if (event.key !== 'Tab') return;
    const buttons = cardRef.current.querySelectorAll('button:not(:disabled)');
    const first = buttons[0];
    const last = buttons[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="tutorial-overlay">
      {rect ? (
        <div className="tutorial-highlight" style={highlightStyle} />
      ) : (
        <div className="tutorial-scrim" />
      )}

      <div
        ref={cardRef}
        className={`tutorial-card tutorial-card--${placement}`}
        style={cardStyle}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tutorial-title"
        onKeyDown={trapFocus}
      >
        <h2 className="tutorial-title" id="tutorial-title">{step.title}</h2>
        <p className="tutorial-body">{step.body}</p>
        <p className="tutorial-progress">
          Step {stepIndex + 1} of {STEPS.length}
        </p>
        <div className="tutorial-buttons">
          {stepIndex > 0 && (
            <button
              type="button"
              onClick={() => setStepIndex((i) => i - 1)}
              disabled={saving}
            >
              Back
            </button>
          )}
          <button
            type="button"
            className="tutorial-next"
            ref={nextButtonRef}
            onClick={isLast ? finish : () => setStepIndex((i) => i + 1)}
            disabled={saving}
          >
            {isLast ? 'Get started' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
}
