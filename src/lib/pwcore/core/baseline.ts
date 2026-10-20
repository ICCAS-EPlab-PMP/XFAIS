/**
 * the reference application 自动拟合 Baseline — faithful port of the original's four-step
 * pipeline (manual ch.6 p.6-1..6-6):
 *
 *   Detection algorithms (where is the baseline?):
 *     endpoints   "Initial,Final Lin" — first & last active points
 *     progressive "Progressive Lin"   — extend a linear fit from each end
 *                 until goodness of fit deteriorates (first peak)
 *     deriv2zero  "2nd Deriv Zero"    — baseline points are where a smoothed
 *                 second derivative is constant and zero (tolerance-gated)
 *
 *   Models (what shape is the baseline?):
 *     const/lin/quad/cub/log (linear, closed form), exp/pow/hyp (non-linear,
 *     small LM), nparm (non-parametric moving linear fit with Gaussian
 *     weights), best (all 8 parametric, pick by F-statistic)
 *
 *   Four-step pipeline (deriv2zero):
 *     1. candidate points from |smoothed d²| ≤ tol
 *     2. fit the model to candidates
 *     3. keep points with |y - fit| ≤ tol (residual re-selection)
 *     4. refit on the surviving points — this is the final baseline
 *
 *   Human-in-the-loop: any point can be toggled in/out of the baseline set
 *   and the fit is recomputed at once (refitOnPoints — no re-detection).
 */

export type BaselineMethod = 'endpoints' | 'progressive' | 'deriv2zero'

export type BaselineModelId =
  | 'best'
  | 'nparm'
  | 'const'
  | 'lin'
  | 'quad'
  | 'cub'
  | 'log'
  | 'exp'
  | 'pow'
  | 'hyp'

export interface BaselineFitResult {
  /** Baseline evaluated at every x (all points, interpolated). */
  z: Float64Array
  /** Resolved model ('best' reports the winner). */
  model: BaselineModelId
  /** Parametric coefficients in the registry-ish order (null for nparm). */
  params: number[] | null
  /** 1 = the point participated in the baseline fit. */
  used: Uint8Array
  /** Goodness of fit over the used points. */
  r2: number
  sse: number
}

// ---------------------------------------------------------------------------
// linear algebra helpers
// ---------------------------------------------------------------------------

function solveLS(A: number[][], b: number[]): number[] | null {
  const n = b.length
  const M = A.map((row, i) => [...row, b[i]])
  for (let col = 0; col < n; col++) {
    let piv = col
    for (let r = col + 1; r < n; r++) if (Math.abs(M[r][col]) > Math.abs(M[piv][col])) piv = r
    if (!(Math.abs(M[piv][col]) > 1e-300)) return null
    if (piv !== col) {
      const t = M[piv]
      M[piv] = M[col]
      M[col] = t
    }
    for (let r = col + 1; r < n; r++) {
      const f = M[r][col] / M[col][col]
      if (f === 0) continue
      for (let c = col; c <= n; c++) M[r][c] -= f * M[col][c]
    }
  }
  const x = new Array<number>(n).fill(0)
  for (let r = n - 1; r >= 0; r--) {
    let s = M[r][n]
    for (let c = r + 1; c < n; c++) s -= M[r][c] * x[c]
    x[r] = s / M[r][r]
  }
  return x
}

// ---------------------------------------------------------------------------
// parametric baseline models
//   const: y = a
//   lin:   y = a + b·x
//   quad:  y = a + b·x + c·x²
//   cub:   y = a + b·x + c·x² + d·x³
//   log:   y = a + b·ln x
//   exp:   y = a + b·exp(−x/c)
//   pow:   y = a + b·x^c
//   hyp:   y = a + b·k/(k+x)
// ---------------------------------------------------------------------------

const LINEAR_MODELS: { id: Exclude<BaselineModelId, 'best' | 'nparm' | 'exp' | 'pow' | 'hyp'>; basis: (x: number) => number[] }[] = [
  { id: 'const', basis: () => [1] },
  { id: 'lin', basis: (x) => [1, x] },
  { id: 'quad', basis: (x) => [1, x, x * x] },
  { id: 'cub', basis: (x) => [1, x, x * x, x * x * x] },
  { id: 'log', basis: (x) => [1, Math.log(Math.max(x, 1e-12))] },
]

