/**
 * rules-router.ts — Deterministic offline fallback for the AI assistant.
 *
 * Keyword routing (zh + en, case-insensitive, substring match) for intent →
 * route, and geometry-based heuristics for intent → integration template.
 * This module must stay side-effect free and fully synchronous so it works
 * with no keys, no network, and no backend.
 */

import type {
  AppState,
  OptionsDecision,
  PoniSummary,
  RouteDecision,
  TemplateDecision,
  IntegrationUnitChoice,
} from './types'
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
  { routeName: 'calibration', keywords: ['定心', '直通', '质心', 'beam center', 'centroid'] },
  { routeName: 'curve-fitting', keywords: ['拟合', '分峰', 'peak fit', 'curve fit', 'fwhm', '半峰宽', '结晶度'] },
  { routeName: 'mask-maker', keywords: ['mask', '掩膜', '遮罩'] },
  { routeName: 'viewer', keywords: ['查看', 'view', '图像'] },
  { routeName: 'h5-toolkit', keywords: ['h5'] },
  { routeName: 'settings', keywords: ['设置', 'setting'] },
  { routeName: 'bg-subtract', keywords: ['背景', 'back'] },
  { routeName: 'image-stitch', keywords: ['拼接', 'stitch'] },
  { routeName: 'image-math', keywords: ['图像运算', '加减', '图像平均'] },
  { routeName: 'orientation-analysis', keywords: ['取向', 'orient'] },
  { routeName: 'lamellar-analysis', keywords: ['片晶', 'lamellar', '长周期'] },
  { routeName: 'poni-importer', keywords: ['poni', '反向导入'] },
  { routeName: 'png-generate', keywords: ['png', '预览图'] },
  { routeName: 'pyfai-calib', keywords: ['calib2', 'pyfai 安装'] },
  { routeName: 'cell-calibrant-generator', keywords: ['标样生成', '理论峰位', 'cif'] },
  // Transmission measurement (2026-10-25). '测透过'/'透过率测量' double-hit
  // phrasings like "直通光测透过率" so the module outranks calibration's '直通'
  // keyword on ties, while a bare "背景扣除导入透过率" still ties into
  // bg-subtract (earlier rule) as intended.
  // 透过率测量（2026-10-25）。「测透过」「透过率测量」让「直通光测透过率」
  // 这类说法双命中、在平分时压过标定的「直通」关键词；而单独的「背景扣除
  // 导入透过率」仍按表序平分给更早的背景扣除规则——符合本意。
  { routeName: 'transmission', keywords: ['透过率', '透射率', 'transmission', '测透过', '透过率测量', '光斑积分'] },
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

// ── Intent → per-module options (Phase 2 generalized / 模块选项判定) ─────────

/**
 * Deterministic per-module option decisions from the same user intent that
 * routed the assistant. Returns null when the intent carries no actionable
 * signal for the module — views keep their current defaults then, and nothing
 * is dispatched. Options use each module's own vocabulary; the views that opt
 * in re-validate their step/state before assigning (decisions, not effects).
 * 各模块选项的确定性判定：复用路由阶段的同一句意图。意图对目标模块没有可执行
 * 信号时返回 null——视图保持现状、不派发任何事件。取值用模块自己的词汇表；
 * 接入的视图在赋值前自行校验步骤/状态（只做「判定」，不做副作用）。
 */
