/**
 * Number / duration / text formatting helpers for display.
 * All UI numeric text goes through these to keep significant-digit policy
 * consistent across panels, status bar and reports.
 */

/** Trim a `toPrecision` result: drop exponent padding + trailing zeros. */
function trimPrecision(s: string): string {
  if (s.includes('e')) return s.replace(/(\.\d*?)0+e/, '$1e').replace(/\.e/, 'e')
  return s.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')
}

/** Fixed significant digits, compact notation. */
export function fmtSig(v: number, sig = 6): string {
  if (v === null || Number.isNaN(v)) return '—'
  if (!Number.isFinite(v)) return v > 0 ? '∞' : '-∞'
  if (v === 0) return '0'
  const a = Math.abs(v)
  if (a >= 1e6 || a < 1e-4) return trimPrecision(v.toExponential(Math.max(0, sig - 1)))
  return trimPrecision(v.toPrecision(sig))
}

/** Scientific notation with fixed mantissa digits, e.g. 1.2345e+3. */
export function fmtSci(v: number, digits = 4): string {
  if (!Number.isFinite(v)) return '—'
  if (v === 0) return '0'
  return v.toExponential(digits)
}

/** Axis tick label: short but precise enough to read a spectrum. */
export function fmtTick(v: number): string {
  if (!Number.isFinite(v)) return ''
  if (v === 0) return '0'
  const a = Math.abs(v)
  if (a >= 1e6 || a < 1e-3) return trimPrecision(v.toExponential(1))
  return trimPrecision(v.toPrecision(5))
}

/** Milliseconds → "842 ms" / "1.24 s" / "2:03 min". */
export function fmtMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`
  const m = Math.floor(ms / 60_000)
  const s = Math.round((ms % 60_000) / 1000)
  return `${m}:${String(s).padStart(2, '0')} min`
}

/** Percent 0..1 → "98.34 %". */
export function fmtPct(v: number, digits = 2): string {
  if (!Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)} %`
}

/** Parse user-typed numeric text; NaN when invalid. */
export function parseNum(text: string): number {
  const cleaned = text.trim().replace(/,/g, '')
  if (!cleaned) return Number.NaN
  return Number(cleaned)
}

/** Clamp respecting null bounds from the registry. */
export function clampBound(v: number, min: number | null, max: number | null): number {
  let out = v
  if (min !== null && out < min) out = min
  if (max !== null && out > max) out = max
  return out
}

/** CSV field escaping. */
export function csvEscape(v: string | number): string {
  const s = typeof v === 'number' ? String(v) : v
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

/** Current local timestamp for report headers. */
export function timeStamp(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
