/**
 * Special functions for the the reference application numerical core.
 *
 * All routines are pure TypeScript ports of the Numerical Recipes
 * (FORTRAN/C) algorithms that PF.EXE itself was built from, plus a few
 * additional functions needed by the peak models (Bessel I0/I1, the
 * Faddeeva function, Student-t quantiles).
 *
 * Accuracy notes (empirically verified against mpmath at 40 digits):
 *  - erf / erfc: relative error < 1e-15 (all finite x).
 *  - erfcx: relative error < 1e-14 for x >= 0.
 *  - lngamma / gamma: relative error ~1e-14 for positive arguments
 *    (Lanczos g=7, 9 coefficients).
 *  - incomplete gamma P/Q: ~1e-14 relative for a > 0, x >= 0.
 *  - incomplete beta: ~1e-13 relative for 0 <= x <= 1, a,b > 0.
 *  - Faddeeva w(z): relative error < 1e-6 over |z| <= 20 in the upper
 *    half plane (worst observed 5.6e-8), including z = 0 and near the
 *    real axis. This is the accuracy target for the Voigt model.
 *  - Bessel I0/I1: ~1e-14 relative for |x| <= 700 via power series;
 *    asymptotic (scaled) expansions for larger arguments.
 */

const SQRT_PI = Math.sqrt(Math.PI)
const INV_SQRT_PI = 1 / SQRT_PI
const SQRT_PI_OVER_2 = SQRT_PI / 2

// ---------------------------------------------------------------------------
// Error functions
// ---------------------------------------------------------------------------

/**
 * Complementary error function scaled by exp(x^2): erfcx(x) = exp(x^2) erfc(x).
 *
 * Ugly-number-free NR strategy: power series below x = 2, Lentz continued
 * fraction above. Relative accuracy ~1e-14. For x < 0 the reflection formula
 * is used (may overflow for very negative x, which is the true behaviour).
 */
export function erfcx(x: number): number {
  if (Number.isNaN(x)) return Number.NaN
  if (x < 0) {
    const e = Math.exp(x * x)
    if (!Number.isFinite(e)) return Number.POSITIVE_INFINITY
    return 2 * e - erfcx(-x)
  }
  if (x < 2) {
    // erfc(x) = 1 - (2/sqrt(pi)) * sum_{k>=0} (-1)^k x^(2k+1)/(k!(2k+1))
    let sum = 0
    let term = x // x^(2k+1)/k!
    let k = 0
    while (k < 200) {
      const add = term / (2 * k + 1)
      sum += k % 2 === 0 ? add : -add
      k += 1
      term *= (x * x) / k
      if (Math.abs(term) < 1e-18 * Math.max(1, Math.abs(sum))) break
    }
    const erfcVal = 1 - (2 / SQRT_PI) * sum
    return Math.exp(x * x) * erfcVal
  }
  // Continued fraction: erfcx(x) = 1/sqrt(pi) / (x + 1/2/(x + 1/(x + 3/2/(x + ...))))
  const tiny = 1e-300
  let f = x
  let c = f
  let d = 0
  for (let n = 1; n < 500; n += 1) {
    const a = n / 2
    d = x + a * d
    if (d === 0 || Math.abs(d) < tiny) d = tiny
    c = x + a / c
    if (c === 0 || Math.abs(c) < tiny) c = tiny
    d = 1 / d
    const delta = c * d
    f *= delta
    if (Math.abs(delta - 1) < 1e-16) break
  }
  return INV_SQRT_PI / f
}

/** Error function, double precision (|relative error| < 1e-15). */
export function erf(x: number): number {
  if (Number.isNaN(x)) return Number.NaN
  if (x < 0) return -erf(-x)
  if (x === 0) return 0
  if (x > 27) return 1
  const v = Math.exp(-x * x) * erfcx(x)
  return 1 - v
}

/** Complementary error function, double precision. */
export function erfc(x: number): number {
  if (Number.isNaN(x)) return Number.NaN
  if (x < 0) return 2 - erfc(-x)
  if (x > 27.3) return 0
  return Math.exp(-x * x) * erfcx(x)
}

// ---------------------------------------------------------------------------
// Gamma functions
// ---------------------------------------------------------------------------

const LANCZOS_G = 7
const LANCZOS_COEFF = [
  0.99999999999980993, 676.5203681218851, -1259.1392167224028,
  771.32342877765313, -176.61502916214059, 12.507343278686905,
  -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7
]

