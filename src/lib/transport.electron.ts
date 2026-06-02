/**
 * transport.electron.ts — Electron transport implementation.
 *
 * Proxies all ITransport methods to window.desktop (exposed via preload.ts).
 * This file is imported only in Electron mode; web mode uses transport.web.ts.
 */

import type {
  ITransport,
  PythonStatus,
  AppMeta,
  TaskBinaryPayload,
} from './transport'

import type {
  DialogOpenFileOptions,
  DialogOpenFileResult,
  DialogSaveFileOptions,
  TaskSubmitResponse,
  TaskProgressPayload,
  TaskResultPayload,
  TaskErrorPayload,
  PyfaiCheckResult,
} from '../types/ipc'

export class ElectronTransport implements ITransport {
  // ── Task operations ────────────────────────────────────────────────────────

  submitTask(command: string, params: Record<string, unknown>): Promise<TaskSubmitResponse> {
    return window.desktop.task.submit(command, params)
  }

  cancelTask(taskId: string): Promise<void> {
    return window.desktop.task.cancel(taskId)
  }

  onTaskProgress(taskId: string, callback: (payload: TaskProgressPayload) => void): () => void {
    return window.desktop.task.onProgress(taskId, callback)
  }

  onTaskResult(taskId: string, callback: (payload: TaskResultPayload) => void): () => void {
    return window.desktop.task.onResult(taskId, callback)
  }

  onTaskError(taskId: string, callback: (payload: TaskErrorPayload) => void): () => void {
    return window.desktop.task.onError(taskId, callback)
  }

  onTaskBinaryData(taskId: string, callback: (payload: TaskBinaryPayload) => void): () => void {
    return window.desktop.task.onBinaryData(taskId, callback)
  }

  // ── File dialogs ─────────────────────────────────────────────────────────────

  selectFiles(options?: DialogOpenFileOptions): Promise<DialogOpenFileResult> {
    return window.desktop.dialog.openFile(options)
  }

  selectFolder(defaultPath?: string): Promise<string | null> {
    return window.desktop.dialog.openFolder(defaultPath)
  }

  selectSavePath(options?: DialogSaveFileOptions): Promise<string | null> {
    return window.desktop.dialog.saveFile(options)
  }

  // ── Python service ──────────────────────────────────────────────────────────

  getPythonStatus(): Promise<PythonStatus | null> {
    return window.desktop.python.getStatus() as Promise<PythonStatus | null>
  }

  onPythonStatusChange(callback: (status: PythonStatus) => void): () => void {
    return window.desktop.python.onStatusChange(callback as unknown as (status: DesktopPythonStatus) => void)
  }

  restartPython(): Promise<PythonStatus | null> {
    return window.desktop.python.restart() as Promise<PythonStatus | null>
  }

  // ── App metadata ─────────────────────────────────────────────────────────────

  getAppMeta(): Promise<AppMeta> {
    return window.desktop.getAppMeta() as Promise<AppMeta>
  }

  // ── pyFAI tools ──────────────────────────────────────────────────────────────

  checkPyfai(): Promise<PyfaiCheckResult> {
    return window.desktop.pyfai.check() as Promise<PyfaiCheckResult>
  }

  launchPyfai(): Promise<{ success: boolean; error?: string }> {
    return window.desktop.pyfai.launch()
  }

  installPyfai(): Promise<{ success: boolean; command?: string; error?: string }> {
    return window.desktop.pyfai.install()
  }

  exportBatPyfai(): Promise<{ success: boolean; error?: string }> {
    return window.desktop.pyfai.exportBat()
  }

  // ── Web-mode file operations (not available in Electron) ─────────────────────

  uploadFile(_file: File): Promise<string> {
    throw new Error('File upload is not available in Electron mode')
  }

  downloadFile(_serverPath: string, _filename: string): Promise<void> {
    throw new Error('File download is not available in Electron mode')
  }

  // ── Environment detection ────────────────────────────────────────────────────

  isDesktop(): boolean {
    return true
  }
}