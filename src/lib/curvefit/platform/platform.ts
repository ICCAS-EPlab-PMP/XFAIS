/**
 * Platform abstraction — X-FAIS adaptation (rewritten for this repository).
 *
 * 平台抽象层——面向 X-FAIS 的改写版本。
 *
 * The reference workbench (PeakWorkbench) shipped two backends behind
 * `WorkbenchPlatform`: an Electron preload bridge (`window.pw` IPC) and a
 * browser preview (module Web Worker + SharedArrayBuffer control flags).
 * X-FAIS has neither: the app shell owns Electron, and fits already run in
 * the dedicated worker exposed by `@/lib/fitEngine` (`runFitInWorker`, whose
 * 停止并保留 / 中止并回滚 semantics are implemented by terminating the
 * worker and replaying the last iteration — no SharedArrayBuffer needed).
 *
 * 参考实现（PeakWorkbench）在 `WorkbenchPlatform` 背后提供了两套后端：
 * Electron preload 桥（`window.pw` IPC）与浏览器预览（模块 Web Worker +
 * SharedArrayBuffer 控制字）。X-FAIS 两者皆无：Electron 外壳由本仓库自行
 * 管理，拟合已由 `@/lib/fitEngine` 的专属 Worker 承担（`runFitInWorker` 通过
 * 终止 Worker 并按最后一次迭代重建来实现“停止并保留 / 中止并回滚”，
 * 无需 SharedArrayBuffer）。
 *
 * This module therefore keeps the SAME `WorkbenchPlatform` surface (so every
 * ported store compiles and behaves unchanged) backed by browser APIs:
 *   - fit / stopFit / abortFit  → runFitInWorker handle
 *   - openDataFile              → hidden <input type="file"> (+ cancel/focus fallback)
 *   - saveDataFile              → object-URL + <a download>
 *   - window / onWindowState    → inert (the app shell owns window controls)
 *
 * 因此本模块保持与参考实现相同的 `WorkbenchPlatform` 表面（所有已移植的
 * store 无需改动即可编译/运行），底层改用浏览器 API：拟合委托给
 * runFitInWorker；文件打开用隐藏 file input（含取消/失焦兜底）；保存用
 * object URL + <a download>；窗口控制为空实现（由应用外壳负责）。
 */
import { runFitInWorker, type FitHandle } from '@/lib/fitEngine'
import type {
  FitIterEvent,
  FitOutcome,
  FitRequest,
  OpenedFile,
  WorkbenchApi,
} from '@/lib/pwcore/shared/types'

export interface WorkbenchPlatform extends WorkbenchApi {
  readonly kind: 'electron' | 'web'
}

// ---------------------------------------------------------------------------
// Fit (worker engine) / 拟合（Worker 引擎）
// ---------------------------------------------------------------------------

/** Current fit handle (module-level so stop/abort always target the live run). */
let currentFit: FitHandle | null = null

/**
 * Run a fit in the shared fit worker. The returned promise resolves with the
 * worker outcome, a reconstructed stop-keep result, or a FitError('aborted')
 * — exactly the reference platform contract. / 在共享拟合 Worker 中执行拟合；
 * 结果契约与参考平台一致（正常结果 / 停止保留重建 / 中止错误）。
 */
function platformFit(req: FitRequest, onIter?: (e: FitIterEvent) => void): Promise<FitOutcome> {
  const handle = runFitInWorker(req, onIter)
  currentFit = handle
  return handle.done.finally(() => {
    if (currentFit === handle) currentFit = null
  })
}

/** 停止并保留: finish at the current best and resolve normally. */
function platformStopFit(): void {
  // The handle settles its promise on every path (see runFitInWorker), but a
  // stop-path throw must never escape into the UI: the caller (anchor
  // pointerdown / toolbar stop) would abort its own logic and — before the
  // 2026-10-20 fix — leave `fit.status` stuck at 'running' with a dead run
  // button. Swallow here; the store also has a release fallback.
  // 句柄在所有路径上都会兑现 Promise（见 runFitInWorker），但停止路径的异常
  // 绝不能抛进 UI：调用方（锚点按下 / 工具栏停止）会被打断，且在 2026-10-20
  // 修复前会把 fit.status 卡在 'running'，运行按钮随之失效。这里吞掉；store
  // 侧另有释放兜底。
  try {
    currentFit?.stop()
  } catch {
    /* the pending fit settles itself; never throw into the UI */
  }
}

