/**
 * fitEngine.ts — X-FAIS 曲线拟合引擎适配层（0.3.3）
 *
 * Thin orchestration around the ported PeakWorkbench (REA/peakfit) pure
 * numeric core (`./pwcore`). The port keeps its exact behaviour: 24 peak
 * shapes + 10 baselines, bounded Levenberg–Marquardt with the reference
 * application's chi-square-significant-digit convergence, soft percent
 * constraints, robust IRLS modes, covariance standard errors, prominence /
 * 2nd-derivative auto detection, the four-step baseline pipeline and
 * anchor-drag inverse solving.
 * 围绕移植的 PeakWorkbench（REA/peakfit）纯数值核心（./pwcore）的薄适配层。
 * 移植保持其原汁原味：24 种峰形 + 10 种基线、参考应用的 χ² 有效数字收敛
 * 规则的有界 Levenberg–Marquardt、百分比软约束、稳健 IRLS、协方差标准误、
 * 显著度/二阶导数自动检测、四步基线流水线与锚点拖拽反解。
 *
 * Architecture (PeakWorkbench 3-layer, adapted to X-FAIS):
 *   renderer interactions (place / drag anchors / live curves) → pwcore
 *   called DIRECTLY in-process (zero latency); a FIT runs inside the
 *   dedicated Web Worker (fitWorker.ts) so the UI never blocks while
 *   iteration telemetry streams in.
 * 架构（PeakWorkbench 三层结构，适配进 X-FAIS）：交互（放峰/拖锚/实时曲线）
 * 在渲染进程内直调 pwcore（零延迟）；拟合在专属 Web Worker 中运行，UI 不
 * 阻塞且迭代遥测流式回传。
 */
import {
  BASELINE_FN_MAP,
  FAMILY_LABELS,
  PEAK_FN_MAP,
  type BaselineFnId,
  type BaselineFnMeta,
  type PeakFnId,
  type PeakFnMeta,
  type ParamInit,
} from './pwcore/shared/registry'
import {
  DEFAULT_CONSTRAINTS,
  type BaselineSpec,
  type DetectedPeak,
  type DetectOptions,
  type FitIterEvent,
  type FitOutcome,
  type FitRequest,
  type FitResult,
  type ParamValues,
  type PeakConstraints,
  type PeakSpec,
  type RobustMethod,
  type SmoothOptions,
} from './pwcore/shared/types'
import { baselineValue, evalPeak, peakValue } from './pwcore/core/models'
import { measurePeakGeometry, solveAnchorDrag } from './pwcore/core/geometry'
import type { AnchorDragInput, PeakGeometry } from './pwcore/core/geometry'
import { detectPeaks } from './pwcore/core/detect'
import {
  autoBaseline,
  refitBaseline,
  subtractBaseline,
  type BaselineFitResult,
  type BaselineMethod,
  type BaselineModelId,
} from './pwcore/core/baseline'
import { smoothData } from './pwcore/core/smooth'
import { peakShape } from './pwcore/core/statsfn'
import FitWorker from './fitWorker?worker&inline'

export type {
  BaselineFnId,
  BaselineSpec,
  DetectedPeak,
  DetectOptions,
  FitIterEvent,
  FitOutcome,
  FitRequest,
  FitResult,
  ParamValues,
  PeakConstraints,
  PeakFnId,
  PeakSpec,
  RobustMethod,
  SmoothOptions,
  AnchorDragInput,
  PeakGeometry,
  BaselineFitResult,
  BaselineMethod,
  BaselineModelId,
}
export { DEFAULT_CONSTRAINTS, FAMILY_LABELS }

// ---------------------------------------------------------------------------
// Registry helpers / 注册表辅助
// ---------------------------------------------------------------------------

export function peakMeta(fn: PeakFnId): PeakFnMeta {
  const m = PEAK_FN_MAP.get(fn)
  if (!m) throw new Error(`unknown peak fn: ${fn}`)
  return m
}

export function baselineMeta(fn: BaselineFnId): BaselineFnMeta {
  const m = BASELINE_FN_MAP.get(fn)
  if (!m) throw new Error(`unknown baseline fn: ${fn}`)
  return m
}

