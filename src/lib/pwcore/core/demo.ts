/**
 * Deterministic synthetic spectra for the demo buttons and for smoke tests.
 *
 * A seeded 32-bit LCG (Numerical Recipes constants) plus Box-Muller
 * transforms supply repeatable Gaussian noise; identical seeds always
 * produce byte-identical arrays. Three profiles are provided:
 *  - 'chrom' : 4 EMG peaks + linear baseline + 1% noise (chromatography)
 *  - 'raman' : 5 mixed Gauss/Lorentz/Voigt peaks + constant baseline + noise
 *  - 'xps'   : 3 Voigt peaks + logistic (sigmoid) background + noise
 */
import type { DemoData, DemoKind, ParamValues } from '../shared/types'
import type { PeakFnId } from '../shared/registry'
import {
  peakValue,
  packPeakParams,
  packBaselineParams,
  baselineValue
} from './models'

class Lcg {
  private state: number
  private spare: number | null = null

  constructor(seed: number) {
    this.state = seed >>> 0
  }

  /** Uniform in [0,1). */
  next(): number {
    this.state = (Math.imul(1664525, this.state) + 1013904223) >>> 0
    return this.state / 4294967296
  }

  /** Standard normal (Box-Muller, cached spare). */
  gaussian(): number {
    if (this.spare !== null) {
      const v = this.spare
      this.spare = null
      return v
    }
    let u = this.next()
    while (u <= 1e-12) u = this.next()
    const v = this.next()
    const r = Math.sqrt(-2 * Math.log(u))
    this.spare = r * Math.sin(2 * Math.PI * v)
    return r * Math.cos(2 * Math.PI * v)
  }
}

interface DemoPeak {
  fn: PeakFnId
  p: ParamValues
}

function makeX(x0: number, x1: number, n: number): Float64Array {
  const x = new Float64Array(n)
  const dx = (x1 - x0) / (n - 1)
  for (let i = 0; i < n; i += 1) x[i] = x0 + i * dx
  return x
}

function sumPeaks(x: Float64Array, peaks: DemoPeak[]): Float64Array {
  const y = new Float64Array(x.length)
  for (const pk of peaks) {
    const p = packPeakParams(pk.fn, pk.p)
    for (let i = 0; i < x.length; i += 1) y[i] += peakValue(pk.fn, p, x[i])
  }
  return y
}

function maxAbs(y: Float64Array): number {
  let m = 0
  for (let i = 0; i < y.length; i += 1) m = Math.max(m, Math.abs(y[i]))
  return m
}

function addNoise(y: Float64Array, sigma: number, rng: Lcg): void {
  for (let i = 0; i < y.length; i += 1) y[i] += sigma * rng.gaussian()
}

function baselineCurve(
  x: Float64Array,
  fn: 'bglin' | 'bgconst',
  p: ParamValues
): Float64Array {
  const y = new Float64Array(x.length)
  const arr = packBaselineParams(fn, p)
  for (let i = 0; i < x.length; i += 1) y[i] = baselineValue(fn, arr, x[i])
  return y
}

/** Renderer-compatible alias for {@link demoData}. */
export function makeDemoData(kind: DemoKind): DemoData {
  return demoData(kind)
}

