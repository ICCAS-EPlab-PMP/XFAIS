/**
 * Smoothing and filtering used by the data-preparation workflow and by the
 * auto peak detectors.
 *
 * - Savitzky-Golay: local least-squares polynomial convolution. Interior
 *   points use the classic symmetric coefficients; boundary points use a
 *   one-sided window of the same length and evaluate the fitted polynomial
 *   at the actual point (low-order extrapolation, no reflection padding).
 * - Moving average: shrinking window at the edges.
 * - FFT low-pass: iterative radix-2 FFT, brick-wall cutoff expressed as a
 *   fraction of the Nyquist frequency (zero padding to the next power of 2).
 */
import type { SmoothMethod, SmoothOptions } from '../shared/types'

/** Solve a small dense linear system in-place-safe way (Gaussian elimination). */
function solveSmall(a: Float64Array, b: Float64Array, n: number): Float64Array {
  const m = new Float64Array(a)
  const x = new Float64Array(b)
  for (let col = 0; col < n; col += 1) {
    let pivot = col
    let best = Math.abs(m[col * n + col])
    for (let r = col + 1; r < n; r += 1) {
      const v = Math.abs(m[r * n + col])
      if (v > best) {
        best = v
        pivot = r
      }
    }
    if (best < 1e-300) {
      // Singular: fall back to a tiny ridge.
      for (let r = 0; r < n; r += 1) m[r * n + r] += 1e-12
      best = Math.abs(m[col * n + col])
      if (best < 1e-300) return x
    }
    if (pivot !== col) {
      for (let c = col; c < n; c += 1) {
        const t = m[col * n + c]
        m[col * n + c] = m[pivot * n + c]
        m[pivot * n + c] = t
      }
      const t = x[col]
      x[col] = x[pivot]
      x[pivot] = t
    }
    const d = m[col * n + col]
    for (let r = col + 1; r < n; r += 1) {
      const f = m[r * n + col] / d
      if (f === 0) continue
      for (let c = col; c < n; c += 1) m[r * n + c] -= f * m[col * n + c]
      x[r] -= f * x[col]
    }
  }
  for (let r = n - 1; r >= 0; r -= 1) {
    let s = x[r]
    for (let c = r + 1; c < n; c += 1) s -= m[r * n + c] * x[c]
    x[r] = s / m[r * n + r]
  }
  return x
}

/**
 * Savitzky-Golay convolution weights for a window of `window` points,
 * polynomial order `order`, evaluating the derivative `deriv` at local
 * offset `evalOffset` from the first window point.
 */
export function sgWeights(
  window: number,
  order: number,
  deriv: number,
  evalOffset: number
): Float64Array {
  const w = Math.max(1, Math.floor(window))
  const p = Math.min(Math.max(0, Math.floor(order)), w - 1)
  const nCoef = p + 1
  const ata = new Float64Array(nCoef * nCoef)
  const rhs = new Float64Array(nCoef)
  for (let a = 0; a < nCoef; a += 1) {
    let s = 0
    for (let k = 0; k < w; k += 1) s += Math.pow(k, a)
    rhs[a] = Math.pow(evalOffset, a)
    for (let b = 0; b < nCoef; b += 1) {
      let t = 0
      for (let k = 0; k < w; k += 1) t += Math.pow(k, a + b)
      ata[a * nCoef + b] = t
    }
  }
  const coef = solveSmall(ata, rhs, nCoef)
  const out = new Float64Array(w)
  for (let k = 0; k < w; k += 1) {
    let v = 0
    for (let a = deriv; a < nCoef; a += 1) {
      // d^deriv/dk^deriv of k^a = a!/(a-deriv)! k^(a-deriv)
      let f = 1
      for (let i = 0; i < deriv; i += 1) f *= a - i
      v += coef[a] * f * Math.pow(k, a - deriv)
    }
    out[k] = v
  }
  return out
}

/**
 * Savitzky-Golay smoothing / differentiation.
 * `window` should be odd; even values are rounded down to odd. If the data
 * is shorter than the window, a lower-order / shorter window is used.
 */
export function savgol(
  y: Float64Array,
  window: number,
  polyOrder: number,
  deriv = 0
): Float64Array {
  const n = y.length
  if (n === 0) return new Float64Array(0)
  let w = Math.max(3, Math.floor(window))
  if (w % 2 === 0) w -= 1
  w = Math.min(w, n % 2 === 1 ? n : n - 1)
  if (w < 3) return Float64Array.from(y)
  let p = Math.min(Math.max(1, Math.floor(polyOrder)), w - 2)
  if (p < deriv) p = Math.min(w - 2, deriv + 1)
  const half = (w - 1) / 2
  const out = new Float64Array(n)

  const interior = sgWeights(w, p, deriv, half)
  for (let i = half; i < n - half; i += 1) {
    let s = 0
    for (let k = 0; k < w; k += 1) s += interior[k] * y[i - half + k]
    out[i] = s
  }
  // Boundaries: one-sided windows, polynomial evaluated at the actual point.
  for (let i = 0; i < half; i += 1) {
    const wts = sgWeights(w, p, deriv, i)
    let s = 0
    for (let k = 0; k < w; k += 1) s += wts[k] * y[k]
    out[i] = s
  }
  for (let i = n - half; i < n; i += 1) {
    const start = n - w
    const ev = i - start
    const wts = sgWeights(w, p, deriv, ev)
    let s = 0
    for (let k = 0; k < w; k += 1) s += wts[k] * y[start + k]
    out[i] = s
  }
  return out
}