function fitLinearModel(basis: (x: number) => number[], x: Float64Array, y: Float64Array, used: Uint8Array): number[] | null {
  const k = basis(0).length
  const A: number[][] = []
  const b: number[] = []
  for (let a = 0; a < k; a++) {
    A.push(new Array<number>(k).fill(0))
    b.push(0)
  }
  for (let i = 0; i < x.length; i++) {
    if (!used[i]) continue
    const f = basis(x[i])
    for (let a = 0; a < k; a++) {
      b[a] += f[a] * y[i]
      for (let c = a; c < k; c++) A[a][c] += f[a] * f[c]
    }
  }
  for (let a = 0; a < k; a++) for (let c = 0; c < a; c++) A[a][c] = A[c][a]
  return solveLS(A, b)
}

/** Non-linear models fitted with a tiny damped Gauss-Newton (≤3 params). */
function fitNonlinearModel(
  id: 'exp' | 'pow' | 'hyp',
  x: Float64Array,
  y: Float64Array,
  used: Uint8Array
): number[] | null {
  // initial guesses: level ~ min y, scale ~ y range, shape ~ 10% x range
  const x0 = x[0]
  const span = Math.max(x[x.length - 1] - x[0], 1e-12)
  let yMin = Number.POSITIVE_INFINITY
  let yMax = Number.NEGATIVE_INFINITY
  let n = 0
  for (let i = 0; i < x.length; i++) {
    if (!used[i]) continue
    if (y[i] < yMin) yMin = y[i]
    if (y[i] > yMax) yMax = y[i]
    n++
  }
  if (n < 4) return null
  const range = Math.max(yMax - yMin, 1e-12)
  const evalAt = (p: number[], xi: number): number => {
    if (id === 'exp') return p[0] + p[1] * Math.exp(-xi / Math.max(p[2], 1e-12))
    if (id === 'pow') return p[0] + p[1] * Math.pow(Math.max(xi, 1e-12), p[2])
    return p[0] + (p[1] * p[2]) / (p[2] + (xi - x0))
  }
  let p: number[]
  if (id === 'exp') p = [yMin, range, span * 0.25]
  else if (id === 'pow') p = [yMin, range / Math.pow(Math.max(x0 + span / 2, 1e-12), 0.5), 0.5]
  else p = [yMin, range, span * 0.25]

  const ids: number[] = []
  for (let i = 0; i < x.length; i++) if (used[i]) ids.push(i)

  let lambda = 1e-3
  const cost = (pp: number[]): number => {
    let s = 0
    for (const i of ids) {
      const r = y[i] - evalAt(pp, x[i])
      s += r * r
    }
    return s
  }
  let f0 = cost(p)
  for (let iter = 0; iter < 60; iter++) {
    const k = 3
    // residuals and finite-difference Jacobian columns at current p
    const res: number[] = []
    const J: number[][] = [[], [], []]
    for (const i of ids) {
      const r = y[i] - evalAt(p, x[i])
      res.push(r)
      for (let j = 0; j < k; j++) {
        const h = Math.max(Math.abs(p[j]) * 1e-6, 1e-9)
        const pp = [...p]
        pp[j] += h
        const rp = y[i] - evalAt(pp, x[i])
        J[j].push((r - rp) / h)
      }
    }
    const g = new Array<number>(k).fill(0)
    const H: number[][] = []
    for (let a = 0; a < k; a++) {
      H.push(new Array<number>(k).fill(0))
      let ga = 0
      for (let t = 0; t < res.length; t++) ga += J[a][t] * res[t]
      g[a] = ga
    }
    for (let a = 0; a < k; a++) {
      for (let b2 = a; b2 < k; b2++) {
        let s = 0
        for (let t = 0; t < res.length; t++) s += J[a][t] * J[b2][t]
        H[a][b2] = s
        H[b2][a] = s
      }
      H[a][a] += lambda * (H[a][a] > 0 ? H[a][a] : 1)
    }
    const delta = solveLS(H, g.map((v) => -v))
    if (!delta) {
      lambda *= 10
      if (lambda > 1e12) break
      continue
    }
    const trial = [...p]
    for (let a = 0; a < k; a++) trial[a] = p[a] + delta[a]
    const ft = cost(trial)
    if (ft < f0) {
      p = trial
      f0 = ft
      lambda = Math.max(lambda / 10, 1e-12)
      if (f0 < 1e-18) break
    } else {
      lambda *= 10
      if (lambda > 1e12) break
    }
  }
  return p
}

