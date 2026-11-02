/**
 * Theme store — inert stub in X-FAIS (adapted from PeakWorkbench).
 *
 * 主题存储——在 X-FAIS 中为惰性占位（改写自 PeakWorkbench）。
 *
 * The reference workbench owned global theming: it wrote
 * `document.documentElement.dataset.theme` and persisted 'pw.theme' in
 * localStorage. X-FAIS already owns app-level theming (theme switcher in the
 * app shell / settings), so this module keeps ONLY the exported API shape that
 * ported components import (`useTheme()` with `mode` + `toggle`) and performs
 * no document or storage side effects. `toggle` is intentionally a no-op.
 *
 * 参考实现的主题存储独占全局主题：写 `document.documentElement.dataset.theme`
 * 并把 'pw.theme' 持久化到 localStorage。X-FAIS 已由应用外壳统一管理主题，
 * 故此处仅保留已移植组件所引用的导出形态（`useTheme()` 的 `mode` + `toggle`），
 * 不再做任何 document / storage 副作用；`toggle` 故意为空操作。
 */
import { ref } from 'vue'

export type ThemeMode = 'dark' | 'light'

/** Always 'dark': chart palettes in palette.ts fall back to their dark tokens. */
const mode = ref<ThemeMode>('dark')

export function useTheme() {
  const toggle = (): void => {
    /* no-op: theming is app-level here / 主题由应用层统一管理 */
  }
  return { mode, toggle }
}
