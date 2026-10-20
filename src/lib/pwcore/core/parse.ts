/**
 * Data-file parsing and PRN generation (pure; no fs/DOM).
 *
 * PRN (the reference application native ASCII), per manual p.77:
 *   line 1: main title
 *   line 2: X title
 *   line 3: Y title
 *   data:   "X Y" whitespace-separated, sorted by X ascending
 *           optional "W<weight>" immediately after Y (no space)
 *           trailing "*" marks an excluded point
 *
 * The SCN reader handles both a generic "typed double array" layout and the
 * the reference application 4 scene layout found in the shipped samples. The shipped .scn
 * files contain a table of four-parameter peak records
 * [amplitude, center, width1, width2] rather than a raw point array; for
 * those the scan curve is reconstructed as a sum of Voigt components so the
 * sample remains usable as a demonstration data set. If a future file does
 * contain raw X/Y arrays, the generic scanner extracts them directly.
 */
import type { ParsedData } from '../shared/types'
import { faddeevaRe } from './special'

export interface BuildPrnOptions {
  /** Significant digits per number. Default 17 (exact double round-trip). */
  precision?: number
  xTitle?: string
  yTitle?: string
  /** Per-point weights; when omitted no W column is written. */
  w?: Float64Array | null
  /** 1 = included, 0 = excluded (writes a trailing '*'). */
  mask?: Uint8Array | null
}

function titleLine(s: string): string {
  const t = s.replace(/\r?\n/g, ' ')
  if (/^[+-]?\d/.test(t)) return `"${t.replace(/"/g, '""')}"`
  return t
}

function formatNumber(v: number, precision: number): string {
  if (!Number.isFinite(v)) return '0'
  const p = Math.max(1, Math.min(21, Math.floor(precision)))
  return v.toPrecision(p)
}

/**
 * Serialize X/Y (and optional weights/mask) as a the reference application-style .PRN text.
 * Default precision is 17 significant digits so that parse(build(x)) returns
 * the identical doubles; pass `precision: 15` to mimic the original 15-digit
 * writer when bit-exact round-tripping is not required.
 */
export function buildPrn(
  x: Float64Array,
  y: Float64Array,
  title: string,
  opts: BuildPrnOptions = {}
): string {
  const n = Math.min(x.length, y.length)
  const precision = opts.precision ?? 17
  const lines: string[] = [
    titleLine(title || 'the reference application Data'),
    titleLine(opts.xTitle ?? 'X'),
    titleLine(opts.yTitle ?? 'Y')
  ]
  const w = opts.w && opts.w.length >= n ? opts.w : null
  const mask = opts.mask && opts.mask.length >= n ? opts.mask : null
  for (let i = 0; i < n; i += 1) {
    let line = `${formatNumber(x[i], precision)} ${formatNumber(y[i], precision)}`
    if (w) line += ` W${formatNumber(w[i], precision)}`
    if (mask && mask[i] === 0) line += '*'
    lines.push(line)
  }
  return lines.join('\n')
}

function stripBom(s: string): string {
  return s.charCodeAt(0) === 0xfeff ? s.slice(1) : s
}

function unquoteTitle(s: string): string {
  const t = s.trim()
  if (t.length >= 2 && t.startsWith('"') && t.endsWith('"')) {
    return t.slice(1, -1).replace(/""/g, '"')
  }
  return t
}

function numericTokens(line: string): string[] {
  return line.trim().split(/\s+/).filter((s) => s.length > 0)
}

function isNumericToken(t: string): boolean {
  if (t.length === 0) return false
  const s = t.endsWith('*') ? t.slice(0, -1) : t
  return /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(s)
}

function looksLikeData(line: string): boolean {
  const t = numericTokens(line)
  return t.length >= 2 && isNumericToken(t[0]) && isNumericToken(t[1])
}

/**
 * Parse a the reference application ASCII .PRN file (also accepts headerless whitespace data).
 */
