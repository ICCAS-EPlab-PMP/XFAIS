/**
 * Asymmetric least squares baseline (Eilers & Boelens) — alternative
 * non-parametric estimator kept for the "自动扫描" quick path.
 */
export interface AutoscanOptions {
  lambda?: number
  asym?: number
  iterations?: number
}

function solvePentadiagonal(w: Float64Array, lam: number, y: Float64Array, z: Float64Array): void {
  const n = y.length
  // M = diag(w) + lam·DᵀD, D = second difference: diag [1,5,6..6,5,1],
  // first off-diagonal -4 (-2 at both ends), second off-diagonal 1.
  const d0 = new Float64Array(n)
  const d1 = new Float64Array(Math.max(0, n - 1))
  const d2 = new Float64Array(Math.max(0, n - 2))
  for (let i = 0; i < n; i++) {
    const ldiag = i === 0 || i === n - 1 ? 1 : i === 1 || i === n - 2 ? 5 : 6
    d0[i] = w[i] + lam * ldiag
  }
  for (let i = 0; i < n - 1; i++) d1[i] = lam * (i === 0 || i === n - 2 ? -2 : -4)
  for (let i = 0; i < n - 2; i++) d2[i] = lam
  const b = new Float64Array(n)
  for (let i = 0; i < n; i++) b[i] = w[i] * y[i]
  // banded Cholesky R (bandwidth 2): M = RᵀR
  const r0 = new Float64Array(n)
  const r1 = new Float64Array(Math.max(0, n - 1))
  const r2 = new Float64Array(Math.max(0, n - 2))
  for (let i = 0; i < n; i++) {
    let s = d0[i]
    if (i >= 1) s -= r1[i - 1] * r1[i - 1]
    if (i >= 2) s -= r2[i - 2] * r2[i - 2]
    if (!(s > 0)) s = 1e-300
    r0[i] = Math.sqrt(s)
    if (i + 1 < n) {
      let t = d1[i]
      if (i >= 1) t -= r1[i - 1] * r2[i - 1]
      r1[i] = t / r0[i]
    }
    if (i + 2 < n) r2[i] = d2[i] / r0[i]
  }
  const u = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    let s = b[i]
    if (i >= 1) s -= r1[i - 1] * u[i - 1]
    if (i >= 2) s -= r2[i - 2] * u[i - 2]
    u[i] = s / r0[i]
  }
  for (let i = n - 1; i >= 0; i--) {
    let s = u[i]
    if (i + 1 < n) s -= r1[i] * z[i + 1]
    if (i + 2 < n) s -= r2[i] * z[i + 2]
    z[i] = s / r0[i]
  }
}

export function autoscanBaseline(
  y: Float64Array,
  mask?: Uint8Array | null,
  opts: AutoscanOptions = {}
): Float64Array {
  const n = y.length
  const out = new Float64Array(n)
  if (n === 0) return out
  const lam = Number.isFinite(opts.lambda) ? Math.max(0, opts.lambda as number) : 1e8
  const asym = Math.max(1e-7, Math.min(1, opts.asym ?? 0.001))
  const iters = Math.max(1, Math.min(200, Math.floor(opts.iterations ?? 15)))
  const w = new Float64Array(n)
  for (let i = 0; i < n; i++) w[i] = mask && mask[i] === 0 ? 0 : 1
  const z = new Float64Array(n)
  solvePentadiagonal(w, lam, y, z)
  for (let it = 0; it < iters; it++) {
    let changed = false
    for (let i = 0; i < n; i++) {
      if (mask && mask[i] === 0) continue
      const want = y[i] > z[i] ? asym : 1
      if (want !== w[i]) {
        w[i] = want
        changed = true
      }
    }
    if (!changed) break
    solvePentadiagonal(w, lam, y, z)
  }
  for (let i = 0; i < n; i++) if (!Number.isFinite(z[i])) z[i] = 0
  out.set(z)
  return out
}
