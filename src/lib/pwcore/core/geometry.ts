/**
 * Peak geometry + anchor dragging (pure math, no DOM).
 *
 * Original the reference application lets the user drag 3–5 anchors per peak directly on the
 * graph (manual ch. 6, "Graphical Placement"):
 *
 *   - primary anchor: center + amplitude
 *   - half-maxima anchors (left / right): width, and on asymmetric functions
 *     the two sides move independently, which changes both width and asymmetry
 *   - quarter-maxima ("FW25") anchor: shape parameters on symmetric functions
 *
 * This module measures the anchor positions of any built-in peak function and
 * solves for parameter values that put a dragged anchor exactly under the
 * pointer, holding the other anchors where they were. All peaking functions
 * are smooth and unimodal around the center, so half/quarter crossings are
 * found by bracketing + bisection; the parameter solve is a tiny damped
 * Gauss–Newton with finite-difference Jacobians.
 */
import type { ParamValues } from '../shared/types'
import type { PeakFnId } from '../shared/registry'
import { PEAK_FN_MAP } from '../shared/registry'
import { evalPeak } from './models'

export type AnchorKind = 'main' | 'leftHalf' | 'rightHalf' | 'quarter'

export interface PeakGeometry {
  /** x of the model maximum inside the search window. */
  centerX: number
  /** y at the maximum. */
  height: number
  /** x where the left flank crosses height/2 (null when none in window). */
  leftHalfX: number | null
  /** x where the right flank crosses height/2. */
  rightHalfX: number | null
  /** x where the right flank crosses height/4 (FW25 anchor). */
  quarterX: number | null
}

/** One evaluation of the peak component at a scalar x. */
function at(fn: PeakFnId, p: ParamValues, x: number): number {
  const out = evalPeak(fn, p, [x])
  const v = out[0]
  return Number.isFinite(v) ? v : 0
}

/** Representative width used to size the search window (positive params only). */
function widthHint(fn: PeakFnId, p: ParamValues): number {
  const meta = PEAK_FN_MAP.get(fn)
  let w = 0
  if (meta) {
    for (const pm of meta.params) {
      if (pm.key === 'a2' || pm.init === 'autoWidth') {
        const v = Math.abs(p[pm.key] ?? 0)
        if (Number.isFinite(v) && v > w) w = v
      }
    }
  }
  if (w <= 0) {
    const a2 = Math.abs(p['a2'] ?? 0)
    w = Number.isFinite(a2) && a2 > 0 ? a2 : 1
  }
  return w
}

/** Locate the model maximum near a1 by a coarse scan + golden-section refine. */
function findMax(fn: PeakFnId, p: ParamValues): { x: number; y: number } {
  const a1 = p['a1'] ?? 0
  const w = widthHint(fn, p)
  const lo = a1 - 4 * w
  const hi = a1 + 4 * w
  const n = 96
  let bestX = a1
  let bestY = Number.NEGATIVE_INFINITY
  for (let i = 0; i <= n; i++) {
    const x = lo + ((hi - lo) * i) / n
    const y = at(fn, p, x)
    if (y > bestY) {
      bestY = y
      bestX = x
    }
  }
  // golden-section refine on the bracketing cell
  let l = bestX - (hi - lo) / n
  let r = bestX + (hi - lo) / n
  const g = (Math.sqrt(5) - 1) / 2
  let c = r - g * (r - l)
  let d = l + g * (r - l)
  let fc = at(fn, p, c)
  let fd = at(fn, p, d)
  for (let i = 0; i < 40; i++) {
    if (fc > fd) {
      r = d
      d = c
      fd = fc
      c = r - g * (r - l)
      fc = at(fn, p, c)
    } else {
      l = c
      c = d
      fc = fd
      d = l + g * (r - l)
      fd = at(fn, p, d)
    }
  }
  const x = (l + r) / 2
  const y = at(fn, p, x)
  return { x, y: Number.isFinite(y) ? y : 0 }
}

/**
 * Find where the flank crosses `level`, marching outward from the center.
 * Returns null when the peak never decays below the level inside the window
 * (e.g. a near-zero height).
 */
