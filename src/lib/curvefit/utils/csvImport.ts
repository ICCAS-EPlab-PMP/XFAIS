/**
 * X-FAIS 积分结果导入适配（2026-10-23 用户要求：衍射峰拟合要能导入 CSV，
 * 特别是积分结果）。
 *
 * 积分模块导出的 TXT/CSV（python/services/export_helper.py `to_txt`，csv 即
 * 制表符换逗号）长这样：
 * ```
 * # X_value unit: q (1/nm)
 * # <若干元信息行>
 * X_value,<曲线1列名>,<曲线2列名>,…
 * 1.234560e-01,3.141590,2.718280
 * …
 * ```
 * 通用 parseCsv 只会取「前两个数值列」——多曲线积分表只能拿到第一条。本模
 * 块把这类表展开成**每条强度列一条曲线**，正好衔接批量模式：首条作参考曲
 * 线、其余入队。另兼容 .xy 导出（两列一段、空行分段）：每段一条曲线。
 * 识别不了时返回 null，调用方回落到通用 parseData。
 */

/** One extracted curve (x shared with its siblings when from a table). /
 *  解析出的一条曲线。 */
export interface ParsedCurve {
  name: string
  x: Float64Array
  y: Float64Array
}

function stripBom(s: string): string {
  return s.charCodeAt(0) === 0xfeff ? s.slice(1) : s
}

function isNum(t: string): boolean {
  if (t.length === 0) return false
  return /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/.test(t)
}

function splitLine(line: string, delim: string): string[] {
  // Integration exports never quote fields; a simple split is faithful.
  return line.split(delim).map((f) => f.trim())
}

/**
 * Parse an X-FAIS integration TXT/CSV/XY export into one curve per intensity
 * column (XY: per blank-line block). Returns null when the text does not
 * match either shape — the caller then falls back to the generic parser.
 * 把 X-FAIS 积分导出展开为逐列曲线（XY 为逐段）；不匹配时返回 null。
 */
export function parseIntegrationTable(text: string, fileName: string): ParsedCurve[] | null {
  const raw = stripBom(text).replace(/\r\n?/g, '\n')
  const lines = raw.split('\n')
  const delim = raw.slice(0, 4000).includes('\t') ? '\t' : ','

  // First data row = first row whose first TWO cells are numeric. /
  // 首个数据行 = 前两个单元格均为数值的第一行。
  let firstData = -1
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim()
    if (!l || l.startsWith('#')) continue
    const f = splitLine(l, delim)
    if (f.length >= 2 && isNum(f[0]) && isNum(f[1])) {
      firstData = i
      break
    }
  }
  if (firstData < 0) return null

  // Column header = the last non-numeric, non-comment row ABOVE firstData. /
  // 列名行 = 首个数据行之上最后一条非注释非数值行。
  let headerRow: string[] | null = null
  for (let i = firstData - 1; i >= 0; i--) {
    const l = lines[i].trim()
    if (!l || l.startsWith('#')) continue
    const f = splitLine(l, delim)
    if (!isNum(f[0])) {
      headerRow = f
      break
    }
  }

  // Collect the numeric rows (a column count from the first data row). /
  // 收集数值行（列数以首个数据行为准）。
  const nCols = splitLine(lines[firstData].trim(), delim).length
  const xs: number[] = []
  const cols: number[][] = Array.from({ length: nCols }, () => [])
  for (let i = firstData; i < lines.length; i++) {
    const l = lines[i].trim()
    if (!l || l.startsWith('#')) continue
    const f = splitLine(l, delim)
    if (f.length < 2 || !isNum(f[0]) || !isNum(f[1])) continue
    xs.push(Number(f[0]))
    for (let c = 1; c < nCols; c++) {
      cols[c].push(c < f.length && isNum(f[c]) ? Number(f[c]) : Number.NaN)
    }
  }
  if (xs.length < 2 || nCols < 2) return null

  const base = fileName.replace(/\.(txt|csv|tsv|dat|xy)$/i, '')
  const curves: ParsedCurve[] = []
  for (let c = 1; c < nCols; c++) {
    const col = cols[c]
    // Drop all-NaN trailing columns produced by ragged rows. /
    // 丢弃因行参差产生的全 NaN 列。
    if (col.every((v) => !Number.isFinite(v))) continue
    const label = headerRow && headerRow[c] && !isNum(headerRow[c]) ? headerRow[c] : `#${c}`
    curves.push({
      name: nCols > 2 ? `${base} · ${label}` : base,
      x: Float64Array.from(xs),
      y: Float64Array.from(col),
    })
  }
  if (curves.length === 0) return null

  // Sanity gate: this must really be an integration TABLE. A generic 2-column
  // CSV also passes through here unchanged (single curve) — same outcome as
  // the fallback parser, so returning it is harmless and saves a re-parse.
  return curves
}

/**
 * Parse an .xy export (two columns per curve, blank line between curves) into
 * one curve per block. Null when the shape does not match. /
 * 解析 .xy 导出：空行分段，每段一条曲线；不匹配返回 null。
 */
export function parseXYBlocks(text: string, fileName: string): ParsedCurve[] | null {
  const raw = stripBom(text).replace(/\r\n?/g, '\n')
  const blocks = raw.split(/\n\s*\n/).map((b) => b.trim()).filter((b) => b.length > 0)
  if (blocks.length < 2) return null
  const base = fileName.replace(/\.xy$/i, '')
  const curves: ParsedCurve[] = []
  for (let b = 0; b < blocks.length; b++) {
    const xs: number[] = []
    const ys: number[] = []
    for (const line of blocks[b].split('\n')) {
      const f = line.trim().split(/[\t,;]+|\s+/).filter((t) => t.length > 0)
      if (f.length < 2 || !isNum(f[0]) || !isNum(f[1])) continue
      xs.push(Number(f[0]))
      ys.push(Number(f[1]))
    }
    if (xs.length < 2) continue
    curves.push({
      name: blocks.length > 1 ? `${base} · #${b + 1}` : base,
      x: Float64Array.from(xs),
      y: Float64Array.from(ys),
    })
  }
  return curves.length >= 2 ? curves : null
}
