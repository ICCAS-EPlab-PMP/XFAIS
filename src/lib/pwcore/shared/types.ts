/**
 * PeakWorkbench 谱峰工作台 — shared type contract (READ-ONLY for all agents).
 *
 * This file is the single source of truth between the renderer (Vue3),
 * the Electron main process (fit worker) and the pure numerical core
 * (`src/core`). If a change is genuinely required, report it in your
 * agent summary instead of editing; the integrator owns this file.
 */
import type { BaselineFnId, PeakFnId } from './registry'

// ---------------------------------------------------------------------------
// IPC channel names (main + preload must use these exact values)
// ---------------------------------------------------------------------------
export const IPC = {
  FIT: 'pw:fit',
  STOP: 'pw:stop',
  ABORT: 'pw:abort',
  ITER: 'pw:iter',
  OPEN_FILE: 'pw:openFile',
  SAVE_FILE: 'pw:saveFile',
  WIN_MIN: 'pw:win:minimize',
  WIN_MAX: 'pw:win:maximize',
  WIN_CLOSE: 'pw:win:close',
  WIN_STATE: 'pw:win:state'
} as const

// ---------------------------------------------------------------------------
// Model description
// ---------------------------------------------------------------------------

/** Parameter values keyed by canonical names (a0..a4 for peaks, b0.. for baselines). */
export type ParamValues = Record<string, number>
/** Lock flags per parameter: locked parameters are held constant during fitting. */
export type ParamLocks = Record<string, boolean>

export interface PeakSpec {
  /** Stable unique id (renderer-generated). */
  id: string
  fn: PeakFnId
  p: ParamValues
  locked: ParamLocks
  /** Disabled peaks stay on the chart (ghosted) but are excluded from fitting. */
  enabled: boolean
  /** Renderer-assigned display color; core/worker never touch it. */
  color?: string
}

export interface BaselineSpec {
  fn: BaselineFnId
  p: ParamValues
  locked: ParamLocks
  /** When true the baseline parameters are fitted together with the peaks (the reference application style). */
  enabled: boolean
}

export type RobustMethod = 'ls' | 'lad' | 'lorentz' | 'p7lim'

/**
 * Built-In Peak Fn Constraints — replicated from the reference application's Fitting Preferences
 * (manual p.6-44..6-45, defaults recovered from the shipped dialog):
 * each peak parameter a0..a4 may be constrained to vary at most `pct` percent
 * from its initial (placed/adjusted) estimate. Constraint enforcement is soft:
 * the engine minimizes goodness-of-fit plus constraint violations, so early
 * iterations may report violations and later work themselves free.
 */
export interface ConstraintSpec {
  enabled: boolean
  pct: number
}

export interface PeakConstraints {
  a0: ConstraintSpec
  a1: ConstraintSpec
  a2: ConstraintSpec
  a3: ConstraintSpec
  a4: ConstraintSpec
}

/** Original shipped defaults: a0 25%, a1 5%, a2 50% ON; a3/a4 OFF. */
export const DEFAULT_CONSTRAINTS: PeakConstraints = {
  a0: { enabled: true, pct: 25 },
  a1: { enabled: true, pct: 5 },
  a2: { enabled: true, pct: 50 },
  a3: { enabled: false, pct: 100 },
  a4: { enabled: false, pct: 100 }
}

export interface FitOptions {
  /** Hard iteration cap; original default 500. */
  maxIter: number
  /**
   * Convergence rule replicated from the reference application: fitting stops when chi-square
   * has been stable to this many significant digits for 5 consecutive
   * iterations. Range 3..14, original default 6.
   */
  convDigits: number
  robust: RobustMethod
  /** Fit extent decimation: use every Nth point in the fit (original default 2 = "Every Other Point"). Plotting always uses all points. */
  fitExtent: number
  /** Fit window bounds (data units). Null = data extremes. */
  xMin: number | null
  xMax: number | null
  /** Built-in peak function constraints (percent variation from initial estimate). */
  constraints: PeakConstraints
}

export interface FitRequest {
  jobId: string
  x: Float64Array
  y: Float64Array
  /** Per-point weights (sigma^-2); optional, defaults to 1. */
  w?: Float64Array
  /** Inclusion mask: 1 = point participates in the fit, 0 = excluded point (the reference application disabled points). */
  mask: Uint8Array
  peaks: PeakSpec[]
  baseline: BaselineSpec
  options: FitOptions
  /** When true the worker streams one FitIterEvent per iteration. */
  stream: boolean
}

/** Flattened parameter vector order: [peak0 params..., peak1 params..., ..., baseline params...] over ENABLED, UNLOCKED params only. */
export interface FitIterEvent {
  jobId: string
  iter: number
  chi2: number
  r2: number
  /** Number of bound-constraint violations this iteration (first-class telemetry, like the original). */
  viol: number
  fnEval: number
  /** Full parameter snapshot in flattened order, same length every iteration. */
  params: number[]
  timeMs: number
}

