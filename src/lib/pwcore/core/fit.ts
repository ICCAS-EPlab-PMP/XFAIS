/**
 * Fit orchestration: FitRequest -> parameter packing -> bounded LM ->
 * statistics + full-range curves.
 *
 * Packing order (matches the shared contract):
 *   [enabled peak 0 params..., enabled peak 1 params..., ..., baseline params...]
 * over the parameters that are not locked. Locked parameters remain in the
 * full vector used internally (so the model evaluator sees their fixed
 * values) but never become LM variables.
 */
import type {
  ConstraintSpec,
  FitError,
  FitIterEvent,
  FitOptions,
  FitOutcome,
  FitRequest,
  FitResult,
  ParamValues,
  PeakConstraints,
  PeakResult
} from '../shared/types'
import { DEFAULT_CONSTRAINTS } from '../shared/types'
import type { BaselineFnId, PeakFnId } from '../shared/registry'
import { PEAK_FN_MAP, BASELINE_FN_MAP } from '../shared/registry'
import { peakValue, baselineValue } from './models'
import { peakShape } from './statsfn'
import {
  levenbergMarquardt,
  makeControl,
  type FitterControl,
  type JacobianColumnFn,
  type SoftBoxConstraint
} from './fitter'

export interface FitRunHooks {
  onIter?: (event: FitIterEvent) => void
  control?: FitterControl
}

function fail(jobId: string, message: string): FitError {
  return { jobId, ok: false, error: message }
}

interface PeakLayout {
  id: string
  fn: PeakFnId
  keys: string[]
  /** Index in the full parameter vector for each parameter. */
  indices: number[]
  /** Number of parameters of this function. */
  n: number
}

interface BaselineLayout {
  fn: BaselineFnId
  keys: string[]
  indices: number[]
  n: number
}

function metadataForPeak(fn: PeakFnId): string[] {
  const meta = PEAK_FN_MAP.get(fn)
  return meta ? meta.params.map((p) => p.key) : []
}

function metadataForBaseline(fn: BaselineFnId): string[] {
  const meta = BASELINE_FN_MAP.get(fn)
  return meta ? meta.params.map((p) => p.key) : []
}

function sanitize(
  raw: number | undefined,
  init: number | string,
  min: number | null,
  max: number | null,
  span: number,
  mid: number,
  isWidth: boolean
): number {
  let v = raw
  if (v === undefined || !Number.isFinite(v)) {
    if (typeof init === 'number') v = init
    else if (init === 'autoWidth') v = span / 20
    else if (init === 'clickX') v = mid
    else v = 0
  }
  if (isWidth && !(v > 0)) {
    // A zero or negative width is meaningless.
    v = Math.max(span / 20, Math.abs(span) * 1e-6, 1e-9)
  }
  if (min !== null && v < min) v = min
  if (max !== null && v > max) v = max
  if (!Number.isFinite(v)) v = 0
  return v
}

const CONSTRAINT_KEYS = ['a0', 'a1', 'a2', 'a3', 'a4'] as const

function normalizeConstraintSpec(
  spec: ConstraintSpec | undefined,
  fallback: ConstraintSpec
): ConstraintSpec {
  if (!spec || typeof spec !== 'object') return { ...fallback }
  const enabled = typeof spec.enabled === 'boolean' ? spec.enabled : fallback.enabled
  const pct = Number.isFinite(spec.pct)
    ? Math.max(0, Math.min(100, spec.pct))
    : fallback.pct
  return { enabled, pct }
}

/** Missing/partial constraints fall back to the shipped the reference application defaults. */
function normalizeConstraints(c: PeakConstraints | undefined | null): PeakConstraints {
  const out = {} as PeakConstraints
  for (const key of CONSTRAINT_KEYS) {
    out[key] = normalizeConstraintSpec(c ? c[key] : undefined, DEFAULT_CONSTRAINTS[key])
  }
  return out
}

