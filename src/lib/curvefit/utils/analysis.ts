/**
 * X-ray analyses on the fitted peak components (X-FAIS 0.3.3, 2026-10-20).
 * 基于（拟合后）峰分量的 X 射线分析。
 *
 * ① Crystallinity by peak classification — the user tags one or more fitted
 *    peaks as AMORPHOUS (the broad halo component(s)); everything else is
 *    crystalline: Xc = ΣA_cryst / (ΣA_cryst + ΣA_amorph) × 100 % (areas are
 *    the baseline-free fitted components). 结晶度（峰分类法）：非晶晕标为
 *    「非晶」，其余为结晶峰，Xc = ΣA结晶 / (ΣA结晶 + ΣA非晶) × 100 %
 *    （面积为扣基线后的峰分量面积）。
 *
 * ② Orientation from an azimuthal I(χ) fit — mirrors
 *    python/services/orientation_analysis.py EXACTLY (same Hermans
 *    half-range convention with the sinφ spherical weight, same
 *    normal→chain conversion <cos²φ_c> = 1 − <cos²χ>, same empirical FWHM
 *    index f = (180° − H) / 180), but applied to ONE fitted component at a
 *    time — the finer per-peak variant the user asked for. 取向分析：与
 *    orientation_analysis.py 完全同口径（Hermans 半区间 sinφ 权重、赤道
 *    法向→链轴换算 <cos²φ_c>=1−<cos²χ>、经验 FWHM 指数 f=(180°−H)/180），
 *    但逐个拟合峰分量计算——用户要求的更细致拟合版。
 *
 * ③ iPP β-phase fraction Kβ (Turner-Jones 1964): the user assigns the fitted
 *    peaks to β(300) / α(110) / α(040) / α(130);
 *    Kβ = Aβ(300) / [Aα(110) + Aα(040) + Aα(130) + Aβ(300)].
 *    iPP β 晶相分数（Turner-Jones）：Kβ = Aβ(300) / [Aα(110)+Aα(040)+
 *    Aα(130)+Aβ(300)]。
 */
import { reactive } from 'vue'
import type { ParamValues } from '@/lib/pwcore/shared/types'
import { PEAK_FN_MAP, type PeakFnId } from '@/lib/pwcore/shared/registry'
import { evalPeak } from '@/lib/pwcore/core/models'
import { peakShape } from '@/lib/pwcore/core/statsfn'

// ---------------------------------------------------------------------------
// Assignment state (module singleton — the workbench session semantics) /
// 指派状态（模块级单例——工作台会话语义）
// ---------------------------------------------------------------------------

/**
 * Which polymer analyses are switched ON (default: all off). Independent
 * per-analysis switches: only the enabled ones are displayed and computed
 * (2026-10-20 user request — never compute all three by default).
 * 三项聚合物分析各自的开关（默认全关）。彼此独立：只有开启的项才显示并
 * 计算（2026-10-20 用户要求——绝不默认全算）。
 */
export const polyOn = reactive({ crystallinity: false, orientation: false, kb: false })

export type CrysRole = 'crystal' | 'amorphous'

/** Per-peak crystallinity role; UNLISTED peaks default to 'crystal'. /
 *  逐峰结晶度角色；未列出的峰默认「结晶」。 */
export const crysRoles = reactive<Record<string, CrysRole>>({})

export type ChiZeroMode = 'meridian' | 'equator' | 'custom'

/** Orientation analysis options (shared by every peak row). /
 *  取向分析选项（所有峰行共用）。 */
export const orientOpts = reactive({
  chiZero: 'meridian' as ChiZeroMode,
  /** Custom reference-axis angle in χ (used when chiZero === 'custom'). /
   *  自定义参考轴在 χ 中的角度（chiZero === 'custom' 时生效）。 */
  refDeg: 0,
  /** equatorial reflection: convert normal moment to chain axis
   *  <cos²φ_c> = 1 − <cos²χ>. / 赤道反射：法向矩换算链轴。 */
  equatorialToChain: true,
})

export type KbRole = 'beta300' | 'a110' | 'a040' | 'a130'

/** iPP Kβ assignment: peak id per crystallographic role (null = unassigned).
 *  Kβ 指派：各晶面角色对应的峰 id（null = 未指派）。 */