/**
 * X-ray-first palette (user request 0.3.3: 以 X 射线峰形为主). The primary
 * group holds the five X-ray diffraction workhorses; the secondary group
 * keeps a few useful extras available without cluttering the default view.
 * 以 X 射线为主的峰形面板（0.3.3 用户要求）：首选组为五个衍射常用峰形；
 * 次选组保留少量实用扩展，不干扰默认视图。
 */
export const XRAY_PALETTE: { primary: PeakFnId[]; secondary: PeakFnId[] } = {
  primary: ['gauss', 'lorentz', 'glorsum', 'pearson7', 'voigt'],
  secondary: ['emg', 'lognorm'],
}

/** Functions whose a0 is the AREA (not the height): placing from a click must
 *  rescale a0 so the visible height matches the clicked y. /
 *  a0 为面积（而非峰高）的峰形：点击放峰时需重标 a0，使可见峰高与点击处一致。 */
const AREA_PARAM_FNS = new Set<PeakFnId>(['glorsum', 'emg', 'gmg', 'hvl', 'giddings', 'nlc'])

/**
 * Build initial parameters for a freshly placed peak from the registry init
 * hints (clickX / clickY / autoWidth / literal). For area-parameterized
 * functions the amplitude is rescaled so the curve actually passes through
 * the clicked point — the same compensation PeakWorkbench applies on
 * detection placement. / 按注册表初值提示（clickX/clickY/autoWidth/字面值）
 * 生成新放峰的初始参数；面积参数化峰形重标 a0 使曲线过点击点——与
 * PeakWorkbench 检测放峰时的补偿一致。
 */
export function initPeakParams(
  fn: PeakFnId,
  clickX: number,
  clickY: number,
  widthHint: number,
): ParamValues {
  const meta = peakMeta(fn)
  const p: ParamValues = {}
  for (const pm of meta.params) {
    const init = pm.init
    if (init === 'clickX') p[pm.key] = clickX
    else if (init === 'clickY') p[pm.key] = clickY
    else if (init === 'autoWidth') p[pm.key] = widthHint
    else p[pm.key] = init
    if (pm.min !== null && p[pm.key] < pm.min) p[pm.key] = pm.min
    if (pm.max !== null && p[pm.key] > pm.max) p[pm.key] = pm.max
  }
  if (AREA_PARAM_FNS.has(fn)) {
    const h = peakValue(fn, packParams(fn, p), p.a1)
    if (Number.isFinite(h) && Math.abs(h) > 1e-300) {
      p.a0 = (p.a0 * clickY) / h
    }
  }
  return p
}

/** Initial parameters for a baseline (b0 from the clicked y, width-like keys
 *  from the span). / 基线初值（b0 取点击 y，宽度类键取数据跨度）。 */
export function initBaselineParams(
  fn: BaselineFnId,
  clickY: number,
  widthHint: number,
): ParamValues {
  const meta = baselineMeta(fn)
  const p: ParamValues = {}
  for (const pm of meta.params) {
    const init = pm.init as ParamInit
    if (init === 'clickY') p[pm.key] = clickY
    else if (init === 'autoWidth') p[pm.key] = widthHint
    else p[pm.key] = typeof init === 'number' ? init : 0
    if (pm.min !== null && p[pm.key] < pm.min) p[pm.key] = pm.min
    if (pm.max !== null && p[pm.key] > pm.max) p[pm.key] = pm.max
  }
  return p
}

/** Positional parameter vector for evalPeak/packPeakParams. / 位置参数向量。 */
function packParams(fn: PeakFnId, p: ParamValues): number[] {
  return peakMeta(fn).params.map((pm) => p[pm.key] ?? 0)
}

// ---------------------------------------------------------------------------
// Live curve evaluation (interaction path — in-process, zero latency) /
// 实时曲线求值（交互路径——进程内直调，零延迟）
// ---------------------------------------------------------------------------

export interface ModelCurves {
  /** Baseline curve over x (zeros when the baseline is off). / 基线曲线。 */
  base: Float64Array
  /** Per-peak component curves, ENABLED peaks only (aligned with compsIds). */
  comps: Float64Array[]
  /** EnginePeak ids of the component curves (enabled, in request order). */
  compsIds: string[]
  /** base + sum of enabled peaks. / 基线 + 启用峰之和。 */
  total: Float64Array
}

