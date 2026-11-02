/**
 * Automatic peak detection, implementing the reference application's two classical methods:
 *
 *  'residual' — auto placement I: smooth the residual y - yModel (or the raw
 *   signal), find local maxima, and rank them by topographic prominence.
 *  'deriv2'   — auto placement II: Savitzky-Golay second derivative; negative
 *   minima of the derivative locate peak centers. Width is estimated from
 *   the curvature at the center and refined by the half-prominence width.
 *
 * `sensitivity` (0..1) selects the prominence quantile that is accepted:
 * higher sensitivity keeps smaller prominences. `maxPeaks` caps the result
 * (strongest first). The returned peaks are sorted by x.
 *
 * The returned x0/y0/width are ready to become the peak's a1/a0/a2 initial
 * parameters for the function selected in `opts.fn`: the detected mode and
 * height are converted for area-parameterized functions (EMG, ...), and the
 * half-prominence width is converted to the function's width parameter
 * (e.g. a Gaussian's sigma). auto placement I additionally applies the reference application's
 * global area-conservation width tuning (manual p.6-8).
 */
import type { DetectOptions, DetectedPeak } from '../shared/types'
import { PEAK_FN_MAP } from '../shared/registry'
import type { PeakFnId } from '../shared/registry'
import { numericArea, numericFwhm } from './statsfn'
import { peakValue } from './models'
import { savgol } from './smooth'

function medianOf(values: number[]): number {
  if (values.length === 0) return 0
  const s = values.slice().sort((a, b) => a - b)
  const m = s.length >> 1
  return s.length % 2 === 1 ? s[m] : 0.5 * (s[m - 1] + s[m])
}

/** Linear interpolation of the x position where a segment reaches `level`. */
function interpX(x0: number, y0: number, x1: number, y1: number, level: number): number {
  const dy = y1 - y0
  if (Math.abs(dy) < 1e-300) return 0.5 * (x0 + x1)
  const t = (level - y0) / dy
  return x0 + Math.max(0, Math.min(1, t)) * (x1 - x0)
}

interface RawPeak {
  index: number
  prominence: number
  leftBase: number
  rightBase: number
}

/** Topographic prominence of a local maximum at index i of sig. */
function prominenceOf(sig: Float64Array, i: number): RawPeak {
  const h = sig[i]
  let minLeft = h
  let l = i
  while (l > 0 && sig[l - 1] <= h) {
    l -= 1
    if (sig[l] < minLeft) minLeft = sig[l]
  }
  let minRight = h
  let r = i
  while (r < sig.length - 1 && sig[r + 1] <= h) {
    r += 1
    if (sig[r] < minRight) minRight = sig[r]
  }
  return {
    index: i,
    prominence: Math.max(0, h - Math.max(minLeft, minRight)),
    leftBase: l,
    rightBase: r
  }
}

/** Half-prominence width in x units around a maximum; 0 when not bracketed. */
function halfProminenceWidth(
  x: Float64Array,
  sig: Float64Array,
  peak: RawPeak,
  prom: number
): number {
  if (!(prom > 0)) return 0
  const i = peak.index
  const level = sig[i] - prom * 0.5
  let l = i
  while (l > peak.leftBase && sig[l] > level) l -= 1
  let r = i
  while (r < peak.rightBase && sig[r] > level) r += 1
  const xl =
    l < i
      ? interpX(x[l], sig[l], x[l + 1], sig[l + 1], level)
      : x[Math.max(0, peak.leftBase)]
  const xr =
    r > i
      ? interpX(x[r - 1], sig[r - 1], x[r], sig[r], level)
      : x[Math.min(x.length - 1, peak.rightBase)]
  return Math.max(0, xr - xl)
}

function noiseLevel(sig: Float64Array): number {
  const med = medianOf(Array.from(sig))
  const dev: number[] = []
  for (let i = 0; i < sig.length; i += 1) dev.push(Math.abs(sig[i] - med))
  return 1.4826 * medianOf(dev)
}

function trapzArea(x: Float64Array, y: Float64Array, n: number): number {
  let sum = 0
  for (let i = 1; i < n; i += 1) {
    sum += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1])
  }
  return sum
}

/** Initial full parameter vector for the placed peak of `fn` at (x0, y0, width). */
function placedParamsFor(fn: PeakFnId, x0: number, y0: number, width: number): number[] | null {
  const meta = PEAK_FN_MAP.get(fn)
  if (!meta) return null
  const p: number[] = [y0, x0, width]
  for (let j = 3; j < meta.params.length; j += 1) {
    const init = meta.params[j].init
    if (typeof init === 'number') p.push(init)
    else if (init === 'autoWidth') p.push(width)
    else if (init === 'clickX') p.push(x0)
    else p.push(y0)
  }
  return p
}