function clampOptions(o: FitOptions): FitOptions {
  const maxIter = Number.isFinite(o.maxIter) ? Math.max(1, Math.min(100000, o.maxIter)) : 500
  const convDigits = Number.isFinite(o.convDigits)
    ? Math.max(3, Math.min(14, o.convDigits))
    : 6
  const fitExtent = Number.isFinite(o.fitExtent) ? Math.max(1, Math.floor(o.fitExtent)) : 1
  const robust =
    o.robust === 'lad' || o.robust === 'lorentz' || o.robust === 'p7lim'
      ? o.robust
      : 'ls'
  return {
    maxIter,
    convDigits,
    robust,
    fitExtent,
    xMin: o.xMin === null || !Number.isFinite(o.xMin) ? null : o.xMin,
    xMax: o.xMax === null || !Number.isFinite(o.xMax) ? null : o.xMax,
    constraints: normalizeConstraints(o.constraints)
  }
}

function medianOf(values: number[]): number {
  if (values.length === 0) return 0
  const s = values.slice().sort((a, b) => a - b)
  const mid = s.length >> 1
  return s.length % 2 === 1 ? s[mid] : 0.5 * (s[mid - 1] + s[mid])
}

/**
 * Synchronous fit driver. Returns a FitResult on success or a FitError for
 * validation failures and user aborts (error === 'aborted'). The Electron
 * worker uses this entry point; the renderer uses the Promise wrapper below.
 */