export function evalModelCurve(
  x: ArrayLike<number>,
  peaks: ReadonlyArray<PeakSpec>,
  baseline: BaselineSpec,
): ModelCurves {
  const n = x.length
  const base = new Float64Array(n)
  const useBase = baseline.enabled && baseline.fn !== 'none'
  if (useBase) {
    const b = packBaseline(baseline)
    for (let i = 0; i < n; i += 1) base[i] = baselineValue(baseline.fn, b, x[i])
  }
  const comps: Float64Array[] = []
  const compsIds: string[] = []
  const total = base.slice()
  for (const pk of peaks) {
    if (!pk.enabled) continue
    const yc = evalPeak(pk.fn, packParams(pk.fn, pk.p), x as ArrayLike<number>)
    for (let i = 0; i < n; i += 1) total[i] += yc[i]
    comps.push(yc)
    compsIds.push(pk.id)
  }
  return { base, comps, compsIds, total }
}

function packBaseline(baseline: BaselineSpec): number[] {
  return baselineMeta(baseline.fn).params.map((pm) => baseline.p[pm.key] ?? 0)
}

// ---------------------------------------------------------------------------
// Detection / smoothing / baseline (passthroughs the view needs) /
// 自动检测 / 平滑 / 基线（视图所需的直通封装）
// ---------------------------------------------------------------------------

export function detectOnCurve(
  x: Float64Array,
  y: Float64Array,
  opts: DetectOptions,
): DetectedPeak[] {
  return detectPeaks(x, y, opts)
}

/** Turn one detection into placed initial parameters. / 把检测结果转为放峰初值。 */
export function placeFromDetection(
  fn: PeakFnId,
  det: DetectedPeak,
): ParamValues {
  return initPeakParams(fn, det.x0, det.y0, Math.max(det.width, 1e-9))
}

export function smoothCurve(y: Float64Array, opts: SmoothOptions): Float64Array {
  return smoothData(y, opts)
}

export {
  autoBaseline,
  refitBaseline,
  subtractBaseline,
}

// ---------------------------------------------------------------------------
// Anchors (PeakWorkbench interaction semantics) / 锚点（交互语义）
// ---------------------------------------------------------------------------

export { measurePeakGeometry, solveAnchorDrag }

/**
 * Drag a half/quarter anchor to targetX: inverse-solve the free width/shape
 * parameters (solveAnchorDrag) and then, for AREA-parameterized functions,
 * hold the peak HEIGHT by rescaling a0 — the exact compensation
 * PeakWorkbench applies after width-anchor drags. Returns new params.
 * 拖拽半高/四分之一锚点到 targetX：反解自由的宽度/形状参数
 * （solveAnchorDrag），随后对面积参数化峰形重标 a0 保持峰高——与
 * PeakWorkbench 宽度锚拖拽后的补偿一致。返回新参数。
 */
export function dragShapeAnchor(
  fn: PeakFnId,
  p: ParamValues,
  locked: Record<string, boolean>,
  startGeom: PeakGeometry,
  kind: 'leftHalf' | 'rightHalf' | 'quarter',
  targetX: number,
): ParamValues {
  const next = solveAnchorDrag({ fn, startP: p, startGeom, kind, targetX, locked })
  if (AREA_PARAM_FNS.has(fn) && Number.isFinite(startGeom.height) && startGeom.height !== 0) {
    const newHeight = measurePeakGeometry(fn, next).height
    if (Number.isFinite(newHeight) && Math.abs(newHeight) > 1e-300) {
      next.a0 = (next.a0 * startGeom.height) / newHeight
    }
  }
  const meta = peakMeta(fn)
  for (const pm of meta.params) {
    // Non-finite solver output (degenerate geometry, NaN pointer) must not
    // reach the model: keep the drag-start value; widths stay strictly > 0.
    // 反解出的非有限值（退化几何 / NaN 指针）绝不能写进模型：保留拖拽起点值，
    // 宽度保持严格为正。（拖拽源在 plotController 还会按数据下限钳制。）
    if (!Number.isFinite(next[pm.key])) next[pm.key] = p[pm.key] ?? 0
    if (pm.min !== null && next[pm.key] < pm.min) next[pm.key] = pm.min
    if (pm.max !== null && next[pm.key] > pm.max) next[pm.key] = pm.max
  }
  return next
}

/**
 * PeakWorkbench-style local width estimate at x: walk outward from the local
 * maximum until the curve falls below half of it (capped), width = the
 * crossing span. Used to seed newly placed peaks. /
 * PeakWorkbench 式局部宽度估计：从局部极大向外走至半高（封顶），宽度 = 交点
 * 跨度；用于新放峰的初宽。
 */