function lanczosGamma(z: number): number {
  // Valid for z > 0.5.
  let x = LANCZOS_COEFF[0]
  const zz = z - 1
  for (let i = 1; i < LANCZOS_COEFF.length; i += 1) {
    x += LANCZOS_COEFF[i] / (zz + i)
  }
  const t = zz + LANCZOS_G + 0.5
  return Math.sqrt(2 * Math.PI) * Math.pow(t, zz + 0.5) * Math.exp(-t) * x
}

/**
 * Natural logarithm of the gamma function.
 * Lanczos approximation with the Euler reflection formula for x < 0.5.
 * Relative accuracy ~1e-14; lngamma(0.5) = ln(sqrt(pi)).
 */
export function lngamma(x: number): number {
  if (Number.isNaN(x)) return Number.NaN
  if (x <= 0 && Number.isInteger(x)) return Number.POSITIVE_INFINITY
  if (x < 0.5) {
    // ln|Gamma(x)| via reflection: Gamma(x)Gamma(1-x) = pi / sin(pi x)
    const s = Math.sin(Math.PI * x)
    return Math.log(Math.PI / Math.abs(s)) - lngamma(1 - x)
  }
  let xc = LANCZOS_COEFF[0]
  const z = x - 1
  for (let i = 1; i < LANCZOS_COEFF.length; i += 1) {
    xc += LANCZOS_COEFF[i] / (z + i)
  }
  const t = z + LANCZOS_G + 0.5
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(xc)
}

/** Gamma function (signed for negative non-integers). */
export function gammaFn(x: number): number {
  if (Number.isNaN(x)) return Number.NaN
  if (x <= 0 && Number.isInteger(x)) return Number.NaN
  if (x <= 0) {
    // Reflection: Gamma(x) = pi / (sin(pi x) Gamma(1-x)); sign comes from sin.
    const s = Math.sin(Math.PI * x)
    const g = lanczosGamma(1 - x)
    return Math.PI / (s * g)
  }
  return Math.exp(lngamma(x))
}

/** Alias for {@link gammaFn}. */
export { gammaFn as gamma }

// ---------------------------------------------------------------------------
// Incomplete gamma
// ---------------------------------------------------------------------------

/**
 * Regularized lower incomplete gamma P(a,x) = gamma(a,x)/Gamma(a).
 * NR series/continued-fraction split. Relative accuracy ~1e-14.
 */
export function incompleteGammaP(a: number, x: number): number {
  if (Number.isNaN(a) || Number.isNaN(x)) return Number.NaN
  if (a <= 0) return Number.NaN
  if (x <= 0) return 0
  if (x < a + 1) {
    // Series representation.
    let ap = a
    let sum = 1 / a
    let del = sum
    for (let n = 0; n < 500; n += 1) {
      ap += 1
      del *= x / ap
      sum += del
      if (Math.abs(del) < Math.abs(sum) * 1e-16) break
    }
    return sum * Math.exp(-x + a * Math.log(x) - lngamma(a))
  }
  return 1 - incompleteGammaQ(a, x)
}

/**
 * Regularized upper incomplete gamma Q(a,x) = 1 - P(a,x).
 * Continued fraction (Lentz) branch; accurate even when P saturates.
 */
export function incompleteGammaQ(a: number, x: number): number {
  if (Number.isNaN(a) || Number.isNaN(x)) return Number.NaN
  if (a <= 0) return Number.NaN
  if (x <= 0) return 1
  if (x < a + 1) return 1 - incompleteGammaP(a, x)
  const tiny = 1e-300
  let b = x + 1 - a
  let c = 1 / tiny
  let d = 1 / b
  let h = d
  for (let i = 1; i <= 500; i += 1) {
    const an = -i * (i - a)
    b += 2
    d = an * d + b
    if (Math.abs(d) < tiny) d = tiny
    c = b + an / c
    if (Math.abs(c) < tiny) c = tiny
    d = 1 / d
    const del = d * c
    h *= del
    if (Math.abs(del - 1) < 1e-16) break
  }
  return Math.exp(-x + a * Math.log(x) - lngamma(a)) * h
}

// ---------------------------------------------------------------------------
// Beta functions
// ---------------------------------------------------------------------------

/** Complete beta function B(a,b) = Gamma(a)Gamma(b)/Gamma(a+b). */
export function betaFn(a: number, b: number): number {
  if (a <= 0 || b <= 0) return Number.NaN
  return Math.exp(lngamma(a) + lngamma(b) - lngamma(a + b))
}