export function runFitSync(req: FitRequest, hooks: FitRunHooks = {}): FitOutcome {
  const jobId = req.jobId
  if (!req.options || !Array.isArray(req.peaks) || !req.baseline) {
    return fail(jobId, 'malformed fit request')
  }
  const x = req.x
  const y = req.y
  if (!x || !y) return fail(jobId, 'missing x/y arrays')
  const nData = x.length
  if (nData !== y.length) return fail(jobId, 'x and y arrays have different lengths')
  if (nData === 0) return fail(jobId, 'no data points')
  if (!Number.isFinite(x[0]) || !Number.isFinite(x[nData - 1])) {
    return fail(jobId, 'data contains non-finite x values')
  }

  let xMinData = Number.POSITIVE_INFINITY
  let xMaxData = Number.NEGATIVE_INFINITY
  for (let i = 0; i < nData; i += 1) {
    const xv = x[i]
    if (!Number.isFinite(xv)) continue
    if (xv < xMinData) xMinData = xv
    if (xv > xMaxData) xMaxData = xv
  }
  if (!Number.isFinite(xMinData) || !Number.isFinite(xMaxData)) {
    return fail(jobId, 'data contains no finite x values')
  }
  const span = Math.max(xMaxData - xMinData, 1e-9)
  const mid = 0.5 * (xMinData + xMaxData)
  const opts = clampOptions(req.options)
  const winLo = opts.xMin === null ? xMinData : Math.max(xMinData, opts.xMin)
  const winHi = opts.xMax === null ? xMaxData : Math.min(xMaxData, opts.xMax)
  if (!(winHi > winLo)) return fail(jobId, 'empty fit window (xMin >= xMax)')

  // ------------------------------------------------------------------
  // Baseline seed
  // ------------------------------------------------------------------
  // The original derives its initial baseline from an automatic scan. When
  // the request still carries the freshly placed zero baseline (b0=0 and
  // every other parameter still 0), seed b0 — and b1 for the linear-family
  // backgrounds — from a straight line through the medians of the first and
  // last 5% of the windowed points. Locked/initialized baselines are left
  // untouched.
  let baselineSeed: Map<string, number> | null = null
  if (req.baseline && req.baseline.enabled && req.baseline.fn !== 'none') {
    const seedKeys = metadataForBaseline(req.baseline.fn)
    let atDefault = seedKeys.length > 0
    for (const key of seedKeys) {
      const v = req.baseline.p[key]
      if (v !== undefined && v !== 0) {
        atDefault = false
        break
      }
    }
    if (atDefault) {
      const maskIn = req.mask
      const winIdx: number[] = []
      for (let i = 0; i < nData; i += 1) {
        const xv = x[i]
        if (!(xv >= winLo && xv <= winHi)) continue
        if (maskIn && maskIn.length === nData && maskIn[i] === 0) continue
        winIdx.push(i)
      }
      if (winIdx.length >= 10) {
        const k = Math.max(1, Math.floor(winIdx.length * 0.05))
        const xsL: number[] = []
        const ysL: number[] = []
        const xsR: number[] = []
        const ysR: number[] = []
        for (let t = 0; t < k; t += 1) {
          const iL = winIdx[t]
          const iR = winIdx[winIdx.length - 1 - t]
          xsL.push(x[iL])
          ysL.push(y[iL])
          xsR.push(x[iR])
          ysR.push(y[iR])
        }
        const xL = medianOf(xsL)
        const yL = medianOf(ysL)
        const xR = medianOf(xsR)
        const yR = medianOf(ysR)
        if (
          Number.isFinite(xL) &&
          Number.isFinite(yL) &&
          Number.isFinite(xR) &&
          Number.isFinite(yR) &&
          xR !== xL
        ) {
          const slope = (yR - yL) / (xR - xL)
          const intercept = yL - slope * xL
          const level = 0.5 * (yL + yR)
          const linearFamily =
            req.baseline.fn === 'bglin' ||
            req.baseline.fn === 'bgquad' ||
            req.baseline.fn === 'bgcub'
          const b0Locked = req.baseline.locked['b0'] === true
          const b1Free =
            seedKeys.includes('b1') && req.baseline.locked['b1'] !== true
          if (!b0Locked && Number.isFinite(intercept) && Number.isFinite(slope)) {
            baselineSeed = new Map<string, number>()
            if (linearFamily && b1Free) {
              baselineSeed.set('b0', intercept)
              baselineSeed.set('b1', slope)
            } else {
              baselineSeed.set('b0', level)
            }
          }
        }
      }
    }
  }

  // ------------------------------------------------------------------
  // Pack parameters
  // ------------------------------------------------------------------
  const fullValues: number[] = []
  const lower: number[] = []
  const upper: number[] = []
  const fixed: number[] = []
  /** Which model component owns each full-vector parameter. */
  const owners: Array<
    { kind: 'peak'; group: number; local: number } |
    { kind: 'baseline'; group: 0; local: number }
  > = []
  const peakLayouts: PeakLayout[] = []
  let baselineLayout: BaselineLayout | null = null

  let maxAbsY = 0
  for (let i = 0; i < nData; i += 1) maxAbsY = Math.max(maxAbsY, Math.abs(y[i]))
  const ampFallback = maxAbsY > 0 ? maxAbsY * 0.25 : 1

  for (const pk of req.peaks) {
    if (!pk.enabled) continue
    const meta = PEAK_FN_MAP.get(pk.fn)
    if (!meta) return fail(jobId, `unknown peak function: ${pk.fn}`)
    const keys = metadataForPeak(pk.fn)
    const indices: number[] = []
    for (let j = 0; j < keys.length; j += 1) {
      const key = keys[j]
      const pm = meta.params[j]
      let raw = pk.p[key]
      if (raw === undefined && key === 'a0') raw = ampFallback
      if (raw === undefined && key === 'a1') raw = mid
      const isWidth = j === 2
      const value = sanitize(raw, pm.init, pm.min, pm.max, span, mid, isWidth)
      indices.push(fullValues.length)
      owners.push({ kind: 'peak', group: peakLayouts.length, local: j })
      fullValues.push(value)
      lower.push(pm.min === null ? -Number.MAX_VALUE : pm.min)
      upper.push(pm.max === null ? Number.MAX_VALUE : pm.max)
      fixed.push(pk.locked[key] === true ? 1 : 0)
    }
    peakLayouts.push({ id: pk.id, fn: pk.fn, keys, indices, n: keys.length })
  }

  let baselineEnabled = false
  if (req.baseline && req.baseline.enabled && req.baseline.fn !== 'none') {
    const meta = BASELINE_FN_MAP.get(req.baseline.fn)
    if (!meta) return fail(jobId, `unknown baseline function: ${req.baseline.fn}`)
    const keys = metadataForBaseline(req.baseline.fn)
    const indices: number[] = []
    for (let j = 0; j < keys.length; j += 1) {
      const key = keys[j]
      const pm = meta.params[j]
      let raw = req.baseline.p[key]
      const seeded = baselineSeed ? baselineSeed.get(key) : undefined
      if (seeded !== undefined) raw = seeded
      if (raw === undefined && j === 0) raw = 0
      // BGHYP's scale (b1) and SINE's period (b1) are width-like; other
      // baseline b1/b2 parameters are coefficients and may be negative.
      const isWidth =
        (req.baseline.fn === 'bghyp' || req.baseline.fn === 'bgsine') && j === 1
      const value = sanitize(raw, pm.init, pm.min, pm.max, span, mid, isWidth)
      indices.push(fullValues.length)
      owners.push({ kind: 'baseline', group: 0, local: j })
      fullValues.push(value)
      lower.push(pm.min === null ? -Number.MAX_VALUE : pm.min)
      upper.push(pm.max === null ? Number.MAX_VALUE : pm.max)
      fixed.push(req.baseline.locked[key] === true ? 1 : 0)
    }
    baselineLayout = { fn: req.baseline.fn, keys, indices, n: keys.length }
    baselineEnabled = true
  }

  const nParam = fullValues.length
  if (nParam === 0) {
    // Nothing to fit: the model is identically zero. Still return a valid
    // result with empty peaks/statistics over the data range.
  }
  const initial = new Float64Array(fullValues)
  const lo = new Float64Array(lower)
  const hi = new Float64Array(upper)
  const fixedMask = new Uint8Array(nParam)
  for (let i = 0; i < nParam; i += 1) fixedMask[i] = fixed[i] === 1 ? 1 : 0

  // ------------------------------------------------------------------
  // Built-In Peak Fn Constraints: soft percent boxes around p0
  // ------------------------------------------------------------------
  // Constraint percentages apply to peak parameters only (baseline
  // parameters are never constrained). The box is anchored to the sanitized
  // initial value of this FitRequest — after a drag, that is the dragged
  // position, exactly like "peaks stay close to where placed".
  const softLower = new Float64Array(nParam)
  const softUpper = new Float64Array(nParam)
  const softScale = new Float64Array(nParam)
  softLower.fill(Number.NEGATIVE_INFINITY)
  softUpper.fill(Number.POSITIVE_INFINITY)
  let hasSoftBox = false
  for (const layout of peakLayouts) {
    for (let j = 0; j < layout.n; j += 1) {
      const key = layout.keys[j]
      if (
        key !== 'a0' &&
        key !== 'a1' &&
        key !== 'a2' &&
        key !== 'a3' &&
        key !== 'a4'
      ) {
        continue
      }
      const spec = opts.constraints[key as keyof PeakConstraints]
      if (!spec.enabled) continue
      const idx = layout.indices[j]
      const p0 = initial[idx]
      const half = Math.abs(p0) * (spec.pct / 100)
      const cLo = Math.max(p0 - half, lower[idx])
      const cHi = Math.min(p0 + half, upper[idx])
      if (!(cHi >= cLo)) continue
      softLower[idx] = cLo
      softUpper[idx] = cHi
      softScale[idx] = Math.max((cHi - cLo) * 0.5, 1e-12)
      hasSoftBox = true
    }
  }
  const softBox: SoftBoxConstraint | null = hasSoftBox
    ? { lower: softLower, upper: softUpper, scale: softScale }
    : null

  const freeOrder: number[] = []
  for (let i = 0; i < nParam; i += 1) if (fixedMask[i] === 0) freeOrder.push(i)

  // ------------------------------------------------------------------
  // Fit subset
  // ------------------------------------------------------------------
  const mask = req.mask
  const extent = opts.fitExtent
  const subset: number[] = []
  let eligible = 0
  for (let i = 0; i < nData; i += 1) {
    const xv = x[i]
    if (!(xv >= winLo && xv <= winHi)) continue
    if (mask && mask.length === nData && mask[i] === 0) continue
    if (eligible % extent === 0) subset.push(i)
    eligible += 1
  }
  const m = subset.length
  if (m === 0) return fail(jobId, 'no data points inside the fit window/mask')
  if (m < freeOrder.length) {
    return fail(jobId, `not enough points (${m}) for ${freeOrder.length} free parameters`)
  }

  const sx = new Float64Array(m)
  const sy = new Float64Array(m)
  const sw = new Float64Array(m)
  for (let i = 0; i < m; i += 1) {
    const src = subset[i]
    sx[i] = x[src]
    sy[i] = y[src]
    let weight = 1
    if (req.w && req.w.length === nData) {
      const wv = req.w[src]
      weight = Number.isFinite(wv) && wv > 0 ? Math.sqrt(wv) : 0
    }
    sw[i] = weight
  }

  // Weighted SST for r2.
  let wsum = 0
  let ybar = 0
  for (let i = 0; i < m; i += 1) {
    const w2 = sw[i] * sw[i]
    wsum += w2
    ybar += w2 * sy[i]
  }
  ybar = wsum > 0 ? ybar / wsum : 0
  let sst = 0
  for (let i = 0; i < m; i += 1) {
    const w2 = sw[i] * sw[i]
    const d = sy[i] - ybar
    sst += w2 * d * d
  }

  // ------------------------------------------------------------------
  // Model evaluation closure (allocation-free per call)
  // ------------------------------------------------------------------
  const scratchLen = Math.max(
    5,
    ...peakLayouts.map((l) => l.n),
    baselineLayout ? baselineLayout.n : 0
  )
  const scratch = new Float64Array(scratchLen)
  const peakBuffers = peakLayouts.map((l) => scratch.subarray(0, Math.max(1, l.n)))
  const baseBuf = baselineLayout ? scratch.subarray(0, Math.max(1, baselineLayout.n)) : null
  const model = new Float64Array(m)

  const residualFn = (pVec: Float64Array, out: Float64Array): void => {
    model.fill(0)
    for (let li = 0; li < peakLayouts.length; li += 1) {
      const layout = peakLayouts[li]
      const buf = peakBuffers[li]
      for (let j = 0; j < layout.n; j += 1) buf[j] = pVec[layout.indices[j]]
      for (let i = 0; i < m; i += 1) {
        model[i] += peakValue(layout.fn, buf, sx[i])
      }
    }
    if (baselineEnabled && baselineLayout && baseBuf) {
      for (let j = 0; j < baselineLayout.n; j += 1) {
        baseBuf[j] = pVec[baselineLayout.indices[j]]
      }
      for (let i = 0; i < m; i += 1) {
        model[i] += baselineValue(baselineLayout.fn, baseBuf, sx[i])
      }
    }
    for (let i = 0; i < m; i += 1) out[i] = sy[i] - model[i]
  }

  // Characteristic parameter scales for the numerical Jacobian.
  // Analytic-structure Jacobian: only the component that owns parameter j
  // changes, so its finite difference is evaluated over one peak (or the
  // baseline) instead of the whole 20-peak model per column.
  const jacModel = new Float64Array(m)
  const jacBuf = new Float64Array(Math.max(5, scratchLen))
  const jacobianColumn: JacobianColumnFn = (pVec, jFull, hp, hm, out) => {
    const owner = owners[jFull]
    if (!owner) {
      out.fill(0)
      return
    }
    if (owner.kind === 'peak') {
      const layout = peakLayouts[owner.group]
      const buf = jacBuf.subarray(0, Math.max(1, layout.n))
      for (let k = 0; k < layout.n; k += 1) buf[k] = pVec[layout.indices[k]]
      const local = owner.local
      const x0 = pVec[jFull]
      const evalAt = (v: number): void => {
        buf[local] = v
        for (let i = 0; i < m; i += 1) out[i] = peakValue(layout.fn, buf, sx[i])
      }
      if (hp > 0 && hm > 0) {
        evalAt(x0 + hp)
        jacModel.set(out)
        evalAt(x0 - hm)
        const inv = 1 / (hp + hm)
        for (let i = 0; i < m; i += 1) out[i] = (jacModel[i] - out[i]) * inv
      } else if (hp > 0) {
        evalAt(x0)
        jacModel.set(out)
        evalAt(x0 + hp)
        for (let i = 0; i < m; i += 1) out[i] = (out[i] - jacModel[i]) / hp
      } else if (hm > 0) {
        evalAt(x0)
        jacModel.set(out)
        evalAt(x0 - hm)
        for (let i = 0; i < m; i += 1) out[i] = (jacModel[i] - out[i]) / hm
      } else {
        out.fill(0)
      }
      return
    }
    if (!baselineLayout) {
      out.fill(0)
      return
    }
    const layout = baselineLayout
    const buf = jacBuf.subarray(0, Math.max(1, layout.n))
    for (let k = 0; k < layout.n; k += 1) buf[k] = pVec[layout.indices[k]]
    const local = owner.local
    const x0 = pVec[jFull]
    const evalAt = (v: number): void => {
      buf[local] = v
      for (let i = 0; i < m; i += 1) out[i] = baselineValue(layout.fn, buf, sx[i])
    }
    if (hp > 0 && hm > 0) {
      evalAt(x0 + hp)
      jacModel.set(out)
      evalAt(x0 - hm)
      const inv = 1 / (hp + hm)
      for (let i = 0; i < m; i += 1) out[i] = (jacModel[i] - out[i]) * inv
    } else if (hp > 0) {
      evalAt(x0)
      jacModel.set(out)
      evalAt(x0 + hp)
      for (let i = 0; i < m; i += 1) out[i] = (out[i] - jacModel[i]) / hp
    } else if (hm > 0) {
      evalAt(x0)
      jacModel.set(out)
      evalAt(x0 - hm)
      for (let i = 0; i < m; i += 1) out[i] = (jacModel[i] - out[i]) / hm
    } else {
      out.fill(0)
    }
  }

  const scales = new Float64Array(nParam)
  for (let i = 0; i < nParam; i += 1) {
    const v = Math.abs(initial[i])
    let s = Math.max(v, 1e-9)
    // Width-like parameters: use the span as a fallback when v is tiny.
    if (lo[i] > 0) s = Math.max(s, span * 1e-6)
    scales[i] = s
  }

  const fitter = levenbergMarquardt(
    {
      initial,
      lower: lo,
      upper: hi,
      fixed: fixedMask,
      residual: residualFn,
      jacobianColumn,
      n: m
    },
    {
      maxIter: opts.maxIter,
      convDigits: opts.convDigits,
      robust: opts.robust,
      sst,
      sqrtW: sw,
      control: hooks.control,
      scales,
      softBox,
      onIter: (info) => {
        if (!hooks.onIter) return
        const params: number[] = new Array(freeOrder.length)
        for (let i = 0; i < freeOrder.length; i += 1) params[i] = info.params[freeOrder[i]]
        hooks.onIter({
          jobId,
          iter: info.iter,
          chi2: info.chi2,
          r2: info.r2,
          viol: info.viol,
          fnEval: info.fnEval,
          params,
          timeMs: info.timeMs
        })
      }
    }
  )

  if (fitter.aborted) return fail(jobId, 'aborted')

  // ------------------------------------------------------------------
  // Assemble results over the full x range
  // ------------------------------------------------------------------
  const pFinal = fitter.p
  const yFit = new Float64Array(nData)
  const yBase = new Float64Array(nData)
  const residual = new Float64Array(nData)
  const yComps: Float64Array[] = []
  const peakResults: PeakResult[] = []

  const peakValues: Float64Array[] = [] // packed arrays for evaluation
  for (const layout of peakLayouts) {
    const arr = new Float64Array(layout.n)
    for (let j = 0; j < layout.n; j += 1) arr[j] = pFinal[layout.indices[j]]
    peakValues.push(arr)
  }
  const baseArr = baselineLayout ? new Float64Array(baselineLayout.n) : null
  if (baselineLayout && baseArr) {
    for (let j = 0; j < baselineLayout.n; j += 1) {
      baseArr[j] = pFinal[baselineLayout.indices[j]]
    }
  }

  for (let li = 0; li < peakLayouts.length; li += 1) {
    const layout = peakLayouts[li]
    const arr = peakValues[li]
    const comp = new Float64Array(nData)
    for (let i = 0; i < nData; i += 1) comp[i] = peakValue(layout.fn, arr, x[i])
    yComps.push(comp)
    const vals: ParamValues = {}
    const errs: ParamValues = {}
    for (let j = 0; j < layout.keys.length; j += 1) {
      const key = layout.keys[j]
      vals[key] = arr[j]
      errs[key] = fixedMask[layout.indices[j]] === 0 ? fitter.pStdErr[layout.indices[j]] : 0
    }
    const shape = peakShape(layout.fn, arr)
    peakResults.push({
      id: layout.id,
      fn: layout.fn,
      p: vals,
      pErr: errs,
      area: shape.area,
      fwhm: shape.fwhm,
      height: shape.height,
      center: shape.center
    })
    for (let i = 0; i < nData; i += 1) yFit[i] += comp[i]
  }

  if (baselineEnabled && baselineLayout && baseArr) {
    for (let i = 0; i < nData; i += 1) yBase[i] = baselineValue(baselineLayout.fn, baseArr, x[i])
    for (let i = 0; i < nData; i += 1) yFit[i] += yBase[i]
  }

  for (let i = 0; i < nData; i += 1) {
    if (x[i] < winLo || x[i] > winHi) residual[i] = Number.NaN
    else residual[i] = y[i] - yFit[i]
  }

  const baselineP: ParamValues = {}
  const baselineErr: ParamValues = {}
  if (baselineLayout && baseArr) {
    for (let j = 0; j < baselineLayout.keys.length; j += 1) {
      const key = baselineLayout.keys[j]
      baselineP[key] = baseArr[j]
      baselineErr[key] = fixedMask[baselineLayout.indices[j]] === 0
        ? fitter.pStdErr[baselineLayout.indices[j]]
        : 0
    }
  } else if (req.baseline) {
    for (const key of Object.keys(req.baseline.p)) {
      baselineP[key] = req.baseline.p[key]
      baselineErr[key] = 0
    }
  }

  const k = freeOrder.length
  const n = m
  const dof = n - k
  const sse = fitter.sse
  const rmse = n > 0 ? Math.sqrt(sse / n) : 0
  const fitStdErr = dof > 0 ? Math.sqrt(sse / dof) : 0
  const r2 = sst > 0 ? 1 - sse / sst : 0
  const r2Adj = dof > 0 && n > 1 ? 1 - (1 - r2) * (n - 1) / dof : 0
  const fValue =
    k > 0 && dof > 0 && sse > 0 ? ((sst - sse) / k) / (sse / dof) : 0

  const result: FitResult = {
    jobId,
    ok: true,
    stats: {
      sse,
      rmse,
      fitStdErr,
      r2,
      r2Adj,
      fValue,
      dof,
      n,
      k,
      fnEval: fitter.fnEval,
      iterations: fitter.iterations,
      timeMs: fitter.timeMs,
      converged: fitter.converged,
      stopped: fitter.stopped,
      violFinal: fitter.violFinal
    },
    peaks: peakResults,
    baselineP,
    baselineErr,
    yFit,
    yBase,
    yComps,
    residual
  }
  return result
}