/** Symmetric moving average with a shrinking window at the edges. */
export function movingAverage(y: Float64Array, window: number): Float64Array {
  const n = y.length
  const out = new Float64Array(n)
  let w = Math.max(1, Math.floor(window))
  if (w % 2 === 0) w += 1
  const half = (w - 1) / 2
  let acc = 0
  let count = 0
  // Initial window for i = 0: indices 0..min(n-1, half).
  const initial = Math.min(n - 1, half)
  for (let k = 0; k <= initial; k += 1) {
    acc += y[k]
    count += 1
  }
  for (let i = 0; i < n; i += 1) {
    out[i] = count > 0 ? acc / count : y[i]
    // Advance from window centered at i to the one centered at i+1.
    const add = i + half + 1
    if (add < n) {
      acc += y[add]
      count += 1
    }
    const remove = i - half
    if (remove >= 0) {
      acc -= y[remove]
      count -= 1
    }
  }
  return out
}

/** Next power of two >= n (minimum 1). */
export function nextPow2(n: number): number {
  let p = 1
  while (p < n) p <<= 1
  return p
}

/**
 * In-place iterative radix-2 FFT. `re.length` and `im.length` must be a
 * power of two and equal. Sign convention: forward transform uses exp(-i...).
 */
export function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length
  if (n <= 1) return
  // Bit-reversal permutation.
  for (let i = 1, j = 0; i < n; i += 1) {
    let bit = n >> 1
    for (; j & bit; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) {
      let t = re[i]
      re[i] = re[j]
      re[j] = t
      t = im[i]
      im[i] = im[j]
      im[j] = t
    }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len
    const wRe = Math.cos(ang)
    const wIm = Math.sin(ang)
    for (let i = 0; i < n; i += len) {
      let curRe = 1
      let curIm = 0
      const half = len >> 1
      for (let j = 0; j < half; j += 1) {
        const aRe = re[i + j]
        const aIm = im[i + j]
        const bRe = re[i + j + half] * curRe - im[i + j + half] * curIm
        const bIm = re[i + j + half] * curIm + im[i + j + half] * curRe
        re[i + j] = aRe + bRe
        im[i + j] = aIm + bIm
        re[i + j + half] = aRe - bRe
        im[i + j + half] = aIm - bIm
        const nRe = curRe * wRe - curIm * wIm
        curIm = curRe * wIm + curIm * wRe
        curRe = nRe
      }
    }
  }
}

/** Inverse FFT (unnormalized forward applied to conjugated spectrum). */
export function ifft(re: Float64Array, im: Float64Array): void {
  for (let i = 0; i < im.length; i += 1) im[i] = -im[i]
  fft(re, im)
  const n = re.length
  for (let i = 0; i < n; i += 1) {
    re[i] /= n
    im[i] = -im[i] / n
  }
}

/** Real FFT of a real signal, zero-padded to the next power of two. */
export function rfft(y: Float64Array): { re: Float64Array; im: Float64Array; n: number } {
  const n = nextPow2(Math.max(1, y.length))
  const re = new Float64Array(n)
  const im = new Float64Array(n)
  re.set(y)
  fft(re, im)
  return { re, im, n }
}

/**
 * FFT low-pass filter. `cutoff` is a fraction of Nyquist in (0,1]; the
 * brick-wall cutoff is softened by a raised-cosine transition over the
 * last 20% of the pass band to control ringing.
 */
export function fftLowpass(y: Float64Array, cutoff: number): Float64Array {
  const n = y.length
  if (n === 0) return new Float64Array(0)
  const frac = Math.max(0, Math.min(1, cutoff))
  if (frac >= 0.999) return Float64Array.from(y)
  const padded = nextPow2(n)
  const re = new Float64Array(padded)
  const im = new Float64Array(padded)
  // Mirror padding avoids the step discontinuity (and edge ringing) of
  // zero padding; for i >= n the signal is reflected about its last sample.
  if (n > 1) {
    const period = 2 * n - 2
    for (let i = 0; i < padded; i += 1) {
      let j = i % period
      if (j >= n) j = period - j
      re[i] = y[j]
    }
  } else {
    re[0] = y[0] ?? 0
  }
  fft(re, im)
  const nyqBins = padded / 2
  const start = Math.max(0, (frac * 0.8) * nyqBins)
  const stop = frac * nyqBins
  for (let i = 0; i <= nyqBins; i += 1) {
    let gain = 1
    if (i >= stop) gain = 0
    else if (i > start && stop > start) {
      const t = (i - start) / (stop - start)
      gain = 0.5 * (1 + Math.cos(Math.PI * t))
    }
    re[i] *= gain
    im[i] *= gain
    if (i > 0 && i < nyqBins) {
      const mirror = padded - i
      re[mirror] *= gain
      im[mirror] *= gain
    }
  }
  ifft(re, im)
  return re.slice(0, n)
}

/** Apply a SmoothOptions request to a signal. */
export function smoothData(y: Float64Array, opts: SmoothOptions): Float64Array {
  switch (opts.method) {
    case 'sg':
      return savgol(y, opts.window, opts.polyOrder, 0)
    case 'movavg':
      return movingAverage(y, opts.window)
    case 'fftLowpass':
      return fftLowpass(y, opts.cutoff)
    default:
      return Float64Array.from(y)
  }
}
