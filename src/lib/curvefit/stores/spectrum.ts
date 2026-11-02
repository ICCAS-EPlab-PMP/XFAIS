/**
 * Spectrum store: the immutable data table (x / y / optional w / mask).
 *
 * Red line #3: TypedArray bodies live in shallowRef (never deep-reactive);
 * components subscribe via version counters instead of reactivity over the
 * arrays themselves.
 */
import { computed, reactive, shallowRef } from 'vue'
import type { DemoData, ParsedData } from '@/lib/pwcore/shared/types'
import { clearHistory } from '../stores/undo'
import { nearestIdxByX } from '../utils/lod'
import { bumpEdit } from '../stores/peaks'

const x = shallowRef<Float64Array | null>(null)
const y = shallowRef<Float64Array | null>(null)
const w = shallowRef<Float64Array | null>(null)
const mask = shallowRef<Uint8Array | null>(null)

/** Bumped on every full data replacement. */
const dataVersion = shallowRef(0)
/** Bumped when a mask entry flips (excluded point marks). */
const maskVersion = shallowRef(0)

const meta = reactive({
  title: '',
  source: '',
  n: 0,
  hasW: false,
  excluded: 0,
  xMin: 0,
  xMax: 0,
  yMin: 0,
  yMax: 0,
  ascending: true,
})

const ready = computed(() => x.value !== null && y.value !== null && mask.value !== null)

function resetState(): void {
  x.value = null
  y.value = null
  w.value = null
  mask.value = null
  meta.title = ''
  meta.source = ''
  meta.n = 0
  meta.hasW = false
  meta.excluded = 0
  meta.xMin = 0
  meta.xMax = 0
  meta.yMin = 0
  meta.yMax = 0
  meta.ascending = true
}

function adoptArrays(title: string, source: string, nx: Float64Array, ny: Float64Array, nw: Float64Array | null, nmask: Uint8Array | null): void {
  x.value = nx
  y.value = ny
  w.value = nw
  mask.value = nmask ?? new Uint8Array(nx.length).fill(1)

  let excluded = 0
  const m = mask.value
  for (let i = 0; i < m.length; i++) if (m[i] === 0) excluded++
  let xMin = Number.POSITIVE_INFINITY
  let xMax = Number.NEGATIVE_INFINITY
  let yMin = Number.POSITIVE_INFINITY
  let yMax = Number.NEGATIVE_INFINITY
  for (let i = 0; i < nx.length; i++) {
    if (nx[i] < xMin) xMin = nx[i]
    if (nx[i] > xMax) xMax = nx[i]
    if (ny[i] < yMin) yMin = ny[i]
    if (ny[i] > yMax) yMax = ny[i]
  }
  meta.title = title
  meta.source = source
  meta.n = nx.length
  meta.hasW = nw !== null
  meta.excluded = excluded
  meta.xMin = Number.isFinite(xMin) ? xMin : 0
  meta.xMax = Number.isFinite(xMax) ? xMax : 1
  meta.yMin = Number.isFinite(yMin) ? yMin : 0
  meta.yMax = Number.isFinite(yMax) ? yMax : 1
  meta.ascending = nx.length < 2 || nx[nx.length - 1] >= nx[0]
  dataVersion.value++
}

/** Load parsed file data. Full session reset happens in App's data watcher. */
export function loadParsed(d: ParsedData, source: string): void {
  adoptArrays(d.title || source, source, d.x, d.y, d.w, d.mask)
}

export function loadDemo(d: DemoData, source: string): void {
  adoptArrays(d.title, source, d.x, d.y, null, null)
}

/** Toggle a single point's inclusion (the reference application disabled points). */
export function togglePoint(i: number): void {
  bumpEdit()
  const m = mask.value
  if (!m || i < 0 || i >= m.length) return
  if (m[i] === 0) {
    m[i] = 1
    meta.excluded--
  } else {
    m[i] = 0
    meta.excluded++
  }
  maskVersion.value++
}

