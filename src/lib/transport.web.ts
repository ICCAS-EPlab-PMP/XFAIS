/**
 * transport.web.ts — Web browser transport implementing ITransport.
 *
 * Uses native WebSocket for task communication and fetch for HTTP endpoints.
 * File dialogs use hidden <input type="file"> elements and browser download APIs.
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
import { normalizeTaskParams, adaptTaskResult } from './task-adapter'

// ── Command → Route mapping ───────────────────────────────────────────────────

const COMMAND_ROUTE_MAP: Record<string, string> = {
  integrate1d: '/api/integrate1d',
  integrate_azimuth: '/api/integrate_azimuth',
  integrate_cake: '/api/integrate_cake',
  integrate_fiber: '/api/integrate_fiber',
  viewer_config: '/api/viewer_config',
  load_preview: '/api/viewer_config',
  mask_maker: '/api/viewer_config',
  h5convert: '/api/h5convert',
  h5convert_scan: '/api/h5convert_scan',
  h5_extract: '/api/h5_extract',
  h5_list_files: '/api/h5_list_files',
  png_generate: '/api/png_generate',
  export_integration: '/api/export_integration',
  calibrant_generate: '/api/calibrant_generate',
  cell_calibrant_generate: '/api/cell_calibrant_generate',
  manual_calibrant_generate: '/api/manual_calibrant_generate',
  list_space_groups: '/api/list_space_groups',
  bg_subtract: '/api/bg_subtract',
}

// ── Internal types ────────────────────────────────────────────────────────────

interface PendingTask {
  command: string
}

type ProgressCallback = (payload: TaskProgressPayload) => void
type ResultCallback = (payload: TaskResultPayload) => void
type ErrorCallback = (payload: TaskErrorPayload) => void
type BinaryCallback = (payload: TaskBinaryPayload) => void

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

// ── WebTransport ──────────────────────────────────────────────────────────────

export class WebTransport implements ITransport {
  private ws!: WebSocket
  private sessionId: string = ''
  private wsReady: Promise<void>
  private resolveReady!: () => void
  private _sessionAcquired!: Promise<void>
  private _resolveSession!: () => void

  private activeTasks: Map<string, PendingTask> = new Map()

  // Per-task event handler sets
  private progressHandlers: Map<string, Set<ProgressCallback>> = new Map()
  private resultHandlers: Map<string, Set<ResultCallback>> = new Map()
  private errorHandlerStore: Map<string, Set<ErrorCallback>> = new Map()
  private binaryHandlers: Map<string, Set<BinaryCallback>> = new Map()

  constructor() {
    this._sessionAcquired = new Promise<void>((resolve) => {
      this._resolveSession = resolve
    })
    this.wsReady = this._init()
  }

  // -- WebSocket URL discovery --------------------------------------------------

  /**
   * The Python backend now serves HTTP and WebSocket on the same port.
   * WebSocket is available at the `/ws` path via HTTP upgrade.
   *
   * Strategy:
   * - Always connect to `ws[s]://<host>/ws` on the same origin.
   */
  private async _discoverWsUrl(): Promise<string> {
    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${wsProtocol}//${location.host}/ws`
  }

  private async _init(): Promise<void> {
    const wsUrl = await this._discoverWsUrl()

    this.ws = new WebSocket(wsUrl)
    this.ws.binaryType = 'arraybuffer'
    this.ws.addEventListener('message', this.handleMessage)

    await new Promise<void>((resolve) => {
      this.resolveReady = resolve

      const timeout = setTimeout(() => {
        console.warn(`WebSocket connection to ${wsUrl} timed out — proceeding without session`)
        resolve()
      }, 10_000)

      this.ws.addEventListener('error', () => {
        clearTimeout(timeout)
        console.warn(`WebSocket connection to ${wsUrl} failed — proceeding without session`)
        resolve()
      })
    })
  }

  // ── WebSocket message handling ──────────────────────────────────────────────

  private handleMessage = (event: MessageEvent): void => {
    // Binary frame: 4-byte header length (BE uint32) + JSON header + PNG data
    if (event.data instanceof ArrayBuffer) {
      this.handleBinaryFrame(event.data as ArrayBuffer)
      return
    }

    if (event.data instanceof Blob) {
      event.data.arrayBuffer().then((ab) => {
        this.handleBinaryFrame(ab)
      })
      return
    }

    // Text (JSON) messages
    try {
      const raw = typeof event.data === 'string' ? event.data : String(event.data)
      const msg = JSON.parse(raw) as Record<string, unknown>

      // First message after connection is session_info
      if (msg.type === 'session_info') {
        this.sessionId = typeof msg.session_id === 'string' ? msg.session_id : ''
        this.resolveReady()
        this._resolveSession()
        return
      }

      this.dispatchJsonMessage(msg)
    } catch {
      // Ignore malformed messages
    }
  }

  private dispatchJsonMessage(msg: Record<string, unknown>): void {
    const type = msg.type as string
    const taskId = typeof msg.task_id === 'string' ? msg.task_id : ''

    switch (type) {
      case 'task_accepted':
        return
      case 'task_progress': {
        if (!this.activeTasks.has(taskId)) return
        const payload: TaskProgressPayload = {
          taskId,
          progress: typeof msg.progress === 'number' ? msg.progress : 0,
          message: typeof msg.message === 'string' ? msg.message : undefined,
        }
        this.emitProgress(taskId, payload)
        return
      }
      case 'task_complete': {
        if (!this.activeTasks.has(taskId)) return
        const pending = this.activeTasks.get(taskId)
        if (!pending) return

        const result = typeof msg.result === 'object' && msg.result !== null
          ? msg.result as Record<string, unknown>
          : {}
        const adapted = adaptTaskResult(pending.command, result)

        if (adapted.kind === 'error') {
          this.emitError(taskId, {
            taskId,
            error: adapted.error,
            code: adapted.code ?? 'TASK_FAILED',
          })
        } else {
          this.emitResult(taskId, {
            taskId,
            data: adapted.data,
          })
        }
        this.activeTasks.delete(taskId)
        return
      }
      case 'task_error': {
        if (!this.activeTasks.has(taskId)) return
        this.emitError(taskId, {
          taskId,
          error: typeof msg.error === 'string' ? msg.error : 'Unknown error',
          code: typeof msg.code === 'string' ? msg.code : 'INTERNAL_ERROR',
        })
        this.activeTasks.delete(taskId)
        return
      }
      case 'task_cancelled': {
        if (!this.activeTasks.has(taskId)) return
        this.emitError(taskId, {
          taskId,
          error: 'Task cancelled',
          code: 'TASK_CANCELLED',
        })
        this.activeTasks.delete(taskId)
        return
      }
    }
  }

  private handleBinaryFrame(buffer: ArrayBuffer): void {
    const view = new DataView(buffer)
    if (buffer.byteLength < 4) return

    const headerLen = view.getUint32(0, false) // big-endian
    if (buffer.byteLength < 4 + headerLen) return

    const headerBytes = new Uint8Array(buffer, 4, headerLen)
    const headerStr = new TextDecoder().decode(headerBytes)
    let header: Record<string, unknown>
    try {
      header = JSON.parse(headerStr)
    } catch {
      return
    }

    const taskId = typeof header.task_id === 'string' ? header.task_id : ''
    if (!taskId || !this.activeTasks.has(taskId)) return

    const pending = this.activeTasks.get(taskId)
    if (!pending) return

    const pngBytes = new Uint8Array(buffer, 4 + headerLen)

    // Adapt the binary result similar to electron/main.ts handleBinaryFrame
    const adapted = adaptTaskResult(pending.command, {
      status: header.status ?? 'ok',
      imageData: header.imageData ?? null,
      fullImageB64: '__binary_blob__',
      metadata: header.metadata,
      stats: header.stats,
      contrast: header.contrast,
      thumbnails: header.thumbnails,
      nextStart: header.nextStart,
      chunkSize: header.chunkSize,
      previewB64: '__binary_blob__',
      origHeight: header.origHeight ?? header.height,
      origWidth: header.origWidth ?? header.width,
    })

    if (adapted.kind === 'error') {
      this.emitError(taskId, {
        taskId,
        error: adapted.error,
        code: adapted.code ?? 'TASK_FAILED',
      })
      return
    }

    // Emit binary data payload
    this.emitBinary(taskId, {
      taskId,
      mime: typeof header.mime === 'string' ? header.mime : 'image/png',
      frame: typeof header.frame === 'number' ? header.frame : 0,
      width: typeof header.width === 'number' ? header.width : 0,
      height: typeof header.height === 'number' ? header.height : 0,
      data: pngBytes.buffer.slice(pngBytes.byteOffset, pngBytes.byteOffset + pngBytes.byteLength),
    })

    // Emit adapted result
    this.emitResult(taskId, {
      taskId,
      data: adapted.data,
    })

    this.activeTasks.delete(taskId)
  }

  // ── Handler emission helpers ────────────────────────────────────────────────

  private emitProgress(taskId: string, payload: TaskProgressPayload): void {
    const handlers = this.progressHandlers.get(taskId)
    if (handlers) {
      for (const cb of handlers) cb(payload)
    }
  }

  private emitResult(taskId: string, payload: TaskResultPayload): void {
    const handlers = this.resultHandlers.get(taskId)
    if (handlers) {
      for (const cb of handlers) cb(payload)
    }
  }

  private emitError(taskId: string, payload: TaskErrorPayload): void {
    const handlers = this.errorHandlerStore.get(taskId)
    if (handlers) {
      for (const cb of handlers) cb(payload)
    }
  }

  private emitBinary(taskId: string, payload: TaskBinaryPayload): void {
    const handlers = this.binaryHandlers.get(taskId)
    if (handlers) {
      for (const cb of handlers) cb(payload)
    }
  }

  // ── Task operations ─────────────────────────────────────────────────────────

  async submitTask(command: string, params: Record<string, unknown>): Promise<TaskSubmitResponse> {
    // Wait for WebSocket to be ready (session_info received)
    await this.wsReady

    const route = COMMAND_ROUTE_MAP[command]
    if (!route) {
      throw new Error(`Unsupported task command: ${command}`)
    }

    const taskId = generateUUID()
    const normalized = normalizeTaskParams(command, params)

    this.activeTasks.set(taskId, { command })

    const message = {
      type: 'task_submit' as const,
      task_id: taskId,
      route,
      payload: normalized,
    }
    this.ws.send(JSON.stringify(message))

    return { taskId }
  }

  async cancelTask(taskId: string): Promise<void> {
    await this.wsReady
    this.ws.send(JSON.stringify({
      type: 'task_cancel',
      task_id: taskId,
    }))
  }

  onTaskProgress(taskId: string, callback: (payload: TaskProgressPayload) => void): () => void {
    let set = this.progressHandlers.get(taskId)
    if (!set) {
      set = new Set()
      this.progressHandlers.set(taskId, set)
    }
    set.add(callback)
    return () => {
      set!.delete(callback)
      if (set!.size === 0) this.progressHandlers.delete(taskId)
    }
  }

  onTaskResult(taskId: string, callback: (payload: TaskResultPayload) => void): () => void {
    let set = this.resultHandlers.get(taskId)
    if (!set) {
      set = new Set()
      this.resultHandlers.set(taskId, set)
    }
    set.add(callback)
    return () => {
      set!.delete(callback)
      if (set!.size === 0) this.resultHandlers.delete(taskId)
    }
  }

  onTaskError(taskId: string, callback: (payload: TaskErrorPayload) => void): () => void {
    let set = this.errorHandlerStore.get(taskId)
    if (!set) {
      set = new Set()
      this.errorHandlerStore.set(taskId, set)
    }
    set.add(callback)
    return () => {
      set!.delete(callback)
      if (set!.size === 0) this.errorHandlerStore.delete(taskId)
    }
  }

  onTaskBinaryData(taskId: string, callback: (payload: TaskBinaryPayload) => void): () => void {
    let set = this.binaryHandlers.get(taskId)
    if (!set) {
      set = new Set()
      this.binaryHandlers.set(taskId, set)
    }
    set.add(callback)
    return () => {
      set!.delete(callback)
      if (set!.size === 0) this.binaryHandlers.delete(taskId)
    }
  }

  // ── File dialogs ────────────────────────────────────────────────────────────

  async selectFiles(options?: DialogOpenFileOptions): Promise<DialogOpenFileResult> {
    return new Promise<DialogOpenFileResult>((resolve, reject) => {
      const input = document.createElement('input')
      input.type = 'file'
      input.style.display = 'none'
      input.multiple = options?.multiSelections ?? false

      if (options?.filters && options.filters.length > 0) {
        const extensions = options.filters
          .flatMap((f) => f.extensions)
          .filter((e) => e !== '*')
        if (extensions.length > 0) {
          input.accept = extensions.map((e) => `.${e}`).join(',')
        }
      }

      document.body.appendChild(input)

      let settled = false
      const cleanup = () => {
        if (settled) return
        settled = true
        window.removeEventListener('focus', onFocus)
        input.value = ''
        if (input.parentNode) {
          document.body.removeChild(input)
        }
      }

      const onFocus = () => {
        setTimeout(() => {
          if (settled) return
          if (!input.files || input.files.length === 0) {
            cleanup()
            resolve(null)
          }
        }, 300)
      }
      window.addEventListener('focus', onFocus)

      input.addEventListener('change', () => {
        const files = input.files
        if (!files || files.length === 0) {
          cleanup()
          resolve(null)
          return
        }

        const captured = Array.from(files)
        cleanup()

        setTimeout(async () => {
          try {
            const paths: string[] = []
            for (const f of captured) {
              const serverPath = await this.uploadFile(f)
              if (!serverPath) {
                throw new Error(`Upload returned empty path for: ${f.name}`)
              }
              paths.push(serverPath)
            }
            resolve(paths.length === 1 ? paths[0] : paths)
          } catch (error) {
            reject(error instanceof Error ? error : new Error(String(error)))
          }
        }, 0)
      })

      input.click()
    })
  }

  async selectFolder(_defaultPath?: string): Promise<string | null> {
    // Folder selection not available in browser mode
    return null
  }

  async selectSavePath(_options?: DialogSaveFileOptions): Promise<string | null> {
    // Save path dialog not available in browser mode
    return null
  }

  // ── Python service ──────────────────────────────────────────────────────────

  async getPythonStatus(): Promise<PythonStatus | null> {
    try {
      const response = await fetch('/health')
      if (!response.ok) return null
      const report = await response.json() as Record<string, unknown>
      return {
        canRetry: true,
        dependencyStatus: (typeof report.dependency_status === 'string'
          ? report.dependency_status : 'unknown') as PythonStatus['dependencyStatus'],
        detail: typeof report.service_name === 'string' ? report.service_name : '',
        lastExitCode: null,
        port: null,
        pythonPath: typeof report.python_executable === 'string' ? report.python_executable : null,
        pythonVersion: typeof report.python_version === 'string' ? report.python_version : null,
        state: 'healthy',
      }
    } catch {
      return null
    }
  }

  onPythonStatusChange(_callback: (status: PythonStatus) => void): () => void {
    // No push-based status in web mode
    return () => {}
  }

  async restartPython(): Promise<PythonStatus | null> {
    // No restart capability in web mode
    return null
  }

  // ── App metadata ────────────────────────────────────────────────────────────

  async getAppMeta(): Promise<AppMeta> {
    // Try reading version from meta tag injected at build time
    const metaTag = document.querySelector('meta[name="app-version"]')
    const version = metaTag?.getAttribute('content') ?? '0.1.0'

    return {
      appName: 'X-FAIS',
      appVersion: version,
      logDirectory: '',
      platform: 'web',
    }
  }

  // ── pyFAI tools ─────────────────────────────────────────────────────────────

  async checkPyfai(): Promise<PyfaiCheckResult> {
    await this.wsReady

    const taskId = generateUUID()
    this.activeTasks.set(taskId, { command: 'check_pyfai' })

    return new Promise<PyfaiCheckResult>((resolve) => {
      const unsubResult = this.onTaskResult(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve(payload.data as PyfaiCheckResult)
      })

      const unsubError = this.onTaskError(taskId, () => {
        unsubResult()
        unsubError()
        resolve({
          embedded: { available: false, version: null, calib2Path: null, hasQtBinding: false },
          system: { available: false, version: null, calib2Path: null, hasQtBinding: false },
          overall: 'not_found',
        })
      })

      this.ws.send(JSON.stringify({
        type: 'task_submit',
        task_id: taskId,
        route: '/api/check_pyfai',
        payload: {},
      }))
    })
  }

  async launchPyfai(): Promise<{ success: boolean; error?: string }> {
    await this.wsReady

    const taskId = generateUUID()
    this.activeTasks.set(taskId, { command: 'launch_pyfai' })

    return new Promise<{ success: boolean; error?: string }>((resolve) => {
      const unsubResult = this.onTaskResult(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve(payload.data as { success: boolean; error?: string })
      })

      const unsubError = this.onTaskError(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve({ success: false, error: payload.error })
      })

      this.ws.send(JSON.stringify({
        type: 'task_submit',
        task_id: taskId,
        route: '/api/launch_pyfai',
        payload: {},
      }))
    })
  }

  async installPyfai(): Promise<{ success: boolean; command?: string; error?: string }> {
    await this.wsReady

    const taskId = generateUUID()
    this.activeTasks.set(taskId, { command: 'install_pyfai' })

    return new Promise<{ success: boolean; command?: string; error?: string }>((resolve) => {
      const unsubResult = this.onTaskResult(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve(payload.data as { success: boolean; command?: string; error?: string })
      })

      const unsubError = this.onTaskError(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve({ success: false, error: payload.error })
      })

      this.ws.send(JSON.stringify({
        type: 'task_submit',
        task_id: taskId,
        route: '/api/install_pyfai',
        payload: {},
      }))
    })
  }

  async exportBatPyfai(): Promise<{ success: boolean; error?: string }> {
    await this.wsReady

    const taskId = generateUUID()
    this.activeTasks.set(taskId, { command: 'export_bat_pyfai' })

    return new Promise<{ success: boolean; error?: string }>((resolve) => {
      const unsubResult = this.onTaskResult(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve(payload.data as { success: boolean; error?: string })
      })

      const unsubError = this.onTaskError(taskId, (payload) => {
        unsubResult()
        unsubError()
        resolve({ success: false, error: payload.error })
      })

      this.ws.send(JSON.stringify({
        type: 'task_submit',
        task_id: taskId,
        route: '/api/export_bat_pyfai',
        payload: {},
      }))
    })
  }

  // ── Web-mode file operations ────────────────────────────────────────────────

  private async _waitForSession(timeoutMs = 8_000): Promise<boolean> {
    if (this.sessionId) return true
    try {
      await Promise.race([
        this._sessionAcquired,
        new Promise<void>((_, rej) => setTimeout(() => rej(new Error('timeout')), timeoutMs)),
      ])
      return !!this.sessionId
    } catch {
      return false
    }
  }

  async uploadFile(file: File, timeout = 15_000): Promise<string> {
    const sessionOk = await this._waitForSession(timeout - 3_000)
    if (!sessionOk) {
      throw new Error('无法建立连接：未能获取服务器会话 ID，请检查网络连接或刷新页面重试。')
    }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/upload', {
        method: 'POST',
        headers: { 'X-Session-Id': this.sessionId },
        body: formData,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`)
      }

      const data = await response.json() as Record<string, unknown>
      const files = Array.isArray(data.files) ? data.files : []
      if (files.length === 0) {
        throw new Error('Upload returned no files')
      }
      const firstFile = files[0] as Record<string, unknown>
      return typeof firstFile.path === 'string' ? firstFile.path : ''
    } finally {
      clearTimeout(timer)
    }
  }

  async downloadFile(serverPath: string, filename: string): Promise<void> {
    const response = await fetch(
      `/api/download?path=${encodeURIComponent(serverPath)}`,
      { headers: { 'X-Session-Id': this.sessionId } },
    )

    if (!response.ok) {
      throw new Error(`Download failed: ${response.status} ${response.statusText}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // ── Environment detection ───────────────────────────────────────────────────

  isDesktop(): boolean {
    return false
  }
}