export function estimateLocalWidth(
  xs: ArrayLike<number>,
  ys: ArrayLike<number>,
  x: number,
): number {
  const n = xs.length
  if (n < 3) return 1e-9
  let i = 0
  let best = Number.POSITIVE_INFINITY
  for (let k = 0; k < n; k += 1) {
    const d = Math.abs(xs[k] - x)
    if (d < best) {
      best = d
      i = k
    }
  }
  const h = ys[i]
  if (!Number.isFinite(h) || h <= 0) {
    const span = Math.abs(xs[n - 1] - xs[0]) || 1
    return span / 20
  }
  const half = h / 2
  let l = i
  while (l > 0 && ys[l - 1] >= half) l -= 1
  let r = i
  while (r < n - 1 && ys[r + 1] >= half) r += 1
  const dx = n > 1 ? Math.abs(xs[n - 1] - xs[0]) / (n - 1) : 1
  const w = xs[r] - xs[l]
  const span = Math.abs(xs[n - 1] - xs[0]) || 1
  if (w >= 2 * dx && w <= span / 2) return w
  return Math.max(4 * dx, span / 200)
}

/** Nearest-grid y value at x (clamped to the ends). / x 处最近网格点的 y。 */
export function valueAt(xs: ArrayLike<number>, ys: ArrayLike<number>, x: number): number {
  const n = xs.length
  if (n === 0) return 0
  if (x <= xs[0]) return ys[0]
  if (x >= xs[n - 1]) return ys[n - 1]
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (xs[mid] <= x) lo = mid
    else hi = mid
  }
  return ys[lo]
}

/**
 * Main-anchor drag: horizontal → a1 (center), vertical → a0 scaled by the
 * dragged height ratio (PeakWorkbench semantics; locked parameters are
 * respected). Returns a NEW parameter object. / 主锚拖拽：横拖改 a1（中心），
 * 纵拖按高度比缩放 a0（锁定参数被尊重）；返回新参数对象。
 */
export function applyMainDrag(
  fn: PeakFnId,
  p: ParamValues,
  locked: Record<string, boolean>,
  geom: PeakGeometry,
  targetX: number,
  targetY: number,
): ParamValues {
  const out = { ...p }
  if (!locked.a1 && Number.isFinite(targetX)) out.a1 = targetX
  if (!locked.a0 && Number.isFinite(geom.height) && Math.abs(geom.height) > 1e-300) {
    const nextA0 = (p.a0 * targetY) / geom.height
    // Guard against a non-finite amplitude from an extreme pointer y — it
    // would freeze the peak in the fitter's step-guard (see paramGuard.ts).
    // 防止极端指针 y 产生非有限幅值——那会让峰在拟合步长守卫中被冻结。
    if (Number.isFinite(nextA0)) out.a0 = nextA0
  }
  const meta = peakMeta(fn)
  for (const pm of meta.params) {
    if (pm.min !== null && out[pm.key] < pm.min) out[pm.key] = pm.min
    if (pm.max !== null && out[pm.key] > pm.max) out[pm.key] = pm.max
  }
  return out
}

/** Numeric { fwhm, area, height, center } of one peak (PeakResult fields
 *  reuse). / 单峰的数值 FWHM/面积/峰高/中心。 */
export function peakStatsOf(fn: PeakFnId, p: ParamValues) {
  return peakShape(fn, packParams(fn, p))
}

// ---------------------------------------------------------------------------
// Fit request assembly / 拟合请求组装
// ---------------------------------------------------------------------------

export interface FitJobInput {
  x: Float64Array
  y: Float64Array
  /** Per-point weights (sigma^-2); optional. */
  w?: Float64Array
  /** Inclusion mask (1 = fit). */
  mask: Uint8Array
  peaks: PeakSpec[]
  baseline: BaselineSpec
  maxIter: number
  convDigits: number
  robust: RobustMethod
  fitExtent: number
  xMin: number | null
  xMax: number | null
  constraints: PeakConstraints
}

