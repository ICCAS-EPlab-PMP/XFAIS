/**
 * Bounded Levenberg-Marquardt fitter with the reference application-compatible convergence,
 * robust objectives and percent-of-initial soft constraints.
 *
 * Convergence rule (replicated from PF.EXE / manual p.168): stop when the
 * objective chi-square has been stable to `convDigits` significant digits
 * for 5 consecutive iterations; hard cap `maxIter` (original default 500).
 * The convergence test deliberately uses the data objective only (the
 * constraint penalty is never part of the significant-digit rule), exactly
 * like the original telemetry.
 *
 * Step acceptance uses the Levenberg-Marquardt gain ratio
 *   rho = (F_old - F_new) / pred,   pred = d^T (lambda D d + g),
 * where g is the descent gradient (-J^T r for residuals r = y - model), D the
 * damping diagonal and d the *unclipped* LM step. A step is accepted only
 * when rho > 0 and F_new is finite; otherwise lambda is increased and the
 * step retried. This replaces the old "any decrease wins" rule, which
 * accepted degenerate steps whose projection onto a bound cut the predicted
 * decrease, shrank lambda and ultimately let parameters explode.
 *
 * Built-In Peak Fn Constraints (manual p.6-44..6-45, shipped dialog defaults
 * a0 25%, a1 5%, a2 50%, a3/a4 off) are soft percent boxes around the
 * initial estimate p0:
 *   [p0 (1 - pct/100), p0 (1 + pct/100)] intersected with the hard registry
 *   bounds. For each violated free parameter the quadratic hinge
 *   mu * (v/s)^2 (v = signed distance out of the box) contributes
 *   g_j += 2 mu v / s^2 and alpha_jj += 2 mu / s^2
 * to the normal equations. The penalty is included in the step-acceptance
 * objective F = chi^2 + penalty, so early iterations may violate the box and
 * later iterations work themselves free. mu is tied to the current data
 * chi-square: mu = 3e2 * chi^2 / m (m = fitted point count). The multiplier
 * was tuned empirically: 1e4 pins a dragged peak inside its box and blocks
 * recovery, while <=3e1 lets a peak collapse into a neighbouring flank
 * (S3 collapses to R2=0.87). 3e2 lets a large, genuine SSE gain overcome the
 * hinge (S3 recovers to R2=0.993) yet still stops parameter blow-up
 * (S1 max |a0| ~= 261, no 1e12 excursion) and keeps S14 bounded.
 *
 * Robust fitting follows the manual's maximum-likelihood objectives:
 *   - 'ls'      : sum r^2                (Gaussian errors)
 *   - 'lad'     : sum |r|                (two-sided exponential)
 *   - 'lorentz' : sum ln(1+(r/s)^2)      (Lorentzian errors)
 *   - 'p7lim'   : 0.5 sum ln(1+(r/s)^2)  (Pearson VII Limit, manual p.6-79)
 * LAD/Lorentz/P7 are solved by iteratively reweighted least squares (IRLS).
 * The Lorentz and Pearson-VII-Limit weights share the same form
 * 1/(1+(r/s)^2); the difference is the objective (P7 has the ln(sqrt(...))
 * form, i.e. the 1/2 factor). The scale s is initialized to 1.4826*MAD and
 * refreshed each iteration, as specified for this project. All reported fit
 * statistics (r2/sse/fitStdErr) are always ordinary least-squares figures and
 * do not change with the robust mode.
 *
 * The fitter is pure: no DOM/Node APIs. It can be driven synchronously from
 * a worker, a browser Web Worker, or a test script.
 */

export type RobustMode = 'ls' | 'lad' | 'lorentz' | 'p7lim'

export interface FitterControl {
  /** Set by 停止并保留; the fitter returns the current best parameters. */
  stop: boolean
  /** Set by 中止并回滚; the fitter returns `aborted: true`. */
  abort: boolean
  /** Optional SharedArrayBuffer flags: [0]=stop, [1]=abort. */
  shared: Int32Array | null
}

/** Create a control object, optionally backed by a SharedArrayBuffer. */
export function makeControl(shared?: SharedArrayBuffer | null): FitterControl {
  return { stop: false, abort: false, shared: shared ? new Int32Array(shared) : null }
}