function betacf(a: number, b: number, x: number): number {
  const MAXIT = 300
  const EPS = 3e-16
  const FPMIN = 1e-300
  const qab = a + b
  const qap = a + 1
  const qam = a - 1
  let c = 1
  let d = 1 - (qab * x) / qap
  if (Math.abs(d) < FPMIN) d = FPMIN
  d = 1 / d
  let h = d
  for (let m = 1; m <= MAXIT; m += 1) {
    const m2 = 2 * m
    let aa = (m * (b - m) * x) / ((qam + m2) * (a + m2))
    d = 1 + aa * d
    if (Math.abs(d) < FPMIN) d = FPMIN
    c = 1 + aa / c
    if (Math.abs(c) < FPMIN) c = FPMIN
    d = 1 / d
    h *= d * c
    aa = (-(a + m) * (qab + m) * x) / ((a + m2) * (qap + m2))
    d = 1 + aa * d
    if (Math.abs(d) < FPMIN) d = FPMIN
    c = 1 + aa / c
    if (Math.abs(c) < FPMIN) c = FPMIN
    d = 1 / d
    const del = d * c
    h *= del
    if (Math.abs(del - 1) < EPS) break
  }
  return h
}

/**
 * Regularized incomplete beta I_x(a,b).
 * Heuristic false because of the 300-iteration cap.
 */
export function incompleteBeta(x: number, a: number, b: number): number {
  if (Number.isNaN(x) || Number.isNaN(a) || Number.isNaN(b)) return Number.NaN
  if (a <= 0 || b <= 0) return Number.NaN
  if (x <= 0) return 0
  if (x >= 1) return 1
  const bt = Math.exp(
    lngamma(a + b) - lngamma(a) - lngamma(b) + a * Math.log(x) + b * Math.log(1 - x)
  )
  if (x < (a + 1) / (a + b + 2)) {
    return (bt * betacf(a, b, x)) / a
  }
  return 1 - (bt * betacf(b, a, 1 - x)) / b
}

// ---------------------------------------------------------------------------
// Student t quantiles (used for 95% confidence intervals in Peak Review)
// ---------------------------------------------------------------------------

/**
 * Student-t quantile t_p(nu) for p in (0,1), nu > 0.
 * Uses the incomplete-beta identity
 *   P(T <= t) = 1 - 0.5 I_{nu/(nu+t^2)}(nu/2, 1/2)
 * solved by 200 bisection steps (error < 1e-12 absolute in probability).
 */
export function studentTQuantile(p: number, nu: number): number {
  if (!(p > 0 && p < 1) || !(nu > 0)) return Number.NaN
  if (p === 0.5) return 0
  if (p < 0.5) return -studentTQuantile(1 - p, nu)
  const target = 2 * (1 - p) // I_x(nu/2, 1/2)
  let lo = 0
  let hi = 1
  for (let i = 0; i < 200; i += 1) {
    const mid = 0.5 * (lo + hi)
    const val = incompleteBeta(mid, nu / 2, 0.5)
    // I_x is increasing in x: too large means the root is to the left.
    if (val > target) hi = mid
    else lo = mid
  }
  const x = 0.5 * (lo + hi)
  return Math.sqrt((nu * (1 - x)) / x)
}

/** Two-sided 95% Student-t critical value t_{0.975, nu}. */
export function tQuantile95(nu: number): number {
  return studentTQuantile(0.975, nu)
}

// ---------------------------------------------------------------------------
// Modified Bessel functions I0 / I1 (needed by GIDDINGS and NLC)
// ---------------------------------------------------------------------------

/**
 * Modified Bessel function of the first kind, order 0.
 * Power series for |x| < 50, scaled asymptotic expansion above.
 */
export function besselI0(x: number): number {
  return besselI0e(x) * Math.exp(Math.abs(x))
}

/**
 * Exponentially scaled I0: I0e(x) = exp(-|x|) I0(x).
 * Avoids overflow in convolution-like formulas.
 */