export function decideOptionsViaRules(routeName: string, intent: string): OptionsDecision | null {
  const text = intent.toLowerCase()
  const options: Record<string, string | string[]> = {}
  const reasons: Record<string, string> = {}

  if (routeName === 'calibration') {
    let mode: 'calibrant' | 'internal' | 'com' | null = null
    let reason = ''
    if (/直通|质心|定心|centroid|beam\s*center/.test(text)) {
      mode = 'com'
      reason = '提到直通光/质心/定心 → 直通光定心模式 / direct-beam centroid centering'
    } else if (/内标|internal/.test(text)) {
      mode = 'internal'
      reason = '提到内标 → 内标定标模式 / internal-standard calibration'
    } else if (/标样|衍射环|calibrant|ring/.test(text)) {
      mode = 'calibrant'
      reason = '提到标样/衍射环 → 标样校正模式 / calibrant-ring calibration'
    }
    if (mode) {
      options.mode = mode
      reasons.mode = reason
    }
  }

  if (routeName === 'orientation-analysis') {
    const picks: string[] = []
    if (/单斜|monoclinic|多反射|multi[- ]?reflection|wilchinsky/.test(text)) picks.push('wilchinsky')
    if (/hermans|二阶矩|取向函数/.test(text)) picks.push('hermans')
    if (/半高宽|半峰宽|半高|fwhm/.test(text)) picks.push('fwhm')
    if (picks.length > 0) {
      options.methods = picks
      reasons.methods = `明确点名的方法：${picks.join(' + ')} / methods named by the user`
    }
  }

  if (routeName === 'curve-fitting') {
    // Peak-shape vocabulary = the pwcore registry ids the workbench places
    // peaks with (gauss / lorentz / pearson7 / voigt / glorsum=pV sum).
    let peakFn: string | null = null
    let reason = ''
    if (/高斯|gauss(ian)?\b/.test(text) && !/pseudo|伪/.test(text)) {
      peakFn = 'gauss'
      reason = '点名高斯峰形 / Gaussian named'
    } else if (/洛伦兹|lorentz/.test(text)) {
      peakFn = 'lorentz'
      reason = '点名洛伦兹峰形 / Lorentzian named'
    } else if (/pearson/.test(text)) {
      peakFn = 'pearson7'
      reason = '点名 Pearson VII / Pearson VII named'
    } else if (/voigt/.test(text) && !/pseudo|伪/.test(text)) {
      peakFn = 'voigt'
      reason = '点名 Voigt 峰形 / Voigt named'
    }
    if (peakFn) {
      options.peakFn = peakFn
      reasons.peakFn = reason
    }
  }

  if (routeName === 'transmission') {
    // Region-shape vocabulary = the two regionMode values the canvas arms.
    // The leading boundary on 'rect' keeps "direct beam" from arming the
    // rectangle tool (2026-10-25). Values are strings; the view's inert
    // listener maps them onto its own state.
    // 区域形状词汇 = 画布可武装的两种 regionMode 取值。'rect' 前置边界避免
    // "direct beam" 里的 rect 误武装方形框（2026-10-25）。取值为字符串，
    // 视图的惰性监听器自行映射到自身状态。
    let shape: 'rect' | 'poly' | null = null
    let shapeReason = ''
    if (/方形框?|矩形|(^|[^a-z])rect(angle)?\b/.test(text)) {
      shape = 'rect'
      shapeReason = '点名方形框/矩形区域 / rectangle region named'
    } else if (/多折框?|多边形|poly(gon)?\b/.test(text)) {
      shape = 'poly'
      shapeReason = '点名多折框/多边形区域 / polygon region named'
    }
    if (shape) {
      options.shape = shape
      reasons.shape = shapeReason
    }
    if (/扣除.*背景|边界背景|扣背景|subtract.*border/.test(text)) {
      options.subtractBorder = 'on'
      reasons.subtractBorder = '要求扣除区域边界背景 / border-background subtraction requested'
    }
  }

  if (Object.keys(options).length === 0) return null
  return { routeName, options, reasons, confidence: 0.8, provider: 'rules' }
}

/** Bilingual display names for module option values (for assistant narration). */
export function moduleOptionLabel(routeName: string, key: string, value: string | string[]): string {
  if (routeName === 'calibration' && key === 'mode' && typeof value === 'string') {
    return ({ calibrant: '标样校正', internal: '内标定标', com: '直通光定心' } as Record<string, string>)[value] ?? value
  }
  if (routeName === 'orientation-analysis' && key === 'methods' && Array.isArray(value)) {
    const names: Record<string, string> = {
      hermans: 'Hermans',
      fwhm: 'FWHM 经验指数',
      wilchinsky: 'Wilchinsky',
    }
    return value.map((m) => names[m] ?? m).join(' + ')
  }
  if (routeName === 'curve-fitting' && key === 'peakFn' && typeof value === 'string') {
    const names: Record<string, string> = {
      gauss: '高斯 GAUSS',
      lorentz: '洛伦兹 LORENTZ',
      pearson7: 'Pearson VII',
      voigt: 'Voigt',
      glorsum: '伪 Voigt (G+L)',
    }
    return names[value] ?? value
  }
  if (routeName === 'transmission') {
    if (key === 'shape' && typeof value === 'string') {
      return ({ rect: '方形框', poly: '多折框' } as Record<string, string>)[value] ?? value
    }
    if (key === 'subtractBorder' && typeof value === 'string') {
      return value === 'on' ? '扣除区域边界背景' : value
    }
  }
  return Array.isArray(value) ? value.join(' + ') : value
}