export interface IterInfo {
  /** 1-based LM iteration. */
  iter: number
  /** Robust objective (SSE for least squares). */
  chi2: number
  /** Coefficient of determination against the supplied SST. */
  r2: number
  /** Number of free parameters currently outside their soft constraint box. */
  viol: number
  /** Number of residual-function evaluations so far. */
  fnEval: number
  /** Full parameter vector snapshot (free and locked parameters). */
  params: Float64Array
  timeMs: number
}

/**
 * Percent soft-constraint box for the full parameter vector.
 * Entries without a constraint use lower=-Infinity, upper=+Infinity.
 * `scale` is the box half-width s_j (>= 1e-12) used by the hinge penalty.
 */
export interface SoftBoxConstraint {
  lower: Float64Array
  upper: Float64Array
  scale: Float64Array
}

export interface FitterOptions {
  maxIter: number
  convDigits: number
  robust: RobustMode
  /** Total weighted sum of squares around the weighted mean (for r2). */
  sst: number
  /** sqrt of input weights (sigma^-1); null/undefined means all ones. */
  sqrtW?: Float64Array | null
  control?: FitterControl
  onIter?: (info: IterInfo) => void
  /** Characteristic parameter magnitudes, one per full parameter (Jacobian steps). */
  scales?: Float64Array | null
  /** Percent-of-initial soft boxes (peak parameters only). */
  softBox?: SoftBoxConstraint | null
}

export interface FitterResult {
  /** Full parameter vector at the solution (including locked entries). */
  p: Float64Array
  /** 1-sigma standard errors for the full parameter vector (0 for locked). */
  pStdErr: Float64Array
  /** Final robust objective value. */
  objective: number
  /** Weighted sum of squared residuals using only the input weights. */
  sse: number
  iterations: number
  converged: boolean
  stopped: boolean
  aborted: boolean
  fnEval: number
  violFinal: number
  timeMs: number
  /** Unweighted residual vector over the fitted subset. */
  residual: Float64Array
  /** Final robust IRLS weights (null for least squares). */
  robustWeights: Float64Array | null
  /** Covariance matrix for free parameters (k x k row-major) or null. */
  covariance: Float64Array | null
}

/**
 * Residual callback: fill `out[i] = y[i] - model(x[i])` for the fitted
 * subset. It must not allocate or throw for valid parameters.
 */
export type ResidualFn = (p: Float64Array, out: Float64Array) => void

/**
 * Optional analytic-structure Jacobian hook. For parameter `j` with
 * one-sided steps hp/hm, fill `out[i] = d model(x[i]) / d p_j` (unweighted).
 * The fitter negates and applies the residual weights. Providing this hook
 * lets the caller evaluate only the affected peak/baseline component instead
 * of the whole model for every finite-difference column.
 */
export type JacobianColumnFn = (
  p: Float64Array,
  j: number,
  hp: number,
  hm: number,
  out: Float64Array
) => void

export interface FitterInput {
  initial: Float64Array
  lower: Float64Array
  upper: Float64Array
  fixed?: Uint8Array | null
  residual: ResidualFn
  jacobianColumn?: JacobianColumnFn
  n: number
}

const MU_MULT = 3e2
const CBRT_EPS = 6.055454452393343e-6

function clip(v: number, lo: number, hi: number): number {
  if (v < lo) return lo
  if (v > hi) return hi
  return v
}

function checkControl(control: FitterControl | undefined): 'stop' | 'abort' | null {
  if (!control) return null
  if (control.shared) {
    if (control.shared[1] !== 0) return 'abort'
    if (control.shared[0] !== 0) return 'stop'
  }
  if (control.abort) return 'abort'
  if (control.stop) return 'stop'
  return null
}

/** Significant digits shared by two positive objective values. */
export function matchingDigits(a: number, b: number): number {
  if (a === b) return 15
  const scale = Math.max(Math.abs(a), Math.abs(b))
  if (scale === 0) return 15
  const diff = Math.abs(a - b)
  if (diff === 0) return 15
  return -Math.log10(diff / scale)
}

