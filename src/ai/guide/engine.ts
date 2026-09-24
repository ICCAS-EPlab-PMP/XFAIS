/**
 * engine.ts — Guided-teaching engine for the AI assistant.
 *
 * Runs one GuideDefinition against the live workspace-state bridge: presents
 * each step (bilingual tip + spotlight), watches the snapshot to detect
 * completion, auto-advances, and — for `autoClick` steps gated by confidence
 * and the user's master toggle — fires the cancellable countdown click.
 * Step definitions themselves are the auto-click allowlist; destructive ids
 * are hard-blocked as a second guard.
 * 逐步教学引擎：对照状态桥推进步骤；自动代点受置信度与总开关双重门控。
 */

import { nextTick, ref, watch, type Ref } from 'vue'
import { useWorkspaceSnapshots, workspaceSnapshotOf } from '@/lib/workspace-state'
import { globalT } from '@/i18n'
import { currentLocale, navTitle } from '../context'
import { activateTarget, clearHighlight, highlightTarget } from '../highlight'
import type { GuideDefinition, GuideStep } from './types'

/** Confidence gates per provider before auto-clicking on the user's behalf. */
const AUTOCLICK_MIN_CONFIDENCE: Record<string, number> = { jev: 0.75, rules: 0.85 }
/** Destructive-ish ids that must never be auto-clicked regardless of defs. */
const AUTOCLICK_BLOCKED = /:(cancel|clear|delete|remove|stop|reset|close)/i

const AUTOCLICK_KEY = 'xfaos.ai.autoClick'
const TEACHING_KEY = 'xfaos.ai.teaching'

export function autoClickEnabled(): boolean {
  try {
    return localStorage.getItem(AUTOCLICK_KEY) !== '0'
  } catch {
    return true
  }
}

export function setAutoClickEnabled(value: boolean): void {
  try {
    localStorage.setItem(AUTOCLICK_KEY, value ? '1' : '0')
  } catch {
    /* best-effort */
  }
}

/** Teaching mode: navigation to a guided page auto-offers/starts the tour. */
export function teachingEnabled(): boolean {
  try {
    return localStorage.getItem(TEACHING_KEY) !== '0'
  } catch {
    return true
  }
}

export function setTeachingEnabled(value: boolean): void {
  try {
    localStorage.setItem(TEACHING_KEY, value ? '1' : '0')
  } catch {
    /* best-effort */
  }
}

export interface GuideEngineDeps {
  /** Speak one line into the assistant transcript. */
  say: (text: string) => void
  /** Called whenever guide lifecycle state changes (bar re-renders). */
  onChange: () => void
  /** Optional handler for step `action` markers (e.g. apply-template). */
  onStepAction?: (action: NonNullable<GuideStep['action']>, step: GuideStep) => void
}

const pick = (bi: { zh: string; en: string }): string =>
  currentLocale() === 'en' ? bi.en : bi.zh

