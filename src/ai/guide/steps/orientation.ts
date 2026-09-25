/**
 * orientation.ts — Guided tour for polymer orientation analysis.
 * View reports: filesCount, hasPoni, phase (derived), extras.exported.
 */

import type { GuideDefinition } from '../types'

export const ORIENTATION_GUIDE: GuideDefinition = {
  routeName: 'orientation-analysis',
  title: { zh: '取向度分析', en: 'Orientation Analysis' },
  steps: [
    {
      id: 'files',
      aiId: 'orientation:files',
      title: { zh: '选择数据文件', en: 'Pick data files' },
      tip: {
        zh: '同一实验条件的多张图可批量；也可切换为直接导入 I(χ) 曲线',
        en: 'Multi-file batch under identical conditions; or switch to importing I(χ) curves directly',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'geometry',
      aiId: 'orientation:geometry',
      title: { zh: '设置几何（PONI）', en: 'Set geometry (PONI)' },
      tip: {
        zh: '图像模式必须提供几何（展开几何/手动参数），并选择分析方法（Hermans/FWHM/Wilchinsky）',
        en: 'Image mode requires geometry; also pick the method(s) (Hermans/FWHM/Wilchinsky)',
      },
      done: (s) => s?.hasPoni === true,
    },
    {
      id: 'run',
      aiId: 'orientation:run',
      title: { zh: '运行分析', en: 'Run analysis' },
      tip: {
        zh: '批量运行会依次处理全部文件并汇总取向参数',
        en: 'Batch run processes every file and summarizes the orientation parameters',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'export',
      aiId: 'orientation:export',
      title: { zh: '导出结果', en: 'Export results' },
      tip: {
        zh: '导出取向参数 CSV（批量时为汇总表）',
        en: 'Export the orientation parameters as CSV (batch summary when multi-file)',
      },
      done: (s) => s?.extras?.exported === true,
    },
  ],
}
