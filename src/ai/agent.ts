/**
 * agent.ts — The AI assistant composable driving the agent flow.
 *
 * Phase 1 (intent → section → enter → guide or highlight → stop):
 *   user text → RouteDecision (Jev → rules). Confidence ≥ 0.5 navigates;
 *   when the target page has a guided tour and teaching applies, the guide
 *   engine takes over (step tips + spotlight + confidence-gated auto-click),
 *   otherwise the key control is spotlit and the user acts manually.
 * Phase 2 (PONI context → internal judgement → template + unit):
 *   on the 1D integration page, template-intent text + stored PONI file →
 *   poni_summary task (with system-pre-computed facts: Cu-target wavelength
 *   check, corner 2θ_max) → TemplateDecision (Jev judges BOTH template and
 *   radial unit in one round trip, seeing the module it is inside; rules
 *   decide offline: Cu+WAXS→2θ, SAXS→q_nm, other WAXS→q_A) →
 *   `xfaos:ai-apply-template` event (Integrate1dView applies it; the
 *   assistant stops there).
 *
 * Everything works offline: with no key configured the rules router answers.
 */

import { nextTick, ref, watch } from 'vue'
import router from '@/router'
import { globalT } from '@/i18n'
import { useTransport } from '@/lib/transport'
import { workspaceSnapshotOf } from '@/lib/workspace-state'
import { INTEGRATE_TEMPLATES, templateDetail } from '@/lib/templates'
import {
  AiProviderError,
  type ChoiceAnswer,
  type IntegrationUnitChoice,
  type PoniSummary,
  type RouteDecision,
  type TemplateDecision,
} from './types'
import { NAV_CATALOG, PONI_PATH_KEY, buildAppState, navEntry, navTitle } from './context'
import { highlightTarget } from './highlight'
import { decideRouteViaRules, decideTemplateViaRules, unitForTemplate, unitRuleReason } from './rules-router'
import { askTypesafeChoice, askTypesafeChoices } from './providers/typesafe'
import { createGuideEngine, teachingEnabled, type GuideEngine } from './guide/engine'
import { GUIDES, hasGuide } from './guide/registry'

// ── AI settings (read straight from the persisted settings blob) ─────────────

/** localStorage key the Settings module persists its reactive object to. */
const SETTINGS_KEY = 'xfaos.settings.v1'

export interface AiSettings {
  jevApiKey?: string
}

/**
 * Safe-read AI provider config from localStorage. The Settings UI (added in
 * parallel) persists under `xfaos.settings.v1`; tolerate several envelope
 * shapes ({ai:{...}} or {value:{ai:{...}}}) and never throw.
 */
export function getAiSettings(): AiSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return {}
    const root = parsed as Record<string, unknown>
    const holder =
      root.ai && typeof root.ai === 'object'
        ? root.ai
        : root.value && typeof root.value === 'object' && (root.value as Record<string, unknown>).ai
          ? (root.value as Record<string, unknown>).ai
          : null
    if (!holder || typeof holder !== 'object') return {}
    const ai = holder as Record<string, unknown>
    const str = (v: unknown): string | undefined =>
      typeof v === 'string' && v.trim().length > 0 ? v.trim() : undefined
    return {
      jevApiKey: str(ai.jevApiKey),
    }
  } catch {
    return {}
  }
}

// ── Shared agent types ────────────────────────────────────────────────────────

export type AgentState =
  | 'idle'
  | 'thinking'
  | 'suggest'
  | 'wait-user'
  | 'template-apply'
  | 'guide'
  | 'error'

export interface HistoryLine {
  role: 'user' | 'agent'
  text: string
}

export const APPLY_TEMPLATE_EVENT = 'xfaos:ai-apply-template'

const TEMPLATE_INTENT_RE = /常规|普通|standard|模板|template|waxs|saxs|giwaxs|广角|小角/i
/** Display names for the radial units the AI layer may apply. */
const UNIT_DISPLAY: Record<IntegrationUnitChoice, string> = {
  q_A: 'q (Å⁻¹)',
  q_nm: 'q (nm⁻¹)',
  '2th_deg': '2θ (deg)',
}
/** How many high-probability candidates the suggest list shows. */
const TOP_PICKS = 4
const HIGHLIGHT_DELAY_MS = 500
const PONI_TASK_TIMEOUT_MS = 20_000

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

const clamp01 = (v: number): number => Math.min(1, Math.max(0, v))

