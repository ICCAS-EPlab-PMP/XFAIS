/**
 * Batch fitting store (v0.3.4, 2026-10-22 user request): fit the FIRST curve
 * interactively, then reuse the current peak list / baseline / data window as
 * the TEMPLATE for every remaining imported curve — sequential fits in the
 * shared fit worker, batch report + CSV export.
 * 批量拟合（2026-10-22 用户要求）：先交互拟合好一条曲线，再以当前峰列表/
 * 基线/数据窗口为模板，逐条拟合其余导入的曲线——顺序在拟合 Worker 中执行，
 * 汇总报告 + CSV 导出。
 *
 * Template semantics (the user's words, implemented literally):
 *   - 峰位（x 轴位置）为后续数据的主要初猜，可小范围移动 —— a1 软约束限制在
 *     ±centerPct%（默认 5%，可调，设 0 即完全锁定中心）；
 *   - y（峰高）用后续曲线自身的数据做初猜（中心处数据值 − 模板基线），但不设
 *     重要影响 —— a0 软约束关闭，幅值完全自由收敛；
 *   - 背景与数据范围设置同第一条 —— 同一基线函数与系数种子（随拟合精修）、
 *     同一 x 窗口（模板掩膜的首末包含点）、同 maxIter/convDigits/robust/
 *     fitExtent。批量曲线不做平滑/扣底等数据步预处理，按原始数据拟合。
 */
