/**
 * Peaks + baseline model store.
 * Peak objects are small and legitimately reactive (param table, popover,
 * list cards all render from them). Curve buffers for the chart are NOT
 * stored here — the plot controller derives view-space curves directly.
 */
import { computed, reactive, ref, shallowRef } from 'vue'
import type { BaselineSpec, ParamValues, PeakResult, PeakSpec } from '@/lib/pwcore/shared/types'
import {
  BASELINE_FNS,
  BASELINE_FN_MAP,
  DEFAULT_BASELINE_FN,
  DEFAULT_PEAK_FN,
  FAMILY_LABELS,
  PEAK_FNS,
  PEAK_FN_MAP,
  type BaselineFnId,
  type PeakFamily,
  type PeakFnId,
} from '@/lib/pwcore/shared/registry'
import { paletteColor } from '../utils/palette'
import { measurePeakGeometry } from '../core-bridge/engine'

// ---------------------------------------------------------------------
// peaks
// ---------------------------------------------------------------------

const list = ref<PeakSpec[]>([])
const selectedId = ref<string | null>(null)
const defaultFn = ref<PeakFnId>(DEFAULT_PEAK_FN)

/** Series-list level changes (add/remove peak, fn change, enable toggle). */
const structureVersion = ref(0)
/** Value-level changes that only affect curve shapes. */
const curvesVersion = ref(0)
/**
 * USER edit signal (Adjust Fit): bumped only by user-initiated model edits
 * (anchor drag, param typing, add/remove/toggle, baseline edits, point
 * exclusion). Internal re-renders and fit-result commits do NOT bump it, so
 * the auto-refit watcher never loops. Mirrors the reference application's adjust→fit→adjust
 * loop where the fit follows every adjustment without extra clicks.
 */
const editTick = ref(0)
/**
 * Non-parametric 自动扫描 baseline preview (the reference application Prepare · 自动扫描).
 * When present, the chart draws it as the baseline curve and the subtract
 * preview subtracts it, so the user can eyeball it before committing.
 */
const scanBase = shallowRef<Float64Array | null>(null)
function setScanBase(v: Float64Array | null): void {
  scanBase.value = v
}
/** Bump the user-edit signal (call from every user edit entry point). */
export function bumpEdit(): void {
  editTick.value += 1
}

let colorSeq = 0
let idSeq = 0

function newId(): string {
  idSeq += 1
  return `pk${Date.now().toString(36)}${idSeq.toString(36)}`
}

/** Initial parameter values from registry metadata. */
export function initParams(fn: PeakFnId, cx: number, cy: number, width: number): ParamValues {
  const meta = PEAK_FN_MAP.get(fn)
  const p: ParamValues = {}
  if (!meta) return p
  for (const pm of meta.params) {
    if (pm.init === 'clickX') p[pm.key] = cx
    else if (pm.init === 'clickY') p[pm.key] = cy
    else if (pm.init === 'autoWidth') p[pm.key] = Math.max(width, pm.min ?? 1e-12)
    else p[pm.key] = pm.init
  }
  return p
}

export function createPeak(fn: PeakFnId, cx: number, cy: number, width: number): PeakSpec {
  bumpEdit()
  const spec: PeakSpec = {
    id: newId(),
    fn,
    p: initParams(fn, cx, cy, width),
    locked: {},
    enabled: true,
    color: paletteColor(colorSeq++),
  }
  list.value.push(spec)
  structureVersion.value++
  curvesVersion.value++
  return spec
}

/** Replace a peak's function keeping a0/a1/a2 (峰调整 semantics). */
/**
 * Change the peak function while preserving the *visual* peak: height, center
 * and FWHM are measured before the switch and restored on the new model.
 * Raw a0 is NOT copied: area-parameterized functions (EMG/GMG/HVL/NLC) would
 * otherwise produce a completely different curve height.
 */
