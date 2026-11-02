/**
 * Fit store: fit options, run lifecycle, streamed iteration telemetry.
 *
 * Red line #5 (遥测节流): iteration events are buffered and applied on a
 * 30 Hz pump — curves (Full mode) at every pump tick, text panels at 10 Hz.
 * The pump keeps ONLY the last event of each window; nothing queues up.
 */
import { reactive, ref, shallowRef, watch } from 'vue'
import type {
  FitIterEvent,
  FitOptions,
  FitResult,
  FitStats,
  PeakSpec,
  RobustMethod,
} from '@/lib/pwcore/shared/types'
import { platform } from '../platform/platform'
import { usePeaks } from '../stores/peaks'
import { useSpectrum } from '../stores/spectrum'
import { useUi, type StepId } from '../stores/ui'
import { pushCommand } from '../stores/undo'
import { pushToast } from '../stores/toast'
import { flattenModel, unflattenInto } from '../core-bridge/engine'
import { estimateLocalWidth } from '@/lib/fitEngine'
import { describeRepairs, guardContextFrom, repairPeakParams } from '../utils/paramGuard'
import type { ModelSnapshot } from '../stores/peaks'

export type FitMode = 'fast' | 'full'

/** Adjust Fit: refit automatically after user edits once a first fit exists. */
const autoRefit = ref(false)
let autoRefitTimer: ReturnType<typeof setTimeout> | null = null

const options = reactive<FitOptions>({
  maxIter: 500,
  convDigits: 6,
  robust: 'ls',
  fitExtent: 2,
  xMin: null,
  xMax: null,
  constraints: {
    a0: { enabled: true, pct: 25 },
    a1: { enabled: true, pct: 5 },
    a2: { enabled: true, pct: 50 },
    a3: { enabled: false, pct: 100 },
    a4: { enabled: false, pct: 100 }
  }
})

const mode = ref<FitMode>('full')

const status = ref<'idle' | 'running'>('idle')
const runningJob = ref<string | null>(null)

/** Live telemetry (30 Hz curve pump / 10 Hz text pump). */
const telemetry = reactive({
  iter: 0,
  chi2: Number.NaN,
  r2: Number.NaN,
  viol: 0,
  fnEval: 0,
  timeMs: 0,
})
/** Bumped at 30 Hz while streaming with curves enabled. */
const curvesTick = shallowRef(0)
/** Bumped at 10 Hz while streaming (text panels). */
const telemetryTick = shallowRef(0)

/** Final result of the last completed fit. */
const lastStats = ref<FitStats | null>(null)
const lastResult = ref<FitResult | null>(null)
/** Result meta version: bumped once per finished fit. */
const resultVersion = shallowRef(0)

/** Full-length result curves; plain container, never deep-reactive. */
export interface FitCurves {
  yFit: Float64Array
  yBase: Float64Array
  residual: Float64Array
}
const curves = shallowRef<FitCurves | null>(null)

// ---------------------------------------------------------------------

let preFitSnapshot: ModelSnapshot | null = null
let pendingEvents: FitIterEvent[] = []
let pumpTimer: number | null = null
let pumpCount = 0

function toPlainSpecs(peaks: readonly PeakSpec[]): PeakSpec[] {
  return peaks.map((p) => ({ ...p, p: { ...p.p }, locked: { ...p.locked } }))
}

/**
 * Deep-copy FitOptions into a structured-clone-safe plain object.
 * Vue's `reactive` wraps nested objects in Proxies, and neither
 * `ipcRenderer.invoke` nor `Worker.postMessage` can clone a Proxy
 * (DataCloneError). A shallow spread is NOT enough — `constraints` would
 * still be the reactive proxy.
 */
function toPlainOptions(o: FitOptions): FitOptions {
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
      a4: { enabled: o.constraints.a4.enabled, pct: o.constraints.a4.pct }
    }
  }
}

