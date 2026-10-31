import { useEffect } from 'react';

/**
 * One tooltip layer for the whole app.
 *
 * Any element with `data-tip="..."` gets a tooltip. Existing `title`
 * attributes and icon-only buttons with an `aria-label` get one too, so the
 * browser's native tooltip never shows. Optional `data-tip-side` (top, bottom,
 * left, right) on the element or an ancestor picks the preferred side.
 *
 * The tooltip is a single element appended to <body> with `position: fixed`
 * and the highest z-index, so cards, table cells, scroll areas, dialogs, and
 * overflow-hidden columns can never clip or cover it. It flips to the
 * opposite side when there is no room and clamps to the viewport, and it ignores the pointer so it never blocks
 * clicks.
 */

const SHOW_DELAY_MS = 450;
// After one tooltip has been shown, moving to a neighbour shows instantly.
const SKIP_DELAY_WINDOW_MS = 400;
const GAP = 8;
const EDGE = 8;

const TIP_SELECTOR = [
  '[data-tip]',
  '[title]',
  '[data-tip-native]',
  'button[aria-label]',
  'a[aria-label]',
  '[role="button"][aria-label]',
  '[role="tab"][aria-label]',
  '[role="combobox"][aria-label]',
].join(',');

function visibleText(el: Element): string {
  return (el.textContent ?? '').replace(/\s+/g, ' ').trim().toLowerCase();
}

/** Moves a native `title` into `data-tip-native` so the browser tooltip never appears. */
function absorbTitle(el: HTMLElement) {
  const title = el.getAttribute('title');
  if (title === null) return;
  el.removeAttribute('title');
  if (!title.trim()) return;
  el.setAttribute('data-tip-native', title);
  // Keep the accessible name the title used to provide for icon-only controls.
  if (!el.hasAttribute('aria-label') && !el.hasAttribute('aria-labelledby') && !visibleText(el)) {
    el.setAttribute('aria-label', title);
  }
}

function tipFor(el: HTMLElement): string | null {
  if (el.closest('[data-tip-off]')) return null;
  absorbTitle(el);
  const explicit = el.getAttribute('data-tip');
  if (explicit !== null) return explicit.trim() || null;
  const native = el.getAttribute('data-tip-native');
  if (native?.trim()) return native.trim();
  const label = el.getAttribute('aria-label')?.trim();
  // aria-label is only a tooltip for icon-only controls; otherwise it repeats the visible text.
  if (label && !visibleText(el)) return label;
  return null;
}

function findTarget(start: EventTarget | null): { el: HTMLElement; text: string } | null {
  let node = start instanceof Element ? start : null;
  while (node) {
    const candidate = node.closest<HTMLElement>(TIP_SELECTOR);
    if (!candidate) return null;
    const text = tipFor(candidate);
    if (text) return { el: candidate, text };
    node = candidate.parentElement;
  }
  return null;
}

/**
 * Disabled buttons use `pointer-events: none`, so the pointer lands on their
 * container instead. Find a disabled control with a tooltip under the pointer.
 */
function findDisabledAt(container: EventTarget | null, x: number, y: number) {
  if (!(container instanceof Element)) return null;
  const disabled = container.querySelectorAll<HTMLElement>(
    'button:disabled, [aria-disabled="true"], [data-disabled]',
  );
  for (const el of disabled) {
    const r = el.getBoundingClientRect();
    if (x < r.left || x > r.right || y < r.top || y > r.bottom) continue;
    const text = tipFor(el);
    if (text) return { el, text };
  }
  return null;
}

