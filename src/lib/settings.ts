// settings store — typed localStorage-backed settings with reactive access
// 类型化 localStorage 设置存储，提供响应式访问。
//
// Storage layout / 存储布局:
//   x-fais-locale          → legacy language key (kept for backward compat / 旧语言键，保留兼容)
//   xfaos.settings.v1      → full AppSettings JSON (v1)
//
// OMP thread override is ALSO pushed to the Electron main process via
// window.desktop.settings.setPythonLaunchEnv so the next Python launch can
// inject OMP_NUM_THREADS before the interpreter starts (see manager.ts).
// OMP 线程数同时推送到 Electron 主进程，下一次拉起 Python 时在解释器
// 启动前注入 OMP_NUM_THREADS（见 manager.ts）。
import { reactive, watch } from 'vue'
import { DEFAULT_SETTINGS, type AppSettings, type AiSettings, type IntegrationMethodSetting } from '@/types/settings'

const STORAGE_KEY = 'xfaos.settings.v1'
const LEGACY_LOCALE_KEY = 'x-fais-locale'

/** True only in the Jev test build (vite --mode jev) / 仅 Jev 测试构建为真 */
export const isJevBuild = (): boolean => import.meta.env.VITE_JEV_BUILD === '1'

function readStored(): Partial<AppSettings> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Partial<AppSettings>
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function migrateLocale(stored: Partial<AppSettings>): Partial<AppSettings> {
  if (stored.locale) return stored
  const legacy = localStorage.getItem(LEGACY_LOCALE_KEY)
  if (legacy === 'zh' || legacy === 'en') {
    return { ...stored, locale: legacy }
  }
  return stored
}

const stored = migrateLocale(readStored())

// Explicit per-field merge keeps AiSettings fields required (a plain spread of
// `Partial<AiSettings>` would widen them back to `string | undefined`).
// 逐字段合并以保持 AiSettings 字段为必填（直接展开 Partial 会把类型放宽回
// string | undefined）。Stale llm* fields from older builds are dropped here.
// 旧版本遗留的 llm* 字段在此合并中被丢弃。
const aiDefaults = DEFAULT_SETTINGS.ai ?? { jevApiKey: '' }
const aiStored: Partial<AiSettings> = stored.ai ?? {}

const state = reactive<AppSettings>({
  ...DEFAULT_SETTINGS,
  ...stored,
  performance: { ...DEFAULT_SETTINGS.performance, ...(stored.performance ?? {}) },
  ai: {
    jevApiKey: aiStored.jevApiKey ?? aiDefaults.jevApiKey
  }
})

/** Push the OMP override to the Electron main process (best-effort, web-safe). */
function pushLaunchEnv(): void {
  const desktop = typeof window !== 'undefined' ? window.desktop : undefined
  const push = desktop?.settings?.setPythonLaunchEnv
  if (typeof push !== 'function') return
  const omp = state.performance.ompThreads
  push(omp === 'auto' ? {} : { ompThreads: omp }).catch(() => {
    /* best-effort: main may be unavailable in web mode / web 模式下尽力而为 */
  })
}

function persist(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    if (state.locale) localStorage.setItem(LEGACY_LOCALE_KEY, state.locale)
  } catch {
    /* storage full/blocked — keep in-memory state / 存储异常时仅保留内存态 */
  }
  pushLaunchEnv()
}

watch(state, persist, { deep: true })
// Sync the override once at startup so a restart picks it up immediately.
// 启动即同步一次，保证重启后立即生效。
if (typeof window !== 'undefined') {
  pushLaunchEnv()
}

export function useSettings() {
  return state
}

export function setLocale(locale: 'zh' | 'en'): void {
  state.locale = locale
}

export function setDefaultMethod(method: IntegrationMethodSetting): void {
  state.performance.defaultMethod = method
}

/** Reset to factory defaults / 恢复默认 */
export function resetSettings(): void {
  Object.assign(state, structuredClone(DEFAULT_SETTINGS))
  persist()
}

export function getSettingsSnapshot(): AppSettings {
  return JSON.parse(JSON.stringify(state)) as AppSettings
}
