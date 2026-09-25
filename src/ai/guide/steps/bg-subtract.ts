/**
 * bg-subtract.ts — Guided tour for background subtraction.
 * View reports: filesCount, phase, extras.hasBackground, extras.hasOutputDir.
 */

import type { GuideDefinition } from '../types'

export const BG_SUBTRACT_GUIDE: GuideDefinition = {
  routeName: 'bg-subtract',
  title: { zh: '背景扣除', en: 'Background Subtraction' },
  steps: [
    {
      id: 'files',
      aiId: 'bg:files',
      title: { zh: '选择样品数据', en: 'Pick sample data' },
      tip: {
        zh: '选择样品衍射图（可多选或按文件夹批量）',
        en: 'Pick sample diffraction images (multi-select or batch by folder)',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'background',
      aiId: 'bg:background',
      title: { zh: '选择背景文件', en: 'Pick the background file' },
      tip: {
        zh: '选择空样品池/溶剂背景测量；透过率可手动或按电离室匹配',
        en: 'Pick the empty-cell/solvent background; transmission can be manual or ionchamber-matched',
      },
      done: (s) => s?.extras?.hasBackground === true,
    },
    {
      id: 'run',
      aiId: 'bg:run',
      title: { zh: '执行扣除', en: 'Subtract' },
      tip: {
        zh: '样品与背景就绪即可执行；批量模式会写入输出目录',
        en: 'Run once sample & background are ready; batch mode writes into the output folder',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'review',
      title: { zh: '核对扣除结果', en: 'Review the result' },
      tip: {
        zh: '对比扣除前后的预览与统计量，确认低 q 区背景已被压低',
        en: 'Compare before/after previews and stats; the low-q background should drop',
      },
      done: (s) => s?.phase === 'done',
    },
  ],
}
