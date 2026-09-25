/**
 * integrate-fiber.ts — Guided tour for the GIWAXS fiber 2D integration view.
 * View reports: filesCount, hasPoni, canRun, phase (derived; 'done' = preview
 * result ready). Fiber-specific rotation overrides live in the geometry group.
 */

import type { GuideDefinition } from '../types'

export const INTEGRATE_FIBER_GUIDE: GuideDefinition = {
  routeName: 'integrate-fiber',
  title: { zh: 'GIWAXS 纤维衍射积分', en: 'GIWAXS Fiber Integration' },
  steps: [
    {
      id: 'files',
      aiId: 'fiber:files',
      title: { zh: '选择数据文件', en: 'Pick data files' },
      tip: {
        zh: '加载掠入射 GIWAXS 2D 图像；运行会批量生成预览缓存',
        en: 'Load GIWAXS 2D images; running builds the batch preview cache',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'geometry',
      aiId: 'fiber:geometry',
      title: { zh: '设置几何与纤维取向', en: 'Set geometry & fiber rotation' },
      tip: {
        zh: '导入 .poni，必要时用纤维旋转覆盖（rot1/2/3）把纤维轴转正',
        en: 'Import the .poni; use fiber rotation overrides (rot1/2/3) to upright the fiber axis',
      },
      done: (s) => s?.hasPoni === true,
    },
    {
      id: 'run',
      aiId: 'fiber:run',
      title: { zh: '生成 2D 积分预览', en: 'Build 2D integration preview' },
      tip: {
        zh: '点击预览对全部文件积分，得到 qχ 二维热图',
        en: 'Run the preview to integrate all files into the qχ 2D heatmap',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'export',
      aiId: 'fiber:export',
      title: { zh: '导出结果', en: 'Export results' },
      tip: {
        zh: '在侧栏导出分区可导出数据；ROI 与 PNG 按钮在主区',
        en: 'Export via the sidebar section; ROI and PNG buttons live in the main area',
      },
      done: (s) => s?.phase === 'done',
    },
  ],
}