export function parsePrn(text: string): ParsedData {
  const rawLines = stripBom(text).replace(/\r\n?/g, '\n').split('\n')
  let first = 0
  while (
    first < rawLines.length &&
    (rawLines[first].trim().length === 0 || /^\s*#/.test(rawLines[first]))
  ) {
    first += 1
  }
  if (first >= rawLines.length) {
    return {
      title: '',
      x: new Float64Array(0),
      y: new Float64Array(0),
      w: null,
      mask: new Uint8Array(0)
    }
  }
  let start = first
  let title = ''
  if (!looksLikeData(rawLines[first])) {
    // Exactly three header lines (the reference application convention); empty title lines are
    // still part of the header block.
    title = unquoteTitle(rawLines[first])
    start = Math.min(first + 3, rawLines.length)
  }

  const xs: number[] = []
  const ys: number[] = []
  const ws: number[] = []
  const ms: number[] = []
  let anyWeight = false
  for (let i = start; i < rawLines.length; i += 1) {
    if (rawLines[i].trim().length === 0 || /^\s*#/.test(rawLines[i])) continue
    let line = rawLines[i].trim()
    let included = 1
    if (line.endsWith('*')) {
      included = 0
      line = line.slice(0, -1).trim()
    }
    const t = numericTokens(line)
    if (t.length < 2) continue
    if (!isNumericToken(t[0]) || !isNumericToken(t[1])) continue
    const xv = Number(t[0].replace(/\*$/, ''))
    const yv = Number(t[1].replace(/\*$/, ''))
    if (!Number.isFinite(xv) || !Number.isFinite(yv)) continue
    let weight = 1
    for (let k = 2; k < t.length; k += 1) {
      const tok = t[k]
      if (/^[wW]/.test(tok) && tok.length > 1) {
        const v = Number(tok.slice(1))
        if (Number.isFinite(v)) {
          weight = v
          anyWeight = true
        }
        break
      }
    }
    xs.push(xv)
    ys.push(yv)
    ws.push(weight)
    ms.push(included)
  }
  const n = xs.length
  const order = new Array<number>(n)
  for (let i = 0; i < n; i += 1) order[i] = i
  order.sort((a, b) => xs[a] - xs[b] || a - b)
  const x = new Float64Array(n)
  const y = new Float64Array(n)
  const mask = new Uint8Array(n)
  const w = anyWeight ? new Float64Array(n) : null
  for (let i = 0; i < n; i += 1) {
    const j = order[i]
    x[i] = xs[j]
    y[i] = ys[j]
    mask[i] = ms[j]
    if (w) w[i] = ws[j]
  }
  return { title, x, y, w, mask }
}

function splitCsvLine(line: string, delim: string): string[] {
  if (delim === '') return numericTokens(line)
  const out: string[] = []
  let cur = ''
  let quoted = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"'
          i += 1
        } else quoted = false
      } else cur += ch
    } else if (ch === '"') {
      quoted = true
    } else if (ch === delim) {
      out.push(cur.trim())
      cur = ''
    } else {
      cur += ch
    }
  }
  out.push(cur.trim())
  return out
}

function detectDelimiter(lines: string[]): string {
  for (const line of lines) {
    if (line.includes(',')) return ','
    if (line.includes('\t')) return '\t'
    if (line.includes(';')) return ';'
    if (numericTokens(line).length >= 2) return ''
  }
  return ''
}

/** Parse a CSV / TSV / semicolon-delimited text file into X,Y columns. */
export function parseCsv(text: string): ParsedData {
  const raw = stripBom(text).replace(/\r\n?/g, '\n')
  const lines = raw.split('\n').filter((l) => l.trim().length > 0)
  if (lines.length === 0) {
    return {
      title: '',
      x: new Float64Array(0),
      y: new Float64Array(0),
      w: null,
      mask: new Uint8Array(0)
    }
  }
  const delim = detectDelimiter(lines)
  const rows = lines.map((l) => splitCsvLine(l, delim))
  // Locate the first row with at least two numeric fields and use the first
  // two numeric columns. This tolerates both "x,y" and "label,x,y" layouts.
  let start = -1
  let colX = 0
  let colY = 1
  for (let i = 0; i < rows.length; i += 1) {
    const numeric: number[] = []
    for (let c = 0; c < rows[i].length; c += 1) {
      if (isNumericToken(rows[i][c])) numeric.push(c)
    }
    if (numeric.length >= 2) {
      start = i
      colX = numeric[0]
      colY = numeric[1]
      break
    }
  }
  const xs: number[] = []
  const ys: number[] = []
  if (start >= 0) {
    for (let i = start; i < rows.length; i += 1) {
      const f = rows[i]
      if (f.length <= Math.max(colX, colY)) continue
      if (!isNumericToken(f[colX]) || !isNumericToken(f[colY])) continue
      const xv = Number(f[colX])
      const yv = Number(f[colY])
      if (Number.isFinite(xv) && Number.isFinite(yv)) {
        xs.push(xv)
        ys.push(yv)
      }
    }
  }
  const n = xs.length
  const order = new Array<number>(n)
  for (let i = 0; i < n; i += 1) order[i] = i
  order.sort((a, b) => xs[a] - xs[b] || a - b)
  const x = new Float64Array(n)
  const y = new Float64Array(n)
  const mask = new Uint8Array(n)
  mask.fill(1)
  for (let i = 0; i < n; i += 1) {
    const j = order[i]
    x[i] = xs[j]
    y[i] = ys[j]
  }
  const title = start > 0 ? splitCsvLine(lines[0], delim)[0] ?? '' : ''
  return { title, x, y, w: null, mask }
}