/** Generate a deterministic demo data set. */
export function demoData(kind: DemoKind): DemoData {
  if (kind === 'chrom') {
    const x = makeX(0, 60, 800)
    const truth: DemoPeak[] = [
      { fn: 'emg', p: { a0: 120, a1: 8.5, a2: 0.8, a3: 1.6 } },
      { fn: 'emg', p: { a0: 260, a1: 15.2, a2: 1.1, a3: 2.2 } },
      { fn: 'emg', p: { a0: 180, a1: 28.0, a2: 1.3, a3: 1.0 } },
      { fn: 'emg', p: { a0: 90, a1: 41.5, a2: 0.7, a3: 3.0 } }
    ]
    const y = sumPeaks(x, truth)
    const base = baselineCurve(x, 'bglin', { b0: 2, b1: 0.02 })
    for (let i = 0; i < y.length; i += 1) y[i] += base[i]
    addNoise(y, 0.01 * maxAbs(y), new Lcg(1234567))
    return {
      title: 'Demo: Chromatogram (4 EMG + linear baseline)',
      x,
      y,
      truth: truth.map((t) => ({ fn: t.fn, p: { ...t.p } }))
    }
  }

  if (kind === 'raman') {
    const x = makeX(200, 2200, 1200)
    const truth: DemoPeak[] = [
      { fn: 'gauss', p: { a0: 120, a1: 420, a2: 18 } },
      { fn: 'lorentz', p: { a0: 90, a1: 780, a2: 24 } },
      { fn: 'voigt', p: { a0: 160, a1: 1120, a2: 14, a3: 18 } },
      { fn: 'gauss', p: { a0: 200, a1: 1500, a2: 30 } },
      { fn: 'lorentz', p: { a0: 70, a1: 1900, a2: 40 } }
    ]
    const y = sumPeaks(x, truth)
    const base = baselineCurve(x, 'bgconst', { b0: 15 })
    for (let i = 0; i < y.length; i += 1) y[i] += base[i]
    addNoise(y, 0.005 * maxAbs(y), new Lcg(7654321))
    return {
      title: 'Demo: Raman spectrum (5 mixed peaks)',
      x,
      y,
      truth: truth.map((t) => ({ fn: t.fn, p: { ...t.p } }))
    }
  }

  // XPS
  if (kind === 'xps') {
    const x = makeX(280, 295, 700)
    const truth: DemoPeak[] = [
      { fn: 'voigt', p: { a0: 5000, a1: 284.5, a2: 0.35, a3: 0.3 } },
      { fn: 'voigt', p: { a0: 3500, a1: 286.8, a2: 0.4, a3: 0.35 } },
      { fn: 'voigt', p: { a0: 2500, a1: 289.2, a2: 0.45, a3: 0.3 } }
    ]
    const y = sumPeaks(x, truth)
    // Logistic (sigmoid) inelastic background, as commonly used in XPS.
    for (let i = 0; i < x.length; i += 1) {
      y[i] += 800 / (1 + Math.exp(-(x[i] - 287) / 0.8)) + 100
    }
    addNoise(y, 0.008 * maxAbs(y), new Lcg(24681357))
    return {
      title: 'Demo: XPS spectrum (3 Voigt + sigmoid background)',
      x,
      y,
      truth: truth.map((t) => ({ fn: t.fn, p: { ...t.p } }))
    }
  }

  // X-FAIS (2026-10-20): WAXS of isotactic polypropylene, Cu Kα 2θ 10–30°.
  // α-form (110/040/130/111·041), β-form (300) and a broad amorphous halo —
  // the classic peak-deconvolution substrate for crystallinity AND the
  // Turner-Jones Kβ. 2θ positions follow standard iPP WAXS literature.
  // X-FAIS 新增：等规聚丙烯 WAXS（Cu Kα，2θ 10–30°）：α 相四个主峰 + β(300)
  // + 宽非晶晕——结晶度与 Turner-Jones Kβ 的经典峰分解示例。
  if (kind === 'waxsPP') {
    const x = makeX(10, 30, 1000)
    const truth: DemoPeak[] = [
      { fn: 'pearson7', p: { a0: 610, a1: 14.08, a2: 0.42, a3: 1.6 } },  // α(110)
      { fn: 'pearson7', p: { a0: 880, a1: 16.95, a2: 0.45, a3: 1.6 } },  // α(040)
      { fn: 'pearson7', p: { a0: 700, a1: 18.60, a2: 0.44, a3: 1.6 } },  // α(130)
      { fn: 'pearson7', p: { a0: 330, a1: 16.10, a2: 0.50, a3: 1.6 } },  // β(300)
      { fn: 'pearson7', p: { a0: 300, a1: 21.20, a2: 0.50, a3: 1.6 } },  // α(111)
      { fn: 'pearson7', p: { a0: 210, a1: 21.90, a2: 0.52, a3: 1.6 } },  // α(041/131)
      // Broad amorphous halo under the crystalline cluster (~2/3 amorphous
      // weight here so the demo crystallinity lands near 55 %).
      { fn: 'gauss', p: { a0: 210, a1: 16.6, a2: 3.6 } },
      { fn: 'gauss', p: { a0: 60, a1: 21.5, a2: 3.0 } }
    ]
    const y = sumPeaks(x, truth)
    const base = baselineCurve(x, 'bglin', { b0: 40, b1: -0.9 })
    for (let i = 0; i < y.length; i += 1) y[i] += base[i]
    addNoise(y, 0.008 * maxAbs(y), new Lcg(20261020))
    return {
      title: 'Demo: iPP WAXS (α + β(300) + amorphous halo, Cu Kα)',
      x,
      y,
      truth: truth.map((t) => ({ fn: t.fn, p: { ...t.p } }))
    }
  }

  // X-FAIS (2026-10-20): azimuthal I(χ) orientation profile, χ ∈ [−90°, 270°].
  // A sharp EQUATORIAL arc pair at ±90° (aligned-fibre equatorial reflection,
  // H ≈ 22°) over weak isotropic scatter — Hermans f should come out close to
  // 1 with the default meridian reference + normal→chain conversion, and the
  // FWHM index f = (180 − H)/180 likewise high.
  // X-FAIS 新增：取向 I(χ) 方位谱（χ −90°…270°）：赤道弧对（±90°，H≈22°）
  // 叠加弱各向同性散射——默认子午线参考 + 法向→链轴换算下 Hermans f 应接
  // 近 1，FWHM 指数同样很高。
  const x = makeX(-90, 270, 1441)
  const truth: DemoPeak[] = [
    { fn: 'pearson7', p: { a0: 500, a1: 90, a2: 22, a3: 1.8 } },
    { fn: 'pearson7', p: { a0: 500, a1: 270, a2: 22, a3: 1.8 } },
    { fn: 'lorentz', p: { a0: 45, a1: 0, a2: 55 } }
  ]
  const y = sumPeaks(x, truth)
  const base = baselineCurve(x, 'bgconst', { b0: 20 })
  for (let i = 0; i < y.length; i += 1) y[i] += base[i]
  addNoise(y, 0.006 * maxAbs(y), new Lcg(13579246))
  return {
    title: 'Demo: Azimuthal I(χ) orientation profile (equatorial arc pair)',
    x,
    y,
    truth: truth.map((t) => ({ fn: t.fn, p: { ...t.p } }))
  }
}