function buildRequest(enabledOnly: PeakSpec[], jobId: string): Parameters<typeof platform.fit>[0] | null {
  const sp = useSpectrum()
  const xv = sp.x.value
  const yv = sp.y.value
  const mv = sp.mask.value
  if (!xv || !yv || !mv) return null
  const pk = usePeaks()
  const specs = toPlainSpecs(enabledOnly)

  // Defensive parameter repair (2026-10-20 regression fix). The REPRODUCED
  // failure: a half-height anchor dragged across the peak center (or a typed
  // 0/1e-12/1e300) leaves a width the sampled data cannot resolve — the fit
  // then has a zero width Jacobian and the ±50 % soft box keeps it collapsed
  // on every later run, so the peak can never be fitted again. Repair the
  // request copy from the data and tell the user; nothing is repaired silently.
  // 防御性参数修正（2026-10-20 回归修复）。复现的故障：半高锚拖过峰心（或输入
  // 0/1e-12/1e300）会留下采样数据无法分辨的宽度——拟合的宽度雅可比为零，且
  // ±50% 软约束每次都把它按在塌缩值上，该峰此后再也无法拟合。这里按数据修正
  // 请求副本并明确告知用户，绝不静默修改。
  const ctx = guardContextFrom(xv, yv)
  if (ctx) {
    const repaired: string[] = []
    for (const spec of specs) {
      const seedFwhm = estimateLocalWidth(xv, yv, spec.p['a1'] ?? ctx.xMid)
      const fixes = repairPeakParams(spec, ctx, Number.isFinite(seedFwhm) ? seedFwhm : null)
      if (fixes.length > 0) repaired.push(describeRepairs(fixes))
    }
    if (repaired.length > 0) {
      pushToast(
        'warn',
        `已修正 ${repaired.length} 个峰的无效参数（宽度低于数据可分辨下限或幅值越界），` +
          `按数据重新估计后再拟合：${repaired[0]}${repaired.length > 1 ? ' …' : ''}`,
      )
    }
  }

  return {
    jobId,
    x: xv,
    y: yv,
    w: sp.w.value ?? undefined,
    mask: mv.slice(),
    peaks: specs,
    baseline: {
      fn: pk.baseline.fn,
      p: { ...pk.baseline.p },
      locked: { ...pk.baseline.locked },
      enabled: pk.baseline.enabled && pk.baseline.fn !== 'none',
    },
    options: toPlainOptions(options),
    stream: true,
  }
}

function startPump(): void {
  stopPump()
  pumpCount = 0
  pumpTimer = window.setInterval(() => {
    pumpCount++
    if (pendingEvents.length === 0) return
    // keep only the newest event (30 Hz merge window)
    const e = pendingEvents[pendingEvents.length - 1]
    pendingEvents.length = 0
    telemetry.iter = e.iter
    telemetry.chi2 = e.chi2
    telemetry.r2 = e.r2
    telemetry.viol = e.viol
    telemetry.fnEval = e.fnEval
    telemetry.timeMs = e.timeMs

    const pk = usePeaks()
    if (mode.value === 'full') {
      // apply live params so the curves + anchor overlay track the engine
      const flat = e.params
      const plan = unflattenInto(flat, pk.list.value, pk.baseline)
      const byId = new Map(plan.peaks.map((p) => [p.id, p]))
      for (const live of pk.list.value) {
        const next = byId.get(live.id)
        if (next) {
          live.p = next.p
        }
      }
      const b = pk.baseline
      b.p = plan.baseline.p
      curvesTick.value++
    }
    if (pumpCount % 3 === 0) telemetryTick.value++
  }, 33)
}

function stopPump(): void {
  if (pumpTimer !== null) {
    window.clearInterval(pumpTimer)
    pumpTimer = null
  }
}

/**
 * Release the shared fit bookkeeping exactly once and only for the LIVE job.
 * Called from every exit path of startFit (success, engine error, abort) and
 * from the stop/abort failure fallbacks, so `status` can never be stranded at
 * 'running' — the REPRODUCED symptom of a stranded status is a silently dead
 * 拟合 button (startFit early-returns on 'running' and nothing else happens).
 * 释放共享拟合簿记，且只对当前作业生效。startFit 的每条退出路径（成功 / 引擎
 * 异常 / 中止）以及停止/中止的失败兜底都会调用它，保证 `status` 不会卡在
 * 'running'——卡住时的复现症状正是“拟合按钮静默失效”（startFit 直接返回）。
 *
 * The jobId check also keeps a STALE continuation (a fit that was aborted by a
 * data reload, or superseded by a newer fit) from clobbering the newer state.
 * jobId 校验同时阻止过期续延（数据重载中止的拟合、或被更新拟合取代的旧拟合）
 * 覆盖新状态。
 */
function releaseFit(jobId: string): { current: boolean; snapshot: ModelSnapshot | null } {
  if (runningJob.value !== jobId) return { current: false, snapshot: null }
  const snap = preFitSnapshot
  stopPump()
  pendingEvents = []
  status.value = 'idle'
  runningJob.value = null
  preFitSnapshot = null
  return { current: true, snapshot: snap }
}

/**
 * Start a fit. `baselineOnly` fits the baseline with no peak components
 * (the reference application "fit baseline only") without touching the peak list.
 */
