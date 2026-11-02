/**
 * Derived shape statistics for a fitted peak: numeric FWHM, numeric area,
 * height at the center parameter, and analytic cross-checks for the two
 * textbook shapes (Gaussian and Lorentzian).
 *
 * FWHM: the peak is sampled on a dense grid, the extremum found, and each
 * half-maximum crossing refined by bisection (the "half-height bisection"
 * procedure used by the reference application's peak review). Area: Simpson quadrature under
 * the substitution x = c + s sinh(u), which concentrates nodes near the
 * peak while still covering the extremely wide Lorentzian tails.
 */
import type { PeakFnId } from '../shared/registry'
import { peakValue, WIDTH_FLOOR } from './models'
import { faddeevaRe } from './special'

export interface PeakShape {
  /** Numeric full width at half maximum in x units (0 when undefined). */
  fwhm: number
  /** Numeric area (signed; amplitude parameter a0 follows the sign). */
  area: number
  /** Peak component value at the center parameter a1 (baseline excluded). */
  height: number
  /** Center parameter a1. */
  center: number
}

function scaleFor(fn: PeakFnId, p: ArrayLike<number>): number {
  const a2 = Math.abs(p[2] ?? 0)
  const a3 = Math.abs(p[3] ?? 0)
  let s = Math.max(a2, WIDTH_FLOOR)
  // EMG/GMG/HVL/NLC use a3 as an additional width-like scale.
  if (fn === 'emg' || fn === 'gmg' || fn === 'hvl' || fn === 'nlc') {
    s = Math.max(s, a3)
  }
  return s
}

/** Analytic area for the forms with a closed expression; null otherwise. */
export function analyticArea(fn: PeakFnId, p: ArrayLike<number>): number | null {
  const a0 = p[0] ?? 0
  const a2 = Math.abs(p[2] ?? 0)
  if (fn === 'gauss') return a0 * a2 * Math.sqrt(2 * Math.PI)
  if (fn === 'lorentz') return a0 * Math.PI * a2
  if (fn === 'voigt') {
    // Height-normalized Voigt: area = a0 * sigma sqrt(2 pi) / Re[w(i gamma/(sqrt2 sigma))]
    const sig = Math.max(a2, WIDTH_FLOOR)
    const gam = Math.abs(p[3] ?? 0)
    const zi = gam / (Math.SQRT2 * sig)
    const dr = faddeevaRe(0, zi)
    if (!(dr > 0)) return null
    return (a0 * sig * Math.sqrt(2 * Math.PI)) / dr
  }
  return null
}

/**
 * Numeric FWHM by sampling + half-height bisection.
 * Uses |y| so negative (absorption-dip) peaks report a positive width.
 */
export function numericFwhm(fn: PeakFnId, p: ArrayLike<number>): number {
  const c = p[1] ?? 0
  const s = scaleFor(fn, p)
  if (!Number.isFinite(c) || !Number.isFinite(s)) return 0

  // Search window: log space for LOGNORM, linear elsewhere.
  let lo: number
  let hi: number
  if (fn === 'lognorm' && c !== 0) {
    // The lognormal is naturally asymmetric in x; sample in log space.
    const a = c * Math.exp(-10 * s)
    const b = c * Math.exp(10 * s)
    lo = Math.min(a, b)
    hi = Math.max(a, b)
  } else {
    lo = c - 400 * s
    hi = c + 400 * s
  }
  if (!(hi > lo)) return 0

  const n = 2049
  const dx = (hi - lo) / (n - 1)
  let bestI = 0
  let bestY = -1
  for (let i = 0; i < n; i += 1) {
    const x = lo + i * dx
    const y = Math.abs(peakValue(fn, p, x))
    if (y > bestY) {
      bestY = y
      bestI = i
    }
  }
  if (!(bestY > 0)) return 0
  // Parabolic refinement of the extremum between the three best samples.
  if (bestI > 0 && bestI < n - 1) {
    const yl = Math.abs(peakValue(fn, p, lo + (bestI - 1) * dx))
    const yr = Math.abs(peakValue(fn, p, lo + (bestI + 1) * dx))
    const den = yl - 2 * bestY + yr
    if (den < 0) {
      const delta = (0.5 * (yl - yr)) / den
      if (Math.abs(delta) <= 1) {
        bestY = bestY - 0.25 * (yl - yr) * delta
      }
    }
  }
  const half = bestY * 0.5

  const cross = (from: number, to: number, step: number): number => {
    let a = from
    let ya = Math.abs(peakValue(fn, p, lo + a * dx)) - half
    for (let i = a + step; step > 0 ? i <= to : i >= to; i += step) {
      const yb = Math.abs(peakValue(fn, p, lo + i * dx)) - half
      if (ya >= 0 && yb < 0) {
        // Bisect on [a, i]
        let left = a
        let right = i
        for (let k = 0; k < 80; k += 1) {
          const mid = 0.5 * (left + right)
          const ym = Math.abs(peakValue(fn, p, lo + mid * dx)) - half
          if (ym >= 0) left = mid
          else right = mid
        }
        return lo + 0.5 * (left + right) * dx
      }
      a = i
      ya = yb
    }
    return step > 0 ? hi : lo
  }

  const xLeft = cross(bestI, 0, -1)
  const xRight = cross(bestI, n - 1, 1)
  return Math.max(0, xRight - xLeft)
}

/**
 * Numeric area by Simpson quadrature over x = c + s sinh(u),
 * u in [-8, 8] (x reaches ~±1490 s). The Jacobian s cosh(u) cancels the
 * 1/x^2 Lorentzian tail decay, so heavy-tailed peaks integrate accurately.
 */
export function numericArea(fn: PeakFnId, p: ArrayLike<number>): number {
  const c = p[1] ?? 0
  const fwhm = numericFwhm(fn, p)
  const s = Math.max(fwhm / 2, scaleFor(fn, p), WIDTH_FLOOR)
  if (!Number.isFinite(c) || !Number.isFinite(s)) return 0
  const U = 8
  const N = 4096 // even number of intervals
  const h = (2 * U) / N
  let sum = 0
  for (let i = 0; i <= N; i += 1) {
    const u = -U + i * h
    const x = c + s * Math.sinh(u)
    const jac = s * Math.cosh(u)
    const y = peakValue(fn, p, x) * jac
    const w = i === 0 || i === N ? 1 : i % 2 === 1 ? 4 : 2
    sum += w * y
  }
  return (sum * h) / 3
}

/** All derived per-peak statistics in one pass. */
export function peakShape(fn: PeakFnId, p: ArrayLike<number>): PeakShape {
  const center = p[1] ?? 0
  return {
    fwhm: numericFwhm(fn, p),
    area: numericArea(fn, p),
    height: peakValue(fn, p, center),
    center
  }
}
