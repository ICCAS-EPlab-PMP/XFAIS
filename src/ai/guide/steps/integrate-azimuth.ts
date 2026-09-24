/**
 * integrate-azimuth.ts — Guided tour for the azimuthal χ integration view.
 * View reports: filesCount, hasPoni, canRun, phase (derived).
 */

import type { GuideDefinition } from '../types'

export const INTEGRATE_AZIMUTH_GUIDE: GuideDefinition = {
  routeName: 'integrate-azimuth',
  title: { zh: '方位角 χ 积分', en: 'Azimuthal χ Integration' },
  steps: [
    {
      id: 'files',
      aiId: 'azimuth:files',
      title: { zh: '选择数据文件', en: 'Pick data files' },
      tip: {
        zh: '加载 2D 衍射图；χ 积分适合分析取向分布',
        en: 'Load 2D diffraction images; χ integration reveals orientation distributions',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'geometry',
      aiId: 'azimuth:geometry',
      title: { zh: '设置几何（PONI）', en: 'Set geometry (PONI)' },
      tip: {
        zh: '导入 .poni 或手动核对距离/波长/束心，χ 换算依赖正确几何',
        en: 'Import the .poni or verify distance/wavelength/beam center — χ mapping depends on it',
      },
      done: (s) => s?.hasPoni === true,
    },
    {
      id: 'run',
      aiId: 'azimuth:run',
      title: { zh: '开始积分', en: 'Run integration' },
      tip: {
        zh: '径向/方位角范围校验通过后即可运行，得到 I(χ) 曲线',
        en: 'Once radial/azimuth ranges validate, run to obtain the I(χ) curve',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'export',
      aiId: 'azimuth:export',
      title: { zh: '查看结果并导出', en: 'Review & export' },
      tip: {
        zh: '核对 I(χ) 曲线后导出为 txt/csv/hdf5',
        en: 'Inspect the I(χ) curve, then export as txt/csv/hdf5',
      },
      done: (s) => s?.phase === 'done',
    },
  ],
}