/**
 * Squared hinge violation of a soft box, sum_j (v_j / s_j)^2.
 * Exported so the smoke suite can compare the analytic hinge gradient with a
 * finite difference.
 */
export function softBoxPenalty(p: ArrayLike<number>, box: SoftBoxConstraint): number {
  let sum = 0
  const n = Math.min(p.length, box.lower.length, box.upper.length, box.scale.length)
  for (let j = 0; j < n; j += 1) {
    const v = p[j]
    let dist = 0
    if (v < box.lower[j]) dist = box.lower[j] - v
    else if (v > box.upper[j]) dist = v - box.upper[j]
    if (dist > 0) {
      const s = Math.max(box.scale[j], 1e-12)
      sum += (dist / s) * (dist / s)
    }
  }
  return sum
}

/**
 * Analytic gradient of {@link softBoxPenalty}. The signed violation is
 * v_j = p_j - lower_j below the box and p_j - upper_j above it, so the
 * gradient 2 v_j / s_j^2 points back toward the box (negative for a
 * lower-bound violation). 0 inside the box.
 */
export function softBoxPenaltyGradient(
  p: ArrayLike<number>,
  box: SoftBoxConstraint,
  out: Float64Array
): void {
  const n = Math.min(p.length, box.lower.length, box.upper.length, box.scale.length)
  for (let j = 0; j < n; j += 1) {
    const v = p[j]
    let signed = 0
    if (v < box.lower[j]) signed = v - box.lower[j]
    else if (v > box.upper[j]) signed = v - box.upper[j]
    if (signed !== 0) {
      const s = Math.max(box.scale[j], 1e-12)
      out[j] = (2 * signed) / (s * s)
    } else {
      out[j] = 0
    }
  }
}

/**
 * Solve A x = b for a small dense system via LU with partial pivoting.
 * A is row-major k x k and is not modified.
 */
function solveLinear(a: Float64Array, b: Float64Array, k: number): Float64Array | null {
  const m = new Float64Array(a) // copy
  const x = new Float64Array(b)
  for (let col = 0; col < k; col += 1) {
    // pivot
    let pivot = col
    let best = Math.abs(m[col * k + col])
    for (let r = col + 1; r < k; r += 1) {
      const v = Math.abs(m[r * k + col])
      if (v > best) {
        best = v
        pivot = r
      }
    }
    if (best < 1e-300) return null
    if (pivot !== col) {
      for (let c = col; c < k; c += 1) {
        const t = m[col * k + c]
        m[col * k + c] = m[pivot * k + c]
        m[pivot * k + c] = t
      }
      const t = x[col]
      x[col] = x[pivot]
      x[pivot] = t
    }
    const diag = m[col * k + col]
    for (let r = col + 1; r < k; r += 1) {
      const f = m[r * k + col] / diag
      if (f === 0) continue
      m[r * k + col] = 0
      for (let c = col + 1; c < k; c += 1) {
        m[r * k + c] -= f * m[col * k + c]
      }
      x[r] -= f * x[col]
    }
  }
  for (let r = k - 1; r >= 0; r -= 1) {
    let s = x[r]
    for (let c = r + 1; c < k; c += 1) s -= m[r * k + c] * x[c]
    x[r] = s / m[r * k + r]
  }
  for (let i = 0; i < k; i += 1) {
    if (!Number.isFinite(x[i])) return null
  }
  return x
}

function median(values: Float64Array, n: number): number {
  if (n <= 0) return 0
  const copy = Float64Array.from(values.subarray(0, n))
  copy.sort()
  const mid = n >> 1
  return n % 2 === 1 ? copy[mid] : 0.5 * (copy[mid - 1] + copy[mid])
}

/**
 * Run a bounded LM fit with soft percent constraints and gain-ratio steps.
 */
