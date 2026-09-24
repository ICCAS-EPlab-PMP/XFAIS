/**
 * integrate-cake.ts — Guided tour for the CAKE sector integration view.
 * View reports: filesCount, hasPoni, canRun, phase (derived).
 */

import type { GuideDefinition } from '../types'

export const INTEGRATE_CAKE_GUIDE: GuideDefinition = {
  routeName: 'integrate-cake',
  title: { zh: 'CAKE 扇区积分', en: 'CAKE Sector Integration' },
  steps: [
    {
      id: 'files',
      aiId: 'cake:files',
      title: { zh: '选择数据文件', en: 'Pick data files' },
      tip: {
        zh: '加载 2D 衍射图；CAKE 积分只取你关心的方位角扇区',
        en: 'Load 2D diffraction images; CAKE integrates only your azimuthal sector of interest',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'geometry',
      aiId: 'cake:geometry',
      title: { zh: '设置几何（PONI）', en: 'Set geometry (PONI)' },
      tip: {
        zh: '导入 .poni 或手动核对几何参数，并设定扇区方位角范围',
        en: 'Import the .poni or verify geometry, then set the sector azimuth range',
      },
      done: (s) => s?.hasPoni === true,
    },
    {
      id: 'run',
      aiId: 'cake:run',
      title: { zh: '开始积分', en: 'Run integration' },
      tip: {
        zh: '扇区范围合法即可运行，得到扇区内的径向分布',
        en: 'Run once the sector range is valid to obtain the in-sector radial profile',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'export',
      aiId: 'cake:export',
      title: { zh: '查看结果并导出', en: 'Review & export' },
      tip: {
        zh: '核对结果曲线后导出为 txt/csv/xy/hdf5',
        en: 'Inspect the resulting curve, then export as txt/csv/xy/hdf5',
      },
      done: (s) => s?.phase === 'done',
    },
  ],
}
