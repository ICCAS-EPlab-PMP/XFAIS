/**
 * lamellar.ts — Guided tour for SAXS lamellar analysis
 * (one-dimensional correlation function, Strobl–Schneider).
 * View reports: filesCount, hasPoni, phase (derived), extras.exported.
 */

import type { GuideDefinition } from '../types'

export const LAMELLAR_GUIDE: GuideDefinition = {
  routeName: 'lamellar-analysis',
  title: { zh: '片晶结构分析', en: 'Lamellar Analysis' },
  steps: [
    {
      id: 'files',
      aiId: 'lamellar:files',
      title: { zh: '选择数据', en: 'Pick data' },
      tip: {
        zh: '图像或 I(q) 曲线均可；曲线模式需 ≥8 个数据点',
        en: 'Images or I(q) curves both work; curve mode needs ≥8 points',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'geometry',
      aiId: 'lamellar:geometry',
      title: { zh: '设置几何与 q 窗口', en: 'Set geometry & q window' },
      tip: {
        zh: '图像模式需几何；设定 q 上下限（建议包含第一峰但避开光束挡块）',
        en: 'Image mode needs geometry; set q limits (include the first peak, avoid the beamstop)',
      },
      done: (s) => s?.hasPoni === true,
    },
    {
      id: 'run',
      aiId: 'lamellar:run',
      title: { zh: '运行相关函数管线', en: 'Run the correlation pipeline' },
      tip: {
        zh: '分步输出 I(q)→扣背景→q²I(q)→γ₁(x)；之后在图上两点切线拟合得长周期',
        en: 'Pipeline: I(q)→background→q²I(q)→γ₁(x); then fit the two-point tangent for the long period',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'export',
      aiId: 'lamellar:export',
      title: { zh: '导出结果', en: 'Export results' },
      tip: {
        zh: '导出各步曲线与长周期结果 CSV',
        en: 'Export the per-step curves and long-period results as CSV',
      },
      done: (s) => s?.extras?.exported === true,
    },
  ],
}