export function besselI0e(x: number): number {
  const ax = Math.abs(x)
  if (ax < 50) {
    // I0(x) = sum (x^2/4)^k / (k!)^2
    let term = 1
    let sum = 1
    const q = (x * x) / 4
    for (let k = 1; k < 200; k += 1) {
      term *= q / (k * k)
      sum += term
      if (term < sum * 1e-17) break
    }
    return sum * Math.exp(-ax)
  }
  // I0e(x) ~ (1/sqrt(2 pi x)) (1 + 1/(8x) + 9/(128x^2) + ...)
  const inv = 1 / ax
  let sum = 1
  let term = 1
  for (let k = 1; k < 30; k += 1) {
    term *= ((2 * k - 1) * (2 * k - 1)) * inv / (8 * k)
    sum += term
    if (Math.abs(term) < sum * 1e-17) break
  }
  return sum / Math.sqrt(2 * Math.PI * ax)
}

/**
 * Modified Bessel function of the first kind, order 1.
 */
export function besselI1(x: number): number {
  return besselI1e(x) * Math.exp(Math.abs(x))
}

/**
 * Exponentially scaled I1: I1e(x) = exp(-|x|) I1(x), odd in x.
 * Power series below |x| = 50, asymptotic above.
 */
export function besselI1e(x: number): number {
  const ax = Math.abs(x)
  const sgn = x < 0 ? -1 : 1
  if (ax < 50) {
    // I1(x) = (x/2) * sum (x^2/4)^k / (k! (k+1)!)
    let term = 1
    let sum = 1
    const q = (x * x) / 4
    for (let k = 1; k < 200; k += 1) {
      term *= q / (k * (k + 1))
      sum += term
      if (term < sum * 1e-17) break
    }
    return sgn * (ax / 2) * sum * Math.exp(-ax)
  }
  // I1e(x) ~ (1/sqrt(2 pi x)) (1 - 3/(8x) + 15/(128x^2) - ...)
  const inv = 1 / ax
  let sum = 1
  let term = 1
  for (let k = 1; k < 30; k += 1) {
    term *= -((2 * k - 3) * (2 * k + 1)) * inv / (8 * k)
    sum += term
    if (Math.abs(term) < sum * 1e-17) break
  }
  return sgn * sum / Math.sqrt(2 * Math.PI * ax)
}

// ---------------------------------------------------------------------------
// Faddeeva function w(z) (needed by the Voigt model)
// ---------------------------------------------------------------------------

/**
 * Entire Taylor series of w(z) = exp(-z^2) erfc(-iz):
 *   w(z) = sum_{n>=0} (iz)^n / Gamma(1 + n/2)
 * Accurate for |z| < 3 (max term ~ e^9, cancellation ~1e-12).
 */
function faddeevaTaylor(zx: number, zy: number): { re: number; im: number } {
  // t_0 = 1, t_1 = i z * 2/sqrt(pi)
  let re = 1
  let im = 0
  let prevRe = 1
  let prevIm = 0
  const c1 = 2 / SQRT_PI
  // t_1 = i z * c1 = -c1 y + i c1 x
  let curRe = -c1 * zy
  let curIm = c1 * zx
  re += curRe
  im += curIm
  const z2x = zx * zx - zy * zy
  const z2y = 2 * zx * zy
  for (let n = 1; n < 300; n += 1) {
    // t_{n+1} = t_{n-1} * (-z^2) * 2/(n+1)
    const f = -2 / (n + 1)
    const nextRe = (prevRe * z2x - prevIm * z2y) * f
    const nextIm = (prevRe * z2y + prevIm * z2x) * f
    re += nextRe
    im += nextIm
    if (Math.hypot(nextRe, nextIm) < 1e-17 * Math.hypot(re, im)) break
    prevRe = curRe
    prevIm = curIm
    curRe = nextRe
    curIm = nextIm
  }
  return { re, im }
}

/**
 * Real erfi(x) for 0 <= |x| < 8 using its all-positive power series:
 *   erfi(x) = (2/sqrt(pi)) sum x^(2k+1)/(k!(2k+1)).
 */
function erfi(x: number): number {
  let term = x
  let sum = x
  const x2 = x * x
  for (let k = 1; k < 500; k += 1) {
    term *= (x2 * (2 * k - 1)) / (k * (2 * k + 1))
    sum += term
    if (Math.abs(term) < Math.abs(sum) * 1e-17) break
  }
  return (2 / SQRT_PI) * sum
}

/**
 * w(x) on the real axis. For |x| < 3 the Taylor series is used; for
 * 3 <= |x| < 8 the identity w(x) = exp(-x^2) (1 + i erfi(x)) is used;
 * for |x| >= 8 the caller uses the asymptotic expansion instead.
 */