const describeError = (err: unknown): string => {
  const raw = err instanceof Error ? err.message : String(err)
  // Friendly mapping for the common "backend not reachable" case (e.g. the
  // dev renderer running without the Python service).
  // 常见"后端不可达"场景（如无 Python 服务的开发渲染层）的友好映射。
  if (/WebSocket|Still in CONNECTING|network|fetch/i.test(raw)) {
    return '无法连接 Python 服务，暂时无法计算 PONI 摘要 / Cannot reach the Python service — PONI summary unavailable right now'
  }
  return raw
}

// ── Composable ────────────────────────────────────────────────────────────────

/**
 * The assistant agent. Call once from a component setup (uses the transport
 * injection for the PONI summary task).
 */
export function useAiAgent() {
  const transport = useTransport()

  const state = ref<AgentState>('idle')
  const lastDecision = ref<RouteDecision | null>(null)
  const history = ref<HistoryLine[]>([])
  const topPicks = ref<Array<{ routeName: string; probability: number }>>([])
  const busy = ref(false)

  const say = (text: string): void => {
    history.value.push({ role: 'agent', text })
  }

  // ── Guided-teaching engine (per-agent instance) ───────────────────────────

  let guideEngine: GuideEngine
  guideEngine = createGuideEngine(GUIDES, {
    say,
    onChange: () => {
      if (guideEngine.isActive()) state.value = 'guide'
      else if (state.value === 'guide') state.value = 'idle'
    },
    onStepAction: (action) => {
      if (action === 'apply-template') void applyTemplateFromPoni('standard template for this sample')
    },
  })

  // Leaving the tour's route ends the tour (its snapshot goes stale anyway).
  watch(
    () => router.currentRoute.value.name,
    (name) => {
      if (guideEngine.isActive() && name !== guideEngine.activeRoute.value) guideEngine.stop()
    }
  )

  // ── Provider chain (Jev → rules) ──────────────────────────────────────────

  const routeViaJev = async (intent: string, ctx: ReturnType<typeof buildAppState>, key: string): Promise<RouteDecision> => {
    const answer: ChoiceAnswer = await askTypesafeChoice(
      {
        id: 'route',
        instructions: 'Which X-FAIS workspace route fits the user request best?',
        choices: NAV_CATALOG.map((e) => e.routeName),
        criteria: Object.fromEntries(
          NAV_CATALOG.map((e) => [e.routeName, `${e.zh} / ${e.en} (${e.path})`])
        ),
        state: { userRequest: intent, app: ctx },
      },
      key
    )
    const entry = navEntry(answer.choice)
    if (!entry) {
      throw new AiProviderError('bad_response', `Jev picked an unknown route: ${answer.choice}`)
    }
    const top = answer.probabilities
      ? Object.entries(answer.probabilities)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 4)
          .map(([routeName, probability]) => ({ routeName, probability }))
      : [{ routeName: entry.routeName, probability: answer.confidence }]
    return {
      routeName: entry.routeName,
      path: entry.path,
      confidence: clamp01(answer.confidence),
      top,
      provider: 'jev',
      aiId: entry.aiId,
    }
  }

  /**
   * Internal (in-module) judgement on the 1D page: template AND output unit,
   * asked in ONE Jev round trip. The state carries (a) the big-module context
   * the user is in (route/title/path — Jev must know WHERE it is judging, not
   * only which module to route to), and (b) system-pre-computed facts it must
   * reason from instead of guessing physics: Cu-target wavelength check
   * (λ≈1.5418 Å) and the corner-reachable 2θ_max.
   * 模块内部判断：模板与积分单位一次往返同问。state 携带 (a) 用户当前所处
   * 大模块信息（路由/标题/路径——Jev 须知其在哪判断，而非只判断去哪个模块），
   * (b) 系统预计算事实（铜靶 λ≈1.5418 Å 判定、角点可达 2θ_max），物理数值
   * 由系统提供，Jev 不做猜测。
   */
  const templateAndUnitViaJev = async (
    intent: string,
    summary: PoniSummary | null,
    key: string
  ): Promise<TemplateDecision> => {
    const ctx = buildAppState()
    const moduleName = navTitle(ctx.currentRouteName) || ctx.currentRouteName || 'unknown'
    const lambdaA = typeof summary?.wavelength_A === 'number' ? summary.wavelength_A : null
    const tthMax = typeof summary?.tth_max_deg === 'number' ? summary.tth_max_deg : null

    const state = {
      userRequest: intent,
      // 大模块信息 / big-module context (WHERE the judgement happens)
      currentModule: {
        routeName: ctx.currentRouteName,
        title: moduleName,
        path: ctx.currentPath,
      },
      // 系统预计算事实 / system-pre-computed physics facts
      poniSummary: summary ?? {},
      systemFacts: {
        wavelength_A: lambdaA,
        wavelength_is_cu: summary?.wavelength_is_cu ?? null,
        tth_max_deg: tthMax,
      },
      // 系统确定性单位规则（判定基线）/ deterministic unit rule baseline
      systemUnitRule: {
        description:
          'Cu target (wavelength_is_cu=true) + WAXS → 2th_deg; SAXS → q_nm always; other WAXS → q_A',
        ifWaxs: unitForTemplate('waxs', summary),
        ifSaxs: unitForTemplate('saxs', summary),
      },
    }

    const [templateAnswer, unitAnswer] = await askTypesafeChoices(
      [
        {
          id: 'template',
          instructions:
            'Choose the standard 1D integration template for this sample given the PONI geometry. You are judging INSIDE the module named in currentModule.',
          choices: ['waxs', 'saxs', 'manual'],
          criteria: {
            waxs: 'Wide-angle: reachable q_max clearly ≥ 2 Å⁻¹; crystalline peaks across a broad q range',
            saxs: 'Small-angle: low-q nanostructure; reachable q_max < 2 Å⁻¹ (long sample distance)',
            manual: 'Not enough geometry context to decide automatically',
          },
          state,
        },
        {
          id: 'unit',
          instructions:
            'Pick the 1D radial output unit. Follow systemUnitRule grounded in systemFacts unless the user explicitly asked for a different axis.',
          choices: ['2th_deg', 'q_nm', 'q_A'],
          criteria: {
            '2th_deg': '2θ in degrees — Cu target (λ≈1.5418 Å) WAXS convention',
            q_nm: 'q in nm⁻¹ — SAXS always',
            q_A: 'q in Å⁻¹ — WAXS on a non-Cu wavelength',
          },
          state,
        },
      ],
      key
    )

    if (
      templateAnswer.choice !== 'waxs' &&
      templateAnswer.choice !== 'saxs' &&
      templateAnswer.choice !== 'manual'
    ) {
      throw new AiProviderError('bad_response', `Jev picked an unknown template: ${templateAnswer.choice}`)
    }
    const template = templateAnswer.choice
    const unit =
      unitAnswer.choice === '2th_deg' || unitAnswer.choice === 'q_nm' || unitAnswer.choice === 'q_A'
        ? unitAnswer.choice
        : template === 'waxs' || template === 'saxs'
          ? unitForTemplate(template, summary)
          : undefined

    const parts: string[] = []
    if (template === 'waxs' || template === 'saxs') parts.push(unitRuleReason(template, summary))
    if (lambdaA !== null) parts.push(`λ=${lambdaA.toFixed(4)} Å`)
    if (tthMax !== null) parts.push(`2θ_max≈${tthMax.toFixed(1)}°`)
    return {
      template,
      unit,
      confidence: clamp01(templateAnswer.confidence),
      reason: parts.join(' · '),
      provider: 'jev',
    }
  }

  /**
   * Speak WHY Jev failed before falling back to rules. A configured key used
   * to fail silently (empty catch), which looked exactly like "the key had no
   * effect" — the renderer fetch was CORS-blocked all along.
   * 回退规则前先播报 Jev 失败原因：此前空 catch 的静默降级让“配了 key 没效果”
   * 无从排查（实际是渲染层 fetch 被 CORS 拦截）。
   */
  const explainJevFailure = (err: unknown): void => {
    if (err instanceof AiProviderError && err.code === 'no_key') {
      say(globalT('ai.bar.jevKeyRejected'))
      return
    }
    const reason = err instanceof Error ? err.message : String(err)
    say(globalT('ai.bar.jevFailed', { reason }))
  }

  const decideRoute = async (intent: string): Promise<RouteDecision> => {
    const ctx = buildAppState()
    const settings = getAiSettings()

    if (settings.jevApiKey) {
      try {
        return await routeViaJev(intent, ctx, settings.jevApiKey)
      } catch (err) {
        explainJevFailure(err)
      }
    }

    return decideRouteViaRules(intent, ctx)
  }

  const decideTemplate = async (intent: string, summary: PoniSummary | null): Promise<TemplateDecision> => {
    const settings = getAiSettings()

    if (settings.jevApiKey) {
      try {
        return await templateAndUnitViaJev(intent, summary, settings.jevApiKey)
      } catch (err) {
        explainJevFailure(err)
      }
    }

    return decideTemplateViaRules(intent, summary)
  }

  // ── Navigation helper (navigate → spotlight → stop; never auto-click) ─────

  const navigateAndHighlight = async (
    routeName: string,
    path: string,
    aiId: string | undefined,
    confidence: number,
    provider: RouteDecision['provider']
  ): Promise<void> => {
    await router.push(path)
    lastDecision.value = { routeName, path, confidence, provider, aiId }
    if (aiId) {
      await nextTick()
      await sleep(HIGHLIGHT_DELAY_MS)
      highlightTarget(aiId, navTitle(routeName))
    }
  }

  // ── Phase 1: intent → route ────────────────────────────────────────────────

  const runRoutePhase = async (intent: string): Promise<void> => {
    state.value = 'thinking'
    const decision = await decideRoute(intent)
    lastDecision.value = decision

    // Teaching mode OFF: never auto-navigate or auto-enter a tour — present
    // the top-4 high-probability candidates for the user to pick.
    // 教学模式关闭：绝不自动导航/自动进入教学，只展示前 4 个高概率候选
    // 供用户选择（用户明确要求此行为，无论意图措辞如何）。
    if (!teachingEnabled()) {
      topPicks.value = topCandidates(decision)
      state.value = 'suggest'
      say(globalT('ai.bar.suggestHint'))
      return
    }

    if (decision.confidence >= 0.5 && navEntry(decision.routeName)) {
      // Guided-teaching takeover: teaching is on and the page has a tour.
      // 教学接管：教学模式开启且目标页有教学流程。
      const wantsGuide = hasGuide(decision.routeName)

      await navigateAndHighlight(
        decision.routeName,
        decision.path,
        wantsGuide ? undefined : (decision.aiId ?? navEntry(decision.routeName)?.aiId),
        decision.confidence,
        decision.provider
      )

      if (wantsGuide) {
        guideEngine.start(decision.routeName, decision.confidence, decision.provider)
        state.value = 'guide'
        return
      }

      state.value = 'wait-user'
      say(`${navTitle(decision.routeName)} · ${Math.round(decision.confidence * 100)}%`)
      return
    }

    topPicks.value = topCandidates(decision)
    state.value = 'suggest'
    say(globalT('ai.bar.suggestHint'))
  }

  /** Top-N candidates for the suggest list (fallback order when none given). */
  const topCandidates = (decision: RouteDecision): Array<{ routeName: string; probability: number }> =>
    decision.top && decision.top.length > 0
      ? decision.top.slice(0, TOP_PICKS)
      : [
          { routeName: 'integrate-1d', probability: 0.35 },
          { routeName: 'calibration', probability: 0.3 },
          { routeName: 'viewer', probability: 0.2 },
          { routeName: 'mask-maker', probability: 0.15 },
        ]

  // ── Phase 2: PONI context → template judgement ─────────────────────────────

  /** Fetch the geometry digest via the `ai_context` backend task. */
  const fetchPoniSummary = async (poniPath: string): Promise<PoniSummary | null> => {
    const response = await transport.submitTask('ai_context', {
      action: 'poni_summary',
      filePath: poniPath,
    })

    return new Promise<PoniSummary | null>((resolve, reject) => {
      let settled = false
      const finish = (fn: () => void): void => {
        if (settled) return
        settled = true
        window.clearTimeout(timer)
        offResult()
        offError()
        fn()
      }
      const timer = window.setTimeout(
        () => finish(() => reject(new Error(`ai_context timed out after ${PONI_TASK_TIMEOUT_MS / 1000}s.`))),
        PONI_TASK_TIMEOUT_MS
      )
      const offResult = transport.onTaskResult(response.taskId, (payload) => {
        finish(() => {
          const data = payload.data as Record<string, unknown> | null
          if (!data || typeof data !== 'object') {
            resolve(null)
            return
          }
          const num = (v: unknown): number | undefined =>
            typeof v === 'number' && Number.isFinite(v) ? v : undefined
          const summary: PoniSummary = {}
          if (num(data.distance_mm) !== undefined) summary.distance_mm = num(data.distance_mm)
          if (num(data.wavelength_A) !== undefined) summary.wavelength_A = num(data.wavelength_A)
          if (typeof data.wavelength_is_cu === 'boolean') summary.wavelength_is_cu = data.wavelength_is_cu
          if (num(data.pixel_size_um) !== undefined) summary.pixel_size_um = num(data.pixel_size_um)
          if (num(data.q_min_nm) !== undefined) summary.q_min_nm = num(data.q_min_nm)
          if (num(data.q_max_nm) !== undefined) summary.q_max_nm = num(data.q_max_nm)
          if (num(data.tth_max_deg) !== undefined) summary.tth_max_deg = num(data.tth_max_deg)
          if (Array.isArray(data.beam_center)) {
            summary.beam_center = data.beam_center.filter(
              (v): v is number => typeof v === 'number' && Number.isFinite(v)
            )
          }
          resolve(summary)
        })
      })
      const offError = transport.onTaskError(response.taskId, (payload) => {
        finish(() => reject(new Error(payload.error)))
      })
    })
  }

  const runTemplatePhase = async (intent: string): Promise<void> => {
    state.value = 'thinking'
    const applied = await applyTemplateFromPoni(intent)
    state.value = applied ? 'template-apply' : 'idle'
  }

  /**
   * PONI summary → template decision → `xfaos:ai-apply-template` dispatch.
   * Prefers the PONI actually loaded in the 1D view (reported via the
   * workspace-state bridge) over the assistant's own stored path.
   */
  const applyTemplateFromPoni = async (userIntent: string): Promise<boolean> => {
    const viewPoni = workspaceSnapshotOf('integrate-1d')?.extras?.poniPath
    const poniPath =
      (typeof viewPoni === 'string' && viewPoni.trim()) ||
      (() => {
        try {
          return localStorage.getItem(PONI_PATH_KEY)?.trim() ?? ''
        } catch {
          return ''
        }
      })()

    if (!poniPath) {
      say(globalT('ai.bar.needPoni'))
      return false
    }

    const summary = await fetchPoniSummary(poniPath)
    const decision = await decideTemplate(userIntent, summary)

    if (decision.template !== 'waxs' && decision.template !== 'saxs') {
      say(decision.reason || 'manual')
      return false
    }

    const template = INTEGRATE_TEMPLATES[decision.template]
    window.dispatchEvent(
      new CustomEvent(APPLY_TEMPLATE_EVENT, {
        detail: {
          ...templateDetail(template, decision.unit),
          reason: decision.reason,
          confidence: decision.confidence,
        },
      })
    )
    const unitText = decision.unit ? UNIT_DISPLAY[decision.unit] : ''
    say(
      `${globalT('ai.template.applied')} · ${template.zh}` +
        (unitText ? ` · ${globalT('ai.template.unitLabel')}: ${unitText}` : '') +
        ` · ${globalT('ai.template.reasonLabel')}: ${decision.reason}`
    )
    return true
  }

  // ── Public actions ─────────────────────────────────────────────────────────

  /** Submit a user message; routes it into Phase 1 or Phase 2. */
  const submit = async (text: string): Promise<void> => {
    const trimmed = text.trim()
    if (!trimmed || busy.value) return

    busy.value = true
    history.value.push({ role: 'user', text: trimmed })
    topPicks.value = []

    try {
      const onIntegrate1d = router.currentRoute.value.name === 'integrate-1d'
      if (TEMPLATE_INTENT_RE.test(trimmed) && onIntegrate1d) {
        await runTemplatePhase(trimmed)
      } else {
        await runRoutePhase(trimmed)
      }
    } catch (err) {
      state.value = 'error'
      say(describeError(err))
    } finally {
      busy.value = false
    }
  }

  /** User picked one of the suggested routes: navigate, then tour if available. */
  const pick = (routeName: string): void => {
    const entry = navEntry(routeName)
    if (!entry) return
    topPicks.value = []
    const wantsGuide = hasGuide(routeName) && teachingEnabled()
    state.value = wantsGuide ? 'guide' : 'wait-user'
    say(navTitle(routeName))
    void navigateAndHighlight(
      routeName,
      entry.path,
      wantsGuide ? undefined : entry.aiId,
      1,
      lastDecision.value?.provider ?? 'rules'
    ).then(() => {
      if (wantsGuide) {
        guideEngine.start(routeName, 1, lastDecision.value?.provider ?? 'rules')
      }
    })
  }

  /** Clear the transcript and suggestions (a running tour keeps running). */
  const clearConversation = (): void => {
    history.value = []
    topPicks.value = []
    if (state.value !== 'guide') state.value = 'idle'
  }

  /** Start (or restart) the guided tour for the CURRENT route, if it has one. */
  const startGuideHere = (): void => {
    const name = router.currentRoute.value.name
    if (typeof name !== 'string' || !hasGuide(name)) {
      say(globalT('ai.guide.noGuide'))
      return
    }
    // Explicit user action — treat as high confidence so auto-click may arm.
    guideEngine.start(name, 0.9, lastDecision.value?.provider ?? 'rules')
    state.value = 'guide'
  }

  return {
    state,
    lastDecision,
    history,
    topPicks,
    busy,
    guide: guideEngine,
    submit,
    pick,
    startGuideHere,
    clearConversation,
  }
}
