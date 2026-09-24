/**
 * context.ts — Navigation catalog + compact app-state snapshot for the AI layer.
 *
 * NAV_CATALOG mirrors BETA/src/router/index.ts (route names/paths are copied
 * verbatim from the router; 'settings' is added in parallel work). The catalog
 * is the single source of truth the rules router, the Jev prompts, and the
 * assistant bar all share.
 */

import router from '@/router'
import type { AppState } from './types'

// ── Nav catalog ───────────────────────────────────────────────────────────────

export interface NavEntry {
  routeName: string
  path: string
  zh: string
  en: string
  /** `data-ai-id` of the default spotlight target on that page (main pages only). */
  aiId?: string
}

/** All navigable destinations the assistant can route to (zh + en titles). */
export const NAV_CATALOG: NavEntry[] = [
  { routeName: 'home', path: '/', zh: '主页', en: 'Home' },
  {
    routeName: 'integrate-1d',
    path: '/workspace/integrate-1d',
    zh: '1D 径向积分',
    en: '1D Radial Integration',
    aiId: 'integrate1d:files',
  },
  { routeName: 'integrate-azimuth', path: '/workspace/integrate-azimuth', zh: '方位角 χ 积分', en: 'Azimuthal χ Integration' },
  { routeName: 'integrate-cake', path: '/workspace/integrate-cake', zh: 'CAKE 方位角窗口积分', en: 'CAKE Sector Integration' },
  { routeName: 'integrate-fiber', path: '/workspace/integrate-fiber', zh: 'GIWAXS 纤维衍射 2D 积分', en: 'GIWAXS Fiber 2D Integration' },
  { routeName: 'viewer', path: '/workspace/viewer', zh: '图像查看器', en: 'Image Viewer' },
  { routeName: 'h5-toolkit', path: '/workspace/h5-toolkit', zh: 'H5 格式处理', en: 'H5 Format Toolkit' },
  { routeName: 'mask-maker', path: '/workspace/mask-maker', zh: '掩膜（Mask）制作', en: 'Mask Maker' },
  { routeName: 'png-generate', path: '/workspace/png-generate', zh: '批量 PNG 生成', en: 'Batch PNG Generation' },
  {
    routeName: 'calibration',
    path: '/workspace/calibration',
    zh: '几何校正（calib2 内置）',
    en: 'Geometry Calibration (built-in calib2)',
    aiId: 'calibration:load',
  },
  {
    routeName: 'pyfai-calib',
    path: '/workspace/pyfai-calib',
    zh: 'PyFAI 校准工具',
    en: 'PyFAI Calibration Tool',
  },
  { routeName: 'cell-calibrant-generator', path: '/workspace/cell-calibrant-generator', zh: '校正标样生成器', en: 'Calibrant Generator' },
  { routeName: 'bg-subtract', path: '/workspace/bg-subtract', zh: '背景扣除', en: 'Background Subtraction' },
  { routeName: 'image-math', path: '/workspace/image-math', zh: '图像运算', en: 'Image Math' },
  { routeName: 'image-stitch', path: '/workspace/image-stitch', zh: '图像拼接', en: 'Image Stitch' },
  { routeName: 'orientation-analysis', path: '/workspace/orientation-analysis', zh: '聚合物取向度分析', en: 'Polymer Orientation Analysis' },
  { routeName: 'lamellar-analysis', path: '/workspace/lamellar-analysis', zh: 'SAXS 片晶结构分析', en: 'SAXS Lamellar Analysis' },
  { routeName: 'poni-importer', path: '/workspace/poni-importer', zh: 'PONI 文件转化', en: 'Switch to PONI' },
  // Added in parallel (Settings work) — exists at runtime even if the route
  // registration lands in another commit. / 并行开发中的设置页。
  { routeName: 'settings', path: '/settings', zh: '设置', en: 'Settings' },
]

/** Look up a catalog entry by route name. */
export function navEntry(routeName: string): NavEntry | undefined {
  return NAV_CATALOG.find((e) => e.routeName === routeName)
}

/** Current UI locale ('zh' | 'en') from the same key the i18n module uses. */
export function currentLocale(): 'zh' | 'en' {
  try {
    const saved = localStorage.getItem('x-fais-locale')
    return saved === 'en' ? 'en' : 'zh'
  } catch {
    return 'zh'
  }
}

/** Localized nav title for a route (falls back to the route name). */
export function navTitle(routeName: string): string {
  const entry = navEntry(routeName)
  if (!entry) return routeName
  return currentLocale() === 'en' ? entry.en : entry.zh
}

// ── Persistence keys ──────────────────────────────────────────────────────────

/** localStorage key holding the assistant's chosen PONI file path. */
export const PONI_PATH_KEY = 'xfaos.ai.poniPath'
/** sessionStorage key holding the most-recent-paths list (JSON array). */
export const RECENT_PATHS_KEY = 'xfaos.ai.recentPaths'
const RECENT_PATHS_MAX = 8

// ── Recent-paths tracking (session-scoped) ────────────────────────────────────

function readRecentPaths(): string[] {
  try {
    const raw = sessionStorage.getItem(RECENT_PATHS_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((p): p is string => typeof p === 'string' && p.length > 0)
  } catch {
    return []
  }
}

function writeRecentPaths(paths: string[]): void {
  try {
    sessionStorage.setItem(RECENT_PATHS_KEY, JSON.stringify(paths.slice(0, RECENT_PATHS_MAX)))
  } catch {
    // Storage unavailable (private mode, etc.) — recent paths are best-effort.
  }
}

/** Record a visited path (dedupes consecutive repeats; keeps last 8). */
export function rememberVisit(path: string): void {
  if (!path) return
  const paths = readRecentPaths()
  if (paths[0] === path) return
  writeRecentPaths([path, ...paths.filter((p) => p !== path)].slice(0, RECENT_PATHS_MAX))
}

// ── App-state snapshot ────────────────────────────────────────────────────────

/**
 * Build the compact, JSON-serializable AppState (~1 KB) handed to providers:
 * current location, localized nav titles, recent paths, and the PONI path.
 */
export function buildAppState(): AppState {
  const current = router.currentRoute.value
  const currentPath = current.fullPath || current.path || '/'
  const currentRouteName =
    typeof current.name === 'string' ? current.name : (current.name?.toString() ?? '')

  const navTitles: Record<string, string> = {}
  const locale = currentLocale()
  for (const entry of NAV_CATALOG) {
    navTitles[entry.routeName] = locale === 'en' ? entry.en : entry.zh
  }

  rememberVisit(currentPath)

  let poniPath = ''
  try {
    poniPath = localStorage.getItem(PONI_PATH_KEY) ?? ''
  } catch {
    poniPath = ''
  }

  return {
    currentPath,
    currentRouteName,
    navTitles,
    recentPaths: readRecentPaths(),
    poniPath,
  }
}