/** Unit-amplitude parameter vector used to analyse the shape of `fn`. */
function unitShapeParams(fn: PeakFnId, x0: number, width: number): number[] | null {
  const meta = PEAK_FN_MAP.get(fn)
  if (!meta) return null
  const p: number[] = [1, x0, width]
  for (let j = 3; j < meta.params.length; j += 1) {
    const init = meta.params[j].init
    if (typeof init === 'number') p.push(init)
    else if (init === 'autoWidth') p.push(width)
    else if (init === 'clickX') p.push(x0)
    else p.push(1)
  }
  return p
}

interface Placement {
  x0: number
  y0: number
  width: number
}

/**
 * Convert a detected (mode, height, half-prominence width) into initial
 * parameter values appropriate for the selected peak function:
 *  - a2 is solved so the model's numeric FWHM matches the detected width
 *    (e.g. a Gaussian's sigma is FWHM/2.3548, not the FWHM itself);
 *  - a0 is scaled so the model's extremum equals the detected height (for
 *    area-parameterized functions such as EMG, a0 is an area, not a height);
 *  - a1 is shifted by the function's mode offset so the placed peak's
 *    maximum lands on the detected center.
 * For height-normalized bells (GAUSS, LORENTZ, VOIGT, ...) this is a no-op
 * except for the width conversion.
 */
function shapeAwarePlacement(
  fn: PeakFnId,
  x0: number,
  y0: number,
  width: number
): Placement {
  if (!(width > 0) || !Number.isFinite(width) || !Number.isFinite(y0)) {
    return { x0, y0, width }
  }
  // Solve the width parameter so the model FWHM equals the detected width.
  let a2 = width
  for (let it = 0; it < 4; it += 1) {
    const params = unitShapeParams(fn, x0, a2)
    if (!params) break
    const fwhm = numericFwhm(fn, params)
    if (!(fwhm > 0) || !Number.isFinite(fwhm)) break
    const next = a2 * (width / fwhm)
    if (!(next > 0) || !Number.isFinite(next)) break
    const done = Math.abs(next - a2) <= 1e-9 * Math.max(next, a2)
    a2 = next
    if (done) break
  }
  // Locate the unit-amplitude extremum and its offset from the a1 parameter.
  const params = unitShapeParams(fn, x0, a2)
  if (!params) return { x0, y0, width: a2 }
  const half = 100 * Math.max(a2, 1e-12)
  const n = 2049
  const dx = (2 * half) / (n - 1)
  let bestAbs = -1
  let bestX = x0
  for (let i = 0; i < n; i += 1) {
    const xv = x0 - half + i * dx
    const v = Math.abs(peakValue(fn, params, xv))
    if (v > bestAbs) {
      bestAbs = v
      bestX = xv
    }
  }
  if (!(bestAbs > 0) || !Number.isFinite(bestAbs)) {
    return { x0, y0, width: a2 }
  }
  const offset = bestX - x0
  return {
    x0: x0 - offset,
    y0: y0 / bestAbs,
    width: a2
  }
}

/**
 * auto placement I area conservation (manual p.6-8): after placing peaks from
 * the residual, scale all widths by one global factor so that the overall
 * area of the placed peaks equals the net area of the raw data.
 *
 *   f = trapz(y - edge-median baseline) / sum(area of placed peaks)
 *
 * The edge-median baseline is the line through the medians of the first and
 * last 5% of the data (the same automatic baseline estimate used by the fit
 * driver). f is clamped to [0.2, 5] against pathological data.
 */
function conserveArea(
  x: Float64Array,
  y: Float64Array,
  n: number,
  fn: PeakFnId,
  peaks: DetectedPeak[]
): void {
  if (peaks.length === 0 || n < 10) return
  const k = Math.max(1, Math.floor(n * 0.05))
  const ysL: number[] = []
  const ysR: number[] = []
  for (let i = 0; i < k; i += 1) {
    ysL.push(y[i])
    ysR.push(y[n - 1 - i])
  }
  const yL = medianOf(ysL)
  const yR = medianOf(ysR)
  const x0 = x[0]
  const x1 = x[n - 1]
  if (!Number.isFinite(yL) || !Number.isFinite(yR) || !(x1 > x0)) return
  const net = new Float64Array(n)
  for (let i = 0; i < n; i += 1) {
    const t = (x[i] - x0) / (x1 - x0)
    net[i] = y[i] - (yL + (yR - yL) * t)
  }
  const netArea = trapzArea(x, net, n)
  let modelArea = 0
  for (const p of peaks) {
    const params = placedParamsFor(fn, p.x0, p.y0, p.width)
    if (!params) return
    const a = numericArea(fn, params)
    if (!Number.isFinite(a)) return
    modelArea += a
  }
  if (!Number.isFinite(netArea) || !Number.isFinite(modelArea)) return
  if (netArea === 0 || modelArea === 0 || netArea * modelArea <= 0) return
  const f = Math.max(0.2, Math.min(5, netArea / modelArea))
  if (!Number.isFinite(f) || f === 1) return
  for (const p of peaks) p.width *= f
}

