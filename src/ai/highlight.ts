/**
 * highlight.ts — Spotlight overlay for guiding the user to a UI element.
 *
 * Finds `[data-ai-id="<aiId>"]`, scrolls it into view, and draws a fixed-
 * position pulsing ring (plus an optional floating note). The plain overlay
 * never intercepts pointer events and auto-dismisses on any click, Escape,
 * history navigation, or after 15 s.
 *
 * `activateTarget` extends the spotlight with a cancellable countdown that
 * ends in a synthetic click on the user's behalf (guided-teaching mode).
 */

const SPOTLIGHT_ID = 'xfaos-ai-spotlight'
const STYLE_ID = 'xfaos-ai-spotlight-style'
const AUTO_CLEAR_MS = 15_000
const PADDING_PX = 6

let teardownActive: (() => void) | null = null

/** CSS.escape with a conservative fallback for very old engines. */
function escapeSelector(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value)
  }
  return value.replace(/["\\\]]/g, '\\$&')
}

/** Inject the spotlight + pulse styles exactly once. */
function ensureStyles(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
#${SPOTLIGHT_ID} {
  position: fixed;
  pointer-events: none;
  z-index: 8999;
  border: 2px solid #6366f1;
  border-radius: 12px;
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15), 0 0 24px rgba(99, 102, 241, 0.45);
  animation: xfaos-ai-pulse 1.6s ease-in-out infinite;
  transition: top 120ms ease-out, left 120ms ease-out, width 120ms ease-out, height 120ms ease-out;
}
@keyframes xfaos-ai-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.16), 0 0 18px rgba(99, 102, 241, 0.35); }
  50%      { box-shadow: 0 0 0 7px rgba(99, 102, 241, 0.28), 0 0 32px rgba(99, 102, 241, 0.55); }
}
#${SPOTLIGHT_ID} .xfaos-ai-note {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  top: calc(100% + 8px);
  background: #4f46e5;
  color: #ffffff;
  font: 12px/1.4 var(--font-sans, system-ui, sans-serif);
  padding: 4px 10px;
  border-radius: 8px;
  white-space: nowrap;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
}
#${SPOTLIGHT_ID} .xfaos-ai-note--above { top: auto; bottom: calc(100% + 8px); }
#${SPOTLIGHT_ID} .xfaos-ai-note--row { display: flex; align-items: center; gap: 8px; }
#${SPOTLIGHT_ID} .xfaos-ai-cancel {
  pointer-events: auto;
  cursor: pointer;
  background: #ffffff;
  color: #4f46e5;
  border: none;
  border-radius: 8px;
  font: 600 12px/1.4 var(--font-sans, system-ui, sans-serif);
  padding: 3px 10px;
  white-space: nowrap;
}
#${SPOTLIGHT_ID} .xfaos-ai-cancel:hover { background: #eef2ff; }
  `
  document.head.appendChild(style)
}

/** Remove the overlay and all its listeners (also cancels a pending activation). */
export function clearHighlight(): void {
  if (cancelActivation) {
    const cancel = cancelActivation
    cancelActivation = null
    cancel()
  }
  if (teardownActive) {
    teardownActive()
    teardownActive = null
  }
  document.getElementById(SPOTLIGHT_ID)?.remove()
}

/**
 * Spotlight the element annotated with `data-ai-id="<aiId>"`.
 *
 * @returns true when a target was found and spotlit, false otherwise.
 */
export function highlightTarget(aiId: string, note?: string): boolean {
  clearHighlight()

  if (!aiId) return false
  const target = document.querySelector(`[data-ai-id="${escapeSelector(aiId)}"]`)
  if (!(target instanceof HTMLElement)) return false

  ensureStyles()

  const overlay = document.createElement('div')
  overlay.id = SPOTLIGHT_ID
  if (note) {
    const label = document.createElement('span')
    label.className = 'xfaos-ai-note'
    label.textContent = note
    overlay.appendChild(label)
  }
  document.body.appendChild(overlay)

  const position = (): void => {
    const rect = target.getBoundingClientRect()
    if (rect.width === 0 && rect.height === 0) return
    overlay.style.left = `${rect.left - PADDING_PX}px`
    overlay.style.top = `${rect.top - PADDING_PX}px`
    overlay.style.width = `${rect.width + 2 * PADDING_PX}px`
    overlay.style.height = `${rect.height + 2 * PADDING_PX}px`
    // Keep the note inside the viewport (flip above the ring near the bottom).
    const noteEl = overlay.querySelector('.xfaos-ai-note')
    if (noteEl) {
      const flip = rect.bottom + 48 > window.innerHeight
      noteEl.classList.toggle('xfaos-ai-note--above', flip)
    }
  }

  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  position()

  const onAnyClick = (): void => clearHighlight()
  const onKeydown = (event: KeyboardEvent): void => {
    if (event.key === 'Escape') clearHighlight()
  }
  document.addEventListener('click', onAnyClick, { capture: true })
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('popstate', onAnyClick)
  window.addEventListener('hashchange', onAnyClick)
  window.addEventListener('scroll', position, { passive: true })
  window.addEventListener('resize', position)
  const timer = window.setTimeout(clearHighlight, AUTO_CLEAR_MS)

  teardownActive = () => {
    window.clearTimeout(timer)
    document.removeEventListener('click', onAnyClick, { capture: true })
    document.removeEventListener('keydown', onKeydown)
    window.removeEventListener('popstate', onAnyClick)
    window.removeEventListener('hashchange', onAnyClick)
    window.removeEventListener('scroll', position)
    window.removeEventListener('resize', position)
  }

  return true
}

// ── Activate (highlight + cancellable countdown + auto-click) ────────────────

export type ActivateOutcome = 'clicked' | 'cancelled' | 'no-target' | 'disabled'

export interface ActivateTargetOptions {
  /** Countdown before the auto-click, ms (default 3000). */
  delayMs?: number
  /** Localized bubble note (also used as the plain note when disabled). */
  note?: string
  /** Localized countdown bubble text for the remaining seconds. */
  countdown?: (secondsRemaining: number) => string
}

/** Cancels a pending auto-click activation, if any (resolves it 'cancelled'). */
let cancelActivation: (() => void) | null = null

/**
 * Spotlight a `data-ai-id` target and, after a visible cancellable countdown,
 * click it on the user's behalf. Disabled targets are spotlit but never
 * clicked; any user interaction (click, Escape, navigation) cancels.
 * 聚光目标并在可取消的倒计时后代为点击；禁用目标只高亮不点击。
 */
export function activateTarget(
  aiId: string,
  opts: ActivateTargetOptions = {}
): Promise<ActivateOutcome> {
  clearHighlight()

  return new Promise<ActivateOutcome>((resolve) => {
    if (!aiId) {
      resolve('no-target')
      return
    }
    const target = document.querySelector(`[data-ai-id="${escapeSelector(aiId)}"]`)
    if (!(target instanceof HTMLElement)) {
      resolve('no-target')
      return
    }

    const disabled =
      (target instanceof HTMLButtonElement && target.disabled) ||
      target.getAttribute('aria-disabled') === 'true'
    if (disabled) {
      highlightTarget(aiId, opts.note)
      resolve('disabled')
      return
    }

    ensureStyles()

    const overlay = document.createElement('div')
    overlay.id = SPOTLIGHT_ID
    const note = document.createElement('span')
    note.className = 'xfaos-ai-note xfaos-ai-note--row'
    const label = document.createElement('span')
    note.appendChild(label)
    const cancelBtn = document.createElement('button')
    cancelBtn.type = 'button'
    cancelBtn.className = 'xfaos-ai-cancel'
    note.appendChild(cancelBtn)
    overlay.appendChild(note)
    document.body.appendChild(overlay)

    const delayMs = opts.delayMs ?? 3000
    let remaining = Math.max(1, Math.ceil(delayMs / 1000))

    const renderLabel = (): void => {
      label.textContent = opts.countdown ? opts.countdown(remaining) : String(remaining)
    }

    const position = (): void => {
      const rect = target.getBoundingClientRect()
      if (rect.width === 0 && rect.height === 0) return
      overlay.style.left = `${rect.left - PADDING_PX}px`
      overlay.style.top = `${rect.top - PADDING_PX}px`
      overlay.style.width = `${rect.width + 2 * PADDING_PX}px`
      overlay.style.height = `${rect.height + 2 * PADDING_PX}px`
      const flip = rect.bottom + 48 > window.innerHeight
      note.classList.toggle('xfaos-ai-note--above', flip)
    }

    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    renderLabel()
    position()

    let settled = false
    let ticker = 0

    const finish = (outcome: ActivateOutcome): void => {
      if (settled) return
      settled = true
      cancelActivation = null
      window.clearInterval(ticker)
      document.removeEventListener('click', onAnyClick, { capture: true })
      document.removeEventListener('keydown', onKeydown)
      window.removeEventListener('popstate', onNav)
      window.removeEventListener('hashchange', onNav)
      window.removeEventListener('scroll', position)
      window.removeEventListener('resize', position)
      overlay.remove()
      resolve(outcome)
    }

    const onCancelClick = (event: MouseEvent): void => {
      event.stopPropagation()
      finish('cancelled')
    }
    const onAnyClick = (): void => finish('cancelled')
    const onKeydown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') finish('cancelled')
    }
    const onNav = (): void => finish('cancelled')

    cancelBtn.addEventListener('click', onCancelClick)
    document.addEventListener('click', onAnyClick, { capture: true })
    document.addEventListener('keydown', onKeydown)
    window.addEventListener('popstate', onNav)
    window.addEventListener('hashchange', onNav)
    window.addEventListener('scroll', position, { passive: true })
    window.addEventListener('resize', position)

    cancelActivation = () => finish('cancelled')

    ticker = window.setInterval(() => {
      remaining -= 1
      if (remaining <= 0) {
        // Detach listeners BEFORE the synthetic click so it is not treated
        // as a user cancellation. / 先摘监听再合成点击，避免误判为取消。
        finish('clicked')
        target.click()
        return
      }
      renderLabel()
      position()
    }, Math.max(250, Math.round(delayMs / Math.max(1, Math.ceil(delayMs / 1000)))))
  })
}