/** 中止并回滚: cancel; the pending promise resolves with FitError('aborted'). */
function platformAbortFit(): void {
  try {
    currentFit?.abort()
  } catch {
    /* same guarantee as stopFit / 与 stopFit 相同的保证 */
  }
}

// ---------------------------------------------------------------------------
// File open / save (browser APIs) / 文件打开与保存（浏览器 API）
// ---------------------------------------------------------------------------

/** Extensions read as UTF-8 text; everything else (e.g. .scn) as raw bytes. */
const TEXT_EXTENSIONS = new Set(['prn', 'csv', 'txt', 'tsv', 'dat'])

function isTextFile(name: string): boolean {
  const dot = name.lastIndexOf('.')
  if (dot < 0) return false
  return TEXT_EXTENSIONS.has(name.slice(dot + 1).toLowerCase())
}

/**
 * Hidden file-picker. Resolves null when the dialog is cancelled:
 * modern Chromium fires 'cancel' on the input; as a fallback a window
 * 'focus' event (the dialog closing returns focus to the page) arms a
 * short timer that resolves null when no file was selected.
 * 隐藏文件选择器。取消时解析为 null：新版 Chromium 会在 input 上触发
 * 'cancel'；兜底方案是在窗口重新获得焦点（对话框关闭）后启动短定时器，
 * 若仍无选中文件则解析为 null。
 */
function openDataFile(): Promise<OpenedFile | null> {
  return new Promise<OpenedFile | null>((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.prn,.csv,.txt,.tsv,.dat,.scn'
    input.style.display = 'none'
    document.body.appendChild(input)

    let settled = false
    let focusTimer: number | null = null

    const cleanup = (): void => {
      if (focusTimer !== null) {
        window.clearTimeout(focusTimer)
        focusTimer = null
      }
      window.removeEventListener('focus', onWindowFocus)
      input.removeEventListener('change', onChange)
      input.removeEventListener('cancel', onCancel)
      input.remove()
    }

    const settle = (value: OpenedFile | null): void => {
      if (settled) return
      settled = true
      cleanup()
      resolve(value)
    }

    const onCancel = (): void => settle(null)

    const onChange = (): void => {
      const file = input.files?.[0]
      if (!file) {
        settle(null)
        return
      }
      const name = file.name
      // Clear the value so picking the SAME file again re-fires 'change'.
      input.value = ''
      if (isTextFile(name)) {
        file
          .text()
          .then((text) => settle({ name, data: text }))
          .catch(() => settle(null))
      } else {
        file
          .arrayBuffer()
          .then((buffer) => settle({ name, data: buffer }))
          .catch(() => settle(null))
      }
    }

    const onWindowFocus = (): void => {
      if (focusTimer !== null) window.clearTimeout(focusTimer)
      focusTimer = window.setTimeout(() => {
        focusTimer = null
        if (!settled && (!input.files || input.files.length === 0)) settle(null)
      }, 600)
    }

    input.addEventListener('change', onChange)
    input.addEventListener('cancel', onCancel)
    window.addEventListener('focus', onWindowFocus)
    input.click()
  })
}

/**
 * Blob download through an object URL + a temporary anchor.
 * Returns true once the download was triggered (the browser cannot confirm
 * the user's "Save" click). / 通过 object URL + 临时 <a> 触发下载；返回 true
 * 表示已触发（浏览器无法确认用户的保存操作）。
 */
async function saveDataFile(defaultName: string, data: string | Uint8Array): Promise<boolean> {
  const blob =
    typeof data === 'string'
      ? new Blob([data], { type: 'text/plain;charset=utf-8' })
      : new Blob([new Uint8Array(data)], { type: 'application/octet-stream' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = defaultName
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 4000)
  return true
}

// ---------------------------------------------------------------------------
// Export / 导出
// ---------------------------------------------------------------------------

export const platform: WorkbenchPlatform = {
  kind: 'web',
  fit: platformFit,
  stopFit: platformStopFit,
  abortFit: platformAbortFit,
  openDataFile,
  saveDataFile,
  window: null,
  onWindowState: () => {
    /* no-op: X-FAIS owns Electron window controls / 窗口控制由应用外壳负责 */
  },
}