export function createGuideEngine(guides: Record<string, GuideDefinition>, deps: GuideEngineDeps) {
  const snapshots = useWorkspaceSnapshots()

  const activeRoute = ref<string | null>(null)
  const stepIndex = ref(0)
  const totalSteps = ref(0)
  const currentTitle = ref('')

  let stopWatcher: (() => void) | null = null
  let stopped = false

  const isActive = (): boolean => activeRoute.value !== null

  const snapshot = () =>
    activeRoute.value ? workspaceSnapshotOf(activeRoute.value) : null

  const stepOf = (index: number): string =>
    globalT('ai.guide.stepOf', { current: index + 1, total: totalSteps.value })

  /** Announce + spotlight the current step; arm the countdown when allowed. */
  const presentStep = (): void => {
    const routeName = activeRoute.value
    if (!routeName) return
    const guide = guides[routeName]
    if (!guide) return
    const snap = snapshot()

    // Fast-forward steps whose goal is already satisfied.
    while (stepIndex.value < guide.steps.length && guide.steps[stepIndex.value].done(snap)) {
      stepIndex.value += 1
    }
    if (stepIndex.value >= guide.steps.length) {
      finishGuide()
      return
    }

    const step = guide.steps[stepIndex.value]
    currentTitle.value = pick(step.title)
    deps.onChange()

    if (step.action) deps.onStepAction?.(step.action, step)

    deps.say(`${stepOf(stepIndex.value)} ${pick(step.title)} — ${pick(step.tip)}`)

    if (!step.aiId) return
    if (step.autoClick && autoClickEnabled() && !AUTOCLICK_BLOCKED.test(step.aiId)) {
      void armAutoClick(step, snap)
    } else {
      highlightTarget(step.aiId, pick(step.title))
    }
  }

  /** Confidence gate → countdown click, or plain spotlight when gated out. */
  const armAutoClick = (step: GuideStep, snap: ReturnType<typeof snapshot>): void => {
    const minConfidence = AUTOCLICK_MIN_CONFIDENCE[confidenceProvider] ?? 1
    const gateOk =
      confidenceValue >= minConfidence && (step.allowWhen ? step.allowWhen(snap) : true)
    if (!gateOk) {
      highlightTarget(step.aiId ?? '', pick(step.title))
      return
    }
    void activateTarget(step.aiId ?? '', {
      note: pick(step.title),
      countdown: (seconds) => globalT('ai.guide.countingDown', { seconds: String(seconds) }),
    }).then((outcome) => {
      if (stopped) return
      if (outcome === 'clicked') {
        deps.say(globalT('ai.guide.clicked'))
        // The workspace watcher picks up the resulting state change; nudge it
        // for targets whose effect is instant (e.g. opening a file dialog).
        void nextTick(() => recheck())
      } else if (outcome === 'cancelled') {
        deps.say(globalT('ai.guide.cancelled'))
      }
      // 'disabled' / 'no-target': stay put; the user acts manually.
    })
  }

  /** Re-evaluate the current step against the latest snapshot. */
  const recheck = (): void => {
    const routeName = activeRoute.value
    if (!routeName) return
    const guide = guides[routeName]
    if (!guide) return
    const snap = snapshot()
    if (stepIndex.value < guide.steps.length && guide.steps[stepIndex.value].done(snap)) {
      const doneTitle = pick(guide.steps[stepIndex.value].title)
      deps.say(globalT('ai.guide.stepDone', { title: doneTitle }))
      stepIndex.value += 1
      clearHighlight()
      void nextTick(() => presentStep())
    }
  }

  const finishGuide = (): void => {
    deps.say(globalT('ai.guide.done'))
    teardown()
  }

  const teardown = (): void => {
    stopped = true
    stopWatcher?.()
    stopWatcher = null
    activeRoute.value = null
    currentTitle.value = ''
    totalSteps.value = 0
    clearHighlight()
    deps.onChange()
  }

  let confidenceValue = 0
  let confidenceProvider = 'rules'

  /**
   * Start a guided tour for a route. `confidence`/`provider` come from the
   * decision that led here and gate the auto-click countdown.
   */
  const start = (routeName: string, confidence: number, provider: string): void => {
    stopWatcher?.()
    stopped = false
    confidenceValue = confidence
    confidenceProvider = provider
    const guide = guides[routeName]
    if (!guide) return
    activeRoute.value = routeName
    stepIndex.value = 0
    totalSteps.value = guide.steps.length
    currentTitle.value = pick(guide.title)
    deps.say(globalT('ai.guide.started', { name: navTitle(routeName) }))
    deps.onChange()

    stopWatcher = watch(
      () => (activeRoute.value ? snapshots[activeRoute.value] : undefined),
      () => {
        if (!stopped) recheck()
      },
      { deep: true }
    )

    void nextTick(() => presentStep())
  }

  /** User pressed "skip": advance past the current step. */
  const skip = (): void => {
    const routeName = activeRoute.value
    if (!routeName) return
    const guide = guides[routeName]
    if (!guide) return
    stepIndex.value += 1
    clearHighlight()
    if (stepIndex.value >= guide.steps.length) {
      finishGuide()
      return
    }
    void nextTick(() => presentStep())
  }

  /** User ended the tour or navigated away. */
  const stop = (): void => {
    stopped = true
    teardown()
  }

  return {
    activeRoute,
    stepIndex,
    totalSteps,
    currentTitle,
    isActive,
    start,
    skip,
    stop,
  }
}

export type GuideEngine = ReturnType<typeof createGuideEngine>