export const kbAssign = reactive<Record<KbRole, string | null>>({
  beta300: null,
  a110: null,
  a040: null,
  a130: null,
})

/** Clear every assignment (called when new data is adopted). `polyOn` is
 *  deliberately left untouched — the user's per-analysis enable switches are
 *  a view preference, not per-dataset assignment state.
 *  清空全部指派（采纳新数据时调用）。`polyOn` 有意保持不动——用户的三项
 *  分析开关属于视图偏好，不属于逐数据集的指派状态。 */
export function resetAnalysisState(): void {
  for (const k of Object.keys(crysRoles)) delete crysRoles[k]
  kbAssign.beta300 = null
  kbAssign.a110 = null
  kbAssign.a040 = null
  kbAssign.a130 = null
}

export function roleOf(peakId: string): CrysRole {
  return crysRoles[peakId] ?? 'crystal'
}

export function toggleRole(peakId: string): void {
  crysRoles[peakId] = roleOf(peakId) === 'crystal' ? 'amorphous' : 'crystal'
}

// ---------------------------------------------------------------------------
// ① Crystallinity / 结晶度
// ---------------------------------------------------------------------------

export interface CrysInput {
  id: string
  /** Baseline-free fitted (or live-model) peak area. / 扣基线的峰面积。 */
  area: number
}

export interface CrysResult {
  xcPct: number
  crystalArea: number
  amorphousArea: number
}

export function crystallinityOf(peaks: CrysInput[]): CrysResult | null {
  let crystalArea = 0
  let amorphousArea = 0
  for (const p of peaks) {
    if (!Number.isFinite(p.area)) continue
    if (roleOf(p.id) === 'amorphous') amorphousArea += Math.abs(p.area)
    else crystalArea += Math.abs(p.area)
  }
  const total = crystalArea + amorphousArea
  if (total <= 0) return null
  return {
    xcPct: (100 * crystalArea) / total,
    crystalArea,
    amorphousArea,
  }
}

// ---------------------------------------------------------------------------
// ② Orientation (per fitted component) / 取向（逐拟合分量）
// ---------------------------------------------------------------------------

function packParams(fn: PeakFnId, p: ParamValues): number[] {
  return (PEAK_FN_MAP.get(fn)?.params ?? []).map((pm) => p[pm.key] ?? 0)
}

export interface OrientResult {
  /** Component center χc (deg). / 分量中心。 */
  centerDeg: number
  /** Numeric FWHM H (deg). / 数值半高宽 H（度）。 */
  fwhmDeg: number
  /** Empirical FWHM orientation index (180 − H)/180 (orientation_analysis
   *  .fwhm_orientation_index convention). / 经验 FWHM 取向指数。 */
  fwhmIndex: number
  /** Measured normal second moment <cos²χ> (clamped to [0,1]). /
   *  实测法向二阶矩 <cos²χ>（钳制到 [0,1]）。 */
  cos2Normal: number
  /** Reported second moment <cos²φ> (chain-axis after the equatorial
   *  conversion when enabled). / 报告的二阶矩 <cos²φ>。 */
  cos2Phi: number
  /** Hermans orientation function f = (3<cos²φ> − 1)/2 ∈ [−0.5, 1]. /
   *  Hermans 取向函数。 */
  f: number
  /** Reference axis angle actually used (deg). / 实际采用的参考轴角度。 */
  refDeg: number
}

/**
 * Hermans moment of ONE fitted component, sampled over its own support
 * (χc ± 4·H) with the orientation module's spherical sinφ weight:
 *   φ = mod(χ − ref, 360°) reduced mod 180° (cos² and |sin| are π-periodic),
 *   <cos²χ> = ∫ I·cos²φ·sinφ dφ / ∫ I·sinφ dφ  (trapezoid),
 * then the same clamping + conversion + f as orientation_analysis.py.
 * 单个拟合分量的 Hermans 矩：在自身支撑域（χc ± 4H）上采样，用取向模块的
 * sinφ 球面权重做梯形积分；钳制、换算与 f 的公式与 orientation_analysis.py
 * 完全一致。对孤立方位峰，此结果与该模块“折叠象限后积分”等价。
 */