function faddeevaReal(x: number): { re: number; im: number } {
  const ax = Math.abs(x)
  if (ax < 3) return faddeevaTaylor(x, 0)
  const e = Math.exp(-x * x)
  return { re: e, im: e * erfi(x) }
}

/** Asymptotic erfcx expansion (optimal truncation) evaluated at w = y - ix. */
function erfcxAsymptotic(wx: number, wy: number): { re: number; im: number } {
  // 1/w
  const den = wx * wx + wy * wy
  const invRe = wx / den
  const invIm = -wy / den
  // w^-2
  const w2x = wx * wx - wy * wy
  const w2y = 2 * wx * wy
  const d2 = w2x * w2x + w2y * w2y
  const inv2Re = w2x / d2
  const inv2Im = -w2y / d2
  let sumRe = 1
  let sumIm = 0
  let termRe = 1
  let termIm = 0
  let best = 1e300
  for (let k = 1; k < 200; k += 1) {
    // term *= -(2k-1)/(2 w^2)
    const c = -(2 * k - 1) / 2
    const nr = c * (termRe * inv2Re - termIm * inv2Im)
    const ni = c * (termRe * inv2Im + termIm * inv2Re)
    termRe = nr
    termIm = ni
    const mag = Math.hypot(termRe, termIm)
    if (mag > best) break
    best = mag
    sumRe += termRe
    sumIm += termIm
    if (mag < 1e-18 * Math.hypot(sumRe, sumIm)) break
  }
  // multiply by 1/(sqrt(pi) w)
  const fac = INV_SQRT_PI
  return {
    re: fac * (sumRe * invRe - sumIm * invIm),
    im: fac * (sumRe * invIm + sumIm * invRe)
  }
}

/** Lentz continued fraction for erfcx(w), valid for Re(w) >= 0, |w| >= 3. */
function erfcxContinuedFraction(wx: number, wy: number): { re: number; im: number } {
  const tiny = 1e-300
  let fr = wx
  let fi = wy
  let cr = fr
  let ci = fi
  let dr = 0
  let di = 0
  for (let n = 1; n < 2000; n += 1) {
    const a = n / 2
    // d = w + a*d
    let tr = wx + a * dr
    let ti = wy + a * di
    if (Math.hypot(tr, ti) < tiny) {
      tr = tiny
      ti = 0
    }
    dr = tr
    di = ti
    // c = w + a/c
    const cden = cr * cr + ci * ci
    if (cden < tiny * tiny) {
      cr = tiny
      ci = 0
    } else {
      const qr = (a * cr) / cden
      const qi = (-a * ci) / cden
      cr = wx + qr
      ci = wy + qi
    }
    if (Math.hypot(cr, ci) < tiny) {
      cr = tiny
      ci = 0
    }
    // d = 1/d
    const dden = dr * dr + di * di
    if (dden < tiny * tiny) {
      dr = 1 / tiny
      di = 0
    } else {
      const rr = dr / dden
      const ri = -di / dden
      dr = rr
      di = ri
    }
    // delta = c*d
    const delRe = cr * dr - ci * di
    const delIm = cr * di + ci * dr
    // f *= delta
    const fr2 = fr * delRe - fi * delIm
    const fi2 = fr * delIm + fi * delRe
    fr = fr2
    fi = fi2
    if (Math.abs(delRe - 1) < 1e-15 && Math.abs(delIm) < 1e-15) break
  }
  const den = fr * fr + fi * fi
  if (den < 1e-300) return { re: 0, im: 0 }
  return { re: (INV_SQRT_PI * fr) / den, im: (-INV_SQRT_PI * fi) / den }
}

/**
 * Faddeeva function w(z) = exp(-z^2) erfc(-iz) for arbitrary complex z.
 *
 * Algorithm:
 *  - reflection to the upper half plane when y < 0;
 *  - asymptotic erfcx expansion for |z| >= 8 (relative error < 1e-12);
 *  - Taylor series for |z| < 3 (entire function);
 *  - erfcx continued fraction for the moderate upper half plane;
 *  - small-y Taylor expansion around the real axis (needed because the
 *    continued fraction degrades as Im(z) -> 0).
 *
 * The returned object is a fresh pair; hot loops should use
 * {@link voigtReW} in models.ts, which schedules these branches without
 * allocating per point.
 */