function crossX(
  fn: PeakFnId,
  p: ParamValues,
  center: number,
  level: number,
  dir: -1 | 1,
  w: number
): number | null {
  if (!(level > 0)) return null
  const maxDist = w * 1e6
  let prevX = center
  let prevY = at(fn, p, center)
  if (!(prevY > level)) return null
  let d = Math.max(w * 0.02, Number.EPSILON * Math.abs(center))
  for (let guard = 0; guard < 200 && d <= maxDist; guard++) {
    const x = center + dir * d
    const y = at(fn, p, x)
    if (!(y > level)) {
      // bisect between prevX (above) and x (at/below)
      let lo = prevX
      let hi = x
      for (let i = 0; i < 60; i++) {
        const mid = (lo + hi) / 2
        if (at(fn, p, mid) > level) lo = mid
        else hi = mid
      }
      return (lo + hi) / 2
    }
    prevX = x
    prevY = y
    d *= 1.7
  }
  return null
}

/** Measure all anchor positions for one peak component. */
export function measurePeakGeometry(fn: PeakFnId, p: ParamValues): PeakGeometry {
  const w = widthHint(fn, p)
  const mx = findMax(fn, p)
  const half = mx.y / 2
  const quarter = mx.y / 4
  return {
    centerX: mx.x,
    height: mx.y,
    leftHalfX: crossX(fn, p, mx.x, half, -1, w),
    rightHalfX: crossX(fn, p, mx.x, half, 1, w),
    quarterX: crossX(fn, p, mx.x, quarter, 1, w)
  }
}

/** Peak parameters that carry width/shape (everything except a0/a1), unlocked. */
function freeShapeKeys(fn: PeakFnId, p: ParamValues, locked: Record<string, boolean>): string[] {
  const meta = PEAK_FN_MAP.get(fn)
  const keys = meta ? meta.params.map((pm) => pm.key) : Object.keys(p)
  return keys.filter((k) => k !== 'a0' && k !== 'a1' && !locked[k] && typeof p[k] === 'number')
}

function boundsOf(fn: PeakFnId, key: string): { min: number | null; max: number | null } {
  const meta = PEAK_FN_MAP.get(fn)
  const pm = meta?.params.find((q) => q.key === key)
  return { min: pm?.min ?? null, max: pm?.max ?? null }
}

function clampKey(fn: PeakFnId, key: string, v: number): number {
  const { min, max } = boundsOf(fn, key)
  let out = v
  if (!Number.isFinite(out)) out = Number.isFinite(v) ? v : 0
  if (min !== null && out < min) out = min
  if (max !== null && out > max) out = max
  return out
}

/** Tiny damped Gauss–Newton over a handful of parameters. */
function solveLevenberg(
  fn: PeakFnId,
  x0: ParamValues,
  keys: string[],
  residual: (x: ParamValues) => number[],
  xScale: number
): ParamValues {
  const x: ParamValues = { ...x0 }
  if (keys.length === 0) return x
  let lambda = 1e-3
  const m = residual(x).length
  for (let iter = 0; iter < 10; iter++) {
    const r0 = residual(x)
    const f = r0.reduce((s, v) => s + v * v, 0)
    if (f < 1e-14) break
    // Finite-difference Jacobian (m x k) at the current x.
    const J: number[][] = []
    for (let j = 0; j < keys.length; j++) {
      const key = keys[j]
      const scale = Math.max(Math.abs(x[key]), xScale * 1e-3, 1e-9)
      const h = 1e-4 * scale
      const backup = x[key]
      x[key] = backup + h
      const rp = residual(x)
      x[key] = backup
      const col = new Array<number>(m)
      for (let i = 0; i < m; i++) col[i] = (rp[i] - r0[i]) / h
      J.push(col)
    }
    // Normal equations (JᵀJ + λdiag) δ = -Jᵀr0
    const k = keys.length
    const A: number[][] = []
    const g: number[] = []
    for (let a = 0; a < k; a++) {
      A.push(new Array<number>(k).fill(0))
      let ga = 0
      for (let i = 0; i < m; i++) ga += J[a][i] * r0[i]
      g.push(ga)
    }
    for (let a = 0; a < k; a++) {
      for (let b = a; b < k; b++) {
        let s = 0
        for (let i = 0; i < m; i++) s += J[a][i] * J[b][i]
        A[a][b] = s
        A[b][a] = s
      }
      A[a][a] += lambda * (A[a][a] > 0 ? A[a][a] : 1)
    }
    const delta = solveDense(A, g.map((v) => -v))
    if (!delta) {
      lambda *= 10
      if (lambda > 1e12) break
      continue
    }
    const trial: ParamValues = { ...x }
    for (let a = 0; a < k; a++) trial[keys[a]] = clampKey(fn, keys[a], x[keys[a]] + delta[a])
    const rt = residual(trial)
    const ft = rt.reduce((s, v) => s + v * v, 0)
    if (ft < f) {
      for (let a = 0; a < k; a++) x[keys[a]] = trial[keys[a]]
      lambda = Math.max(lambda / 10, 1e-12)
    } else {
      lambda *= 10
      if (lambda > 1e12) break
    }
  }
  return x
}

