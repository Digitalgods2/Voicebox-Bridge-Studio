import { useCallback, useEffect, useRef, useState } from 'react';
import appLogo from '@/assets/app-logo.png';
import { cn } from '@/lib/utils/cn';

const SEEN_KEY = 'launch-screen-seen';
const LEAVE_MS = 600;

/** Whether this tab has already shown the launch screen (a page refresh skips it). */
export function launchScreenSeen(): boolean {
  try {
    return sessionStorage.getItem(SEEN_KEY) === '1';
  } catch {
    return false;
  }
}

function markLaunchScreenSeen() {
  try {
    sessionStorage.setItem(SEEN_KEY, '1');
  } catch {
    // Without storage the title card simply shows again after a refresh.
  }
}

/**
 * Full-window title card shown when the program launches: the emblem large in
 * the center, the app name set around it, and a prompt to continue.
 */
export function LaunchScreen({ onContinue }: { onContinue: () => void }) {
  const [leaving, setLeaving] = useState(false);
  const promptRef = useRef<HTMLButtonElement>(null);

  const dismiss = useCallback(() => {
    markLaunchScreenSeen();
    setLeaving(true);
  }, []);

  useEffect(() => {
    promptRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'Escape') {
        event.preventDefault();
        dismiss();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dismiss]);

  useEffect(() => {
    if (!leaving) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const timer = window.setTimeout(onContinue, reduceMotion ? 0 : LEAVE_MS);
    return () => window.clearTimeout(timer);
  }, [leaving, onContinue]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="VoiceBox Bridge Studio"
      className={cn(
        'launch-screen fixed inset-0 z-[100] flex flex-col items-center justify-center overflow-hidden select-none cursor-pointer',
        leaving && 'launch-screen-leave',
      )}
      onClick={dismiss}
      onKeyDown={(event) => event.key === 'Enter' && dismiss()}
    >
      <div className="launch-screen-glow" aria-hidden="true" />

      <img
        src={appLogo}
        alt=""
        draggable={false}
        className="launch-screen-logo relative object-contain"
        style={{ height: 'min(54vh, 72vw)', width: 'min(54vh, 72vw)' }}
      />

      <div className="launch-screen-title relative mt-4 flex flex-col items-center text-center">
        <h1
          className="launch-screen-gold font-normal uppercase leading-none"
          style={{ fontSize: 'clamp(2rem, 5.2vw, 4.5rem)', letterSpacing: '0.16em' }}
        >
          VoiceBox Bridge
        </h1>
        <div className="mt-3 flex items-center gap-4" style={{ width: 'min(36rem, 80vw)' }}>
          <span className="launch-screen-rule h-px flex-1" />
          <span
            className="launch-screen-gold uppercase"
            style={{ fontSize: 'clamp(0.95rem, 1.7vw, 1.45rem)', letterSpacing: '0.62em' }}
          >
            Studio
          </span>
          <span className="launch-screen-rule h-px flex-1" />
        </div>
      </div>

      <button
        ref={promptRef}
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          dismiss();
        }}
        className="launch-screen-prompt relative mt-10 rounded px-4 py-2 text-xs uppercase outline-none focus-visible:ring-1 focus-visible:ring-[#d9b26a]/60"
        style={{ letterSpacing: '0.42em' }}
      >
        Press Enter to continue
      </button>
    </div>
  );
}