function selectPeaks(
  candidates: RawPeak[],
  sensitivity: number,
  maxPeaks: number,
  floor: number
): RawPeak[] {
  if (candidates.length === 0) return []
  const proms = candidates.map((c) => c.prominence).sort((a, b) => a - b)
  const sens = Math.max(0, Math.min(1, sensitivity))
  const idx = Math.max(
    0,
    Math.min(proms.length - 1, Math.floor((1 - sens) * (proms.length - 1)))
  )
  const threshold = Math.max(floor, proms[idx])
  let kept = candidates.filter((c) => c.prominence >= threshold)
  if (kept.length === 0) {
    kept = [candidates.reduce((a, b) => (a.prominence >= b.prominence ? a : b))]
  }
  kept.sort((a, b) => b.prominence - a.prominence)
  if (maxPeaks > 0) kept = kept.slice(0, Math.max(1, Math.floor(maxPeaks)))
  kept.sort((a, b) => a.index - b.index)
  return kept
}

/**
 * Detect peaks in (x, y). `yModel` is subtracted first when provided.
 * The returned width is in x units and is intended as the initial width
 * parameter for the peak function selected in `opts.fn`.
 */
export function detectPeaks(
  x: Float64Array,
  y: Float64Array,
  opts: DetectOptions
): DetectedPeak[] {
  const n = Math.min(x.length, y.length)
  if (n < 5) return []
  const target = new Float64Array(n)
  for (let i = 0; i < n; i += 1) {
    target[i] = y[i] - (opts.yModel ? opts.yModel[i] ?? 0 : 0)
  }

  let win = Math.floor(opts.smoothWindow)
  if (win > 0) {
    if (win % 2 === 0) win += 1
    if (win < 5) win = 5
    if (win > n) win = n % 2 === 1 ? n : n - 1
  }
  const method = opts.method

  if (method === 'deriv2') {
    const w = win >= 5 ? win : Math.min(n % 2 === 1 ? n : n - 1, 9)
    const d2 = savgol(target, w, 3, 2)
    // Uniform x spacing is required for the curvature-to-width conversion.
    const dx = n > 1 ? (x[n - 1] - x[0]) / (n - 1) : 1
    const neg = new Float64Array(n)
    for (let i = 0; i < n; i += 1) neg[i] = -d2[i]
    const floor = Math.max(noiseLevel(neg) * 2, 1e-300)
    const candidates: RawPeak[] = []
    for (let i = 1; i < n - 1; i += 1) {
      if (neg[i] > neg[i - 1] && neg[i] >= neg[i + 1]) {
        const p = prominenceOf(neg, i)
        if (p.prominence > 0) candidates.push(p)
      }
    }
    const kept = selectPeaks(candidates, opts.sensitivity, opts.maxPeaks, floor)
    let maxProm = 0
    for (const p of kept) maxProm = Math.max(maxProm, p.prominence)
    const result: DetectedPeak[] = []
    for (const p of kept) {
      const i = p.index
      // Curvature width estimate: y'' = -A/sigma^2 for a Gaussian.
      let width = 0
      if (dx > 0 && d2[i] < 0 && target[i] > 0) {
        const sigma = Math.sqrt(target[i] / (-d2[i] / (dx * dx)))
        width = 2.3548200450309493 * sigma
      }
      if (!(width > 0) || !Number.isFinite(width)) {
        width = halfProminenceWidth(x, neg, p, p.prominence)
      }
      if (!(width > 0)) width = Math.abs(dx) * 4
      const placement = shapeAwarePlacement(opts.fn, x[i], target[i], width)
      result.push({
        x0: placement.x0,
        y0: placement.y0,
        width: placement.width,
        strength: maxProm > 0 ? p.prominence / maxProm : 0
      })
    }
    return result
  }

  // 'residual' (and any unknown value) -> local maxima of the residual.
  let sig: Float64Array = target
  if (win >= 5) sig = savgol(target, win, 3, 0)
  const floor = Math.max(noiseLevel(sig) * 2, 1e-300)
  const candidates: RawPeak[] = []
  for (let i = 1; i < n - 1; i += 1) {
    if (sig[i] > sig[i - 1] && sig[i] >= sig[i + 1]) {
      const p = prominenceOf(sig, i)
      if (p.prominence > 0) candidates.push(p)
    }
  }
  const kept = selectPeaks(candidates, opts.sensitivity, opts.maxPeaks, floor)
  let maxProm = 0
  for (const p of kept) maxProm = Math.max(maxProm, p.prominence)
  const result: DetectedPeak[] = []
  for (const p of kept) {
    const i = p.index
    let width = halfProminenceWidth(x, sig, p, p.prominence)
    if (!(width > 0) || !Number.isFinite(width)) width = 4 * Math.abs(x[Math.min(n - 1, 1)] - x[0])
    const placement = shapeAwarePlacement(opts.fn, x[i], target[i], width)
    result.push({
      x0: placement.x0,
      y0: placement.y0,
      width: placement.width,
      strength: maxProm > 0 ? p.prominence / maxProm : 0
    })
  }
  conserveArea(x, y, n, opts.fn, result)
  return result
}