// ---------------------------------------------------------------------------
// Renderer-facing Promise wrapper (web-preview / in-page engine fallback)
// ---------------------------------------------------------------------------

let activeControl: FitterControl | null = null

/**
 * Promise-based fit entry point used by the renderer's in-page engine.
 *
 * The underlying LM loop is synchronous (the Electron path runs it in a
 * worker with shared-memory stop flags). This wrapper therefore executes the
 * fit immediately and resolves with its outcome; `stopFit` / `abortFit` are
 * still exported so the same UI code compiles for both engines, but they can
 * only interrupt a fit started from another thread (the Electron preload
 * path). See the integration notes in the project summary.
 */
export function runFit(
  req: FitRequest,
  onIter?: (event: FitIterEvent) => void
): Promise<FitOutcome> {
  const control = makeControl()
  activeControl = control
  try {
    return Promise.resolve(runFitSync(req, { onIter, control }))
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return Promise.resolve({ jobId: req.jobId, ok: false, error: message })
  } finally {
    activeControl = null
  }
}

/** 停止并保留 semantics for the in-page engine (cooperative flag). */
export function stopFit(): void {
  if (activeControl) activeControl.stop = true
}

/** 中止并回滚 semantics for the in-page engine (cooperative flag). */
export function abortFit(): void {
  if (activeControl) activeControl.abort = true
}