export function changePeakFn(peak: PeakSpec, fn: PeakFnId): void {
  if (peak.fn === fn) return
  bumpEdit()
  const old = peak.p
  const geo = measurePeakGeometry(peak.fn, old)
  const targetH = geo.height
  const targetFwhm =
    geo.leftHalfX !== null && geo.rightHalfX !== null ? geo.rightHalfX - geo.leftHalfX : null

  peak.fn = fn
  peak.p = initParams(fn, old.a1, old.a0, old.a2)
  peak.p.a1 = old.a1

  const meta = PEAK_FN_MAP.get(fn)
  const wMin = meta?.params.find((pm) => pm.key === 'a2')?.min ?? 1e-12

  // Width: FWHM scales approximately linearly with a2; iterate to converge
  // because asymmetric models (EMG/GMG) couple width and shape.
  if (targetFwhm !== null && targetFwhm > 0) {
    for (let pass = 0; pass < 3; pass++) {
      const g = measurePeakGeometry(fn, peak.p)
      if (g.leftHalfX === null || g.rightHalfX === null) break
      const curFwhm = g.rightHalfX - g.leftHalfX
      if (!(curFwhm > 1e-12)) break
      const ratio = targetFwhm / curFwhm
      if (Math.abs(ratio - 1) < 0.003) break
      peak.p.a2 = Math.max(peak.p.a2 * ratio, wMin)
    }
  }
  // Height: y is linear in a0 for every built-in peak.
  const gH = measurePeakGeometry(fn, peak.p).height
  if (gH > 1e-12 && targetH > 0) {
    peak.p.a0 = (peak.p.a0 * targetH) / gH
  }

  structureVersion.value++
  curvesVersion.value++
}

export function removePeak(id: string): void {
  bumpEdit()
  const i = list.value.findIndex((p) => p.id === id)
  if (i >= 0) {
    list.value.splice(i, 1)
    if (selectedId.value === id) selectedId.value = null
    structureVersion.value++
    curvesVersion.value++
  }
}

/** Re-insert an exact spec (undo/redo of peak placement). */
export function reinsertPeak(spec: PeakSpec): void {
  if (list.value.some((p) => p.id === spec.id)) return
  list.value.push(spec)
  structureVersion.value++
  curvesVersion.value++
}

export function setPeakEnabled(id: string, enabled: boolean): void {
  bumpEdit()
  const p = list.value.find((q) => q.id === id)
  if (p && p.enabled !== enabled) {
    p.enabled = enabled
    structureVersion.value++
    curvesVersion.value++
  }
}

export function setParam(spec: PeakSpec | null, key: string, value: number): void {
  bumpEdit()
  if (!spec) return
  spec.p[key] = value
  curvesVersion.value++
}

export function setParamLocked(spec: PeakSpec | null, key: string, locked: boolean): void {
  if (!spec) return
  if (locked) spec.locked[key] = true
  else delete spec.locked[key]
}

export function selectPeak(id: string | null): void {
  selectedId.value = id
}

// ---------------------------------------------------------------------
// baseline
// ---------------------------------------------------------------------

const baseline = reactive<BaselineSpec>({
  fn: DEFAULT_BASELINE_FN,
  p: initBaselineParams(DEFAULT_BASELINE_FN),
  locked: {},
  enabled: true,
})

function initBaselineParams(fn: BaselineFnId): ParamValues {
  const meta = BASELINE_FN_MAP.get(fn)
  const p: ParamValues = {}
  if (!meta) return p
  for (const pm of meta.params) {
    p[pm.key] = typeof pm.init === 'number' ? pm.init : 0
  }
  return p
}

/** Re-initialize baseline params against data (clickY → yMin, autoWidth → 5% span). */
export function resetBaselineForData(xMin: number, xMax: number, yHint: number): void {
  const meta = BASELINE_FN_MAP.get(baseline.fn)
  if (!meta) return
  const span = Math.max(xMax - xMin, 1e-12)
  for (const pm of meta.params) {
    if (pm.init === 'clickY') baseline.p[pm.key] = yHint
    else if (pm.init === 'autoWidth') baseline.p[pm.key] = span * 0.05
    else if (typeof pm.init === 'number') baseline.p[pm.key] = pm.init
  }
  baseline.locked = {}
  structureVersion.value++
  curvesVersion.value++
}