/**
 * Non-parametric baseline: local Gaussian-weighted linear fit evaluated at
 * the USED points, then linear interpolation across stretches without used
 * points (peak regions) — no extrapolation blow-ups inside gaps.
 */
function fitNparm(x: Float64Array, y: Float64Array, used: Uint8Array, window = 12): Float64Array {
  const n = x.length
  const z = new Float64Array(n)
  const idx: number[] = []
  for (let i = 0; i < n; i++) if (used[i]) idx.push(i)
  if (idx.length === 0) return z
  // local weighted QUADRATIC fit AT each used point. The basis is centered
  // ON xi so the prediction is the intercept — bounded by the local data and
  // immune to one-sided-neighborhood extrapolation blow-ups at gap edges.
  const zAt = new Float64Array(idx.length)
  for (let q = 0; q < idx.length; q++) {
    const xi = x[idx[q]]
    const dists = idx.map((j) => Math.abs(x[j] - xi))
    const order = dists.map((_, t) => t).sort((a, b) => dists[a] - dists[b])
    const take = order.slice(0, Math.max(5, window))
    const sigma = Math.max(dists[take[take.length - 1]], 1e-12)
    const A: number[][] = [
      [0, 0, 0],
      [0, 0, 0],
      [0, 0, 0],
    ]
    const b: number[] = [0, 0, 0]
    for (let t = 0; t < take.length; t++) {
      const w = Math.exp(-0.5 * (dists[t] / sigma) ** 2)
      const dx = (x[idx[take[t]]] - xi) / sigma
      const dy = y[idx[take[t]]]
      const p = [1, dx, dx * dx]
      for (let a = 0; a < 3; a++) {
        b[a] += w * p[a] * dy
        for (let c = a; c < 3; c++) {
          const v = w * p[a] * p[c]
          A[a][c] += v
          if (c !== a) A[c][a] += v
        }
      }
    }
    // ridge for stability
    for (let a = 0; a < 3; a++) A[a][a] += 1e-9 * (A[a][a] + 1)
    const sol = solveLS(A, b)
    let v: number
    if (sol) {
      v = sol[0]
    } else {
      // weighted mean fallback
      let sw = 0
      let sy = 0
      for (let t = 0; t < take.length; t++) {
        const w = Math.exp(-0.5 * (dists[t] / sigma) ** 2)
        sw += w
        sy += w * y[idx[take[t]]]
      }
      v = sy / Math.max(sw, 1e-300)
    }
    zAt[q] = Number.isFinite(v) ? v : y[idx[q]]
  }

  // fill used points; interpolate across gaps; clamp the edges
  for (let i = 0; i < n; i++) z[i] = Number.NaN
  for (let q = 0; q < idx.length; q++) z[idx[q]] = zAt[q]
  for (let q = 0; q < idx.length - 1; q++) {
    const u0 = idx[q]
    const u1 = idx[q + 1]
    if (u1 - u0 > 1) {
      const a = z[u0]
      const b = z[u1]
      for (let t = u0 + 1; t < u1; t++) z[t] = a + ((b - a) * (t - u0)) / (u1 - u0)
    }
  }
  const first = idx[0]
  for (let t = 0; t < first; t++) z[t] = zAt[0]
  const last = idx[idx.length - 1]
  for (let t = last + 1; t < n; t++) z[t] = zAt[idx.length - 1]
  for (let i = 0; i < n; i++) if (!Number.isFinite(z[i])) z[i] = 0
  return z
}

