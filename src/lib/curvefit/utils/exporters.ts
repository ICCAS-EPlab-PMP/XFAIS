/**
 * Export builders (CSV / TXT) — pure text composition over store state.
 * PNG export lives in the plot controller; file delivery via platform layer.
 */
import type { PeakResult } from '@/lib/pwcore/shared/types'
import { BASELINE_FN_MAP, PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { evalModelCurve } from '@/lib/fitEngine'
import { platform } from '../platform/platform'
import { useSpectrum } from '../stores/spectrum'
import { usePeaks } from '../stores/peaks'
import { useFit } from '../stores/fit'
import { useBatch } from '../stores/batch'
import { csvEscape, fmtMs, fmtSci, fmtSig, timeStamp } from '../utils/format'

/** Parameter CSV: one row per (peak, parameter). */
export function buildPeakParamsCsv(): string {
  const pk = usePeaks()
  const fit = useFit()
  const rows: string[] = []
  rows.push(['peak', 'fn', 'param', 'value', 'stderr', 'locked', 'area', 'fwhm', 'height', 'center'].join(','))
  pk.list.value.forEach((p, i) => {
    const meta = PEAK_FN_MAP.get(p.fn)
    const res: PeakResult | undefined = pk.resultById.value.get(p.id)
    for (const pm of meta?.params ?? []) {
      rows.push(
        [
          i + 1,
          meta?.name ?? p.fn,
          pm.key,
          fmtSig(p.p[pm.key] ?? 0, 10),
          res ? fmtSig(res.pErr[pm.key] ?? 0, 6) : '',
          p.locked[pm.key] ? 'yes' : 'no',
          res ? fmtSig(res.area, 10) : '',
          res ? fmtSig(res.fwhm, 10) : '',
          res ? fmtSig(res.height, 10) : '',
          res ? fmtSig(res.center, 10) : '',
        ]
          .map(csvEscape)
          .join(','),
      )
    }
  })
  const s = fit.lastStats.value
  // Background (baseline) parameters — fitted alongside the peaks.
  const bl = pk.baseline
  const blMeta = BASELINE_FN_MAP.get(bl.fn)
  const blRes = fit.lastResult.value
  if (bl.fn !== 'none' && blMeta) {
    for (const pm of blMeta.params) {
      rows.push(
        [
          'baseline',
          blMeta.name,
          pm.key,
          fmtSig(bl.p[pm.key] ?? 0, 10),
          blRes ? fmtSig(blRes.baselineErr[pm.key] ?? 0, 6) : '',
          bl.locked[pm.key] ? 'yes' : 'no',
          '',
          '',
          '',
          '',
        ]
          .map(csvEscape)
          .join(','),
      )
    }
  }
  rows.push('')
  if (s) {
    rows.push(`# r2,${fmtSig(s.r2, 10)}`)
    rows.push(`# r2adj,${fmtSig(s.r2Adj, 10)}`)
    rows.push(`# fitStdErr,${fmtSig(s.fitStdErr, 10)}`)
    rows.push(`# sse,${fmtSig(s.sse, 10)}`)
    rows.push(`# dof,${s.dof}`)
    rows.push(`# iterations,${s.iterations}`)
    rows.push(`# timeMs,${Math.round(s.timeMs)}`)
  }
  return rows.join('\r\n')
}

/** Data + model CSV: x, y, weight, mask, fit, baseline, residual + EVERY
 * fitted component curve (v0.3.4, 2026-10-22 user report: the export did not
 * carry all fitted curve x/y — the per-peak components were missing).
 * 数据+拟合 CSV：在原有列之外补上每个拟合分量的完整 x/y 曲线列。 */
export function buildDataFitCsv(): string {
  const sp = useSpectrum()
  const fit = useFit()
  const xv = sp.x.value
  const yv = sp.y.value
  const wv = sp.w.value
  const mv = sp.mask.value
  const curves = fit.curves.value
  if (!xv || !yv || !mv) return ''
  // Component curves come from the last fit RESULT (aligned with its enabled
  // peak order); they are full-length like x, so the columns line up.
  const lastRes = fit.lastResult.value
  const comps = lastRes?.yComps ?? []
  const head = [
    'x',
    'y',
    'weight',
    'included',
    'fit',
    'baseline',
    'residual',
    ...comps.map((_, i) => `p${i + 1}`),
  ]
  const rows: string[] = [head.join(',')]
  for (let i = 0; i < xv.length; i++) {
    rows.push(
      [
        fmtSig(xv[i], 12),
        fmtSig(yv[i], 12),
        wv ? fmtSig(wv[i], 10) : '',
        mv[i] === 1 ? '1' : '0',
        curves ? fmtSig(curves.yFit[i] ?? Number.NaN, 12) : '',
        curves ? fmtSig(curves.yBase[i] ?? Number.NaN, 12) : '',
        curves ? fmtSig(curves.residual[i] ?? Number.NaN, 12) : '',
        ...comps.map((c) => fmtSig(c[i] ?? Number.NaN, 12)),
      ].join(','),
    )
  }
  if (comps.length > 0 && lastRes) {
    rows.push('')
    lastRes.peaks.forEach((r, i) => {
      rows.push(`# p${i + 1}=${PEAK_FN_MAP.get(r.fn)?.name ?? r.fn} center=${fmtSig(r.center, 10)}`)
    })
  }
  return rows.join('\r\n')
}

/**
 * Fitted-curve CSV (v0.3.4, 2026-10-22 user report: 「拟合的曲线数据不能导
 * 出」): the model evaluated on a DENSE uniform grid over the full x range —
 * baseline, every enabled component and the total, using the CURRENT (post
 * fit) parameters. x resolution: at least the data grid, capped for file size.
 * 拟合曲线 CSV（密采样）：当前模型（拟合后的参数）在全程均匀密网格上的
 * 基线、逐分量与总曲线。
 */
export function buildFitCurveCsv(): string {
  const sp = useSpectrum()
  const pk = usePeaks()
  const xv = sp.x.value
  if (!xv || xv.length < 2) return ''
  const enabled = pk.list.value.filter((p) => p.enabled)
  const useBase = pk.baseline.enabled && pk.baseline.fn !== 'none'
  if (enabled.length === 0 && !useBase) return ''

  const n = Math.min(20000, Math.max(2000, xv.length))
  const x0 = sp.meta.xMin
  const x1 = sp.meta.xMax
  const xs = new Float64Array(n)
  for (let i = 0; i < n; i++) xs[i] = x0 + ((x1 - x0) * i) / (n - 1)

  const model = evalModelCurve(xs, pk.list.value, {
    fn: pk.baseline.fn,
    p: { ...pk.baseline.p },
    locked: { ...pk.baseline.locked },
    enabled: useBase,
  })
  const head = ['x', 'baseline', ...model.comps.map((_, i) => `p${i + 1}`), 'model']
  const rows: string[] = [head.join(',')]
  for (let i = 0; i < n; i++) {
    rows.push(
      [
        fmtSig(xs[i], 12),
        fmtSig(model.base[i], 12),
        ...model.comps.map((c) => fmtSig(c[i], 12)),
        fmtSig(model.total[i], 12),
      ].join(','),
    )
  }
  rows.push('')
  rows.push(`# source=${sp.meta.title} points=${n} range=[${fmtSig(x0, 8)}, ${fmtSig(x1, 8)}]`)
  model.compsIds.forEach((id, i) => {
    const spec = pk.list.value.find((p) => p.id === id)
    if (spec) {
      rows.push(
        `# p${i + 1}=${PEAK_FN_MAP.get(spec.fn)?.name ?? spec.fn} center=${fmtSig(spec.p.a1 ?? 0, 10)}`,
      )
    }
  })
  return rows.join('\r\n')
}

/** Human-readable analysis report. */
export function buildReportTxt(): string {
  const sp = useSpectrum()
  const pk = usePeaks()
  const fit = useFit()
  const s = fit.lastStats.value
  const lines: string[] = []
  lines.push('PeakWorkbench 谱峰工作台 — 拟合报告')
  lines.push('='.repeat(56))
  lines.push(`数据: ${sp.meta.title}`)
  lines.push(`时间: ${timeStamp()}`)
  lines.push(`点数: ${sp.meta.n}（参与拟合 ${s ? s.n : sp.meta.n - sp.meta.excluded}，排除 ${sp.meta.excluded}）`)
  lines.push(`峰函数: ${pk.list.value.map((p) => PEAK_FN_MAP.get(p.fn)?.name ?? p.fn).join(', ') || '—'}`)
  lines.push(`基线: ${pk.baseline.fn} (enabled=${pk.baseline.enabled})`)
  lines.push(`选项: maxIter=${fit.options.maxIter} convDigits=${fit.options.convDigits} robust=${fit.options.robust} fitExtent=1/${fit.options.fitExtent}`)
  lines.push('')
  if (s) {
    lines.push('统计')
    lines.push('-'.repeat(56))
    const row = (k: string, v: string): string => `  ${k.padEnd(18)}${v}`
    lines.push(row('R²', fmtSig(s.r2, 8)))
    lines.push(row('调整 R²', fmtSig(s.r2Adj, 8)))
    lines.push(row('Fit Std Err', fmtSig(s.fitStdErr, 8)))
    lines.push(row('F 值', fmtSig(s.fValue, 8)))
    lines.push(row('SSE', fmtSci(s.sse, 6)))
    lines.push(row('自由度 DOF', String(s.dof)))
    lines.push(row('迭代 / FnEval', `${s.iterations} / ${s.fnEval}`))
    lines.push(row('耗时', fmtMs(s.timeMs)))
    lines.push(row('收敛', s.converged ? (s.stopped ? '用户停止（当前最优）' : '是') : '达到迭代上限'))
    lines.push(row('约束违约', String(s.violFinal)))
    lines.push('')
  }
  lines.push('峰参数')
  lines.push('-'.repeat(56))
  pk.list.value.forEach((p, i) => {
    const meta = PEAK_FN_MAP.get(p.fn)
    const res = pk.resultById.value.get(p.id)
    lines.push(`[${i + 1}] ${meta?.name ?? p.fn}  color=${p.color ?? ''}  ${p.enabled ? 'enabled' : 'DISABLED'}`)
    for (const pm of meta?.params ?? []) {
      const err = res?.pErr[pm.key]
      lines.push(
        `    ${pm.key.padEnd(3)} ${pm.label.padEnd(12)} ${fmtSig(p.p[pm.key] ?? 0, 10).padStart(14)}` +
          (err !== undefined ? ` ± ${fmtSig(err, 6)}` : '') +
          (p.locked[pm.key] ? '  [locked]' : ''),
      )
    }
    if (res) {
      lines.push(`    area=${fmtSig(res.area, 10)}  fwhm=${fmtSig(res.fwhm, 10)}  height=${fmtSig(res.height, 10)}  center=${fmtSig(res.center, 10)}`)
    }
    lines.push('')
  })
  // Background (baseline) parameters
  const bl = pk.baseline
  const blMeta = BASELINE_FN_MAP.get(bl.fn)
  if (bl.fn !== 'none' && blMeta) {
    const blRes = fit.lastResult.value
    lines.push(`基线参数 (${blMeta.name}${bl.enabled ? '' : ' — 未参与拟合'})`)
    lines.push('-'.repeat(56))
    for (const pm of blMeta.params) {
      const err = blRes?.baselineErr[pm.key]
      lines.push(
        `    ${pm.key.padEnd(3)} ${pm.label.padEnd(12)} ${fmtSig(bl.p[pm.key] ?? 0, 10).padStart(14)}` +
          (err !== undefined ? ` ± ${fmtSig(err, 6)}` : '') +
          (bl.locked[pm.key] ? '  [locked]' : ''),
      )
    }
    lines.push('')
  }
  return lines.join('\r\n')
}

/** Save text through the platform layer. */
export async function saveTextFile(defaultName: string, content: string): Promise<boolean> {
  return platform.saveDataFile(defaultName, content)
}

// ---------------------------------------------------------------------------
// Batch fitting exports (v0.3.4, 2026-10-22) / 批量拟合导出
// ---------------------------------------------------------------------------

/**
 * Batch summary CSV: one row per (file, peak) with center/height/FWHM/area
 * (± stderr) and the per-file fit stats repeated on every row (spreadsheet
 * friendly). Failed files get a single row with their error.
 * 批量汇总 CSV：每（文件×峰）一行，含参数±标准误；每行重复该文件的拟合
 * 统计（便于筛选透视）。失败文件占一行错误信息。
 */
export function buildBatchSummaryCsv(): string {
  const batch = useBatch()
  const rs = batch.results.value
  if (!rs || rs.length === 0) return ''
  const head = [
    'file',
    'peak',
    'fn',
    'center',
    'center_err',
    'height',
    'height_err',
    'fwhm',
    'area',
    'r2',
    'r2_adj',
    'iterations',
    'converged',
    'time_ms',
    'status',
  ]
  const rows: string[] = [`# 批量拟合报告 ${timeStamp()}`]
  rows.push(`# 峰位软约束 ±${batch.batchOpts.centerPct}% · 幅值自由 · 背景与数据窗口同模板`)
  rows.push(head.join(','))
  for (const r of rs) {
    const stat = [
      r.r2 !== undefined ? fmtSig(r.r2, 8) : '',
      r.r2Adj !== undefined ? fmtSig(r.r2Adj, 8) : '',
      r.iterations ?? '',
      r.converged === undefined ? '' : r.converged ? 'yes' : 'no',
      r.timeMs !== undefined ? Math.round(r.timeMs) : '',
      r.status,
    ]
    if (r.status === 'done' && r.peaks) {
      r.peaks.forEach((p) => {
        rows.push(
          [
            r.name,
            p.index,
            csvEscape(p.fnName),
            fmtSig(p.center, 10),
            fmtSig(p.centerErr, 6),
            fmtSig(p.height, 10),
            fmtSig(p.heightErr, 6),
            fmtSig(p.fwhm, 10),
            fmtSig(p.area, 10),
            ...stat,
          ].join(','),
        )
      })
    } else {
      rows.push(
        [r.name, '', '', '', '', '', '', '', '', '', '', '', '', '', csvEscape(r.error ?? r.status)].join(','),
      )
    }
  }
  return rows.join('\r\n')
}

/**
 * Batch curves CSV: stacked data+fit blocks for every file that kept its
 * curves (file column included; component columns omitted — see
 * buildBatchSummaryCsv for parameters). / 批量曲线 CSV：每条保留曲线的
 * 数据+拟合堆叠输出（含文件列）。
 */
export function buildBatchCurvesCsv(): string {
  const batch = useBatch()
  const rs = batch.results.value
  if (!rs) return ''
  const rows: string[] = ['file,x,y,included,fit,baseline,residual']
  let any = false
  for (const r of rs) {
    const c = r.curves
    if (!c) continue
    any = true
    for (let i = 0; i < c.x.length; i++) {
      rows.push(
        [
          csvEscape(r.name),
          fmtSig(c.x[i], 12),
          fmtSig(c.y[i], 12),
          c.mask[i] === 1 ? '1' : '0',
          fmtSig(c.yFit[i] ?? Number.NaN, 12),
          fmtSig(c.yBase[i] ?? Number.NaN, 12),
          fmtSig(c.residual[i] ?? Number.NaN, 12),
        ].join(','),
      )
    }
  }
  if (!any) return ''
  return rows.join('\r\n')
}