/** Key-to-function lookup for clamping; set per solve call. */
function solveDense(A: number[][], b: number[]): number[] | null {
  const n = b.length
  const m = A.map((row, i) => [...row, b[i]])
  for (let col = 0; col < n; col++) {
    let piv = col
    for (let r = col + 1; r < n; r++) if (Math.abs(m[r][col]) > Math.abs(m[piv][col])) piv = r
    if (!(Math.abs(m[piv][col]) > 1e-300)) return null
    if (piv !== col) {
      const tmp = m[piv]
      m[piv] = m[col]
      m[col] = tmp
    }
    for (let r = col + 1; r < n; r++) {
      const f = m[r][col] / m[col][col]
      if (f === 0) continue
      for (let c = col; c <= n; c++) m[r][c] -= f * m[col][c]
    }
  }
  const x = new Array<number>(n).fill(0)
  for (let r = n - 1; r >= 0; r--) {
    let s = m[r][n]
    for (let c = r + 1; c < n; c++) s -= m[r][c] * x[c]
    x[r] = s / m[r][r]
  }
  return x
}

export interface AnchorDragInput {
  fn: PeakFnId
  /** Parameters at drag start. */
  startP: ParamValues
  /** Geometry measured at drag start. */
  startGeom: PeakGeometry
  /** Which anchor is being dragged. */
  kind: Exclude<AnchorKind, 'main'>
  /** Target x under the pointer (data units). */
  targetX: number
  locked: Record<string, boolean>
}

/**
 * Solve peak parameters so the dragged half/quarter anchor lands on targetX
 * while the opposite anchor stays where it was. Returns a new parameter object
 * (never mutates the input).
 */
export function solveAnchorDrag(input: AnchorDragInput): ParamValues {
  const { fn, startP, startGeom, kind, targetX, locked } = input
  const w = widthHint(fn, startP)
  const degenerate = Math.max(w, Math.abs(startGeom.centerX) * 1e-9, 1e-9)
  const xScale = Math.max(Math.abs(degenerate), 1e-12)
  const p0 = { ...startP }
  if (kind === 'quarter') {
    // Shape anchor: hold the right half crossing, move the quarter crossing.
    const shapeKeys = freeShapeKeys(fn, p0, locked).filter((k) => k !== 'a2')
    const keys = shapeKeys.length > 0 ? shapeKeys : ['a2']
    const holdHalf = startGeom.rightHalfX
    const withHalf = shapeKeys.length > 0 && holdHalf !== null
    const residual = (x: ParamValues): number[] => {
      const g = measurePeakGeometry(fn, x)
      const r1 = g.quarterX === null ? 5 : (g.quarterX - targetX) / xScale
      if (!withHalf) return [r1]
      const r2 = g.rightHalfX === null ? 5 : (g.rightHalfX - (holdHalf as number)) / xScale
      return [r1, r2 * 0.7]
    }
    return solveLevenberg(fn, p0, keys, residual, xScale)
  }

  // Half anchors: move one side, keep the other side fixed when the model has
  // enough shape freedom; otherwise scale the width symmetrically.
  const side = kind
  const keys = freeShapeKeys(fn, p0, locked)
  if (keys.length === 0) return p0
  const otherX = side === 'rightHalf' ? startGeom.leftHalfX : startGeom.rightHalfX
  // One free parameter means a symmetric model: a single residual (the other
  // side necessarily moves along with it).
  const twoSided = keys.length >= 2 && otherX !== null
  const residual = (x: ParamValues): number[] => {
    const g = measurePeakGeometry(fn, x)
    const cross = side === 'rightHalf' ? g.rightHalfX : g.leftHalfX
    const r1 = cross === null ? 5 : (cross - targetX) / xScale
    if (!twoSided) return [r1]
    const other = side === 'rightHalf' ? g.leftHalfX : g.rightHalfX
    const r2 = other === null ? 5 : (other - (otherX as number)) / xScale
    return [r1, r2 * 0.8]
  }
  return solveLevenberg(fn, p0, keys, residual, xScale)
}
