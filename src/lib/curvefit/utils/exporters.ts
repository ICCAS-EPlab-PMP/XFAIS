/**
 * Export builders (CSV / TXT) — pure text composition over store state.
 * PNG export lives in the plot controller; file delivery via platform layer.
 */
import type { PeakResult } from '@/lib/pwcore/shared/types'
import { BASELINE_FN_MAP, PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { platform } from '../platform/platform'
import { useSpectrum } from '../stores/spectrum'
import { usePeaks } from '../stores/peaks'
import { useFit } from '../stores/fit'
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

/** Data + model CSV: x, y, weight, mask, fit, baseline, residual. */
export function buildDataFitCsv(): string {
  const sp = useSpectrum()
  const fit = useFit()
  const xv = sp.x.value
  const yv = sp.y.value
  const wv = sp.w.value
  const mv = sp.mask.value
  const curves = fit.curves.value
  if (!xv || !yv || !mv) return ''
  const head = ['x', 'y', 'weight', 'included', 'fit', 'baseline', 'residual']
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
      ].join(','),
    )
  }
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