export async function startFit(opts?: {
  baselineOnly?: boolean
  onDone?: () => void
  stepTo?: StepId
  /** Adjust-Fit silent auto refit: no toast, no undo entry, no step change. */
  auto?: boolean
}): Promise<void> {
  if (status.value === 'running') {
    // REPRODUCED failure this prevents: a manual 拟合 click during a (silent)
    // Adjust-Fit refit used to disappear without any feedback — "no result,
    // no error". Manual clicks now report it; the silent auto loop stays quiet.
    // 复现的故障：Adjust Fit 静默重拟合期间手动点“拟合”完全没有反馈（无结果、
    // 无报错）。手动点击现在给出提示，自动重拟合仍保持静默。
    if (!opts?.auto) pushToast('info', '已有拟合正在运行：请稍候，或先点“停止 / 中止”')
    return
  }
  const sp = useSpectrum()
  const pk = usePeaks()
  if (!sp.ready.value) {
    pushToast('warn', '没有数据：请先导入数据或加载示例')
    return
  }
  const enabled = opts?.baselineOnly ? [] : pk.list.value.filter((p) => p.enabled)
  if (!opts?.baselineOnly && enabled.length === 0) {
    pushToast('warn', '请先在“放峰”步骤添加至少一个峰')
    return
  }

  preFitSnapshot = pk.exportSnapshot()
  const jobId = `fit-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const req = buildRequest(enabled, jobId)
  if (!req) {
    preFitSnapshot = null
    pushToast('error', '构建拟合请求失败：数据不可用')
    return
  }

  status.value = 'running'
  runningJob.value = jobId
  pendingEvents = []
  telemetry.iter = 0
  telemetry.chi2 = Number.NaN
  telemetry.r2 = Number.NaN
  telemetry.viol = 0
  telemetry.fnEval = 0
  telemetry.timeMs = 0
  startPump()

  let outcome: Awaited<ReturnType<typeof platform.fit>>
  try {
    outcome = await platform.fit(req, (e) => {
      if (e.jobId === runningJob.value) pendingEvents.push(e)
    })
  } catch (err) {
    // The engine must always settle; this is belt-and-braces so a synchronous
    // platform/worker rejection can never leave status at 'running'.
    // 引擎本应总是兑现；此处兜底，防止平台/Worker 同步拒绝把状态留在 running。
    const { current } = releaseFit(jobId)
    if (current) {
      pushToast('error', `拟合引擎异常：${err instanceof Error ? err.message : String(err)}`)
    }
    return
  }

  // ALWAYS release status/job/snapshot first, whatever happens to the result
  // below: result application (store commits, undo push, charts) must not be
  // able to keep the run button locked. / 先无条件释放状态，后续结果写入不得
  // 再把运行按钮锁死。
  const { current, snapshot } = releaseFit(jobId)
  if (!current) return

  if (!outcome.ok) {
    if (outcome.error === 'aborted') {
      // 中止并回滚: roll the whole model back to the pre-fit snapshot
      if (snapshot) pk.importSnapshot(snapshot)
      pushToast('info', '拟合已中止，参数已回滚到拟合前')
    } else {
      pushToast('error', `拟合失败：${outcome.error}`)
    }
    return
  }

  try {
    applyResult(outcome, snapshot, !opts?.auto)
  } catch (err) {
    pushToast('error', `拟合结果写入失败：${err instanceof Error ? err.message : String(err)}`)
    return
  }
  if (opts?.stepTo) useUi().step.value = opts.stepTo
  try {
    opts?.onDone?.()
  } catch (err) {
    pushToast('error', `拟合完成回调失败：${err instanceof Error ? err.message : String(err)}`)
  }
}

/** Commit a finished FitResult into stores. `announce` pushes undo + toast. */
function applyResult(res: FitResult, preSnap: ModelSnapshot | null, announce = true): void {
  const pk = usePeaks()
  const before = preSnap ?? pk.exportSnapshot()

  const byId = new Map(res.peaks.map((r) => [r.id, r]))
  for (const live of pk.list.value) {
    const r = byId.get(live.id)
    if (r) live.p = { ...r.p }
  }
  if (pk.baseline.enabled && pk.baseline.fn !== 'none') {
    pk.baseline.p = { ...res.baselineP }
  }
  pk.setResultMap(byId)

  curves.value = { yFit: res.yFit, yBase: res.yBase, residual: res.residual }
  lastStats.value = res.stats
  lastResult.value = res
  resultVersion.value++

  if (announce) {
    const after = pk.exportSnapshot()
    pushCommand({
      label: '拟合提交',
      undo: () => {
        pk.importSnapshot(before)
        revokeCurves()
      },
      redo: () => {
        pk.importSnapshot(after)
        curves.value = { yFit: res.yFit, yBase: res.yBase, residual: res.residual }
        pk.setResultMap(byId)
        lastStats.value = res.stats
        lastResult.value = res
        resultVersion.value++
      },
    })
    pushToast(
      'success',
      `拟合完成：R² = ${Number.isFinite(res.stats.r2) ? res.stats.r2.toFixed(5) : '—'}，` +
        `${res.stats.iterations} 次迭代，耗时 ${Math.round(res.stats.timeMs)} ms`,
    )
  }
}

/** Drop result curves (data changed / undo past a fit commit). */
export function revokeCurves(): void {
  curves.value = null
  lastStats.value = null
  lastResult.value = null
  resultVersion.value++
}

/**
 * Commit an EXTERNALLY produced FitResult (2026-10-23: viewing a batch-fitted
 * curve in the workbench) — restores curves / stats / per-peak results for
 * display WITHOUT an undo entry or toast (the result belongs to the batch,
 * not to this session's undo history).
 * 提交外部拟合结果（2026-10-23：在工作台查看某条批量拟合曲线）——恢复曲线/
 * 统计/逐峰结果供显示，不进撤销栈、不弹 toast。
 */
export function applyExternalResult(res: FitResult): void {
  applyResult(res, null, false)
}

/** 停止并保留: finish at the current best and resolve normally. */
export function stopFit(): void {
  if (status.value !== 'running') return
  const jobId = runningJob.value
  try {
    platform.stopFit()
  } catch (err) {
    // A throwing stop path must never strand 'running' (that is the exact
    // state where every later fit is silently ignored). Release and report.
    // 停止路径抛错绝不能把状态留在 running（那正是之后每次拟合都被静默忽略的
    // 状态）。释放并报告。
    if (jobId) releaseFit(jobId)
    pushToast('error', `停止失败：${err instanceof Error ? err.message : String(err)}`)
    return
  }
  pushToast('info', '已请求停止：将停在当前最优参数')
}

/** 中止并回滚: cancel and roll back. */
export function abortFit(): void {
  if (status.value !== 'running') return
  const jobId = runningJob.value
  try {
    platform.abortFit()
  } catch (err) {
    // Same guarantee as stopFit: the abort button can never lock the UI.
    // 与 stopFit 相同的保证：中止按钮同样不能把界面锁死。
    if (jobId) releaseFit(jobId)
    pushToast('error', `中止失败：${err instanceof Error ? err.message : String(err)}`)
  }
}

export function setRobust(m: RobustMethod): void {
  options.robust = m
}

export function resetFitState(): void {
  // Abort any in-flight engine run before wiping the session: the worker is
  // terminated and its promise settles, so a stale continuation can neither
  // burn CPU nor (thanks to the jobId guard in releaseFit) apply an old model
  // onto the new data. / 清空会话前先中止在途拟合：Worker 被终止、Promise 兑现，
  // 过期续延既不会空耗 CPU，也不会（靠 releaseFit 的 jobId 校验）把旧模型写进
  // 新数据。
  try {
    platform.abortFit()
  } catch {
    /* reset must never throw; the handle itself is exception-safe */
  }
  stopPump()
  revokeCurves()
  status.value = 'idle'
  runningJob.value = null
  preFitSnapshot = null
  pendingEvents = []
  telemetry.iter = 0
  telemetry.chi2 = Number.NaN
  telemetry.r2 = Number.NaN
  telemetry.viol = 0
  telemetry.fnEval = 0
  telemetry.timeMs = 0
}

export function useFit() {
  const pk = usePeaks()
  const enabledCount = () => pk.enabledPeaks.value.length
  return {
    options, mode, status, runningJob,
    telemetry, telemetryTick, curvesTick,
    lastStats, lastResult, resultVersion,
    curves, autoRefit,
    startFit, stopFit, abortFit,
    setRobust, resetFitState,
    applyExternalResult,
    enabledCount,
    flattenModel,
  }
}

// ---------------------------------------------------------------------------
// Adjust Fit: the reference application's adjust→fit→adjust loop. Every user edit (anchor drag,
// numeric edit, peak add/remove/toggle, baseline change, point exclusion)
// bumps `editTick`; once a fit result exists we silently refit ~200 ms after
// the last edit. Fit-result commits and streaming param writes never bump the
// tick, so this watcher cannot loop.
// ---------------------------------------------------------------------------
watch(
  () => usePeaks().editTick.value,
  () => {
    if (!autoRefit.value || status.value !== 'idle' || !lastResult.value) return
    if (autoRefitTimer !== null) clearTimeout(autoRefitTimer)
    autoRefitTimer = setTimeout(() => {
      autoRefitTimer = null
      const p = usePeaks()
      if (autoRefit.value && status.value === 'idle' && lastResult.value && p.enabledPeaks.value.length > 0) {
        void startFit({ auto: true })
      }
    }, 200)
  },
)