function evalModel(id: BaselineModelId, p: number[], x: number, x0: number): number {
  switch (id) {
    case 'const': return p[0]
    case 'lin': return p[0] + p[1] * x
    case 'quad': return p[0] + p[1] * x + p[2] * x * x
    case 'cub': return p[0] + p[1] * x + p[2] * x * x + p[3] * x * x * x
    case 'log': return p[0] + p[1] * Math.log(Math.max(x, 1e-12))
    case 'exp': return p[0] + p[1] * Math.exp(-x / Math.max(p[2], 1e-12))
    case 'pow': return p[0] + p[1] * Math.pow(Math.max(x, 1e-12), p[2])
    case 'hyp': return p[0] + (p[1] * p[2]) / (p[2] + (x - x0))
    default: return Number.NaN
  }
}

const PARAM_MODELS: Exclude<BaselineModelId, 'best' | 'nparm'>[] = ['const', 'lin', 'quad', 'cub', 'log', 'exp', 'pow', 'hyp']

// ---------------------------------------------------------------------------
// fitting on a point set
// ---------------------------------------------------------------------------

function fitOne(id: Exclude<BaselineModelId, 'best'>, x: Float64Array, y: Float64Array, used: Uint8Array): { z: Float64Array; params: number[] | null; r2: number; sse: number } | null {
  const n = x.length
  const x0 = x[0]
  if (id === 'nparm') {
    const z = fitNparm(x, y, used)
    return finalize(z, null, x, y, used)
  }
  let p: number[] | null = null
  const lin = LINEAR_MODELS.find((m) => m.id === id)
  if (lin) p = fitLinearModel(lin.basis, x, y, used)
  else p = fitNonlinearModel(id as 'exp' | 'pow' | 'hyp', x, y, used)
  if (!p) return null
  const z = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    const v = evalModel(id, p, x[i], x0)
    z[i] = Number.isFinite(v) ? v : 0
  }
  return finalize(z, p, x, y, used)
}

function finalize(z: Float64Array, params: number[] | null, x: Float64Array, y: Float64Array, used: Uint8Array): { z: Float64Array; params: number[] | null; r2: number; sse: number } {
  let sse = 0
  let sst = 0
  let m = 0
  let mean = 0
  for (let i = 0; i < x.length; i++) {
    if (!used[i]) continue
    mean += y[i]
    m++
  }
  mean = m > 0 ? mean / m : 0
  for (let i = 0; i < x.length; i++) {
    if (!used[i]) continue
    const r = y[i] - z[i]
    sse += r * r
    sst += (y[i] - mean) ** 2
  }
  const r2 = sst > 1e-300 ? Math.max(0, 1 - sse / sst) : 1
  return { z, params, r2, sse }
}

/**
 * Fit the requested model to the CURRENT baseline point set. `best` tries all
 * eight parametric models and keeps the highest-F (lowest SSE per DOF) one.
 */
export function fitBaselineModel(model: BaselineModelId, x: Float64Array, y: Float64Array, used: Uint8Array): BaselineFitResult | null {
  if (model !== 'best' && model !== 'nparm') {
    const r = fitOne(model, x, y, used)
    return r ? { ...r, model, used } : null
  }
  if (model === 'nparm') {
    const r = fitOne('nparm', x, y, used)
    return r ? { ...r, model: 'nparm', used } : null
  }
  let best: { z: Float64Array; params: number[] | null; r2: number; sse: number; id: (typeof PARAM_MODELS)[number] } | null = null
  for (const id of PARAM_MODELS) {
    const r = fitOne(id, x, y, used)
    if (!r) continue
    // F-ish score: SSE per residual DOF (params count differs across models)
    const k = r.params ? r.params.length : 1
    let m = 0
    for (let i = 0; i < used.length; i++) if (used[i]) m++
    const dof = Math.max(1, m - k)
    const score = r.sse / dof
    const bestScore = best ? best.sse / Math.max(1, m - (best.params ? best.params.length : 1)) : Number.POSITIVE_INFINITY
    if (score < bestScore * 0.995 || !best) best = { ...r, id }
  }
  if (!best) return null
  return { z: best.z, params: best.params, r2: best.r2, sse: best.sse, model: best.id, used }
}

// ---------------------------------------------------------------------------
// detection algorithms
// ---------------------------------------------------------------------------