export function GlobalTooltips() {
  useEffect(() => {
    const tip = document.createElement('div');
    tip.className = 'studio-tooltip';
    tip.setAttribute('role', 'tooltip');
    tip.id = 'studio-tooltip';
    const body = document.createElement('div');
    body.className = 'studio-tooltip__body';
    const arrow = document.createElement('div');
    arrow.className = 'studio-tooltip__arrow';
    tip.append(body, arrow);
    document.body.appendChild(tip);

    let current: HTMLElement | null = null;
    let showTimer: number | undefined;
    let lastHiddenAt = 0;
    let visible = false;

    const place = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      const vw = document.documentElement.clientWidth;
      const vh = document.documentElement.clientHeight;
      tip.style.left = '0px';
      tip.style.top = '0px';
      const { width: w, height: h } = tip.getBoundingClientRect();
      const preferred = el.closest('[data-tip-side]')?.getAttribute('data-tip-side') ?? 'top';

      const room = {
        top: r.top - GAP - EDGE,
        bottom: vh - r.bottom - GAP - EDGE,
        left: r.left - GAP - EDGE,
        right: vw - r.right - GAP - EDGE,
      };
      const fits = (side: string) =>
        side === 'top' || side === 'bottom' ? room[side] >= h : room[side as 'left' | 'right'] >= w;
      const opposite: Record<string, string> = {
        top: 'bottom',
        bottom: 'top',
        left: 'right',
        right: 'left',
      };
      let side = preferred in opposite ? preferred : 'top';
      if (!fits(side)) {
        side =
          [opposite[side], 'top', 'bottom'].find(fits) ??
          (room.top > room.bottom ? 'top' : 'bottom');
      }

      let left: number;
      let top: number;
      if (side === 'top' || side === 'bottom') {
        const center = r.left + r.width / 2;
        left = Math.max(EDGE, Math.min(center - w / 2, vw - w - EDGE));
        top = side === 'bottom' ? r.bottom + GAP : r.top - GAP - h;
        top = Math.max(EDGE, Math.min(top, vh - h - EDGE));
        arrow.style.top = '';
        arrow.style.left = `${Math.round(Math.max(10, Math.min(center - left, w - 10)))}px`;
      } else {
        const middle = r.top + r.height / 2;
        top = Math.max(EDGE, Math.min(middle - h / 2, vh - h - EDGE));
        left = side === 'right' ? r.right + GAP : r.left - GAP - w;
        arrow.style.left = '';
        arrow.style.top = `${Math.round(Math.max(10, Math.min(middle - top, h - 10)))}px`;
      }

      tip.style.left = `${Math.round(left)}px`;
      tip.style.top = `${Math.round(top)}px`;
      tip.dataset.side = side;
    };

    const show = (el: HTMLElement, text: string) => {
      current = el;
      body.textContent = text;
      tip.dataset.open = 'true';
      visible = true;
      place(el);
      el.setAttribute('aria-describedby', tip.id);
    };

    const hide = () => {
      window.clearTimeout(showTimer);
      if (current?.getAttribute('aria-describedby') === tip.id) {
        current.removeAttribute('aria-describedby');
      }
      if (visible) lastHiddenAt = performance.now();
      visible = false;
      current = null;
      delete tip.dataset.open;
    };

    const schedule = (el: HTMLElement, text: string) => {
      if (el === current) return;
      hide();
      current = el;
      const instant = performance.now() - lastHiddenAt < SKIP_DELAY_WINDOW_MS;
      showTimer = window.setTimeout(
        () => {
          if (current === el && el.isConnected) show(el, text);
        },
        instant ? 0 : SHOW_DELAY_MS,
      );
    };

    const resolve = (event: PointerEvent) =>
      findDisabledAt(event.target, event.clientX, event.clientY) ?? findTarget(event.target);

    const onPointerOver = (event: PointerEvent) => {
      if (event.pointerType === 'touch') return;
      const found = resolve(event);
      if (!found) {
        if (current) hide();
        return;
      }
      schedule(found.el, found.text);
    };

    // Moving within one container can cross onto or off a disabled control without a pointerover.
    let moveFrame = 0;
    const onPointerMove = (event: PointerEvent) => {
      if (event.pointerType === 'touch' || moveFrame) return;
      moveFrame = requestAnimationFrame(() => {
        moveFrame = 0;
        const found = resolve(event);
        if (found) schedule(found.el, found.text);
        else if (current && !current.contains(event.target as Node)) hide();
      });
    };

    const onPointerOut = (event: PointerEvent) => {
      if (!current) return;
      const next = event.relatedTarget;
      if (next instanceof Node && current.contains(next)) return;
      // A disabled control doesn't receive the pointer; its container does.
      if (
        next instanceof Element &&
        findDisabledAt(next, event.clientX, event.clientY)?.el === current
      )
        return;
      hide();
    };

    const onFocusIn = (event: FocusEvent) => {
      const target = event.target;
      if (!(target instanceof HTMLElement) || !target.matches(':focus-visible')) return;
      const found = findTarget(target);
      if (found) schedule(found.el, found.text);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') hide();
    };

    // A modal or menu opening, or content scrolling under the pointer, ends the hover.
    const onDismiss = () => hide();

    document.addEventListener('pointerover', onPointerOver, true);
    document.addEventListener('pointermove', onPointerMove, true);
    document.addEventListener('pointerout', onPointerOut, true);
    document.addEventListener('focusin', onFocusIn, true);
    document.addEventListener('focusout', onDismiss, true);
    document.addEventListener('pointerdown', onDismiss, true);
    document.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('scroll', onDismiss, true);
    document.addEventListener('wheel', onDismiss, { capture: true, passive: true });
    window.addEventListener('resize', onDismiss);
    window.addEventListener('blur', onDismiss);

    // An element removed while hovered (for example a row that was deleted) takes its tooltip with it.
    const watchdog = window.setInterval(() => {
      if (visible && current && !current.isConnected) hide();
    }, 500);

    return () => {
      hide();
      window.clearInterval(watchdog);
      cancelAnimationFrame(moveFrame);
      document.removeEventListener('pointerover', onPointerOver, true);
      document.removeEventListener('pointermove', onPointerMove, true);
      document.removeEventListener('pointerout', onPointerOut, true);
      document.removeEventListener('focusin', onFocusIn, true);
      document.removeEventListener('focusout', onDismiss, true);
      document.removeEventListener('pointerdown', onDismiss, true);
      document.removeEventListener('keydown', onKeyDown, true);
      document.removeEventListener('scroll', onDismiss, true);
      document.removeEventListener('wheel', onDismiss, true);
      window.removeEventListener('resize', onDismiss);
      window.removeEventListener('blur', onDismiss);
      tip.remove();
    };
  }, []);

  return null;
}