import { reactive, ref } from 'vue'
import type {
  BaselineSpec,
  FitOptions,
  FitOutcome,
  FitRequest,
  FitResult,
  ParamValues,
  PeakSpec,
} from '@/lib/pwcore/shared/types'
import { PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { runFitInWorker, type FitHandle } from '@/lib/fitEngine'
import { platform } from '../platform/platform'
import { parseData, evalBaseline } from '../core-bridge/engine'
import { parseIntegrationTable, parseXYBlocks, type ParsedCurve } from '../utils/csvImport'
import { useSpectrum } from './spectrum'
import { usePeaks } from './peaks'
import { useFit, applyExternalResult } from './fit'
import { adoptParsedData } from './session'
import { useUi } from './ui'
import { pushToast } from './toast'
import { crysRoles, kbAssign } from '../utils/analysis'
import { nearestIdxByX } from '../utils/lod'
import { peakValue } from '@/lib/pwcore/core/models'

// ---------------------------------------------------------------------------
// State / 状态
// ---------------------------------------------------------------------------

/** One queued curve (parsed at add time; raw file never re-read). /
 *  一条排队曲线（添加时即解析，不再重读文件）。 */
export interface BatchEntry {
  id: string
  name: string
  n: number
  x: Float64Array
  y: Float64Array
  w: Float64Array | null
  /** Parse-time mask from the file (PRN trailing '*'). / 文件解析期掩膜。 */
  mask: Uint8Array
}

/** Per-peak row of the batch report. / 批量报告的逐峰行。 */
export interface BatchPeakRow {
  index: number
  fnName: string
  center: number
  centerErr: number
  height: number
  heightErr: number
  fwhm: number
  area: number
}

/** Per-file outcome. / 单条曲线的批量结果。 */
export interface BatchFileResult {
  id: string
  name: string
  status: 'pending' | 'running' | 'done' | 'failed'
  error?: string
  r2?: number
  r2Adj?: number
  iterations?: number
  converged?: boolean
  timeMs?: number
  peaks?: BatchPeakRow[]
  baselineP?: ParamValues
  /** Fitted model snapshot (template peaks with fitted params + baseline) —
   * the basis for「点击曲线条查看该曲线」(2026-10-23). / 拟合模型快照（模板
   * 峰代入拟合参数 + 基线），供点击曲线条在工作台查看该曲线。 */
  model?: { peaks: PeakSpec[]; baseline: BaselineSpec }
  /** Full fit outcome (stats + per-peak PeakResult + curves) when keepCurves
   * is on — restores curves/stats on view without refitting. /
   *  完整拟合结果（keepCurves 时保留），查看时免重拟合恢复曲线与统计。 */
  outcome?: FitResult
  /** Curves kept for the optional data+fit export (only when keepCurves). /
   *  保留的曲线（仅 keepCurves 时），供可选的数据+拟合导出。 */
  curves?: {
    x: Float64Array
    y: Float64Array
    mask: Uint8Array
    yFit: Float64Array
    yBase: Float64Array
    residual: Float64Array
  }
}

const entries = ref<BatchEntry[]>([])
const results = ref<BatchFileResult[] | null>(null)
const running = ref(false)
const progress = reactive({ done: 0, total: 0, current: '' })

/** Batch options (view preferences — deliberately not reset per run). /
 *  批量选项（视图偏好，不随运行重置）。 */
export const batchOpts = reactive({
  /** Soft-constraint box for peak centers, ±% of each center. 0 = free. /
   *  峰位软约束（各峰 ±%，0 = 不限制）。 */
  centerPct: 5,
  /** Keep per-file curves in memory for the combined data+fit export. /
   *  保留每条曲线用于合并导出。 */
  keepCurves: true,
})

let cancelRequested = false
let entrySeq = 0

// ---------------------------------------------------------------------------
// File → curves (2026-10-23: X-FAIS integration imports) / 文件 → 曲线
// ---------------------------------------------------------------------------

/** Curves extracted from ONE opened file + the file-level weights/mask that
 * apply to every curve from it. / 单个文件解析出的曲线及文件级权重/掩膜。 */
interface FileCurves {
  curves: ParsedCurve[]
  w: Float64Array | null
  mask: Uint8Array | null
}

/**
 * X-FAIS 积分结果导入（2026-10-23 用户要求）：优先按积分导出表解析——
 * TXT/CSV 的每条强度列各成一条曲线、.xy 每空行分段一条；不匹配时回落到
 * 通用 parseData（保留其权重列与掩膜）。
 */
function curvesFromFile(name: string, text: string): FileCurves {
  if (/\.xy$/i.test(name)) {
    const xy = parseXYBlocks(text, name)
    if (xy) return { curves: xy, w: null, mask: null }
  }
  const table = parseIntegrationTable(text, name)
  if (table) return { curves: table, w: null, mask: null }
  const parsed = parseData(text, name)
  if (parsed.x.length < 2) throw new Error('有效数据点不足')
  return {
    curves: [{ name, x: parsed.x, y: parsed.y }],
    w: parsed.w,
    mask: parsed.mask ?? null,
  }
}

function queueCurve(c: ParsedCurve, w: Float64Array | null, mask: Uint8Array | null): void {
  entries.value.push({
    id: newEntryId(),
    name: c.name,
    n: c.x.length,
    x: c.x,
    y: c.y,
    w,
    mask: mask ?? new Uint8Array(c.x.length).fill(1),
  })
}
/**
 * Own handle for the CURRENT batch fit. The batch runs its own worker via
 * runFitInWorker instead of platform.fit on purpose: platform.fit keeps ONE
 * module-level "current" handle, so an interactive fit started while a batch
 * is running would otherwise make cancelBatch() abort the WRONG run.
 * 批量拟合自持当前 worker 句柄：不走 platform.fit（它只保留一个全局当前
 * 句柄，批量期间用户若启动交互拟合，取消会打错目标）。
 */
let currentBatchFit: FitHandle | null = null

function newEntryId(): string {
  entrySeq += 1
  return `be${Date.now().toString(36)}${entrySeq.toString(36)}`
}

// ---------------------------------------------------------------------------
// Queue management / 队列管理
// ---------------------------------------------------------------------------

/**
 * Add curve files through the platform multi-file picker. Requires a working
 * curve to exist first (the template is the CURRENT session) — the user's
 * flow is "fit one curve first, then batch the rest". Integration exports
 * (TXT/CSV multi-column, XY multi-block) expand to one curve per column /
 * block (2026-10-23). / 通过平台多选文件对话框添加批量曲线。要求当前已有
 * 工作曲线；积分导出表按列/按段展开为多条曲线。
 */
export async function addBatchFiles(): Promise<number> {
  const sp = useSpectrum()
  if (!sp.ready.value) {
    pushToast('warn', '请先用「导入数据」载入并拟合第一条曲线，再添加批量文件')
    return 0
  }
  const files = await platform.openDataFiles()
  if (!files || files.length === 0) return 0
  let added = 0
  let failed = 0
  for (const f of files) {
    try {
      const text = typeof f.data === 'string' ? f.data : new TextDecoder().decode(f.data)
      const fc = curvesFromFile(f.name, text)
      for (const c of fc.curves) queueCurve(c, fc.w, fc.mask)
      added += fc.curves.length
    } catch {
      failed++
    }
  }
  if (added > 0) {
    results.value = null
    pushToast('success', `已添加 ${added} 条批量曲线${failed > 0 ? `（${failed} 个文件解析失败）` : ''}`)
  } else {
    pushToast('error', `批量文件解析失败（${failed} 个）`)
  }
  return added
}

export function removeEntry(id: string): void {
  const i = entries.value.findIndex((e) => e.id === id)
  if (i >= 0) entries.value.splice(i, 1)
  // The result row of a removed curve must not linger in the strip/report.
  // 被删曲线的结果行不能残留在曲线条/报告里。
  if (results.value) results.value = results.value.filter((r) => r.id !== id)
}

export function clearBatchQueue(): void {
  entries.value = []
  results.value = null
}

// ---------------------------------------------------------------------------
// Multi-file import & curve switching (2026-10-23 user request) /
// 多选导入与曲线切换（2026-10-23 用户要求）
// ---------------------------------------------------------------------------

/**
 * Multi-select import — the ONE import entry point now (the paste box is
 * gone). Picking a single file behaves exactly like the old import; picking
 * several ENTERS BATCH MODE: the first curve becomes the working (reference)
 * curve when none is loaded, every curve joins the bottom curve strip.
 * X-FAIS integration exports expand here (2026-10-23): a multi-column
 * TXT/CSV table yields ONE CURVE PER INTENSITY COLUMN, a multi-block .xy
 * yields one curve per block — the natural batch input.
 * 多选导入（唯一导入入口）。选 1 个 = 原单文件导入；选多个 = 进入批量模式。
 * 积分导出在此展开：多列 TXT/CSV 每条强度列一条曲线、多段 .xy 每段一条。
 */
export async function importMultiple(): Promise<number> {
  const sp = useSpectrum()
  const files = await platform.openDataFiles()
  if (!files || files.length === 0) return 0
  const ok: FileCurves[] = []
  let failed = 0
  for (const f of files) {
    try {
      const text = typeof f.data === 'string' ? f.data : new TextDecoder().decode(f.data)
      ok.push(curvesFromFile(f.name, text))
    } catch {
      failed++
    }
  }
  const total = ok.reduce((a, fc) => a + fc.curves.length, 0)
  if (total === 0) {
    pushToast('error', `导入失败：${failed} 个文件均无法解析`)
    return 0
  }
  results.value = null
  // 无数据时第一条成为工作（参考）曲线；其余全部入队。 /
  // First curve becomes the working (reference) curve when none is loaded.
  if (!sp.ready.value) {
    const first = ok[0]?.curves.shift()
    if (first) {
      adoptParsedData(
        {
          title: first.name,
          x: first.x,
          y: first.y,
          w: null,
          mask: new Uint8Array(first.x.length).fill(1),
        },
        first.name,
      )
      pushToast('success', `已载入 ${first.name}（${first.x.length} 点）`)
    }
  }
  let queued = 0
  for (const fc of ok) {
    for (const c of fc.curves) {
      queueCurve(c, fc.w, fc.mask)
      queued++
    }
  }
  if (queued > 0) {
    pushToast(
      'success',
      `批量模式：已加入 ${queued} 条曲线${failed > 0 ? `（${failed} 个文件解析失败）` : ''}。底部曲线条可点击切换参考曲线；` +
        '工具栏「批量拟合」以当前曲线为模板运行',
    )
  } else if (failed > 0) {
    pushToast('warn', `已载入 1 条曲线；其余 ${failed} 个文件解析失败`)
  }
  return queued
}

/**
 * Switch the workbench to ONE batch curve (2026-10-23: 「下方数据处理由用户
 * 来选择以哪一条来参考」「批量拟合后也可以点击某一条来观看效果」). Loads
 * the curve's data (with its effective batch mask), restores its fitted model
 * and — when curves were kept — its curves/stats without refitting. Polymer
 * analysis assignments are preserved across the switch (peak ids are the
 * template's). / 切换工作台到某条批量曲线：载入数据（含批量有效掩膜）、
 * 恢复拟合模型；保留曲线时连曲线与统计一并恢复（免重拟合）。聚合物分析
 * 指派跨曲线保留（峰 id 即模板 id）。
 */
export function loadCurveIntoSession(id: string): void {
  if (running.value) {
    pushToast('info', '批量拟合进行中：请先等待或取消，再切换曲线')
    return
  }
  const entry = entries.value.find((e) => e.id === id)
  if (!entry) return
  const res = results.value?.find((r) => r.id === id)
  const effMask = res?.curves ? res.curves.mask : entry.mask
  // adoptParsedData performs a full session reset INCLUDING the analysis
  // assignments — snapshot and restore them so Kβ/结晶度 tags survive the
  // curve switch (they reference template peak ids, which stay valid).
  // adoptParsedData 会整体重置会话（含分析指派）——快照并在切换后恢复，
  // 让 Kβ/结晶度标注跨曲线存活（它们引用模板峰 id，始终有效）。
  const savedRoles = { ...crysRoles }
  const savedKb = { ...kbAssign }
  adoptParsedData(
    { title: entry.name, x: entry.x, y: entry.y, w: entry.w, mask: effMask },
    entry.name,
  )
  for (const k of Object.keys(savedRoles)) crysRoles[k] = savedRoles[k]
  Object.assign(kbAssign, savedKb)

  const pk = usePeaks()
  if (res?.model) {
    pk.importSnapshot({ peaks: res.model.peaks, baseline: res.model.baseline, selectedId: null })
    if (res.outcome) {
      applyExternalResult(res.outcome)
      useUi().step.value = 'report'
    } else {
      useUi().step.value = 'peaks'
    }
  }
  pushToast(
    'success',
    `已切换到 ${entry.name}${res?.status === 'done' ? '（含批量拟合结果）' : ''}`,
  )
}

// ---------------------------------------------------------------------------
// Template capture & request build / 模板捕获与请求构建
// ---------------------------------------------------------------------------

interface BatchTemplate {
  peaks: PeakSpec[]
  baseline: BaselineSpec
  options: FitOptions
  winLo: number
  winHi: number
}

/** Plain copy of the (reactive) fit options — Vue proxies cannot be
 * structuredClone'd / posted to a worker; copy field by field like fit.ts. /
 * 拟合选项的普通副本——Vue 代理不可 structuredClone/不可 postMessage。 */
function plainOptions(o: FitOptions): FitOptions {
  return {
    maxIter: o.maxIter,
    convDigits: o.convDigits,
    robust: o.robust,
    fitExtent: o.fitExtent,
    xMin: o.xMin,
    xMax: o.xMax,
    constraints: {
      a0: { enabled: o.constraints.a0.enabled, pct: o.constraints.a0.pct },
      a1: { enabled: o.constraints.a1.enabled, pct: o.constraints.a1.pct },
      a2: { enabled: o.constraints.a2.enabled, pct: o.constraints.a2.pct },
      a3: { enabled: o.constraints.a3.enabled, pct: o.constraints.a3.pct },
      a4: { enabled: o.constraints.a4.enabled, pct: o.constraints.a4.pct },
    },
  }
}

function captureTemplate(): BatchTemplate | null {
  const sp = useSpectrum()
  const pk = usePeaks()
  const fit = useFit()
  const xv = sp.x.value
  const mv = sp.mask.value
  if (!xv || !mv) return null
  const enabled = pk.list.value.filter((p) => p.enabled)
  if (enabled.length === 0) return null

  // Data window = first..last INCLUDED point of the template mask (the user's
  // 「数据范围设置同第一条」: excluded bands in the data step are honoured).
  // 数据窗口 = 模板掩膜的首末包含点（「数据范围同第一条」，尊重数据步的排除）。
  let lo = Number.POSITIVE_INFINITY
  let hi = Number.NEGATIVE_INFINITY
  for (let i = 0; i < mv.length; i++) {
    if (mv[i] !== 1) continue
    if (xv[i] < lo) lo = xv[i]
    if (xv[i] > hi) hi = xv[i]
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
    lo = sp.meta.xMin
    hi = sp.meta.xMax
  }

  return {
    peaks: enabled.map((p) => ({ ...p, p: { ...p.p }, locked: { ...p.locked } })),
    baseline: {
      fn: pk.baseline.fn,
      p: { ...pk.baseline.p },
      locked: { ...pk.baseline.locked },
      enabled: pk.baseline.enabled && pk.baseline.fn !== 'none',
    },
    options: plainOptions(fit.options),
    winLo: lo,
    winHi: hi,
  }
}

function baselineAt(tpl: BatchTemplate, x: number): number {
  if (!tpl.baseline.enabled) return 0
  const v = evalBaseline(tpl.baseline.fn, tpl.baseline.p, [x])
  return v[0] ?? 0
}

/**
 * Rescale ONE template peak's amplitude so its height seeds from the entry's
 * own data (y at the nearest x to the center, minus the template baseline) —
 * the user's 「y 为后续初猜，但不设置重要影响」. Unreliable seeds (wrong
 * sign / vanishing magnitude) keep the template amplitude.
 * 以该曲线自身数据重标峰幅初猜（中心最近点数据值 − 模板基线）；种子不可靠
 * （异号/量级消失）时沿用模板幅值。
 */
function seedPeakForEntry(tp: PeakSpec, entry: BatchEntry, tpl: BatchTemplate): PeakSpec {
  const p: ParamValues = { ...tp.p }
  const meta = PEAK_FN_MAP.get(tp.fn)
  const center = tp.p.a1 ?? 0
  const packed = (meta?.params ?? []).map((pm) => tp.p[pm.key] ?? 0)
  const hT = peakValue(tp.fn, packed, center)
  if (Number.isFinite(hT) && Math.abs(hT) > 1e-300) {
    const j = nearestIdxByX(entry.x, center)
    const hSeed = entry.y[j] - baselineAt(tpl, center)
    if (
      Number.isFinite(hSeed) &&
      hT * hSeed > 0 &&
      Math.abs(hSeed) > 1e-300 &&
      Math.abs(hSeed / hT) > 1e-6
    ) {
      const a0 = tp.p.a0 * (hSeed / hT)
      if (Number.isFinite(a0)) p.a0 = a0
    }
  }
  return { ...tp, p, locked: { ...tp.locked } }
}

function buildEntryRequest(
  entry: BatchEntry,
  tpl: BatchTemplate,
  jobId: string,
): { req: FitRequest; included: number } | { error: string } {
  const mask = new Uint8Array(entry.x.length)
  let included = 0
  for (let i = 0; i < entry.x.length; i++) {
    const ok =
      entry.mask[i] === 1 &&
      entry.x[i] >= tpl.winLo &&
      entry.x[i] <= tpl.winHi &&
      !(entry.w && !Number.isFinite(entry.w[i]))
    mask[i] = ok ? 1 : 0
    if (ok) included++
  }
  if (included < 5) {
    return {
      error: `窗口内有效点仅 ${included} 个（数据范围与模板窗口不重叠？）`,
    }
  }
  const opts = tpl.options
  const req: FitRequest = {
    jobId,
    x: entry.x,
    y: entry.y,
    w: entry.w ?? undefined,
    mask,
    peaks: tpl.peaks.map((tp) => seedPeakForEntry(tp, entry, tpl)),
    baseline: {
      fn: tpl.baseline.fn,
      p: { ...tpl.baseline.p },
      locked: { ...tpl.baseline.locked },
      enabled: tpl.baseline.enabled,
    },
    options: {
      maxIter: opts.maxIter,
      convDigits: opts.convDigits,
      robust: opts.robust,
      fitExtent: opts.fitExtent,
      xMin: opts.xMin,
      xMax: opts.xMax,
      constraints: {
        // 幅值自由（y 不设重要影响）；峰位限 ±centerPct% 小范围移动；
        // 宽度等沿用模板约束设置。
        a0: { enabled: false, pct: 100 },
        a1: { enabled: batchOpts.centerPct > 0, pct: batchOpts.centerPct },
        a2: { ...opts.constraints.a2 },
        a3: { ...opts.constraints.a3 },
        a4: { ...opts.constraints.a4 },
      },
    },
    stream: false,
  }
  return { req, included }
}

// ---------------------------------------------------------------------------
// Runner / 运行器
// ---------------------------------------------------------------------------

export async function runBatch(): Promise<void> {
  const sp = useSpectrum()
  const pk = usePeaks()
  const fit = useFit()
  if (running.value) return
  if (!sp.ready.value) {
    pushToast('warn', '没有数据：请先载入并拟合第一条曲线')
    return
  }
  if (pk.list.value.filter((p) => p.enabled).length === 0) {
    pushToast('warn', '当前没有峰模型：请先在第一条曲线上放峰并拟合')
    return
  }
  if (entries.value.length === 0) {
    pushToast('warn', '批量队列为空：请先添加批量曲线文件')
    return
  }
  if (fit.status.value === 'running') {
    pushToast('info', '交互拟合正在进行：请等它结束再开始批量拟合')
    return
  }
  const tpl = captureTemplate()
  if (!tpl) {
    pushToast('error', '模板捕获失败')
    return
  }

  running.value = true
  cancelRequested = false
  progress.done = 0
  progress.total = entries.value.length
  progress.current = ''
  results.value = entries.value.map((e) => ({ id: e.id, name: e.name, status: 'pending' }))

  let okCount = 0
  let failCount = 0
  for (let i = 0; i < entries.value.length; i++) {
    if (cancelRequested) break
    const entry = entries.value[i]
    const res = results.value![i]!
    progress.current = entry.name
    res.status = 'running'
    const built = buildEntryRequest(entry, tpl, `batch-${i}-${Date.now().toString(36)}`)
    if ('error' in built) {
      res.status = 'failed'
      res.error = built.error
      failCount++
      progress.done++
      continue
    }
    let outcome: FitOutcome
    const handle = runFitInWorker(built.req)
    currentBatchFit = handle
    try {
      outcome = await handle.done
    } catch (err) {
      outcome = {
        jobId: built.req.jobId,
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      }
    } finally {
      if (currentBatchFit === handle) currentBatchFit = null
    }
    if (!outcome.ok) {
      if (outcome.error === 'aborted') {
        res.status = 'pending'
        res.error = '已取消'
        break
      }
      res.status = 'failed'
      res.error = outcome.error
      failCount++
    } else {
      res.status = 'done'
      okCount++
      res.r2 = outcome.stats.r2
      res.r2Adj = outcome.stats.r2Adj
      res.iterations = outcome.stats.iterations
      res.converged = outcome.stats.converged
      res.timeMs = outcome.stats.timeMs
      res.baselineP = { ...outcome.baselineP }
      res.peaks = outcome.peaks.map((r, k) => ({
        index: k + 1,
        fnName: PEAK_FN_MAP.get(r.fn)?.name ?? r.fn,
        center: r.center,
        centerErr: r.pErr.a1 ?? 0,
        height: r.height,
        heightErr: r.pErr.a0 ?? 0,
        fwhm: r.fwhm,
        area: r.area,
      }))
      if (batchOpts.keepCurves) {
        res.curves = {
          x: entry.x,
          y: entry.y,
          mask: built.req.mask,
          yFit: outcome.yFit,
          yBase: outcome.yBase,
          residual: outcome.residual,
        }
        res.outcome = outcome
      }
      // Model snapshot for「点击查看」：template peak specs with the FITTED
      // params merged in (peak ids stay = template ids, so polymer-analysis
      // assignments keep working across curves). / 供点击查看的模型快照：
      // 模板峰代入拟合参数（id 保持模板 id，聚合物分析指派跨曲线有效）。
      const fitted = new Map(outcome.peaks.map((r) => [r.id, r]))
      res.model = {
        peaks: built.req.peaks.map((qp) => {
          const r = fitted.get(qp.id)
          return r ? { ...qp, p: { ...qp.p, ...r.p } } : { ...qp, p: { ...qp.p } }
        }),
        baseline: {
          ...built.req.baseline,
          p: { ...built.req.baseline.p, ...outcome.baselineP },
        },
      }
    }
    progress.done++
  }

  running.value = false
  progress.current = ''
  if (cancelRequested) {
    pushToast('info', `批量拟合已取消：完成 ${okCount} 条，失败 ${failCount} 条`)
  } else {
    pushToast(
      okCount > 0 ? 'success' : 'error',
      `批量拟合完成：成功 ${okCount} 条${failCount > 0 ? `，失败 ${failCount} 条` : ''}`,
    )
  }
}

/** Cancel after the current file's fit settles (aborts the in-flight fit). */
export function cancelBatch(): void {
  if (!running.value) return
  cancelRequested = true
  try {
    currentBatchFit?.abort()
  } catch {
    /* the in-flight promise settles itself; the loop stops on the flag */
  }
}

export function resetBatchState(): void {
  cancelBatch()
  entries.value = []
  results.value = null
  running.value = false
  progress.done = 0
  progress.total = 0
  progress.current = ''
}

export function useBatch() {
  return {
    entries, results, running, progress, batchOpts,
    addBatchFiles, removeEntry, clearBatchQueue,
    importMultiple, loadCurveIntoSession,
    runBatch, cancelBatch,
  }
}