export function buildFitRequest(input: FitJobInput): FitRequest {
  return {
    jobId: `fit-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    x: input.x,
    y: input.y,
    w: input.w,
    mask: input.mask,
    peaks: input.peaks,
    baseline: input.baseline,
    options: {
      maxIter: input.maxIter,
      convDigits: input.convDigits,
      robust: input.robust,
      fitExtent: input.fitExtent,
      xMin: input.xMin,
      xMax: input.xMax,
      constraints: input.constraints,
    },
    stream: true,
  }
}

// ---------------------------------------------------------------------------
// Worker fit client / Worker 拟合客户端
// ---------------------------------------------------------------------------

export interface FitHandle {
  /** Resolves with the worker outcome, a reconstructed stop-keep result, or
   *  an abort error. / 以 Worker 结果、重建的停止保留结果或中止错误兑现。 */
  done: Promise<FitOutcome>
  /** 停止并保留 semantics (reconstructed from the last iteration event; the
   *  synchronous worker loop cannot be interrupted cooperatively without
   *  SharedArrayBuffer, so the worker is terminated). / 停止并保留：按最后
   *  迭代事件重建（无 SAB 无法协作式中断同步循环，故直接终止 Worker）。 */
  stop(): void
  /** 中止并回滚 semantics: terminate, resolve FitError('aborted'). /
   *  中止并回滚：终止并以 FitError('aborted') 兑现。 */
  abort(): void
}

export function runFitInWorker(
  req: FitRequest,
  onIter?: (event: FitIterEvent) => void,
): FitHandle {
  const worker = new FitWorker()
  let lastIter: FitIterEvent | null = null
  let settled = false
  let resolve: (outcome: FitOutcome) => void
  const done = new Promise<FitOutcome>((res) => {
    resolve = res
  })
  const settle = (outcome: FitOutcome) => {
    if (settled) return
    settled = true
    try {
      worker.terminate()
    } catch {
      /* terminate is best-effort; the promise below must still settle */
    }
    resolve(outcome)
  }
  worker.onmessage = (e: MessageEvent) => {
    const msg = e.data as
      | { type: 'iter'; event: FitIterEvent }
      | { type: 'done'; outcome: FitOutcome }
    if (msg.type === 'iter') {
      lastIter = msg.event
      onIter?.(msg.event)
    } else if (msg.type === 'done') {
      settle(msg.outcome)
    }
  }
  worker.onerror = (err) => {
    settle({ jobId: req.jobId, ok: false, error: `worker error: ${err.message}` })
  }
  try {
    worker.postMessage({ type: 'fit', request: req })
  } catch (err) {
    // A structured-clone failure (reactive Proxy leaked into the request, or
    // a non-cloneable typed array) must settle the SAME promise the caller
    // awaits. Before the 2026-10-20 fix it escaped runFitInWorker before the
    // handle existed, leaking the worker; now it becomes a normal FitError.
    // 结构化克隆失败（请求里混入响应式 Proxy 或不可克隆的类型数组）必须兑现
    // 调用方等待的同一个 Promise；2026-10-20 修复前它会从 runFitInWorker 抛出、
    // 泄漏 Worker，现在统一变成普通 FitError。
    settle({
      jobId: req.jobId,
      ok: false,
      error: `拟合请求无法序列化：${err instanceof Error ? err.message : String(err)}`,
    })
  }
  return {
    done,
    stop() {
      if (settled) return
      if (lastIter) {
        // 停止并保留 reconstruction is pure math but may allocate large
        // arrays; if it ever throws, settle with an explicit FitError instead
        // of leaving `done` pending forever (which used to strand
        // fit.status === 'running' and kill every later fit). / 停止保留的
        // 重建本身是纯数学，但会分配大数组；一旦抛错必须以显式 FitError 兑现，
        // 而不是让 done 永远挂起（那会把 fit.status 卡在 running，之后所有拟合
        // 被静默忽略）。
        let outcome: FitOutcome
        try {
          outcome = reconstructStoppedResult(req, lastIter)
        } catch (err) {
          outcome = {
            jobId: req.jobId,
            ok: false,
            error: `停止重建失败：${err instanceof Error ? err.message : String(err)}`,
          }
        }
        settle(outcome)
      } else {
        settle({ jobId: req.jobId, ok: false, error: 'stopped before the first iteration' })
      }
    },
    abort() {
      settle({ jobId: req.jobId, ok: false, error: 'aborted' })
    },
  }
}

/**
 * Rebuild the peaks/baseline from a flattened iteration snapshot. Order per
 * the core contract: [enabled peaks' params in registry order, unlocked
 * only] + [baseline params, unlocked only]. / 按扁平迭代快照重建峰与基线
 * 参数。顺序依核心契约：[启用峰的注册表序参数（仅未锁定）] + [基线参数
 * （仅未锁定）]。
 */
export function unflattenSnapshot(
  req: FitRequest,
  flat: number[],
): { peaks: PeakSpec[]; baseline: BaselineSpec } {
  let cursor = 0
  const next = (): number => (cursor < flat.length ? flat[cursor++] : Number.NaN)
  const peaks = req.peaks.map((pk) => {
    if (!pk.enabled) return pk
    const p: ParamValues = { ...pk.p }
    for (const pm of peakMeta(pk.fn).params) {
      if (pk.locked[pm.key] === true) continue
      p[pm.key] = next()
    }
    return { ...pk, p }
  })
  const baseline: BaselineSpec = { ...req.baseline, p: { ...req.baseline.p } }
  if (baseline.enabled && baseline.fn !== 'none') {
    for (const pm of baselineMeta(baseline.fn).params) {
      if (baseline.locked[pm.key] === true) continue
      baseline.p[pm.key] = next()
    }
  }
  return { peaks, baseline }
}

/**
 * Stop-keep reconstruction: evaluate the last-iteration parameters over the
 * FULL x range and compute honest display statistics over the windowed,
 * masked points (the optimizer's fitExtent decimation applied only during
 * optimization — statistics here are display-grade). /
 * 停止保留重建：按最后迭代参数在全程求值曲线，并在窗口内有效点上计算展示
 * 级统计量（优化期的 fitExtent 抽稀不在此重复——统计量仅供显示）。
 */
export function reconstructStoppedResult(
  req: FitRequest,
  iter: FitIterEvent,
): FitResult {
  const { peaks, baseline } = unflattenSnapshot(req, iter.params)
  const curves = evalModelCurve(req.x, peaks, baseline)
  const residual = new Float64Array(req.x.length)
  let sse = 0
  let sst = 0
  let n = 0
  const lo = req.options.xMin === null ? Number.NEGATIVE_INFINITY : req.options.xMin
  const hi = req.options.xMax === null ? Number.POSITIVE_INFINITY : req.options.xMax
  const idx: number[] = []
  const ys: number[] = []
  for (let i = 0; i < req.x.length; i += 1) {
    const inWin = req.x[i] >= lo && req.x[i] <= hi
    residual[i] = inWin ? req.y[i] - curves.total[i] : Number.NaN
    if (!inWin || req.mask[i] === 0) continue
    idx.push(i)
    ys.push(req.y[i])
    n += 1
  }
  const mean = n > 0 ? ys.reduce((a, b) => a + b, 0) / n : 0
  for (const i of idx) {
    sse += (req.y[i] - curves.total[i]) ** 2
    sst += (req.y[i] - mean) ** 2
  }
  const k = iter.params.length
  const dof = Math.max(n - k, 1)
  const r2 = sst > 0 ? 1 - sse / sst : Number.NaN
  return {
    jobId: req.jobId,
    ok: true,
    stats: {
      sse,
      rmse: Math.sqrt(n > 0 ? sse / n : Number.NaN),
      fitStdErr: Math.sqrt(sse / dof),
      r2,
      r2Adj: n > 1 && sst > 0 ? 1 - (1 - r2) * (n - 1) / dof : Number.NaN,
      fValue: k > 0 && sse > 0 ? ((sst - sse) / k) / (sse / dof) : Number.NaN,
      dof: n - k,
      n,
      k,
      fnEval: iter.fnEval,
      iterations: iter.iter,
      timeMs: iter.timeMs,
      converged: false,
      stopped: true,
      violFinal: iter.viol,
    },
    peaks: peaks
      .filter((pk) => pk.enabled)
      .map((pk) => {
        const shape = peakStatsOf(pk.fn, pk.p)
        const pErr: ParamValues = {}
        for (const pm of peakMeta(pk.fn).params) pErr[pm.key] = 0
        return {
          id: pk.id,
          fn: pk.fn,
          p: pk.p,
          pErr,
          area: shape.area,
          fwhm: shape.fwhm,
          height: shape.height,
          center: shape.center,
        }
      }),
    baselineP: baseline.p,
    baselineErr: {},
    yFit: curves.total,
    yBase: curves.base,
    yComps: curves.comps,
    residual,
  }
}