export interface PeakResult {
  id: string
  fn: PeakFnId
  p: ParamValues
  /** 1-sigma standard errors (only for fitted parameters; locked ones get 0). */
  pErr: ParamValues
  /** Numeric peak area (trapezoid over a wide window, or analytic when available). */
  area: number
  /** Numeric FWHM in x units. */
  fwhm: number
  /** Height at center of the peak component (baseline excluded). */
  height: number
  /** Center parameter value (a1). */
  center: number
}

export interface FitStats {
  sse: number
  rmse: number
  /** Fit Std Err = sqrt(SSE / dof). */
  fitStdErr: number
  r2: number
  r2Adj: number
  fValue: number
  /** Degrees of freedom = n_points - n_params. */
  dof: number
  /** Number of data points actually used in the fit. */
  n: number
  /** Number of free parameters. */
  k: number
  fnEval: number
  iterations: number
  timeMs: number
  converged: boolean
  /** True when the user pressed 停止并保留: parameters are the best so far. */
  stopped: boolean
  violFinal: number
}

export interface FitResult {
  jobId: string
  ok: true
  stats: FitStats
  peaks: PeakResult[]
  baselineP: ParamValues
  baselineErr: ParamValues
  /** Model curve over the FULL x range (evaluate final params everywhere). */
  yFit: Float64Array
  yBase: Float64Array
  /** Per enabled peak component curves over the FULL x range. */
  yComps: Float64Array[]
  /** residual = y - yFit over the FULL x range (NaN where x outside fit window). */
  residual: Float64Array
}

export interface FitError {
  jobId: string
  ok: false
  error: string
}

export type FitOutcome = FitResult | FitError

// ---------------------------------------------------------------------------
// Auto peak detection (残差法 residual / 残差法I second-derivative)
// ---------------------------------------------------------------------------

export interface DetectOptions {
  method: 'residual' | 'deriv2'
  /** 0..1 sensitivity; higher finds more peaks. */
  sensitivity: number
  maxPeaks: number
  /** Peak function used for the added initial guesses. */
  fn: PeakFnId
  /** Optional Savitzky-Golay pre-smooth window (0 = none). */
  smoothWindow: number
  /** Current model curve to compute residuals from; omit to work on raw data. */
  yModel?: Float64Array
}

export interface DetectedPeak {
  x0: number
  y0: number
  width: number
  /** Prominence (or 2nd-deriv depth) normalized 0..1, for UI sorting. */
  strength: number
}

// ---------------------------------------------------------------------------
// Smoothing / filtering (traditional data prep)
// ---------------------------------------------------------------------------

export type SmoothMethod = 'sg' | 'movavg' | 'fftLowpass'

export interface SmoothOptions {
  method: SmoothMethod
  /** Window in points (sg, movavg); ignored by fftLowpass. */
  window: number
  /** Savitzky-Golay polynomial order 2..6. */
  polyOrder: number
  /** FFT lowpass cutoff as fraction of Nyquist, 0..1. */
  cutoff: number
}

// ---------------------------------------------------------------------------
// Data files
// ---------------------------------------------------------------------------

export interface ParsedData {
  title: string
  x: Float64Array
  y: Float64Array
  w: Float64Array | null
  /** 1 = included, 0 = excluded (PRN trailing '*'). */
  mask: Uint8Array
}

// X-FAIS fork (2026-10-20, user request): two X-ray demos join the original
// three — WAXS polypropylene (α/β crystalline peaks + amorphous halo) and an
// azimuthal I(χ) orientation profile. X-FAIS 分叉：在原三种示例外新增两个
// X 射线示例——聚丙烯 WAXS（α/β 结晶峰 + 非晶晕）与取向 I(χ) 方位谱。
export type DemoKind = 'chrom' | 'raman' | 'xps' | 'waxsPP' | 'azimuth'

export interface DemoData {
  title: string
  x: Float64Array
  y: Float64Array
  /** True components for optional ground-truth demo overlay. */
  truth?: { fn: PeakFnId; p: ParamValues }[]
}

// ---------------------------------------------------------------------------
// Preload API surface (window.pw)
// ---------------------------------------------------------------------------

export interface OpenedFile {
  name: string
  /** UTF-8 text for prn/csv/txt, raw bytes for scn. */
  data: string | ArrayBuffer
}

export interface WindowControls {
  minimize(): void
  toggleMaximize(): void
  close(): void
}

export interface WorkbenchApi {
  /** Run a fit; onIter receives throttled-by-nothing iteration events (renderer throttles display). */
  fit(req: FitRequest, onIter?: (e: FitIterEvent) => void): Promise<FitOutcome>
  /** 停止并保留 semantics: finish at current best, resolve the fit promise normally. */
  stopFit(): void
  /** 中止并回滚 semantics: cancel; the pending promise resolves with FitError('aborted'). Renderer rolls back its own snapshot. */
  abortFit(): void
  /** Native open dialog; null when cancelled. */
  openDataFile(): Promise<OpenedFile | null>
  /** Native save dialog; false when cancelled. */
  saveDataFile(defaultName: string, data: string | Uint8Array): Promise<boolean>
  /** Null when running in plain browser preview. */
  window: WindowControls | null
  onWindowState(cb: (s: { maximized: boolean }) => void): void
}