// ---------------------------------------------------------------------------
// SCN
// ---------------------------------------------------------------------------

const SCN_MAGIC = 'PFWScan1'
/** Record stride observed in all shipped the reference application 4 scene samples. */
const SCN_RECORD_STRIDE = 0x158

interface PeakRecord {
  amplitude: number
  center: number
  width1: number
  width2: number
}

function readMagic(bytes: Uint8Array): string {
  if (bytes.length < 8) return ''
  let s = ''
  for (let i = 0; i < 8; i += 1) s += String.fromCharCode(bytes[i])
  return s
}

/** Try to find interleaved or split X/Y double arrays (generic layout). */
function scanDoubleArrays(bytes: Uint8Array, view: DataView): ParsedData | null {
  // Look for the typed-array tag 0x00 followed by a plausible count, then
  // `count` IEEE-754 little-endian doubles.
  for (let off = 8; off + 5 <= bytes.length; off += 1) {
    if (bytes[off] !== 0) continue
    const count = view.getUint32(off + 1, true)
    if (count < 8 || count > 200000) continue
    const dataStart = off + 5
    if (dataStart + count * 8 > bytes.length) continue
    const vals = new Float64Array(count)
    let finite = true
    for (let i = 0; i < count; i += 1) {
      const v = view.getFloat64(dataStart + i * 8, true)
      if (!Number.isFinite(v)) {
        finite = false
        break
      }
      vals[i] = v
    }
    if (!finite) continue

    // Layout A: interleaved (x, y) pairs.
    if (count >= 8 && count % 2 === 0) {
      const half = count / 2
      let ok = true
      for (let i = 1; i < half; i += 1) {
        if (!(vals[2 * i] > vals[2 * (i - 1)])) {
          ok = false
          break
        }
      }
      if (ok) {
        const x = new Float64Array(half)
        const y = new Float64Array(half)
        for (let i = 0; i < half; i += 1) {
          x[i] = vals[2 * i]
          y[i] = vals[2 * i + 1]
        }
        const mask = new Uint8Array(half)
        mask.fill(1)
        return { title: 'the reference application scan', x, y, w: null, mask }
      }
    }
    // Layout B: first half X, second half Y.
    {
      const half = Math.floor(count / 2)
      let ok = true
      for (let i = 1; i < half; i += 1) {
        if (!(vals[half + i] >= vals[half + i - 1])) {
          ok = false
          break
        }
      }
      if (ok && half >= 4) {
        // X may be either half; choose the one that looks like an axis.
        for (let which = 0; which < 2 && ok; which += 1) {
          const xo = which === 0 ? 0 : half
          const yo = which === 0 ? half : 0
          let mono = true
          for (let i = 1; i < half; i += 1) {
            if (!(vals[xo + i] > vals[xo + i - 1])) {
              mono = false
              break
            }
          }
          if (mono) {
            const x = new Float64Array(half)
            const y = new Float64Array(half)
            for (let i = 0; i < half; i += 1) {
              x[i] = vals[xo + i]
              y[i] = vals[yo + i]
            }
            const mask = new Uint8Array(half)
            mask.fill(1)
            return { title: 'the reference application scan', x, y, w: null, mask }
          }
        }
      }
    }
  }
  return null
}

