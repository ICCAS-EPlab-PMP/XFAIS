/**
 * Peak and baseline model evaluators.
 *
 * Every formula below is a direct transcription of the corresponding
 * function in the official the legacy reference application manual, chapter 7
 * (`the reference manual chapter 7 text` and the formula screenshots
 * in `the reference formula screenshots`). The manual function name is quoted
 * in each case; the parameter convention is always
 *   a0 = amplitude or area (as documented per function),
 *   a1 = center,
 *   a2 = width,
 *   a3/a4 = shape/skew parameters.
 *
 * Numerical safety: every evaluator is total. Outside a formula's real
 * domain it returns 0 (the manual explicitly states this for the
 * statistics family: "The function returns 0 for those x where it is
 * undefined"), and no evaluator may emit NaN or Infinity for finite inputs.
 */
import type { BaselineFnId, PeakFnId } from '../shared/registry'
import { PEAK_FN_MAP, BASELINE_FN_MAP } from '../shared/registry'
import {
  erfc,
  erfcx,
  erf,
  faddeevaRe,
  besselI1e,
  incompleteGammaQ
} from './special'

/** Smallest admissible width, replicating the original GAUSS binary (1e-12). */
export const WIDTH_FLOOR = 1e-12

function widthOf(v: number): number {
  const a = Math.abs(v)
  return a < WIDTH_FLOOR ? WIDTH_FLOOR : a
}

function finiteOr0(v: number): number {
  return Number.isFinite(v) ? v : 0
}

function safeExp(v: number): number {
  if (v > 709) return Number.POSITIVE_INFINITY
  if (v < -745) return 0
  return Math.exp(v)
}

/** base^exp, defined as 0 outside the real domain (base <= 0). */
function safePow(base: number, exp: number): number {
  if (!(base > 0)) {
    if (base === 0 && exp > 0) return 0
    return 0
  }
  const v = Math.pow(base, exp)
  return Number.isFinite(v) ? v : 0
}

/**
 * Scalar value of one peak at x. `a` is indexed by parameter position
 * (a[0] = a0, a[1] = a1, ...); missing entries are treated as 0.
 */
