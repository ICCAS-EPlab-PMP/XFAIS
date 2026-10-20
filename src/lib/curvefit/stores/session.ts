/**
 * Session-level data lifecycle shared by the toolbar and the empty state:
 * import / demo loading always performs a full session reset (peaks, results,
 * history cleared; baseline re-seeded against the new data).
 */
import type { DemoKind } from '@/lib/pwcore/shared/types'
import { platform } from '../platform/platform'
import { loadDemo, loadParsed, useSpectrum } from '../stores/spectrum'
import { makeDemoData, parseData } from '../core-bridge/engine'
import { clearPeaks, clearResults, resetBaselineForData } from '../stores/peaks'
import { resetFitState } from '../stores/fit'
import { clearHistory } from '../stores/undo'
import { useUi } from '../stores/ui'
import { pushToast } from '../stores/toast'
import { resetAnalysisState } from '../utils/analysis'

// X-FAIS (2026-10-20, user request: the reference's chromatography/Raman/XPS
// demos are irrelevant here) — the toolbar lists X-RAY demos only. X-FAIS
// 分叉（2026-10-20 用户要求：参考程序的色谱/拉曼/XPS 示例与本领域无关）——
// 工具栏只列 X 射线示例（原三套仍保留在 pwcore 中供测试用）。
export const DEMO_LABELS: { id: string; label: string; kind: DemoKind }[] = [
  { id: 'waxsPP', label: '聚丙烯 WAXS（α + β(300) + 非晶晕）', kind: 'waxsPP' },
  { id: 'azimuth', label: '取向 I(χ)（赤道弧对）', kind: 'azimuth' },
]

function adoptNewData(): void {
  const sp = useSpectrum()
  const ui = useUi()
  clearPeaks()
  clearResults()
  resetFitState()
  clearHistory()
  // X-ray analysis assignments (crystallinity roles / Kβ mapping) refer to
  // peak ids — reset them with the session. / X 射线分析指派（结晶度角色/
  // Kβ 映射）引用峰 id——随会话一并重置。
  resetAnalysisState()
  resetBaselineForData(sp.meta.xMin, sp.meta.xMax, sp.meta.yMin + (sp.meta.yMax - sp.meta.yMin) * 0.02)
  ui.step.value = 'baseline'
  ui.subtractPreview.value = false
  ui.popover.value = null
}

/** Open a data file through the platform layer and adopt it. */
export async function importFromPlatform(): Promise<void> {
  const file = await platform.openDataFile()
  if (!file) return
  try {
    const text = typeof file.data === 'string' ? file.data : new TextDecoder().decode(file.data)
    const parsed = parseData(text, file.name)
    if (parsed.x.length < 2) throw new Error('有效数据点不足')
    loadParsed(parsed, file.name)
    adoptNewData()
    pushToast('success', `已导入 ${parsed.x.length} 个数据点`)
  } catch (err) {
    pushToast('error', `导入失败：${err instanceof Error ? err.message : String(err)}`)
  }
}

/**
 * Import xy text pasted into the DataPanel textarea.
 * A successful load bumps `dataVersion`, which lets the caller detect success
 * (and clear the input) without changing this function's void signature.
 */
export function importFromText(text: string, name = '粘贴数据'): void {
  try {
    const parsed = parseData(text, name)
    if (parsed.x.length < 2) throw new Error('有效数据点不足')
    loadParsed(parsed, name)
    adoptNewData()
    pushToast('success', `已导入 ${parsed.x.length} 个数据点`)
  } catch (err) {
    pushToast('error', `解析失败：${err instanceof Error ? err.message : String(err)}`)
  }
}

/** Load a built-in demo dataset. */
export function loadDemoSet(id: string): void {
  const d = DEMO_LABELS.find((x) => x.id === id)
  const kind: DemoKind = d ? d.kind : 'chrom'
  const label = d ? d.label.split('（')[0] : '示例'
  try {
    const demo = makeDemoData(kind)
    loadDemo(demo, `示例 · ${label}`)
    adoptNewData()
    pushToast('success', `已加载示例：${demo.title}（${demo.x.length} 点）`)
  } catch (err) {
    pushToast('error', `示例加载失败：${err instanceof Error ? err.message : String(err)}`)
  }
}
