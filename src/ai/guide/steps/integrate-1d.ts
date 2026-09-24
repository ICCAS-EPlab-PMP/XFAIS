/**
 * integrate-1d.ts — Guided tour for the 1D radial integration view.
 * Requires the view to report: filesCount, hasPoni, canRun, phase and
 * extras.templateApplied (see Integrate1dView reporting).
 */

import type { GuideDefinition } from '../types'

export const INTEGRATE_1D_GUIDE: GuideDefinition = {
  routeName: 'integrate-1d',
  title: { zh: '1D 径向积分', en: '1D Radial Integration' },
  steps: [
    {
      id: 'files',
      aiId: 'integrate1d:files',
      title: { zh: '选择数据文件', en: 'Pick data files' },
      tip: {
        zh: '点击加载 2D 衍射图（EDF/TIFF/H5），可多选做批量处理',
        en: 'Load 2D diffraction images (EDF/TIFF/H5); multi-select for batch runs',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'poni',
      aiId: 'integrate1d:geometry',
      title: { zh: '设置几何（PONI）', en: 'Set geometry (PONI)' },
      tip: {
        zh: '若有 .poni 校准文件请在此导入；否则手动核对距离、波长与束心位置',
        en: 'Import your .poni here, or verify distance, wavelength and beam center manually',
      },
      done: (s) => s?.hasPoni === true,
    },
    {
      id: 'template',
      aiId: 'integrate1d:advanced',
      title: { zh: '应用标准模板参数', en: 'Apply template parameters' },
      tip: {
        zh: '我会依据 PONI 几何判断 WAXS/SAXS 并填入推荐参数（点数、q 单位与范围）',
        en: 'I will judge WAXS/SAXS from the PONI geometry and fill in recommended parameters',
      },
      done: (s) => s?.extras?.templateApplied === true,
      action: 'apply-template',
    },
    {
      id: 'run',
      aiId: 'integrate1d:run',
      title: { zh: '开始积分', en: 'Run integration' },
      tip: {
        zh: '文件与几何就绪，点击运行得到 I(q) 曲线',
        en: 'Files and geometry are ready — run to obtain the I(q) curve',
      },
      done: (s) => s?.phase === 'running' || s?.phase === 'done',
      autoClick: true,
      allowWhen: (s) => s?.canRun === true,
    },
    {
      id: 'export',
      aiId: 'integrate1d:export',
      title: { zh: '查看结果并导出', en: 'Review & export' },
      tip: {
        zh: '曲线生成后可核对结果，并导出为 txt/csv/hdf5',
        en: 'Inspect the resulting curve, then export as txt/csv/hdf5',
      },
      done: (s) => s?.extras?.exported === true,
    },
  ],
}