/**
 * Detect candidate baseline points.
 *  - endpoints: first + last active points only
 *  - progressive: extend a linear fit from each end while the new point stays
 *    within a noise-scaled residual band (original "Progressive Lin")
 *  - deriv2zero: baseline = everything outside detected peak regions. The
 *    original judged points by a smoothed second-derivative tolerance; per-
 *    sample d² cannot separate wide chromatographic peaks from noise, so we
 *    realize the same intent ("baseline exists where no peak exists") by
 *    excluding center ± k·FWHM around every detected peak. tolPct scales the
 *    exclusion width (higher tolerance → more points judged baseline).
 */
export function detectBaselinePoints(
  method: BaselineMethod,
  x: Float64Array,
  y: Float64Array,
  activeMask: Uint8Array | null,
  tolPct = 2
): Uint8Array {
  const n = x.length
  const used = new Uint8Array(n)
  const active = activeMask ?? new Uint8Array(n).fill(1)

  if (method === 'endpoints') {
    for (let i = 0; i < n; i++) {
      if (active[i]) {
        used[i] = 1
        break
      }
    }
    for (let i = n - 1; i >= 0; i--) {
      if (active[i]) {
        used[i] = 1
        break
      }
    }
    return used
  }

  if (method === 'progressive') {
    const growFrom = (start: number, step: number): void => {
      let m = 0
      let miss = 0
      let sx = 0
      let sy = 0
      let sxx = 0
      let sxy = 0
      let rmse = 0
      let yRange = 1e-12
      for (let i = 0; i < n; i++) if (active[i]) yRange = Math.max(yRange, Math.abs(y[i]))
      for (let i = start; i >= 0 && i < n; i += step) {
        if (!active[i]) continue
        if (m >= 2) {
          const det = m * sxx - sx * sx
          const a = det > 1e-300 ? (sxx * sy - sx * sxy) / det : sy / m
          const b = det > 1e-300 ? (m * sxy - sx * sy) / det : 0
          const pred = a + b * x[i]
          const band = Math.max(3 * rmse, yRange * 0.005)
          if (m >= 6 && Math.abs(y[i] - pred) > band) {
            miss += 1
            if (miss >= 2) break // sustained exceedance = first sign of a peak
          } else {
            miss = 0
          }
        }
        // accept the point
        sx += x[i]
        sy += y[i]
        sxx += x[i] * x[i]
        sxy += x[i] * y[i]
        used[i] = 1
        m++
        if (m >= 3) {
          const det = m * sxx - sx * sx
          if (det > 1e-300) {
            const a = (sxx * sy - sx * sxy) / det
            const b = (m * sxy - sx * sy) / det
            let se = 0
            let c = 0
            for (let j = start; ; j += step) {
              if (j < 0 || j >= n) break
              if (!active[j]) continue
              se += (y[j] - (a + b * x[j])) ** 2
              c++
              if (c === m) break
            }
            rmse = Math.sqrt(se / Math.max(1, m - 2))
          }
        }
      }
    }
    growFrom(0, 1)
    growFrom(n - 1, -1)
    return used
  }

  // deriv2zero — exclude detected peak regions
  const { detectPeaks } = detectMod
  const tol = Math.max(0.5, Math.min(10, tolPct))
  let peaks: { x0: number; width: number }[] = []
  try {
    const found = detectPeaks(x, y, {
      method: 'deriv2',
      sensitivity: Math.max(0.05, Math.min(0.95, 0.95 - tol * 0.12)),
      maxPeaks: 200,
      fn: 'gauss',
      smoothWindow: 0,
    })
    // the deriv2 width estimate can hit its floor — measure FWHM directly
    // from the data by half-max crossings around each detected center.
    peaks = found.map((d) => ({ x0: d.x0, width: localFwhm(x, y, d.x0) }))
  } catch {
    peaks = []
  }
  // d.width is an FWHM estimate; a Gaussian is ~contained within ±1.06 FWHM.
  // tol 0.5 → ±1.5 FWHM, tol 2 → ±1.2, tol 5 → ±0.6 (more points survive).
  const k = Math.max(0.6, 1.7 - 0.25 * tol)
  for (let i = 0; i < n; i++) {
    if (!active[i]) continue
    let inPeak = false
    for (const p of peaks) {
      if (Math.abs(x[i] - p.x0) <= k * p.width) {
        inPeak = true
        break
      }
    }
    used[i] = inPeak ? 0 : 1
  }
  // degenerate: nothing detected → everything is baseline except extremes
  let cnt = 0
  for (let i = 0; i < n; i++) cnt += used[i]
  if (cnt < 2) {
    for (let i = 0; i < n; i++) used[i] = active[i]
  }
  return used
}

