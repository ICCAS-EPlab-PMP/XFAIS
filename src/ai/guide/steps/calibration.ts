/**
 * calibration.ts — Guided tour for the geometry calibration wizard.
 * Requires CalibrationView to report: filesCount (calibrant image loaded),
 * extras.ringsCount, extras.refined, extras.exported, extras.mode (2026-10-25).
 *
 * 2026-10-25: the peak step no longer anchors to the removed 高级 full-image
 * auto-detect button — ring picking is manual ring-by-ring (finish-ring), and
 * the tour is GATED to the calibrant (standard) branch: the com /
 * internal-standard branches have different steps and controls, so starting
 * this table there would only spotlight missing anchors.
 */

import type { GuideDefinition } from '../types'

export const CALIBRATION_GUIDE: GuideDefinition = {
  routeName: 'calibration',
  title: { zh: '几何校正', en: 'Geometry Calibration' },
  // The com (direct-beam) and internal-standard branches have their own flows;
  // this step table describes the standard calibrant branch only.
  // com（直通光）与内标支路各有流程；本表只描述标样校正支路。
  applicable: (s) => {
    const mode = s?.extras?.mode
    return mode !== 'com' && mode !== 'internal'
  },
  inapplicableNote: {
    zh: '当前处于直通光定心或内标定标支路——本教程对应「标样校正」支路（设置里切换模式后可用）',
    en: 'You are on the direct-beam or internal-standard branch — this tour covers the calibrant branch (switch the mode in setup)',
  },
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
      aiId: 'calibration:finish-ring',
      title: { zh: '逐一环选收峰', en: 'Pick rings one by one' },
      tip: {
        zh: '在当前环上点击 ≥3 个引导点后「完成本环」收环；数字框设环号，收完自动进下一环（回退可撤销，框选可批量删点）',
        en: 'Click ≥3 guide points on the current ring, then Finish ring; the spinner sets the ring number and advances (undo / box-erase help clean up)',
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