export function setBaselineFn(fn: BaselineFnId): void {
  bumpEdit()
  if (baseline.fn === fn) return
  baseline.fn = fn
  baseline.p = initBaselineParams(fn)
  baseline.locked = {}
  structureVersion.value++
  curvesVersion.value++
}

export function setBaselineParam(key: string, value: number): void {
  bumpEdit()
  baseline.p[key] = value
  curvesVersion.value++
}

export function setBaselineLocked(key: string, locked: boolean): void {
  if (locked) baseline.locked[key] = true
  else delete baseline.locked[key]
}

export function setBaselineEnabled(on: boolean): void {
  bumpEdit()
  if (baseline.enabled !== on) {
    baseline.enabled = on
    structureVersion.value++
    curvesVersion.value++
  }
}

// ---------------------------------------------------------------------
// snapshots (fit pre-roll / undo payloads)
// ---------------------------------------------------------------------

export interface ModelSnapshot {
  peaks: PeakSpec[]
  baseline: BaselineSpec
  selectedId: string | null
}

export function exportSnapshot(): ModelSnapshot {
  return {
    peaks: list.value.map((p) => ({ ...p, p: { ...p.p }, locked: { ...p.locked } })),
    baseline: { ...baseline, p: { ...baseline.p }, locked: { ...baseline.locked } },
    selectedId: selectedId.value,
  }
}

export function importSnapshot(s: ModelSnapshot): void {
  list.value = s.peaks.map((p) => ({ ...p, p: { ...p.p }, locked: { ...p.locked } }))
  const b = s.baseline
  baseline.fn = b.fn
  baseline.p = { ...b.p }
  baseline.locked = { ...b.locked }
  baseline.enabled = b.enabled
  selectedId.value = s.selectedId
  structureVersion.value++
  curvesVersion.value++
}

export function clearPeaks(): void {
  list.value = []
  selectedId.value = null
  structureVersion.value++
  curvesVersion.value++
}

// ---------------------------------------------------------------------
// fit results merged per peak id
// ---------------------------------------------------------------------

const resultById = ref<Map<string, PeakResult>>(new Map())

export function setResultMap(map: Map<string, PeakResult>): void {
  resultById.value = map
  curvesVersion.value++
}

export function clearResults(): void {
  resultById.value = new Map()
}

// ---------------------------------------------------------------------
// grouped function lists for <select>/<optgroup>
// ---------------------------------------------------------------------

interface FnGroup {
  family: PeakFamily
  label: string
  fns: { id: PeakFnId; label: string; name: string }[]
}

export const FN_GROUPS: FnGroup[] = (Object.keys(FAMILY_LABELS) as PeakFamily[]).map((family) => ({
  family,
  label: FAMILY_LABELS[family],
  fns: PEAK_FNS.filter((f) => f.family === family).map((f) => ({ id: f.id, label: f.label, name: f.name })),
}))

export const BASELINE_OPTIONS = BASELINE_FNS.map((f) => ({ id: f.id, label: f.label, name: f.name }))

const enabledPeaks = computed(() => list.value.filter((p) => p.enabled))

export function usePeaks() {
  return {
    list,
    selectedId,
    defaultFn,
    baseline,
    structureVersion,
    curvesVersion,
    editTick,
    scanBase, setScanBase,
    resultById,
    enabledPeaks,
    createPeak,
    changePeakFn,
    removePeak,
    setPeakEnabled,
    setParam,
    setParamLocked,
    selectPeak,
    resetBaselineForData,
    setBaselineFn,
    setBaselineParam,
    setBaselineLocked,
    setBaselineEnabled,
    exportSnapshot,
    importSnapshot,
    clearPeaks,
    setResultMap,
    clearResults,
  }
}
