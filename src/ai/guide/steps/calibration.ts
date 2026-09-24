/**
 * calibration.ts — Guided tour for the geometry calibration wizard.
 * Requires CalibrationView to report: filesCount (calibrant image loaded),
 * extras.ringsCount, extras.refined, extras.exported.
 */

import type { GuideDefinition } from '../types'

export const CALIBRATION_GUIDE: GuideDefinition = {
  routeName: 'calibration',
  title: { zh: '几何校正', en: 'Geometry Calibration' },
  steps: [
    {
      id: 'load',
      aiId: 'calibration:load',
      title: { zh: '加载标样图像', en: 'Load calibrant image' },
      tip: {
        zh: '选择标样（如 LaB₆）衍射图并确认探测器型号',
        en: 'Pick the calibrant (e.g. LaB₆) diffraction image and confirm the detector',
      },
      done: (s) => (s?.filesCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'peaks',
      aiId: 'calibration:auto-peaks',
      title: { zh: '自动拾取衍射环', en: 'Auto-detect rings' },
      tip: {
        zh: '自动寻峰圈出 Debye–Scherrer 环；不满意可逐环手动修正',
        en: 'Auto-detect the Debye–Scherrer rings; refine individual rings manually if needed',
      },
      done: (s) => Number(s?.extras?.ringsCount ?? 0) > 0,
      autoClick: true,
    },
    {
      id: 'refine',
      aiId: 'calibration:refine',
      title: { zh: '精修几何', en: 'Refine geometry' },
      tip: {
        zh: '最小二乘精修距离/波长/取向，观察 χ² 收敛',
        en: 'Least-squares refine distance/wavelength/orientation; watch χ² converge',
      },
      done: (s) => s?.extras?.refined === true,
      autoClick: true,
    },
    {
      id: 'export',
      aiId: 'calibration:export',
      title: { zh: '导出 PONI', en: 'Export PONI' },
      tip: {
        zh: '导出 .poni 后即可在 1D 积分页直接使用，完成校正闭环',
        en: 'Export the .poni — the 1D integration view picks it up directly',
      },
      done: (s) => s?.extras?.exported === true,
      autoClick: true,
    },
  ],
}