export function levenbergMarquardt(
  input: FitterInput,
  opts: FitterOptions
): FitterResult {
  const t0 = Date.now()
  const nParam = input.initial.length
  const m = input.n
  const p = new Float64Array(input.initial)
  const lo = input.lower
  const hi = input.upper
  const fixed = input.fixed
  const control = opts.control
  const scales = opts.scales
  const soft = opts.softBox

  for (let i = 0; i < nParam; i += 1) {
    p[i] = clip(p[i], lo[i], hi[i])
  }

  // Free-parameter index map.
  const free: number[] = []
  for (let i = 0; i < nParam; i += 1) {
    if (!fixed || fixed[i] === 0) free.push(i)
  }
  const k = free.length

  const zeroErr = new Float64Array(nParam)
  if (k === 0 || m === 0) {
    const residual = new Float64Array(m)
    input.residual(p, residual)
    let sse = 0
    let obj = 0
    for (let i = 0; i < m; i += 1) {
      const w = opts.sqrtW && opts.sqrtW.length === m ? opts.sqrtW[i] : 1
      const r = residual[i] * w
      sse += r * r
      if (opts.robust === 'lad') obj += Math.abs(r)
      else if (opts.robust === 'lorentz') obj += Math.log1p(r * r)
      else if (opts.robust === 'p7lim') obj += 0.5 * Math.log1p(r * r)
      else obj += r * r
    }
    return {
      p,
      pStdErr: zeroErr,
      objective: obj,
      sse,
      iterations: 0,
      converged: true,
      stopped: false,
      aborted: false,
      fnEval: 1,
      violFinal: 0,
      timeMs: Date.now() - t0,
      residual,
      robustWeights: null,
      covariance: null
    }
  }

  const raw = new Float64Array(m)
  const work = new Float64Array(m)
  const baseW = new Float64Array(m)
  const sqrtW = new Float64Array(m)
  if (opts.sqrtW && opts.sqrtW.length === m) sqrtW.set(opts.sqrtW)
  else sqrtW.fill(1)
  const robustW = new Float64Array(m)
  robustW.fill(1)
  const jac = new Float64Array(m * k)
  const normal = new Float64Array(k * k)
  const grad = new Float64Array(k)
  const gradAug = new Float64Array(k)
  const dampDiag = new Float64Array(k)
  const trial = new Float64Array(k)
  const pTrial = new Float64Array(nParam)
  const aTmp = new Float64Array(k * k)
  const bTmp = new Float64Array(k)
  const penGradFull = new Float64Array(nParam)

  let fnEval = 0
  /** raw <- y - model; return number of evaluations. */
  const evalRaw = (params: Float64Array): void => {
    input.residual(params, raw)
    fnEval += 1
  }
  /** weighted residual into work, using current sqrtW * sqrt(robustW). */
  const makeWork = (): void => {
    for (let i = 0; i < m; i += 1) {
      work[i] = raw[i] * sqrtW[i] * Math.sqrt(robustW[i])
      baseW[i] = work[i]
    }
  }
  const sseInputWeights = (): number => {
    let s = 0
    for (let i = 0; i < m; i += 1) {
      const r = raw[i] * sqrtW[i]
      s += r * r
    }
    return s
  }
  const objective = (): number => {
    if (opts.robust === 'ls') return sseInputWeights()
    if (opts.robust === 'lad') {
      let s = 0
      for (let i = 0; i < m; i += 1) s += Math.abs(raw[i] * sqrtW[i])
      return s
    }
    if (opts.robust === 'p7lim') {
      // Pearson VII Limit: ln(sqrt(1+(r/s)^2)) = 0.5 ln(1+(r/s)^2),
      // manual p.6-79. Kept as its own branch (not shared with Lorentzian).
      let s = 0
      for (let i = 0; i < m; i += 1) {
        const r = (raw[i] * sqrtW[i]) / robustScale
        s += 0.5 * Math.log1p(r * r)
      }
      return s
    }
    // Lorentzian MLE with the current scale.
    let s = 0
    for (let i = 0; i < m; i += 1) {
      const r = (raw[i] * sqrtW[i]) / robustScale
      s += Math.log1p(r * r)
    }
    return s
  }

  let robustScale = 1
  const updateRobustWeights = (): void => {
    if (opts.robust === 'ls') {
      robustW.fill(1)
      return
    }
    // Scale/weights use input-weighted residuals.
    if (opts.robust === 'lad') {
      let medAbs = 0
      for (let i = 0; i < m; i += 1) work[i] = Math.abs(raw[i] * sqrtW[i])
      medAbs = median(work, m)
      const eps = Math.max(1e-12, 1e-9 * medAbs)
      for (let i = 0; i < m; i += 1) {
        const a = Math.abs(raw[i] * sqrtW[i])
        robustW[i] = 1 / Math.max(a, eps)
      }
      return
    }
    // Lorentzian / Pearson VII Limit: s = 1.4826 * MAD, updated each
    // iteration. Both use w = 1/(1+(r/s)^2); P7 differs only in the
    // objective (0.5 ln(...)).
    for (let i = 0; i < m; i += 1) work[i] = Math.abs(raw[i] * sqrtW[i])
    const medAbs = median(work, m)
    robustScale = Math.max(1e-12, 1.4826 * medAbs)
    const s2 = robustScale * robustScale
    for (let i = 0; i < m; i += 1) {
      const r = raw[i] * sqrtW[i]
      robustW[i] = 1 / (1 + (r * r) / s2)
    }
  }

  /** Count of free parameters outside the soft box. */
  const countViolations = (params: Float64Array): number => {
    if (!soft) return 0
    let count = 0
    for (let a = 0; a < k; a += 1) {
      const j = free[a]
      const v = params[j]
      if (v < soft.lower[j] || v > soft.upper[j]) count += 1
    }
    return count
  }

  // Initial residual and weights.
  evalRaw(p)
  updateRobustWeights()

  let iterations = 0
  let converged = false
  let stopped = false
  let aborted = false
  let violFinal = countViolations(p)
  let prevObjective = Number.NaN
  let stable = 0
  let lambda = 1e-3

  for (let iter = 1; iter <= Math.max(1, opts.maxIter); iter += 1) {
    const ctlTop = checkControl(control)
    if (ctlTop === 'abort') {
      aborted = true
      break
    }
    if (ctlTop === 'stop') {
      stopped = true
      break
    }

    // --- Build the Jacobian of the weighted residual at p -----------------
    makeWork()
    let probe = 0
    for (let i = 0; i < m; i += 1) probe += baseW[i] * baseW[i]
    if (probe === 0) {
      converged = true
      break
    }
    jac.fill(0)
    for (let jj = 0; jj < k; jj += 1) {
      const j = free[jj]
      const scale = scales && Number.isFinite(scales[j]) ? Math.abs(scales[j]) : 1
      const base = Math.max(Math.abs(p[j]), scale, 1e-8)
      const h = CBRT_EPS * base
      const canUp = p[j] + h <= hi[j]
      const canDown = p[j] - h >= lo[j]
      if (!canUp && !canDown) continue
      let hp = h
      let hm = h
      if (!canUp) hp = 0
      if (!canDown) hm = 0
      const col = jj * m
      if (input.jacobianColumn) {
        input.jacobianColumn(p, j, hp, hm, work)
        fnEval += (hp > 0 ? 1 : 0) + (hm > 0 ? 1 : 0)
        for (let i = 0; i < m; i += 1) {
          jac[col + i] = -work[i] * sqrtW[i] * Math.sqrt(robustW[i])
        }
        const ctlHook = checkControl(control)
        if (ctlHook) {
          if (ctlHook === 'abort') aborted = true
          else stopped = true
          break
        }
        continue
      }
      pTrial.set(p)
      if (hp > 0 && hm > 0) {
        pTrial[j] = p[j] + hp
        evalRaw(pTrial)
        const inv = 1 / (hp + hm)
        // store + temporarily in the jacobian column, then subtract -
        for (let i = 0; i < m; i += 1) {
          jac[col + i] = raw[i] * sqrtW[i] * Math.sqrt(robustW[i])
        }
        pTrial[j] = p[j] - hm
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) {
          const wm = raw[i] * sqrtW[i] * Math.sqrt(robustW[i])
          jac[col + i] = (jac[col + i] - wm) * inv
        }
      } else if (hp > 0) {
        pTrial[j] = p[j] + hp
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) {
          const wp = raw[i] * sqrtW[i] * Math.sqrt(robustW[i])
          jac[col + i] = (wp - baseW[i]) / hp
        }
      } else {
        pTrial[j] = p[j] - hm
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) {
          const wm = raw[i] * sqrtW[i] * Math.sqrt(robustW[i])
          jac[col + i] = (baseW[i] - wm) / hm
        }
      }
      const ctlJac = checkControl(control)
      if (ctlJac) {
        if (ctlJac === 'abort') aborted = true
        else stopped = true
        break
      }
    }
    if (aborted || stopped) break

    // Restore work at p (Jacobian loops overwrote it).
    makeWork()
    const sseOld = (() => {
      let s = 0
      for (let i = 0; i < m; i += 1) s += work[i] * work[i]
      return s
    })()

    // --- Normal equations (data part) --------------------------------------
    for (let a = 0; a < k; a += 1) {
      const ca = a * m
      for (let b = a; b < k; b += 1) {
        const cb = b * m
        let s = 0
        for (let i = 0; i < m; i += 1) s += jac[ca + i] * jac[cb + i]
        normal[a * k + b] = s
        normal[b * k + a] = s
      }
      let g = 0
      const cg = a * m
      for (let i = 0; i < m; i += 1) g += jac[cg + i] * work[i]
      grad[a] = g
    }

    // --- Soft percent-constraint hinge penalty -----------------------------
    // mu tracks the current data chi-square scale: 3e2 * mean square
    // residual. The penalty value below uses the same mu, so the normal
    // equations are exactly the Gauss-Newton model of F = chi^2 + penalty.
    let mu = 0
    let penOld = 0
    gradAug.set(grad)
    for (let a = 0; a < k; a += 1) dampDiag[a] = normal[a * k + a]
    if (soft) {
      let chi2Data = 0
      for (let i = 0; i < m; i += 1) {
        const r = raw[i] * sqrtW[i]
        chi2Data += r * r
      }
      mu = (MU_MULT * Math.max(chi2Data, 0)) / m
      if (!Number.isFinite(mu) || mu < 0) mu = 0
      penGradFull.fill(0)
      softBoxPenaltyGradient(p, soft, penGradFull)
      for (let a = 0; a < k; a += 1) {
        const j = free[a]
        const v = p[j]
        const s = Math.max(soft.scale[j], 1e-12)
        let dist = 0
        if (v < soft.lower[j]) dist = soft.lower[j] - v
        else if (v > soft.upper[j]) dist = v - soft.upper[j]
        if (dist > 0) {
          penOld += mu * (dist / s) * (dist / s)
          gradAug[a] += mu * penGradFull[j]
          const diagAdd = (2 * mu) / (s * s)
          normal[a * k + a] += diagAdd
          dampDiag[a] += diagAdd
        }
      }
    }
    const fOld = sseOld + penOld

    // --- LM inner loop with gain-ratio step acceptance ---------------------
    let accepted = false
    let appliedViol = violFinal
    let sseNew = sseOld
    for (let attempt = 0; attempt < 24; attempt += 1) {
      aTmp.set(normal)
      for (let a = 0; a < k; a += 1) {
        const d = dampDiag[a]
        aTmp[a * k + a] += lambda * (d > 0 ? d : 1e-12)
      }
      // Solve A d = -grad(F); the right-hand side is the descent direction.
      for (let a = 0; a < k; a += 1) bTmp[a] = -gradAug[a]
      const step = solveLinear(aTmp, bTmp, k)
      if (!step) {
        lambda *= 10
        if (lambda > 1e20) break
        continue
      }

      // Predicted reduction of F for the *unclipped* step:
      //   pred = d^T (lambda D d + g) with g = -grad(F) (descent).
      let pred = 0
      for (let a = 0; a < k; a += 1) {
        pred += step[a] * (lambda * dampDiag[a] * step[a] - gradAug[a])
      }
      if (!(pred > 0) || !Number.isFinite(pred)) {
        lambda *= 10
        if (lambda > 1e20) break
        continue
      }

      // Guard: reject non-finite or absurdly large trial coordinates.
      let bad = false
      for (let a = 0; a < k; a += 1) {
        const j = free[a]
        const rawVal = p[j] + step[a]
        const paramScale =
          scales && Number.isFinite(scales[j]) ? Math.abs(scales[j]) : 1
        const limit = 1e12 * Math.max(paramScale, 1e-6)
        if (!Number.isFinite(rawVal) || Math.abs(rawVal) > limit) {
          bad = true
          break
        }
      }
      if (bad) {
        lambda *= 10
        if (lambda > 1e20) break
        continue
      }

      // Trial point: hard-bound clipping is only for evaluation. The gain
      // ratio above used the unclipped step, so a step whose projected
      // version is degenerate is naturally rejected by rho <= 0.
      pTrial.set(p)
      for (let a = 0; a < k; a += 1) {
        const j = free[a]
        const rawVal = p[j] + step[a]
        pTrial[j] = clip(rawVal, lo[j], hi[j])
      }
      evalRaw(pTrial)
      let s = 0
      for (let i = 0; i < m; i += 1) {
        const w = raw[i] * sqrtW[i] * Math.sqrt(robustW[i])
        s += w * w
      }
      let penNew = 0
      if (soft && mu > 0) {
        for (let a = 0; a < k; a += 1) {
          const j = free[a]
          const v = pTrial[j]
          const ss = Math.max(soft.scale[j], 1e-12)
          let dist = 0
          if (v < soft.lower[j]) dist = soft.lower[j] - v
          else if (v > soft.upper[j]) dist = v - soft.upper[j]
          if (dist > 0) penNew += mu * (dist / ss) * (dist / ss)
        }
      }
      const fNew = s + penNew
      if (!Number.isFinite(fNew)) {
        lambda *= 10
        if (lambda > 1e20) break
        continue
      }
      const rho = (fOld - fNew) / pred
      if (rho > 0) {
        p.set(pTrial)
        // raw already holds residuals at pTrial
        sseNew = s
        appliedViol = countViolations(pTrial)
        accepted = true
        lambda = Math.max(lambda / 10, 1e-12)
        break
      }
      lambda *= 10
      if (lambda > 1e20) break
    }
    if (!accepted) {
      // No step improved F at any damping level. This is a stationary point
      // for the current model/weights; restore the residual at p so the
      // telemetry and convergence digits describe p, not the last rejected
      // trial. The iteration is still reported: the original streams one
      // iteration event per LM pass, and the 5-stable-digit rule (not a
      // single failed retry) decides convergence.
      evalRaw(p)
      iterations = iter
      violFinal = countViolations(p)
    } else {
      void sseNew
      iterations = iter
      violFinal = appliedViol
    }

    // --- Report and convergence -------------------------------------------
    // Refresh the robust scale/weights from the accepted residuals before
    // forming the reported objective (the step itself used the previous
    // IRLS weights, as usual for IRLS).
    updateRobustWeights()
    const obj = objective()
    const sseW = sseInputWeights()
    const r2 = opts.sst > 0 ? 1 - sseW / opts.sst : 0
    if (Number.isFinite(prevObjective) && prevObjective >= 0 && obj >= 0) {
      const digits = matchingDigits(prevObjective, obj)
      if (digits >= opts.convDigits) stable += 1
      else stable = 0
    }
    prevObjective = obj
    if (opts.onIter) {
      opts.onIter({
        iter,
        chi2: obj,
        r2,
        viol: violFinal,
        fnEval,
        params: p.slice(),
        timeMs: Date.now() - t0
      })
    }
    if (stable >= 5) {
      converged = true
      break
    }
    const ctlEnd = checkControl(control)
    if (ctlEnd === 'abort') {
      aborted = true
      break
    }
    if (ctlEnd === 'stop') {
      stopped = true
      break
    }
  }

  // Ensure raw is the residual at the final p (it is unless we aborted early).
  evalRaw(p)

  // --- Covariance (J^T J)^-1 * sse/dof using input weights -----------------
  let covariance: Float64Array | null = null
  const err = new Float64Array(nParam)
  if (!aborted && k > 0) {
    for (let a = 0; a < k; a += 1) {
      const ca = a * m
      const j = free[a]
      const scale = scales && Number.isFinite(scales[j]) ? Math.abs(scales[j]) : 1
      const base = Math.max(Math.abs(p[j]), scale, 1e-8)
      const h = CBRT_EPS * base
      const canUp = p[j] + h <= hi[j]
      const canDown = p[j] - h >= lo[j]
      if (input.jacobianColumn) {
        const hp = canUp ? h : 0
        const hm = canDown ? h : 0
        if (hp === 0 && hm === 0) {
          for (let i = 0; i < m; i += 1) jac[ca + i] = 0
        } else {
          input.jacobianColumn(p, j, hp, hm, work)
          fnEval += (hp > 0 ? 1 : 0) + (hm > 0 ? 1 : 0)
          for (let i = 0; i < m; i += 1) jac[ca + i] = -work[i] * sqrtW[i]
        }
        continue
      }
      pTrial.set(p)
      if (canUp && canDown) {
        pTrial[j] = p[j] + h
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) work[i] = raw[i] * sqrtW[i]
        for (let i = 0; i < m; i += 1) jac[ca + i] = work[i]
        pTrial[j] = p[j] - h
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) {
          const wm = raw[i] * sqrtW[i]
          jac[ca + i] = (jac[ca + i] - wm) / (2 * h)
        }
      } else if (canUp) {
        pTrial[j] = p[j] + h
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) work[i] = raw[i] * sqrtW[i]
        pTrial[j] = p[j]
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) {
          const w0 = raw[i] * sqrtW[i]
          jac[ca + i] = (work[i] - w0) / h
        }
      } else if (canDown) {
        pTrial[j] = p[j]
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) work[i] = raw[i] * sqrtW[i]
        pTrial[j] = p[j] - h
        evalRaw(pTrial)
        for (let i = 0; i < m; i += 1) {
          const wm = raw[i] * sqrtW[i]
          jac[ca + i] = (work[i] - wm) / h
        }
      } else {
        for (let i = 0; i < m; i += 1) jac[ca + i] = 0
      }
    }
    // Restore raw at the solution.
    evalRaw(p)
    for (let a = 0; a < k; a += 1) {
      const ca = a * m
      for (let b = a; b < k; b += 1) {
        const cb = b * m
        let s = 0
        for (let i = 0; i < m; i += 1) s += jac[ca + i] * jac[cb + i]
        normal[a * k + b] = s
        normal[b * k + a] = s
      }
    }
    let sseW = 0
    for (let i = 0; i < m; i += 1) {
      const r = raw[i] * sqrtW[i]
      sseW += r * r
    }
    const dof = m - k
    if (dof > 0) {
      // Diagonal loading retries for rank-deficient J^T J.
      let inv: Float64Array | null = null
      let maxDiag = 0
      for (let a = 0; a < k; a += 1) maxDiag = Math.max(maxDiag, Math.abs(normal[a * k + a]))
      const loadBase = Math.max(maxDiag, 1e-12)
      for (let attempt = 0; attempt < 6 && !inv; attempt += 1) {
        aTmp.set(normal)
        const load = loadBase * Math.pow(10, -12 + 3 * attempt)
        for (let a = 0; a < k; a += 1) aTmp[a * k + a] += load
        // Invert column by column.
        const result = new Float64Array(k * k)
        let ok = true
        for (let c = 0; c < k; c += 1) {
          bTmp.fill(0)
          bTmp[c] = 1
          const sol = solveLinear(aTmp, bTmp, k)
          if (!sol) {
            ok = false
            break
          }
          for (let r = 0; r < k; r += 1) result[r * k + c] = sol[r]
        }
        if (ok) inv = result
      }
      if (inv) {
        covariance = inv
        const factor = sseW / dof
        for (let a = 0; a < k; a += 1) {
          const v = inv[a * k + a] * factor
          err[free[a]] = v > 0 && Number.isFinite(v) ? Math.sqrt(v) : 0
        }
      }
    }
  }

  const finalObj = objective()
  return {
    p,
    pStdErr: err,
    objective: finalObj,
    sse: sseInputWeights(),
    iterations,
    converged,
    stopped,
    aborted,
    fnEval,
    violFinal,
    timeMs: Date.now() - t0,
    residual: raw.slice(),
    robustWeights: opts.robust === 'ls' ? null : robustW.slice(),
    covariance
  }
}