/** Extract the 4-double peak records of the shipped scene files. */
function scanPeakRecords(bytes: Uint8Array, view: DataView): PeakRecord[] {
  const candidates: number[] = []
  for (let off = 8; off + 5 + 32 <= bytes.length; off += 1) {
    if (
      bytes[off] === 0 &&
      bytes[off + 1] === 4 &&
      bytes[off + 2] === 0 &&
      bytes[off + 3] === 0 &&
      bytes[off + 4] === 0
    ) {
      const a = view.getFloat64(off + 5, true)
      const c = view.getFloat64(off + 13, true)
      const w1 = view.getFloat64(off + 21, true)
      const w2 = view.getFloat64(off + 29, true)
      if (
        Number.isFinite(a) &&
        Number.isFinite(c) &&
        Number.isFinite(w1) &&
        Number.isFinite(w2) &&
        Math.abs(a) < 1e15 &&
        Math.abs(c) < 1e12 &&
        Math.abs(w1) > 1e-12 &&
        Math.abs(w1) < 1e9 &&
        Math.abs(w2) < 1e9 &&
        Math.abs(a) + Math.abs(c) > 0
      ) {
        candidates.push(off)
      }
    }
  }
  if (candidates.length === 0) return []

  // Keep candidates lying on the dominant 0x158 lattice (all shipped
  // samples use it); fall back to the most common pairwise difference.
  const groups = new Map<number, number[]>()
  for (const off of candidates) {
    const key = off % SCN_RECORD_STRIDE
    const arr = groups.get(key)
    if (arr) arr.push(off)
    else groups.set(key, [off])
  }
  let bestGroup: number[] = []
  for (const arr of groups.values()) {
    if (arr.length > bestGroup.length) bestGroup = arr
  }
  let chosen = bestGroup
  if (chosen.length < 2) {
    const diffs = new Map<number, number>()
    for (let i = 0; i < candidates.length; i += 1) {
      for (let j = i + 1; j < candidates.length; j += 1) {
        const d = Math.abs(candidates[j] - candidates[i])
        if (d >= 40) diffs.set(d, (diffs.get(d) ?? 0) + 1)
      }
    }
    let stride = 0
    let count = 0
    for (const [d, c] of diffs) {
      if (c > count) {
        stride = d
        count = c
      }
    }
    if (stride > 0) {
      const sorted = candidates.slice().sort((a, b) => a - b)
      const byResidue = new Map<number, number[]>()
      for (const off of sorted) {
        const key = off % stride
        const arr = byResidue.get(key)
        if (arr) arr.push(off)
        else byResidue.set(key, [off])
      }
      for (const arr of byResidue.values()) {
        if (arr.length > chosen.length) chosen = arr
      }
    }
  }

  const out: PeakRecord[] = []
  for (const off of chosen) {
    const a = view.getFloat64(off + 5, true)
    const c = view.getFloat64(off + 13, true)
    const w1 = view.getFloat64(off + 21, true)
    const w2 = view.getFloat64(off + 29, true)
    if (Math.abs(a) < 1e-12 && Math.abs(c) < 1e-12) continue
    out.push({ amplitude: a, center: c, width1: w1, width2: w2 })
  }
  return out
}

/**
 * Reconstruct a scan curve from a the reference application scene peak table.
 * Each record is interpreted as [amplitude, center, gaussian width,
 * lorentzian width] and rendered as a Voigt component.
 */