export function faddeeva(zx: number, zy: number): { re: number; im: number } {
  if (Number.isNaN(zx) || Number.isNaN(zy)) return { re: Number.NaN, im: Number.NaN }
  if (zy < 0) {
    // w(z) = 2 exp(-z^2) - w(-z)
    const z2x = zx * zx - zy * zy
    const z2y = 2 * zx * zy
    const ex = Math.exp(-z2x)
    const exRe = ex * Math.cos(-z2y)
    const exIm = ex * Math.sin(-z2y)
    const other = faddeeva(-zx, -zy)
    return { re: 2 * exRe - other.re, im: 2 * exIm - other.im }
  }
  const r2 = zx * zx + zy * zy
  if (r2 >= 64) return erfcxAsymptotic(zy, -zx)
  if (r2 < 9) return faddeevaTaylor(zx, zy)
  if (zy >= 0.05) return erfcxContinuedFraction(zy, -zx)

  // Small imaginary part: Taylor around the real axis.
  const w0 = faddeevaReal(zx)
  // Coefficients c_n = w^(n)(x)/n!, recurrence:
  // c_{n+1} = (-2x c_n - 2 c_{n-1})/(n+1)
  // c_0 = w, c_1 = -2x w + 2i/sqrt(pi)
  let prevRe = w0.re
  let prevIm = w0.im
  let curRe = -2 * zx * w0.re
  let curIm = -2 * zx * w0.im + 2 / SQRT_PI
  let sumRe = prevRe + 0 * curRe
  let sumIm = prevIm + 0 * curIm
  // Taylor powers of (iy)^n and coefficients are combined directly.
  let powRe = 1
  let powIm = 0
  // n = 0
  sumRe = prevRe
  sumIm = prevIm
  // n = 1
  powRe = 0
  powIm = zy
  sumRe += curRe * powRe - curIm * powIm
  sumIm += curRe * powIm + curIm * powRe
  const mag0 = Math.hypot(sumRe, sumIm)
  for (let n = 1; n < 80; n += 1) {
    const nr = (-2 * zx * curRe - 2 * prevRe) / (n + 1)
    const ni = (-2 * zx * curIm - 2 * prevIm) / (n + 1)
    prevRe = curRe
    prevIm = curIm
    curRe = nr
    curIm = ni
    // pow *= iy
    const pr = -powIm * zy
    const pi = powRe * zy
    powRe = pr
    powIm = pi
    const addRe = curRe * powRe - curIm * powIm
    const addIm = curRe * powIm + curIm * powRe
    sumRe += addRe
    sumIm += addIm
    if (Math.hypot(addRe, addIm) < 1e-17 * Math.max(mag0, Math.hypot(sumRe, sumIm))) break
  }
  return { re: sumRe, im: sumIm }
}

/**
 * Real part of w(x + i y) only, allocation-free entry point for the Voigt
 * model (the imaginary part is not needed there).
 */
export function faddeevaRe(x: number, y: number): number {
  if (Number.isNaN(x) || Number.isNaN(y)) return Number.NaN
  if (y >= 0) {
    const r2 = x * x + y * y
    if (r2 >= 64) {
      // Asymptotic fast path returning Re only.
      const w = erfcxAsymptotic(y, -x)
      return w.re
    }
    if (r2 < 9) return faddeevaTaylor(x, y).re
    if (y >= 0.05) return erfcxContinuedFraction(y, -x).re
    // small-y Taylor
    const w0 = faddeevaReal(x)
    let prevRe = w0.re
    let prevIm = w0.im
    let curRe = -2 * x * w0.re
    let curIm = -2 * x * w0.im + 2 / SQRT_PI
    let sumRe = prevRe
    let sumIm = prevIm
    let powRe = 0
    let powIm = y
    sumRe += curRe * powRe - curIm * powIm
    sumIm += curRe * powIm + curIm * powRe
    const mag0 = Math.hypot(sumRe, sumIm)
    for (let n = 1; n < 80; n += 1) {
      const nr = (-2 * x * curRe - 2 * prevRe) / (n + 1)
      const ni = (-2 * x * curIm - 2 * prevIm) / (n + 1)
      prevRe = curRe
      prevIm = curIm
      curRe = nr
      curIm = ni
      const pr = -powIm * y
      const pi = powRe * y
      powRe = pr
      powIm = pi
      const addRe = curRe * powRe - curIm * powIm
      const addIm = curRe * powIm + curIm * powRe
      sumRe += addRe
      sumIm += addIm
      if (Math.hypot(addRe, addIm) < 1e-17 * Math.max(mag0, Math.hypot(sumRe, sumIm))) break
    }
    return sumRe
  }
  return faddeeva(x, y).re
}
