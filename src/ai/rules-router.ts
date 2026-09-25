/**
 * rules-router.ts — Deterministic offline fallback for the AI assistant.
 *
 * Keyword routing (zh + en, case-insensitive, substring match) for intent →
 * route, and geometry-based heuristics for intent → integration template.
 * This module must stay side-effect free and fully synchronous so it works
 * with no keys, no network, and no backend.
 */

import type { AppState, PoniSummary, RouteDecision, TemplateDecision, IntegrationUnitChoice } from './types'
import { navEntry } from './context'

// ── Intent → route ────────────────────────────────────────────────────────────

interface RouteRule {
  routeName: string
  keywords: string[]
}

/**
 * Ordered by specificity (first-listed wins on score ties). The GIWAXS
 * special-case (grazing + WAXS → fiber) is handled before this table.
 */
const ROUTE_RULES: RouteRule[] = [
  { routeName: 'integrate-1d', keywords: ['waxs', 'giwaxs', '广角'] },
  { routeName: 'integrate-1d', keywords: ['saxs', '小角'] },
  { routeName: 'integrate-1d', keywords: ['积分', 'integrat', 'integration', 'integrate'] },
  { routeName: 'integrate-cake', keywords: ['cake', '扇形'] },
  { routeName: 'integrate-azimuth', keywords: ['azimuth', '方位'] },
  { routeName: 'calibration', keywords: ['calib', '校准', '标定'] },
  { routeName: 'mask-maker', keywords: ['mask', '掩膜', '遮罩'] },
  { routeName: 'viewer', keywords: ['查看', 'view', '图像'] },
  { routeName: 'h5-toolkit', keywords: ['h5'] },
  { routeName: 'settings', keywords: ['设置', 'setting'] },
  { routeName: 'bg-subtract', keywords: ['背景', 'back'] },
  { routeName: 'image-stitch', keywords: ['拼接', 'stitch'] },
  { routeName: 'orientation-analysis', keywords: ['取向', 'orient'] },
  { routeName: 'lamellar-analysis', keywords: ['片晶', 'lamellar'] },
  { routeName: 'poni-importer', keywords: ['poni', '反向导入'] },
]

/** Word-boundary 'GI' match — avoids hitting the 'gi' inside 'grazing'. */
const GI_RE = /(^|[^a-z])gi([^a-z]|$)/
const GRAZING_RE = /grazing|掠入射/

function pathOf(routeName: string): string {
  return navEntry(routeName)?.path ?? (routeName === 'home' ? '/' : `/${routeName}`)
}

interface RuleHit {
  routeName: string
  score: number
}

/** Score every rule by how many of its keywords appear in the intent. */
function scoreRules(intent: string): RuleHit[] {
  const text = intent.toLowerCase()
  const hits: RuleHit[] = []
  for (const rule of ROUTE_RULES) {
    const score = rule.keywords.reduce(
      (acc, kw) => acc + (text.includes(kw.toLowerCase()) ? 1 : 0),
      0
    )
    if (score > 0) hits.push({ routeName: rule.routeName, score })
  }
  return hits
}

/**
 * Deterministic route decision from keywords.
 *
 * Rules are matched by keyword-hit count (more specific phrasing wins); ties
 * resolve in table order above. GI (grazing-incidence) + WAXS/GIWAXS is
 * promoted to the fiber view. No match → home with low confidence.
 */
export function decideRouteViaRules(intent: string, _ctx?: AppState): RouteDecision {
  const text = intent.toLowerCase()
  const hits = scoreRules(intent)

  // Special case: grazing-incidence WAXS belongs to the GIWAXS fiber view.
  const waxsHit = hits.find((h) => h.routeName === 'integrate-1d' && h.score > 0)
  const mentionsWaxs = /waxs|giwaxs|广角/.test(text)
  if (waxsHit && mentionsWaxs && (GI_RE.test(text) || GRAZING_RE.test(text))) {
    hits.unshift({ routeName: 'integrate-fiber', score: waxsHit.score + 1 })
  }

  hits.sort((a, b) => b.score - a.score)

  const top = hits.slice(0, 4).map((h, i) => ({
    routeName: h.routeName,
    probability: 0,
  }))

  if (hits.length === 0) {
    return {
      routeName: 'home',
      path: pathOf('home'),
      confidence: 0.3,
      top: [
        { routeName: 'home', probability: 0.35 },
        { routeName: 'integrate-1d', probability: 0.3 },
        { routeName: 'calibration', probability: 0.2 },
        { routeName: 'viewer', probability: 0.15 },
      ],
      provider: 'rules',
    }
  }

  // Primary = highest score (stable: first in table order on ties).
  const best = hits[0]
  const confidence = Math.min(0.95, 0.6 + 0.15 * (best.score - 1))

  // Probabilities from scores (softmax-free normalization; add epsilon so the
  // primary stays on top and everything sums to 1).
  const total = hits.reduce((acc, h) => acc + h.score, 0) || 1
  for (let i = 0; i < top.length; i += 1) {
    top[i].probability = hits[i].score / total
  }

  const entry = navEntry(best.routeName)
  return {
    routeName: best.routeName,
    path: pathOf(best.routeName),
    confidence,
    top,
    provider: 'rules',
    aiId: entry?.aiId,
  }
}

