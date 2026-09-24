/**
 * registry.ts — All guided-teaching definitions, keyed by route name.
 *
 * Step `autoClick: true` entries ARE the auto-click allowlist — only author
 * them on load/run/export-style actions. Views must report matching
 * WorkspaceSnapshot fields (see src/lib/workspace-state.ts) for `done`.
 * 本注册表即自动代点白名单——只允许在加载/运行/导出类动作上标记 autoClick。
 */

import type { GuideDefinition } from './types'
import { INTEGRATE_1D_GUIDE } from './steps/integrate-1d'
import { CALIBRATION_GUIDE } from './steps/calibration'
import { INTEGRATE_AZIMUTH_GUIDE } from './steps/integrate-azimuth'
import { INTEGRATE_CAKE_GUIDE } from './steps/integrate-cake'
import { INTEGRATE_FIBER_GUIDE } from './steps/integrate-fiber'
import { VIEWER_GUIDE } from './steps/viewer'
import { MASK_MAKER_GUIDE } from './steps/mask-maker'
import { BG_SUBTRACT_GUIDE } from './steps/bg-subtract'
import { IMAGE_MATH_GUIDE } from './steps/image-math'
import { IMAGE_STITCH_GUIDE } from './steps/image-stitch'
import { ORIENTATION_GUIDE } from './steps/orientation'
import { LAMELLAR_GUIDE } from './steps/lamellar'

export const GUIDES: Record<string, GuideDefinition> = {
  'integrate-1d': INTEGRATE_1D_GUIDE,
  calibration: CALIBRATION_GUIDE,
  'integrate-azimuth': INTEGRATE_AZIMUTH_GUIDE,
  'integrate-cake': INTEGRATE_CAKE_GUIDE,
  'integrate-fiber': INTEGRATE_FIBER_GUIDE,
  viewer: VIEWER_GUIDE,
  'mask-maker': MASK_MAKER_GUIDE,
  'bg-subtract': BG_SUBTRACT_GUIDE,
  'image-math': IMAGE_MATH_GUIDE,
  'image-stitch': IMAGE_STITCH_GUIDE,
  'orientation-analysis': ORIENTATION_GUIDE,
  'lamellar-analysis': LAMELLAR_GUIDE,
}

/** Does a route have a guided tour? */
export function hasGuide(routeName: string): boolean {
  return routeName in GUIDES
}