export function orientationOfComponent(
  fn: PeakFnId,
  p: ParamValues,
  opts: { chiZero: ChiZeroMode; refDeg: number; equatorialToChain: boolean } = orientOpts,
): OrientResult | null {
  const packed = packParams(fn, p)
  const shape = peakShape(fn, packed)
  const centerDeg = shape.center
  const fwhmDeg = shape.fwhm
  if (!Number.isFinite(centerDeg) || !Number.isFinite(fwhmDeg) || fwhmDeg <= 0) return null

  const ref = opts.chiZero === 'custom' ? opts.refDeg : opts.chiZero === 'equator' ? 90 : 0
  const rad = Math.PI / 180
  const half = 4 * fwhmDeg
  const n = 1201
  const comp = evalPeak(fn, packed, sampleXs(centerDeg - half, centerDeg + half, n))
  let num = 0
  let den = 0
  for (let i = 0; i < n; i += 1) {
    const chi = centerDeg - half + ((2 * half) * i) / (n - 1)
    const a = ((((chi - ref) % 360) + 360) % 360) % 180
    const w = Math.sin(a * rad)
    const c2 = Math.cos(a * rad) ** 2
    num += comp[i] * c2 * w
    den += comp[i] * w
  }
  // Trapezoid on a UNIFORM grid: the constant dx factor cancels in the ratio.
  // 均匀网格梯形积分：公因子 dx 在比值中消去。
  let cos2Normal = den > 0 ? num / den : 1 / 3
  cos2Normal = Math.min(Math.max(cos2Normal, 0), 1)
  const cos2Phi = opts.equatorialToChain ? 1 - cos2Normal : cos2Normal
  return {
    centerDeg,
    fwhmDeg,
    fwhmIndex: (180 - Math.min(fwhmDeg, 180)) / 180,
    cos2Normal,
    cos2Phi,
    f: (3 * cos2Phi - 1) / 2,
    refDeg: ref,
  }
}

function sampleXs(x0: number, x1: number, n: number): Float64Array {
  const xs = new Float64Array(n)
  const dx = (x1 - x0) / (n - 1)
  for (let i = 0; i < n; i += 1) xs[i] = x0 + i * dx
  return xs
}

// ---------------------------------------------------------------------------
// ③ iPP Kβ (Turner-Jones) / β 晶相分数
// ---------------------------------------------------------------------------

export interface KbResult {
  /** Kβ as a fraction [0,1]. / Kβ（0–1）。 */
  kb: number
  areas: { beta300: number; a110: number; a040: number; a130: number }
}

export const KB_ROLES: Array<{ key: KbRole; label: string; hint: string }> = [
  { key: 'beta300', label: 'β(300)', hint: 'β 晶 (300)，2θ ≈ 16.1°（Cu Kα）' },
  { key: 'a110', label: 'α(110)', hint: 'α 晶 (110)，2θ ≈ 14.1°' },
  { key: 'a040', label: 'α(040)', hint: 'α 晶 (040)，2θ ≈ 16.9°' },
  { key: 'a130', label: 'α(130)', hint: 'α 晶 (130)，2θ ≈ 18.6°' },
]

/**
 * Turner-Jones β-phase fraction from fitted AREAS:
 *   Kβ = Aβ(300) / [Aα(110) + Aα(040) + Aα(130) + Aβ(300)]
 * Returns null until all four roles are assigned. 用拟合面积按 Turner-Jones
 * 公式计算 Kβ；四项全部指派后才返回结果。
 */
export function kbFractionOf(
  areasByRole: { beta300: number | null; a110: number | null; a040: number | null; a130: number | null },
): KbResult | null {
  const { beta300, a110, a040, a130 } = areasByRole
  if (beta300 == null || a110 == null || a040 == null || a130 == null) return null
  const areas = {
    beta300: Math.abs(beta300),
    a110: Math.abs(a110),
    a040: Math.abs(a040),
    a130: Math.abs(a130),
  }
  const denom = areas.beta300 + areas.a110 + areas.a040 + areas.a130
  if (denom <= 0) return null
  return { kb: areas.beta300 / denom, areas }
}
