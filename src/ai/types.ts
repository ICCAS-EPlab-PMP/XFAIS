/**
 * types.ts — Shared types for the X-FAIS AI assistant layer.
 *
 * The assistant works fully offline through the deterministic rules router;
 * the Jev (TypeSafe) network adapter is optional behind these types.
 */

/** Which backend produced a decision. */
export type AiProviderKind = 'jev' | 'rules'

/** Stable error codes every provider adapter must use. */
export type AiErrorCode = 'no_key' | 'network' | 'bad_response'

/** Error thrown by provider adapters; the agent chain catches and falls through. */
export class AiProviderError extends Error {
  readonly code: AiErrorCode
  readonly status?: number

  constructor(code: AiErrorCode, message: string, status?: number) {
    super(message)
    this.name = 'AiProviderError'
    this.code = code
    this.status = status
  }
}

/** A single-choice question for the Jev (TypeSafe System One) API. */
export interface ChoiceQuestion {
  /** Our own key; the answer comes back under `answers.<id>`. */
  id: string
  /** Question text (API field: `instructions`). */
  instructions: string
  /** Option keys (API field: `criteria` keys). */
  choices: string[]
  /** Optional per-option rubric descriptions sent as `criteria`. */
  criteria?: Record<string, string>
  /** Optional context sent as the top-level `state` field. */
  state?: Record<string, unknown>
}

/** Normalized answer for a ChoiceQuestion. */
export interface ChoiceAnswer {
  id: string
  choice: string
  /** 0..1 — probability mass the provider assigns to `choice`. */
  confidence: number
  /** Optional full distribution over `choices`, normalized to sum 1. */
  probabilities?: Record<string, number>
}

/**
 * Compact, JSON-serializable snapshot of where the user is in the app.
 * Built by `buildAppState()` in `@/ai/context`; keep it under ~2 KB.
 */
export interface AppState {
  currentPath: string
  currentRouteName: string
  /** routeName → localized nav title (current locale). */
  navTitles: Record<string, string>
  /** Last visited paths (most recent first, max 8), session-scoped. */
  recentPaths: string[]
  /** Path of the PONI geometry file the assistant should reason about. */
  poniPath: string
}

/**
 * PONI geometry digest returned by the `ai_context` backend task.
 * `wavelength_is_cu` / `tth_max_deg` are system-pre-computed facts fed to the
 * unit judgement (系统预计算事实：铜靶判定 + 角点最大 2θ).
 */
export interface PoniSummary {
  distance_mm?: number
  wavelength_A?: number
  /** True when λ ≈ 1.5418 Å (Cu Kα, close values tolerated). */
  wavelength_is_cu?: boolean
  pixel_size_um?: number
  q_min_nm?: number
  q_max_nm?: number
  /** Max reachable 2θ at the detector corners, degrees. */
  tth_max_deg?: number
  beam_center?: [number, number] | number[]
}

/** Radial units the AI layer may choose for 1D integration output. */
export type IntegrationUnitChoice = 'q_A' | 'q_nm' | '2th_deg'

/** Result of intent → route routing (Phase 1 of the agent flow). */
export interface RouteDecision {
  routeName: string
  path: string
  /** 0..1 — ≥ 0.5 auto-navigates, < 0.5 shows suggestions instead. */
  confidence: number
  /** Ranked alternatives for the "suggest" state. */
  top?: Array<{ routeName: string; probability: number }>
  provider: AiProviderKind
  /** Optional `data-ai-id` of the element to spotlight after navigating. */
  aiId?: string
}

/** Result of the PONI-based template judgement (Phase 2 of the agent flow). */
export interface TemplateDecision {
  template: 'waxs' | 'saxs' | 'manual'
  /** Output unit decided alongside the template (system rule / Jev). */
  unit?: IntegrationUnitChoice
  confidence: number
  reason: string
  provider: AiProviderKind
}
