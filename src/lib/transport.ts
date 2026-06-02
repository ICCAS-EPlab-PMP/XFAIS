/**
 * transport.ts — Transport abstraction layer for runtime environment detection.
 *
 * Provides a flat, unified interface for desktop-specific APIs (file dialogs,
 * Python service, task execution, pyFAI tools) that works in both Electron
 * and web modes.
 *
 * In Electron mode, delegates to window.desktop (exposed via preload.ts).
 * In web mode, provides web-compatible implementations (upload/download, etc.)
 *
 * Usage:
 *   import { useTransport } from '~/lib/transport'
 *   const transport = useTransport()
 *   const meta = await transport.getAppMeta()
 */

import { inject, type InjectionKey } from 'vue'
import { ElectronTransport } from './transport.electron'
import { WebTransport } from './transport.web'
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

// ── Shared Types ──────────────────────────────────────────────────────────────

/**
 * Python service status — mirrors DesktopPythonStatus from preload.ts.
 * Defined inline to avoid importing from electron (not available in web build).
 */
export interface PythonStatus {
  canRetry: boolean
  dependencyStatus: 'ready' | 'missing' | 'outdated' | 'unknown'
  detail: string
  lastExitCode: number | null
  port: number | null
  pythonPath: string | null
  pythonVersion: string | null
  state: 'starting' | 'healthy' | 'error' | 'stopped' | 'restarting'
}

/** App metadata from the desktop environment. */
export interface AppMeta {
  appName: string
  appVersion: string
  logDirectory: string
  platform: string
}

/** Payload for task binary data events (e.g. image frames). */
export interface TaskBinaryPayload {
  taskId: string
  mime: string
  frame: number
  width: number
  height: number
  data: ArrayBuffer
}

// ── ITransport Interface ──────────────────────────────────────────────────────

/**
 * Flat transport interface covering all desktop APIs exposed via preload.ts.
 *
 * Methods are organized by domain:
 * - Task operations: submit, cancel, progress/result/error/binary listeners
 * - File dialogs: selectFiles, selectFolder, selectSavePath
 * - Python service: status, status change listener, restart
 * - App metadata: getAppMeta
 * - pyFAI tools: check, launch, install
 * - Web-mode file operations: uploadFile, downloadFile
 * - Environment detection: isDesktop
 */
export interface ITransport {
  // ── Task operations ────────────────────────────────────────────────────────

  /**
   * Submit a task to the Python service worker.
   * @param command  Route identifier (e.g. '/api/integrate1d')
   * @param params   Arbitrary key/value params for the task
   */
  submitTask(command: string, params: Record<string, unknown>): Promise<TaskSubmitResponse>

  /** Cancel an in-progress task by its id. */
  cancelTask(taskId: string): Promise<void>

  /**
   * Subscribe to progress events for a task.
   * @returns Unsubscribe function.
   */
  onTaskProgress(taskId: string, callback: (payload: TaskProgressPayload) => void): () => void

  /**
   * Subscribe to completion events for a task.
   * @returns Unsubscribe function.
   */
  onTaskResult(taskId: string, callback: (payload: TaskResultPayload) => void): () => void

  /**
   * Subscribe to error events for a task.
   * @returns Unsubscribe function.
   */
  onTaskError(taskId: string, callback: (payload: TaskErrorPayload) => void): () => void

  /**
   * Subscribe to binary data events (e.g. streaming image frames) for a task.
   * @returns Unsubscribe function.
   */
  onTaskBinaryData(taskId: string, callback: (payload: TaskBinaryPayload) => void): () => void

  // ── File dialogs ─────────────────────────────────────────────────────────────

  /**
   * Open a file picker dialog.
   * @param options  Dialog options (filters, default path, multi-select)
   */
  selectFiles(options?: DialogOpenFileOptions): Promise<DialogOpenFileResult>

  /**
   * Open a folder picker dialog.
   * @param defaultPath  Optional path to pre-select
   */
  selectFolder(defaultPath?: string): Promise<string | null>

  /**
   * Open a save-file dialog.
   * @param options  Dialog options (filters, default path)
   */
  selectSavePath(options?: DialogSaveFileOptions): Promise<string | null>

  // ── Python service ──────────────────────────────────────────────────────────

  /** Get the current Python service status. */
  getPythonStatus(): Promise<PythonStatus | null>

  /**
   * Subscribe to Python service status change events.
   * @returns Unsubscribe function.
   */
  onPythonStatusChange(callback: (status: PythonStatus) => void): () => void

  /** Restart the Python service. */
  restartPython(): Promise<PythonStatus | null>

  // ── App metadata ─────────────────────────────────────────────────────────────

  /** Get app metadata (name, version, log directory, platform). */
  getAppMeta(): Promise<AppMeta>

  // ── pyFAI tools ──────────────────────────────────────────────────────────────

  /** Check pyFAI availability (embedded + system). */
  checkPyfai(): Promise<PyfaiCheckResult>

  /** Launch the pyFAI GUI. */
  launchPyfai(): Promise<{ success: boolean; error?: string }>

  /**
   * Install pyFAI dependencies.
   * @returns Object with success flag and optional command or error message.
   */
  installPyfai(): Promise<{ success: boolean; command?: string; error?: string }>

  /** Export a .bat launcher script for pyFAI-calib2. */
  exportBatPyfai(): Promise<{ success: boolean; error?: string }>

  // ── Web-mode file operations ─────────────────────────────────────────────────

  /**
   * Upload a file to the server (web mode).
   * @param file  Browser File object to upload
   * @returns Server path of the uploaded file
   */
  uploadFile(file: File): Promise<string>

  /**
   * Trigger a browser download for a server file (web mode).
   * @param serverPath  Path of the file on the server
   * @param filename    Suggested filename for the downloaded file
   */
  downloadFile(serverPath: string, filename: string): Promise<void>

  // ── Environment detection ────────────────────────────────────────────────────

  /** Returns true when running in Electron, false when in web mode. */
  isDesktop(): boolean
}

// ── Vue Provider Symbol ────────────────────────────────────────────────────────

/** Symbol for Vue provide/inject of the transport instance. */
export const TransportProvider: InjectionKey<ITransport> = Symbol('transport')

// ── Factory Function ───────────────────────────────────────────────────────────

/**
 * Create a transport instance for the current runtime environment.
 *
 * Runtime detection checks for the Electron preload's window.desktop object.
 * Uses eager imports — Vite tree-shakes the unused transport in production.
 */
let _cachedTransport: ITransport | null = null

export function createTransport(): ITransport {
  if (_cachedTransport) return _cachedTransport

  const hasDesktop =
    typeof window !== 'undefined' && typeof (window as any).desktop !== 'undefined'

  _cachedTransport = hasDesktop ? new ElectronTransport() : new WebTransport()
  return _cachedTransport
}

// ── Vue Composable ─────────────────────────────────────────────────────────────

/**
 * Vue composable to inject the transport instance.
 *
 * @example
 * ```vue
 * <script setup>
 * import { useTransport } from '~/lib/transport'
 * const transport = useTransport()
 * const meta = await transport.getAppMeta()
 * </script>
 * ```
 *
 * @throws Error if TransportProvider was not installed in the app.
 */
export function useTransport(): ITransport {
  const transport = inject<ITransport>(TransportProvider)
  if (!transport) {
    throw new Error(
      'Transport not provided. Did you forget to install the transport plugin?'
    )
  }
  return transport
}