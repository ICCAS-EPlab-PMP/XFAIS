/**
 * View-table LOD for plotting.
 *
 * Red line #4 (保尖): large datasets are decimated with per-pixel min/max
 * buckets — each bucket keeps BOTH its min-y and max-y point so narrow peaks
 * never visually disappear. The fit input is never touched; this is
 * display-only. `rawIdx` maps every view sample back to its raw index so
 * exclusion marks / point hit-testing stay exact.
 */

export interface ViewTable {
  /** x values of kept samples (raw data values). */
  xs: Float64Array
  /** raw y at kept samples. */
  ys: Float64Array
  /** raw data index for each kept sample. */
  rawIdx: Int32Array
  /** true when the table is the raw slice itself (1:1). */
  exact: boolean
}

/** Is x ascending? (spectra are almost always monotonic; support both) */
export function isAscending(x: ArrayLike<number>): boolean {
  const n = x.length
  if (n < 2) return true
  return x[n - 1] >= x[0]
}

/** Binary search nearest raw index for a target x. Works for ascending or descending x. */
export function nearestIdxByX(x: ArrayLike<number>, target: number): number {
  const n = x.length
  if (n === 0) return -1
  const asc = isAscending(x)
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    const xv = x[mid]
    const before = asc ? target < xv : target > xv
    if (before) hi = mid
    else lo = mid
  }
  const dl = Math.abs(x[lo] - target)
  const dh = Math.abs(x[hi] - target)
  return dl <= dh ? lo : hi
}

/** Lowest index with x >= target (ascending) — start of the visible window. */
function lowerBound(x: ArrayLike<number>, target: number, asc: boolean): number {
  const n = x.length
  let lo = 0
  let hi = n
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    const xv = x[mid]
    const ge = asc ? xv >= target : xv <= target
    if (ge) hi = mid
    else lo = mid + 1
  }
  return lo
}

/**
 * Build the visible view table.
 * @param xMin/xMax current viewport in data units (null = full range)
 * @param maxSamples budget ≈ 2 samples per pixel column
 */
export function buildViewTable(
  x: ArrayLike<number>,
  y: ArrayLike<number>,
  xMin: number | null,
  xMax: number | null,
  maxSamples: number,
): ViewTable {
  const n = x.length
  if (n === 0) return { xs: new Float64Array(0), ys: new Float64Array(0), rawIdx: new Int32Array(0), exact: true }

  const asc = isAscending(x)
  let i0 = 0
  let i1 = n - 1
  if (xMin !== null && xMax !== null && Number.isFinite(xMin) && Number.isFinite(xMax)) {
    const a = lowerBound(x, Math.min(xMin, xMax), asc)
    const b = lowerBound(x, Math.max(xMin, xMax), asc)
    i0 = Math.max(0, a - 1)
    i1 = Math.min(n - 1, b)
    if (i1 < i0) {
      i0 = 0
      i1 = n - 1
    }
  }

  const span = i1 - i0 + 1
  if (span <= maxSamples) {
    const xs = new Float64Array(span)
    const ys = new Float64Array(span)
    const idx = new Int32Array(span)
    for (let k = 0; k < span; k++) {
      const i = i0 + k
      xs[k] = x[i]
      ys[k] = y[i]
      idx[k] = i
    }
    return { xs, ys, rawIdx: idx, exact: true }
  }

  // min-max bucketing: each bucket contributes its min-y and max-y points.
  const buckets = Math.max(16, Math.floor(maxSamples / 2))
  const per = span / buckets
  const xs: number[] = []
  const ys: number[] = []
  const idx: number[] = []
  for (let b = 0; b < buckets; b++) {
    const s = i0 + Math.floor(b * per)
    const e = Math.min(i1, i0 + Math.floor((b + 1) * per) - 1)
    if (e < s) continue
    let iMin = s
    let iMax = s
    for (let i = s + 1; i <= e; i++) {
      const v = y[i]
      if (v < y[iMin]) iMin = i
      if (v > y[iMax]) iMax = i
    }
    // emit in index order so the polyline stays monotonic in x
    if (iMin === iMax) {
      xs.push(x[iMin])
      ys.push(y[iMin])
      idx.push(iMin)
    } else if (iMin < iMax) {
      xs.push(x[iMin], x[iMax])
      ys.push(y[iMin], y[iMax])
      idx.push(iMin, iMax)
    } else {
      xs.push(x[iMax], x[iMin])
      ys.push(y[iMax], y[iMin])
      idx.push(iMax, iMin)
    }
  }
  return {
    xs: Float64Array.from(xs),
    ys: Float64Array.from(ys),
    rawIdx: Int32Array.from(idx),
    exact: false,
  }
}

/** Sample a full-length curve at the view table's raw indices. */
export function sampleCurve(src: ArrayLike<number>, table: ViewTable): Float64Array {
  const out = new Float64Array(table.rawIdx.length)
  for (let k = 0; k < out.length; k++) {
    const i = table.rawIdx[k]
    out[k] = i >= 0 && i < src.length ? src[i] : Number.NaN
  }
  return out
}

/** Sample a full-length curve into a nullable array (for the residual plot: NaN → null gaps). */
export function sampleCurveNullable(src: ArrayLike<number>, table: ViewTable): (number | null)[] {
  const out: (number | null)[] = new Array(table.rawIdx.length)
  for (let k = 0; k < out.length; k++) {
    const i = table.rawIdx[k]
    const v = i >= 0 && i < src.length ? src[i] : Number.NaN
    out[k] = Number.isFinite(v) ? v : null
  }
  return out
}