export function peakValue(fn: PeakFnId, a: ArrayLike<number>, x: number): number {
  const a0 = a[0] ?? 0
  const a1 = a[1] ?? 0
  const a2 = a[2] ?? 0
  const a3 = a[3] ?? 0
  const a4 = a[4] ?? 0

  switch (fn) {
    // ------------------------------------------------------------------
    // Basic symmetric peaks
    // ------------------------------------------------------------------
    case 'gauss': {
      // GAUSS (amplitude): y = a0 exp(-1/2 ((x-a1)/a2)^2), a2 = sigma.
      const w = widthOf(a2)
      const z = (x - a1) / w
      return a0 * Math.exp(-0.5 * z * z)
    }
    case 'lorentz': {
      // LORENTZ (amplitude): y = a0 / (1 + ((x-a1)/a2)^2), a2 = HWHM.
      const w = widthOf(a2)
      const z = (x - a1) / w
      return a0 / (1 + z * z)
    }
    case 'pearson7': {
      // PEARSON7 (amplitude):
      // y = a0 / [1 + 4 ((x-a1)/a2)^2 (2^(1/a3) - 1)]^a3, a2 = FWHM.
      const w = widthOf(a2)
      const m = Math.max(a3, 1e-6)
      const z = (x - a1) / w
      const k = Math.expm1(Math.LN2 / m)
      return a0 * Math.exp(-m * Math.log1p(4 * z * z * k))
    }
    case 'voigt': {
      // VOIGT (Amplitude, Gaussian/Lorentzian Widths) — manual p.217:
      // normalized convolution of Gauss(sigma=a2) and Lorentz(HWHM=a3).
      // Implemented as Re[w(z)] / Re[w(z0)], z = ((x-a1) + i a3)/(sqrt2 a2).
      const sig = widthOf(a2)
      const gam = widthOf(a3)
      const s2 = Math.SQRT2 * sig
      const zi = gam / s2
      const nr = faddeevaRe((x - a1) / s2, zi)
      const dr = faddeevaRe(0, zi)
      if (!(dr > 0) || !Number.isFinite(dr)) return 0
      const v = (a0 * nr) / dr
      return Number.isFinite(v) ? v : 0
    }
    case 'glorsum': {
      // GLORSUM (Gaussian-Lorentzian Sum, Amplitude) — manual p.220:
      // a2 = common FWHM, a3 = Gaussian fraction in [0,1].
      // Note: registry label for a3 says "Lorentz HWHM", but the manual
      // formula uses a3 as the 0..1 mixing fraction; the manual wins.
      const w = widthOf(a2)
      const z = (x - a1) / w
      const g = Math.exp(-4 * Math.LN2 * z * z)
      const l = 1 / (1 + 4 * z * z)
      const aG = (a3 * Math.sqrt(Math.LN2)) / (w * Math.sqrt(Math.PI))
      const aL = (1 - a3) / (Math.PI * w)
      const den = aG + aL
      if (!Number.isFinite(den) || Math.abs(den) < 1e-300) return 0
      const v = (a0 * (aG * g + aL * l)) / den
      return Number.isFinite(v) ? v : 0
    }

    // ------------------------------------------------------------------
    // Chromatography family
    // ------------------------------------------------------------------
    case 'emg': {
      // EMG (Exponentially Modified Gaussian), bi-directional form — p.237.
      // Area form with a2 = sigma and a3 = tau (>0 in this application):
      // y = a0/(2 tau) exp(sigma^2/(2 tau^2) - (x-a1)/tau)
      //     * erfc(sigma/(sqrt2 tau) - (x-a1)/(sqrt2 sigma))
      const sig = widthOf(a2)
      const tau = widthOf(a3)
      const u = (x - a1) / tau
      const r = sig / tau
      const z = r / Math.SQRT2 - u / (Math.SQRT2 * r)
      const pref = a0 / (2 * tau)
      let v: number
      if (z >= 0) {
        // erfc(z) = erfcx(z) exp(-z^2); combined exponent is -u^2/(2r^2).
        v = pref * Math.exp(-(u * u) / (2 * r * r)) * erfcx(z)
      } else {
        v = pref * Math.exp(r * r / 2 - u) * erfc(z)
      }
      return Number.isFinite(v) ? v : 0
    }
    case 'gmg': {
      // GMG (Gamma Modified Gaussian, Area) — manual p.240:
      // y = a0 exp(-(x-a1)^2/(2(a3^2+a2^2)))
      //     * (1 + erf(a3 (x-a1)/(sqrt2 a2 sqrt(a3^2+a2^2))))
      //     / (sqrt(2 pi) sqrt(a3^2+a2^2))
      const sig = widthOf(a2)
      const gam = a3
      const s2 = sig * sig + gam * gam
      const s = Math.sqrt(s2)
      const d = x - a1
      const arg = (gam * d) / (Math.SQRT2 * sig * s)
      const v = (a0 * Math.exp(-0.5 * (d * d) / s2) * (1 + erf(arg))) /
        (Math.sqrt(2 * Math.PI) * s)
      return Number.isFinite(v) ? v : 0
    }
    case 'hvl': {
      // HVL (Haarhoff-Van der Linde, Area) — manual p.230:
      // y = [a0 a2 / (a1 a3 sqrt(2pi)) exp(-1/2 ((x-a1)/a2)^2)]
      //     / [ 1/exp(a1 a3/a2^2 - 1) + 1/2 (1 + erf((x-a1)/(sqrt2 a2))) ]
      const ctr = a1
      const w = widthOf(a2)
      const dist = a3
      const prod = ctr * dist
      if (Math.abs(prod) < 1e-300) return 0
      const theta = prod / (w * w) - 1
      let invTerm: number
      if (theta > 709) invTerm = 0
      else if (theta < -745) invTerm = Number.POSITIVE_INFINITY
      else invTerm = 1 / Math.exp(theta)
      const erfTerm = 0.5 * (1 + erf((x - ctr) / (Math.SQRT2 * w)))
      const den = invTerm + erfTerm
      if (!(den > 0) || !Number.isFinite(den)) return 0
      const z = (x - ctr) / w
      const num = ((a0 * w) / (prod * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * z * z)
      const v = num / den
      return Number.isFinite(v) ? v : 0
    }
    case 'giddings': {
      // GIDDING (Area) — manual p.232:
      // y = a0/a2 sqrt(a1/x) I1(2 sqrt(a1 x)/a2) exp((-x-a1)/a2)
      // a1 = center (>0), a2 = width (>0), domain x>0.
      const ctr = a1
      const w = widthOf(a2)
      if (!(x > 0) || !(ctr > 0)) return 0
      const u = (2 * Math.sqrt(ctr * x)) / w
      const expo = u - (x + ctr) / w // <= 0 by AM-GM
      const v = (a0 / w) * Math.sqrt(ctr / x) * besselI1e(u) * Math.exp(expo)
      return Number.isFinite(v) ? v : 0
    }
    case 'nlc': {
      // NLC (Non-Linear Chromatography, Area) — manual p.234.
      // y = a0/a3 * (1-exp(-a3/a2)) * [sqrt(a1/x) I1(2 sqrt(a1 x)/a2)
      //     exp((-x-a1)/a2)] / [1 - T(a1/a2, x/a2)(1-exp(-a3/a2))]
      // T is Moffitt's function
      //   T(u,v) = exp(-v) int_0^u exp(-t) I0(2 sqrt(vt)) dt
      // computed here as a Poisson(v) mixture of regularized incomplete
      // gammas: 1 - T = exp(-v) sum_n v^n/n! Q(n+1,u).
      // As a3 -> 0 this reduces exactly to the Giddings equation.
      const ctr = a1
      const w = widthOf(a2)
      const dist = a3
      if (!(x > 0) || !(ctr > 0)) return 0
      if (Math.abs(dist) < 1e-12) return 0
      const u0 = ctr / w
      const vv = x / w
      const u = (2 * Math.sqrt(ctr * x)) / w
      const expo = u - (x + ctr) / w
      const num = Math.sqrt(ctr / x) * besselI1e(u) * Math.exp(expo)
      // 1 - exp(-a3/a2), evaluated accurately for small a3
      const oneMinusExp = -Math.expm1(-dist / w)
      const oneMinusT = nlcOneMinusT(u0, vv)
      if (!(oneMinusT >= 0) || !Number.isFinite(oneMinusT)) return 0
      const tValue = 1 - oneMinusT
      const den = 1 - tValue * oneMinusExp
      if (!(den > 0) || !Number.isFinite(den)) return 0
      const v = ((a0 * oneMinusExp) / (dist * den)) * num
      return Number.isFinite(v) ? v : 0
    }

    // ------------------------------------------------------------------
    // Statistics family
    // ------------------------------------------------------------------
    case 'lognorm': {
      // LOGNORM (Amplitude) — manual p.246:
      // y = a0 exp(-1/2 (ln(x/a1)/a2)^2), a1 = center (!= 0).
      const ctr = a1
      const w = widthOf(a2)
      if (ctr === 0) return 0
      const r = x / ctr
      if (!(r > 0)) return 0
      const q = Math.log(r) / w
      return a0 * Math.exp(-0.5 * q * q)
    }
    case 'lognorm4': {
      // LOGNORM4 (Amplitude) — manual p.247:
      // y = a0 exp(-ln2 [ln(1 + (x-a1)(a3^2-1)/(a2 a3))]^2 / ln(a3)^2)
      // a2 = FWHM (exact: half-widths are a2 a3/(a3+1) and a2/(a3+1)).
      const ctr = a1
      const w = widthOf(a2)
      const asym = a3
      if (Math.abs(asym - 1) < 1e-8) {
        const z = (x - ctr) / w
        return a0 * Math.exp(-4 * Math.LN2 * z * z)
      }
      const denom = Math.log(asym) * Math.log(asym)
      if (!(denom > 0)) return 0
      const base = 1 + ((x - ctr) * (asym * asym - 1)) / (w * asym)
      if (!(base > 0)) return 0
      const q = Math.log(base)
      return a0 * Math.exp((-Math.LN2 * q * q) / denom)
    }
    case 'extrval': {
      // EXTRVAL (Amplitude) — manual p.248:
      // y = a0 exp(-exp(-(x-a1)/a2) - (x-a1)/a2 + 1)
      const w = widthOf(a2)
      const z = (x - a1) / w
      const e = safeExp(-z)
      if (!Number.isFinite(e)) return 0
      return finiteOr0(a0 * Math.exp(-e - z + 1))
    }
    case 'extrval4': {
      // EXTRVAL4 (Amplitude) — manual p.249 (Tailed/Fronted):
      // y = a0 exp([-x+a1+a2-a2 a3 exp(-(x+a2 ln a3-a1)/a2)]/(a3 a2))
      //   = a0 exp((1 - z - exp(-z))/a3), z=(x-a1)/a2.
      const w = widthOf(a2)
      const k = a3
      if (Math.abs(k) < 1e-12) return 0
      const z = (x - a1) / w
      const e = safeExp(-z)
      if (!Number.isFinite(e)) return 0
      return finiteOr0(a0 * Math.exp((1 - z - e) / k))
    }
    case 'logistic': {
      // LOGISTIC (Amplitude) — manual p.250:
      // y = 4 a0 exp(-(x-a1)/a2) / [1 + exp(-(x-a1)/a2)]^2
      const w = widthOf(a2)
      const z = (x - a1) / w
      const e = safeExp(-z)
      if (!Number.isFinite(e)) return 0
      const d = 1 + e
      const v = (4 * a0 * e) / (d * d)
      return Number.isFinite(v) ? v : 0
    }
    case 'gamma': {
      // GAMMA (Amplitude) — manual p.251:
      // y = a0 exp(-(x-a1)/a2) [((x-a1)/a2 + a3 - 1)/(a3 - 1)]^(a3-1)
      // a3 = shape (>1.01 in the manual). The |a3-1| -> 0 limit is the
      // pure exponential, handled explicitly.
      const w = widthOf(a2)
      const k = a3
      const u = (x - a1) / w
      if (Math.abs(k - 1) < 1e-6) return a0 * Math.exp(-u)
      const base = (u + k - 1) / (k - 1)
      if (!(base > 0)) return 0
      // log form avoids overflow/underflow for large shape values
      const exponent = -u + (k - 1) * Math.log(base)
      const v = a0 * Math.exp(exponent)
      return Number.isFinite(v) ? v : 0
    }
    case 'weibull': {
      // WEIBULL (Amplitude) — manual p.252:
      // c = ((a3-1)/a3)^(1/a3), u = (x-a1)/a2 + c
      // y = a0 c^(1-a3) u^(a3-1) exp(-u^a3 + (a3-1)/a3)
      const w = widthOf(a2)
      const k = a3
      if (!(k > 1)) return 0
      const base = (k - 1) / k
      const c = Math.pow(base, 1 / k)
      const u = (x - a1) / w + c
      if (!(u > 0)) return 0
      // c^(1-k) u^(k-1) = (u/c)^(k-1); compute the whole product in log space.
      const exponent = (k - 1) * Math.log(u / c) - Math.pow(u, k) + (k - 1) / k
      const v = a0 * Math.exp(exponent)
      return Number.isFinite(v) ? v : 0
    }
    case 'beta': {
      // BETA (Amplitude) — manual p.253:
      // t = (x - a1 + a2 (a3-1)/(a3+a4-2)) / a2
      // y = a0 t^(a3-1) (1-t)^(a4-1)
      //        / [ ((a3-1)/(a3+a4-2))^(a3-1)
      //            ((a4-1)/(a3+a4-2))^(a4-1) ]
      const w = widthOf(a2)
      const aa = a3
      const bb = a4
      const ab = aa + bb - 2
      if (!(aa > 0) || !(bb > 0) || Math.abs(ab) < 1e-12) return 0
      const t0 = (aa - 1) / ab
      const t1 = (bb - 1) / ab
      if (!(t0 > 0) || !(t1 > 0)) return 0
      const t = (x - a1 + w * t0) / w
      if (!(t > 0) || !(t < 1)) return 0
      const exponent =
        (aa - 1) * Math.log(t) + (bb - 1) * Math.log(1 - t) -
        (aa - 1) * Math.log(t0) - (bb - 1) * Math.log(t1)
      const v = a0 * Math.exp(exponent)
      return Number.isFinite(v) ? v : 0
    }
    case 'invgamma': {
      // IGAMMA (Inverse Gamma, Amplitude) — manual p.258:
      // A = (a3+1)(x-a1) + a2
      // y = a0 a2 exp((x-a1)(a3+1)^2/A) (A/a2)^(-a3) / A
      const w = widthOf(a2)
      const k = a3
      const A = (k + 1) * (x - a1) + w
      if (Math.abs(A) < 1e-300) return 0
      const ratio = A / w
      const isInt = Math.abs(k - Math.round(k)) < 1e-9
      if (ratio <= 0 && !isInt) return 0
      const exponent = ((x - a1) * (k + 1) * (k + 1)) / A
      // a0*a2*exp(exponent)*ratio^-k / A, combined in log space.
      if (ratio > 0) {
        const logAbs = Math.log(Math.abs(a0)) + Math.log(w) - Math.log(Math.abs(A)) +
          exponent - k * Math.log(ratio)
        const v = Math.sign(a0 * A) * Math.exp(logAbs)
        return Number.isFinite(v) ? v : 0
      }
      // Integer k with a negative ratio: keep the signed power.
      const e = safeExp(exponent)
      const pw = Math.pow(ratio, -k)
      if (!Number.isFinite(e) || !Number.isFinite(pw)) return 0
      const v = (a0 * w * e * pw) / A
      return Number.isFinite(v) ? v : 0
    }
    case 'chisq': {
      // CHISQ (Chi-Squared, Amplitude) — manual p.260:
      // z = (x-a1)/a2 + (a3-2)
      // y = a0 z^(a3/2-1) exp(-z/2)
      //        / [ (a3-2)^(a3/2-1) exp(-(a3-2)/2) ]
      // a3 > 2.01 per the manual.
      const w = widthOf(a2)
      const k = a3
      if (!(k >= 2)) return 0
      if (Math.abs(k - 2) < 1e-9) {
        // Limit k -> 2: y = a0 exp(-(x-a1)/(2 a2)) for x >= a1 (0 otherwise).
        const zz = (x - a1) / w
        return zz >= 0 ? a0 * Math.exp(-zz / 2) : 0
      }
      const z = (x - a1) / w + (k - 2)
      if (!(z > 0)) return 0
      // log form is stable for the full manual range 2.01 < a3 < 335.84
      const logNum = (k / 2 - 1) * Math.log(z) - z / 2
      const logDen = (k / 2 - 1) * Math.log(k - 2) - (k - 2) / 2
      const v = a0 * Math.exp(logNum - logDen)
      return Number.isFinite(v) ? v : 0
    }
    case 'laplace': {
      // LAPLACE (Amplitude) — manual p.255:
      // y = a0 exp(-sqrt(2) |x-a1| / a2)
      const w = widthOf(a2)
      return a0 * Math.exp((-Math.SQRT2 * Math.abs(x - a1)) / w)
    }
    case 'error': {
      // ERROR (generalized error distribution, Amplitude) — manual p.256:
      // y = a0 exp(-1/2 |x-a1|^(2/a3) / a2)
      // (a3 = shape > 0; this is the manual formula, NOT an erf-based step.)
      const w = widthOf(a2)
      const k = Math.max(a3, 1e-6)
      const v = a0 * Math.exp(-0.5 * Math.pow(Math.abs(x - a1) / w, 2 / k))
      return Number.isFinite(v) ? v : 0
    }
    case 'student': {
      // STUDENT (Student t, Amplitude) — manual p.257:
      // y = a0 / [1 + (x-a1)^2/(a2^2 a3)]^((a3+1)/2)
      const w = widthOf(a2)
      const nu = Math.max(a3, 1e-6)
      const base = 1 + ((x - a1) * (x - a1)) / (w * w * nu)
      const v = a0 * Math.pow(base, -(nu + 1) / 2)
      return Number.isFinite(v) ? v : 0
    }

    // ------------------------------------------------------------------
    // Shape family
    // ------------------------------------------------------------------
    case 'erfcpk': {
      // ERFCPK (Amplitude) — manual p.264:
      // y = a0 erfc(((x-a1)/a2)^2)
      const w = widthOf(a2)
      const z = (x - a1) / w
      return a0 * erfc(z * z)
    }
    default:
      return 0
  }
}

/**
 * 1 - T(u,v) for Moffitt's T function, evaluated as
 *   exp(-v) sum_{n>=0} v^n/n! Q(n+1,u).
 * Q is the regularized upper incomplete gamma.
 */
function nlcOneMinusT(u: number, v: number): number {
  if (!(u > 0) || !(v > 0)) return 1
  let weight = Math.exp(-v)
  let sum = weight * incompleteGammaQ(1, u)
  const limit = Math.min(4000, Math.ceil(v + 12 * Math.sqrt(v) + 40))
  for (let n = 1; n <= limit; n += 1) {
    weight *= v / n
    sum += weight * incompleteGammaQ(n + 1, u)
    if (n > v && weight < 1e-17) break
  }
  return Number.isFinite(sum) ? sum : 0
}

function isPositional(p: ArrayLike<number> | Record<string, number>): p is ArrayLike<number> {
  return Array.isArray(p) || ArrayBuffer.isView(p)
}

// Reused only inside evalPeak/evalBaseline for the ParamValues form, so a
// per-point call (renderer width anchors) does not allocate.
const peakScratch = new Float64Array(8)
const baselineScratch = new Float64Array(4)

function fillPeakScratch(fn: PeakFnId, p: Record<string, number>): Float64Array {
  const meta = PEAK_FN_MAP.get(fn)
  if (!meta) return peakScratch.subarray(0, 0)
  const n = Math.min(meta.params.length, peakScratch.length)
  for (let i = 0; i < n; i += 1) peakScratch[i] = p[meta.params[i].key] ?? 0
  return n === peakScratch.length ? peakScratch : peakScratch.subarray(0, n)
}

function fillBaselineScratch(fn: BaselineFnId, p: Record<string, number>): Float64Array {
  const meta = BASELINE_FN_MAP.get(fn)
  if (!meta) return baselineScratch.subarray(0, 0)
  const n = Math.min(meta.params.length, baselineScratch.length)
  for (let i = 0; i < n; i += 1) baselineScratch[i] = p[meta.params[i].key] ?? 0
  return n === baselineScratch.length ? baselineScratch : baselineScratch.subarray(0, n)
}

/**
 * Evaluate one peak over an x array, optionally reusing `out`.
 * `p` may be either a positional array (a0, a1, ...) or a ParamValues object
 * keyed by the registry parameter names; both forms are accepted so the
 * renderer can pass its model objects directly.
 */
export function evalPeak(
  fn: PeakFnId,
  p: ArrayLike<number> | Record<string, number>,
  x: ArrayLike<number>,
  out?: Float64Array
): Float64Array {
  const params = isPositional(p) ? p : fillPeakScratch(fn, p)
  const dst =
    out && out.length === x.length ? out : new Float64Array(x.length)
  for (let i = 0; i < x.length; i += 1) {
    dst[i] = peakValue(fn, params, x[i])
  }
  return dst
}

/** Scalar value of one baseline at x (`b` is indexed by parameter position). */
export function baselineValue(fn: BaselineFnId, b: ArrayLike<number>, x: number): number {
  const b0 = b[0] ?? 0
  const b1 = b[1] ?? 0
  const b2 = b[2] ?? 0
  const b3 = b[3] ?? 0
  switch (fn) {
    case 'none':
      return 0
    case 'bgconst':
      // BGCNST: y = b0
      return b0
    case 'bglin':
      // BGLIN: y = b0 + b1 x
      return b0 + b1 * x
    case 'bgquad':
      // BGQUAD: y = b0 + b1 x + b2 x^2
      return b0 + b1 * x + b2 * x * x
    case 'bgcub':
      // BGCUB: y = b0 + b1 x + b2 x^2 + b3 x^3
      return b0 + b1 * x + b2 * x * x + b3 * x * x * x
    case 'bgexp': {
      // BGEXP: offset b2 + amplitude b0 * exp(-x / decay b1)
      if (Math.abs(b1) < 1e-300) return b2
      const e = safeExp(-x / b1)
      return Number.isFinite(e) ? b2 + b0 * e : b2
    }
    case 'bgpow': {
      // BGPOW: offset b2 + amplitude b0 * x^(exponent b1), x > 0.
      if (!(x > 0)) return b2
      return b2 + b0 * safePow(x, b1)
    }
    case 'bglog':
      // BGLOG: offset b1 + amplitude b0 * ln(x), x > 0.
      return x > 0 ? b1 + b0 * Math.log(x) : b1
    case 'bghyp': {
      // BGHYP: offset b2 + amplitude b0 * scale b1 / (scale b1 + x)
      const den = b1 + x
      if (Math.abs(den) < 1e-300) return b2
      return b2 + (b0 * b1) / den
    }
    case 'bgsine': {
      // SINE (background): b0 sin(2 pi x / period b1 + phase b2)
      if (Math.abs(b1) < 1e-300) return 0
      return b0 * Math.sin((2 * Math.PI * x) / b1 + b2)
    }
    default:
      return 0
  }
}

/** Evaluate one baseline over an x array, optionally reusing `out`. */
export function evalBaseline(
  fn: BaselineFnId,
  p: ArrayLike<number> | Record<string, number>,
  x: ArrayLike<number>,
  out?: Float64Array
): Float64Array {
  const params = isPositional(p) ? p : fillBaselineScratch(fn, p)
  const dst =
    out && out.length === x.length ? out : new Float64Array(x.length)
  for (let i = 0; i < x.length; i += 1) {
    dst[i] = baselineValue(fn, params, x[i])
  }
  return dst
}

/** Pack a ParamValues object into an ordered array using registry metadata. */
export function packPeakParams(fn: PeakFnId, p: Record<string, number>): Float64Array {
  const meta = PEAK_FN_MAP.get(fn)
  const n = meta ? meta.params.length : 0
  const out = new Float64Array(n)
  if (!meta) return out
  for (let i = 0; i < n; i += 1) {
    out[i] = p[meta.params[i].key] ?? 0
  }
  return out
}

/** Pack baseline params into an ordered array using registry metadata. */
export function packBaselineParams(
  fn: BaselineFnId,
  p: Record<string, number>
): Float64Array {
  const meta = BASELINE_FN_MAP.get(fn)
  const n = meta ? meta.params.length : 0
  const out = new Float64Array(n)
  if (!meta) return out
  for (let i = 0; i < n; i += 1) {
    out[i] = p[meta.params[i].key] ?? 0
  }
  return out
}

/**
 * Evaluate a whole model (baseline + enabled peaks) at a single x.
 * Returns { total, components } where components align with `peaks`.
 */
export function modelValueAt(
  x: number,
  peaks: ReadonlyArray<{ fn: PeakFnId; p: ArrayLike<number>; enabled: boolean }>,
  baseline: { fn: BaselineFnId; p: ArrayLike<number>; enabled: boolean }
): { total: number; components: number[] } {
  const components: number[] = []
  let total = baseline.enabled ? baselineValue(baseline.fn, baseline.p, x) : 0
  for (let i = 0; i < peaks.length; i += 1) {
    const pk = peaks[i]
    if (!pk.enabled) continue
    const v = peakValue(pk.fn, pk.p, x)
    components.push(v)
    total += v
  }
  return { total, components }
}