// late import to avoid a cycle (detect → … does not import baseline)
import * as detectMod from './detect'

/** FWHM of the data peak around `center`, measured by half-max crossings
 *  against a straight local floor (min of the flanking ±60-point window). */
function localFwhm(x: Float64Array, y: Float64Array, center: number): number {
  const n = x.length
  let ci = 0
  let best = Number.POSITIVE_INFINITY
  for (let i = 0; i < n; i++) {
    const d = Math.abs(x[i] - center)
    if (d < best) {
      best = d
      ci = i
    }
  }
  const peakY = y[ci]
  let floor = Number.POSITIVE_INFINITY
  for (let i = Math.max(0, ci - 60); i <= Math.min(n - 1, ci + 60); i++) {
    if (y[i] < floor) floor = y[i]
  }
  const fallback = Math.max(x[n - 1] - x[0], 1e-9) * 0.02
  if (!(peakY > floor + 1e-12)) return fallback
  const half = floor + (peakY - floor) * 0.5
  let lo = ci
  while (lo > 0 && y[lo] > half) lo--
  let hi = ci
  while (hi < n - 1 && y[hi] > half) hi++
  const w = Math.abs(x[hi] - x[lo])
  return Number.isFinite(w) && w > 1e-9 ? w : fallback
}

/**
 * The original four-step 自动拟合 Baseline pipeline.
 * Returns null when nothing can be fitted.
 */
export function autoBaseline(
  method: BaselineMethod,
  model: BaselineModelId,
  x: Float64Array,
  y: Float64Array,
  activeMask: Uint8Array | null,
  tolPct = 2
): BaselineFitResult | null {
  const n = x.length
  const active = activeMask ?? new Uint8Array(n).fill(1)
  // Step 1: candidates
  let used = detectBaselinePoints(method, x, y, active, tolPct)
  let count = 0
  for (let i = 0; i < n; i++) count += used[i]
  if (count < 2) return null

  // Steps 2-4 (steps 3-4 only refine for deriv2zero)
  const fit = (u: Uint8Array): BaselineFitResult | null => fitBaselineModel(model, x, y, u)
  const first = fit(used)
  if (!first) return null
  if (method !== 'deriv2zero') return first

  // Step 3: residual re-selection within tol% of the y range
  let yMin = Number.POSITIVE_INFINITY
  let yMax = Number.NEGATIVE_INFINITY
  for (let i = 0; i < n; i++) {
    if (!active[i]) continue
    if (y[i] < yMin) yMin = y[i]
    if (y[i] > yMax) yMax = y[i]
  }
  const yTol = Math.max(0.0001, tolPct / 100) * Math.max(yMax - yMin, 1e-300)
  const used2 = new Uint8Array(n)
  let count2 = 0
  for (let i = 0; i < n; i++) {
    if (!active[i]) continue
    if (Math.abs(y[i] - first.z[i]) <= yTol) {
      used2[i] = 1
      count2++
    }
  }
  if (count2 < 2) return first
  // Step 4: refit
  const second = fit(used2)
  return second ?? first
}

/**
 * Refit on a manually edited point set (original's real-time interaction:
 * toggle points / drag bands → immediate refit, no re-detection).
 */
export function refitBaseline(model: BaselineModelId, x: Float64Array, y: Float64Array, used: Uint8Array): BaselineFitResult | null {
  return fitBaselineModel(model, x, y, used)
}

/** Subtract a baseline from the data; optionally clamp small negatives to 0. */
export function subtractBaseline(y: Float64Array, z: Float64Array, zeroNegative = false): Float64Array {
  const out = new Float64Array(y.length)
  for (let i = 0; i < y.length; i++) {
    let v = y[i] - z[i]
    if (zeroNegative && v < 0) v = 0
    out[i] = Number.isFinite(v) ? v : 0
  }
  return out
}

// keep AsLS available as an alternative non-parametric estimator
export { autoscanBaseline } from './baseline-asls'
export type { AutoscanOptions } from './baseline-asls'