/** Batch point inclusion edit (Section drag: right = exclude, left = restore). */
export function setMaskRange(i0: number, i1: number, value: 0 | 1): void {
  const m = mask.value
  if (!m) return
  const lo = Math.max(0, Math.min(i0, i1))
  const hi = Math.min(m.length - 1, Math.max(i0, i1))
  if (hi < lo) return
  let changed = false
  for (let i = lo; i <= hi; i++) {
    if (m[i] === value) continue
    if (value === 0) meta.excluded++
    else meta.excluded--
    m[i] = value
    changed = true
  }
  if (!changed) return
  bumpEdit()
  maskVersion.value++
}

/** Count excluded raw points and publish it (single source of truth). */
function recountExcluded(m: Uint8Array): void {
  let excluded = 0
  for (let i = 0; i < m.length; i++) if (m[i] === 0) excluded++
  meta.excluded = excluded
}

/** Restore every point; bumpEdit so an armed Adjust-Fit refits on new input. */
export function restoreAllPoints(): void {
  const m = mask.value
  if (!m) return
  m.fill(1)
  meta.excluded = 0
  bumpEdit()
  maskVersion.value++
}

/**
 * Keep ONLY raw indices [lo, hi] (inclusive) as fit input; every other point
 * is excluded. The index range is clamped to the data table; `meta.excluded`
 * is recomputed from scratch. Used by 「确认保留」 after a region drag.
 * 只保留 [lo, hi] 区间内的数据参与拟合：区间外全部排除，排除计数按全表重算。
 */
export function keepOnlyRange(lo: number, hi: number): void {
  const m = mask.value
  if (!m || m.length === 0) return
  const a = Math.max(0, Math.min(lo, hi))
  const b = Math.min(m.length - 1, Math.max(lo, hi))
  if (b < a) return
  m.fill(0)
  for (let i = a; i <= b; i++) m[i] = 1
  meta.excluded = m.length - (b - a + 1)
  bumpEdit()
  maskVersion.value++
}

/**
 * Replace the whole inclusion mask from a snapshot (undo/redo of a region
 * edit). Recomputes `meta.excluded` and bumps the mask/edit counters.
 * 用快照整体回写掩膜（区域编辑的撤销/重做），并重算排除计数。
 */
export function applyMaskSnapshot(snap: Uint8Array): void {
  const m = mask.value
  if (!m || snap.length !== m.length) return
  m.set(snap)
  recountExcluded(m)
  bumpEdit()
  maskVersion.value++
}

/** Nearest raw index for a data-space x (for hover readout / hit testing). */
export function indexAtX(xVal: number): number {
  const xv = x.value
  if (!xv || xv.length === 0) return -1
  return nearestIdxByX(xv, xVal)
}

/** Wipe everything (used when a load fails mid-swap). */
export function resetSpectrum(): void {
  resetState()
  clearHistory()
  dataVersion.value++
}

/** Swap in a processed y column (smoothing); returns the previous column for undo. */
export function replaceY(ny: Float64Array): Float64Array | null {
  const old = y.value
  if (!old) return null
  let yMin = Number.POSITIVE_INFINITY
  let yMax = Number.NEGATIVE_INFINITY
  for (let i = 0; i < ny.length; i++) {
    if (ny[i] < yMin) yMin = ny[i]
    if (ny[i] > yMax) yMax = ny[i]
  }
  y.value = ny
  meta.yMin = Number.isFinite(yMin) ? yMin : 0
  meta.yMax = Number.isFinite(yMax) ? yMax : 1
  dataVersion.value++
  return old
}

/** Restore a previous y column (undo of smoothing). */
export function restoreY(old: Float64Array): void {
  let yMin = Number.POSITIVE_INFINITY
  let yMax = Number.NEGATIVE_INFINITY
  for (let i = 0; i < old.length; i++) {
    if (old[i] < yMin) yMin = old[i]
    if (old[i] > yMax) yMax = old[i]
  }
  y.value = old
  meta.yMin = Number.isFinite(yMin) ? yMin : 0
  meta.yMax = Number.isFinite(yMax) ? yMax : 1
  dataVersion.value++
}

export function useSpectrum() {
  return {
    x, y, w, mask,
    meta,
    ready,
    dataVersion,
    maskVersion,
    loadParsed,
    loadDemo,
    togglePoint,
    setMaskRange,
    restoreAllPoints,
    keepOnlyRange,
    applyMaskSnapshot,
    indexAtX,
    resetSpectrum,
    replaceY,
    restoreY,
  }
}