function synthesizeFromRecords(records: PeakRecord[]): ParsedData {
  let cMin = Number.POSITIVE_INFINITY
  let cMax = Number.NEGATIVE_INFINITY
  let wMin = Number.POSITIVE_INFINITY
  let wMax = 0
  for (const r of records) {
    cMin = Math.min(cMin, r.center)
    cMax = Math.max(cMax, r.center)
    const w1 = Math.abs(r.width1)
    const w2 = Math.abs(r.width2)
    wMin = Math.min(wMin, w1 > 0 ? w1 : w2)
    wMax = Math.max(wMax, w1, w2)
  }
  if (!Number.isFinite(cMin) || !Number.isFinite(cMax)) {
    return {
      title: 'the reference application scan',
      x: new Float64Array(0),
      y: new Float64Array(0),
      w: null,
      mask: new Uint8Array(0)
    }
  }
  const span = Math.max(cMax - cMin, wMax * 8, 1)
  const pad = Math.max(wMax * 20, span * 0.02)
  const xMin = cMin - pad
  const xMax = cMax + pad
  const stepHint = wMin > 0 ? wMin / 6 : span / 1000
  let n = Math.ceil((xMax - xMin) / stepHint) + 1
  n = Math.max(600, Math.min(8000, n))
  const x = new Float64Array(n)
  const y = new Float64Array(n)
  const dx = n > 1 ? (xMax - xMin) / (n - 1) : 1
  for (let i = 0; i < n; i += 1) x[i] = xMin + i * dx
  for (const r of records) {
    const sig = Math.max(Math.abs(r.width1), 1e-12)
    const gam = Math.abs(r.width2)
    // Voigt (normalized to amplitude): use the model evaluator so the same
    // numerical path is exercised as in fitting.
    const comp = new Float64Array(4)
    comp[0] = r.amplitude
    comp[1] = r.center
    comp[2] = sig
    comp[3] = gam
    for (let i = 0; i < n; i += 1) {
      y[i] += voigtValue(comp, x[i])
    }
  }
  const mask = new Uint8Array(n)
  mask.fill(1)
  return {
    title: `the reference application scan (${records.length} peaks)`,
    x,
    y,
    w: null,
    mask
  }
}

/** Local, import-cycle-free equivalent of evalPeak('voigt') for SCN synthesis. */
function voigtValue(a: ArrayLike<number>, x: number): number {
  // Imported lazily at module scope would create a cycle with models.ts only
  // if models also imported parse.ts; it does not, so a static import would be
  // fine, but keeping the scene reconstruction self-contained avoids pulling
  // the full model registry into file parsing.
  return voigtPeak(a[0] ?? 0, a[1] ?? 0, a[2] ?? 0, a[3] ?? 0, x)
}

function voigtPeak(a0: number, a1: number, sigRaw: number, gamRaw: number, x: number): number {
  const sig = Math.max(Math.abs(sigRaw), 1e-12)
  const gam = Math.max(Math.abs(gamRaw), 0)
  const s2 = Math.SQRT2 * sig
  const zi = gam / s2
  const nr = faddeevaRe((x - a1) / s2, zi)
  const dr = faddeevaRe(0, zi)
  if (!(dr > 0) || !Number.isFinite(dr)) return 0
  const v = (a0 * nr) / dr
  return Number.isFinite(v) ? v : 0
}

/**
 * Parse a the reference application .scn scan file.
 * Accepts an ArrayBuffer, a Uint8Array view, or a Node Buffer.
 */
export function parseScn(input: ArrayBuffer | Uint8Array, title?: string): ParsedData {
  const bytes =
    input instanceof Uint8Array
      ? input
      : new Uint8Array(input)
  if (readMagic(bytes) !== SCN_MAGIC) {
    throw new Error('Not a the reference application scan file (missing PFWScan1 magic)')
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const generic = scanDoubleArrays(bytes, view)
  if (generic) {
    if (title) generic.title = title
    return generic
  }
  const records = scanPeakRecords(bytes, view)
  if (records.length > 0) {
    const parsed = synthesizeFromRecords(records)
    if (title) parsed.title = title
    return parsed
  }
  throw new Error('Unsupported .scn layout: no X/Y array or peak records found')
}

/**
 * Renderer-friendly text parser: `parseData(text, fileName?)`.
 * Equivalent to parseDataFile for text content (CSV vs PRN auto-detected).
 */
export function parseData(text: string, fileName = 'data.prn'): ParsedData {
  return parseDataFile(fileName, text)
}

/**
 * Dispatch on file name/content. Text data is parsed as CSV when a
 * comma/tab/semicolon delimiter is present, otherwise as the reference application PRN.
 */
export function parseDataFile(
  name: string,
  data: string | ArrayBuffer | Uint8Array
): ParsedData {
  const lower = name.toLowerCase()
  if (typeof data !== 'string') return parseScn(data, name)
  if (lower.endsWith('.scn')) {
    throw new Error('.scn data must be supplied as binary (ArrayBuffer/Uint8Array)')
  }
  const text = data
  if (lower.endsWith('.prn')) return parsePrn(text)
  if (lower.endsWith('.csv')) return parseCsv(text)
  if (/,|\t|;/.test(text.slice(0, 4000))) return parseCsv(text)
  return parsePrn(text)
}