// ── Intent → integration template + output unit ──────────────────────────────

/** q threshold in Å⁻¹ above which geometry clearly reads as WAXS. */
const WAXS_QMAX_A = 2

function toQmaxA(summary: PoniSummary): number | null {
  // Prefer an explicit Å⁻¹ field; otherwise convert nm⁻¹ (×0.1).
  const direct = (summary as { q_max_A?: unknown }).q_max_A
  if (typeof direct === 'number' && Number.isFinite(direct)) return direct
  if (typeof summary.q_max_nm === 'number' && Number.isFinite(summary.q_max_nm)) {
    return summary.q_max_nm * 0.1
  }
  return null
}

/**
 * Deterministic output-unit rule (system pre-computed, handed to Jev as the
 * baseline): SAXS always q_nm; WAXS on a Cu target (λ≈1.5418 Å) reads as
 * 2θ (deg) — the conventional lab-source axis; other WAXS uses q_A.
 * 系统确定性单位规则（同时作为提供给 Jev 的基线）：SAXS 统一 q_nm；
 * 铜靶（λ≈1.5418 Å）WAXS 用 2θ（度）——实验室光源惯例轴；其余 WAXS 用 q_A。
 */
export function unitForTemplate(
  template: 'waxs' | 'saxs',
  poniSummary?: PoniSummary | null
): IntegrationUnitChoice {
  if (template === 'saxs') return 'q_nm'
  return poniSummary?.wavelength_is_cu === true ? '2th_deg' : 'q_A'
}

/** Human-readable facts behind a unit call (bilingual, for reason strings). */
export function unitRuleReason(
  template: 'waxs' | 'saxs',
  poniSummary?: PoniSummary | null
): string {
  const unit = unitForTemplate(template, poniSummary)
  if (template === 'saxs') return `SAXS 统一用 q_nm / SAXS always q (nm⁻¹) → ${unit}`
  if (poniSummary?.wavelength_is_cu === true) {
    const lambda = typeof poniSummary.wavelength_A === 'number' ? poniSummary.wavelength_A.toFixed(4) : '?'
    return `铜靶 λ=${lambda} Å + WAXS → 2θ / Cu target λ=${lambda} Å + WAXS → 2θ (deg)`
  }
  const lambda = typeof poniSummary?.wavelength_A === 'number' ? poniSummary.wavelength_A.toFixed(4) : null
  return `非铜靶${lambda ? ` λ=${lambda} Å` : ''} WAXS → q_A / non-Cu${lambda ? ` λ=${lambda} Å` : ''} WAXS → q (Å⁻¹)`
}

/**
 * Deterministic template + unit judgement:
 * 1. explicit SAXS/小角 → saxs, WAXS/广角 → waxs;
 * 2. else, with a PONI summary, decide from q_max (≥ 2 Å⁻¹ → waxs, else saxs);
 * 3. without either → 'manual' (not enough context to act on).
 * The output unit follows the fixed rule in `unitForTemplate`; reasons cite
 * the dist/qmax/λ/2θ_max numbers used for the call.
 * 确定性模板+单位判定；理由中引用判定所用的 dist/qmax/λ/2θ_max 数字。
 */
export function decideTemplateViaRules(
  intent: string,
  poniSummary?: PoniSummary | null
): TemplateDecision {
  const text = intent.toLowerCase()

  if (/saxs|小角/.test(text)) {
    return {
      template: 'saxs',
      unit: unitForTemplate('saxs', poniSummary),
      confidence: 0.85,
      reason: '用户明确提到 SAXS/小角 / user mentioned SAXS explicitly',
      provider: 'rules',
    }
  }
  if (/waxs|giwaxs|广角/.test(text)) {
    return {
      template: 'waxs',
      unit: unitForTemplate('waxs', poniSummary),
      confidence: 0.85,
      reason: '用户明确提到 WAXS/广角 / user mentioned WAXS explicitly',
      provider: 'rules',
    }
  }

  if (poniSummary) {
    const qmaxA = toQmaxA(poniSummary)
    if (qmaxA !== null) {
      const dist = typeof poniSummary.distance_mm === 'number'
        ? poniSummary.distance_mm.toFixed(1)
        : '?'
      const isWaxs = qmaxA >= WAXS_QMAX_A
      return {
        template: isWaxs ? 'waxs' : 'saxs',
        unit: unitForTemplate(isWaxs ? 'waxs' : 'saxs', poniSummary),
        confidence: 0.75,
        reason:
          `dist=${dist} mm, q_max≈${qmaxA.toFixed(2)} Å⁻¹ ` +
          (isWaxs ? `≥ ${WAXS_QMAX_A} → WAXS` : `< ${WAXS_QMAX_A} → SAXS`),
        provider: 'rules',
      }
    }
    return {
      template: 'manual',
      confidence: 0.4,
      reason: 'PONI 摘要缺少 q_max，无法判断 / poni summary lacks q_max',
      provider: 'rules',
    }
  }

  return {
    template: 'manual',
    confidence: 0.3,
    reason: '未提供 PONI 几何信息 / no PONI geometry available',
    provider: 'rules',
  }
}
