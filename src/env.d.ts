/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

interface DesktopAppMeta {
  appName: string
  appVersion: string
  logDirectory: string
  platform: string
}

interface DesktopPythonStatus {
  canRetry: boolean
  dependencyStatus: 'ready' | 'missing' | 'outdated' | 'unknown'
  detail: string
  lastExitCode: number | null
  port: number | null
  pythonPath: string | null
  pythonVersion: string | null
  state: 'starting' | 'healthy' | 'error' | 'stopped' | 'restarting'
}

interface FileFilter {
  name: string
  extensions: string[]
}

interface DialogOpenFileOptions {
  filters?: FileFilter[]
  defaultPath?: string
  multiSelections?: boolean
}

interface DialogSaveFileOptions {
  filters?: FileFilter[]
  defaultPath?: string
}

interface TaskSubmitResponse {
  taskId: string
}

interface TaskProgressPayload {
  taskId: string
  progress: number
  message?: string
}

interface TaskResultPayload {
  taskId: string
  data: unknown
}

interface TaskErrorPayload {
  taskId: string
  error: string
  code?: string
}

interface TaskBinaryPayload {
  taskId: string
  mime: string
  frame: number
  width: number
  height: number
  data: ArrayBuffer
}

interface PyfaiCheckResult {
  embedded: {
    available: boolean
    version: string | null
    calib2Path: string | null
    hasQtBinding: boolean
  }
  system: {
    available: boolean
    version: string | null
    calib2Path: string | null
    hasQtBinding: boolean
  }
  overall: 'available' | 'embedded_only' | 'system_only' | 'not_found'
}

interface Window {
  desktop: {
    getAppMeta: () => Promise<DesktopAppMeta>
    dialog: {
      openFile: (options?: DialogOpenFileOptions) => Promise<string | null>
      saveFile: (options?: DialogSaveFileOptions) => Promise<string | null>
      openFolder: (defaultPath?: string) => Promise<string | null>
    }
    python: {
      crashForTest: () => Promise<boolean>
      getStatus: () => Promise<DesktopPythonStatus>
      onStatusChange: (listener: (status: DesktopPythonStatus) => void) => () => void
      restart: () => Promise<DesktopPythonStatus>
    }
    task: {
      submit: (command: string, params: Record<string, unknown>) => Promise<TaskSubmitResponse>
      cancel: (taskId: string) => Promise<void>
      onProgress: (taskId: string, callback: (payload: TaskProgressPayload) => void) => () => void
      onResult: (taskId: string, callback: (payload: TaskResultPayload) => void) => () => void
      onError: (taskId: string, callback: (payload: TaskErrorPayload) => void) => () => void
      onBinaryData: (taskId: string, callback: (payload: TaskBinaryPayload) => void) => () => void
    }
    pyfai: {
      check: () => Promise<PyfaiCheckResult>
      launch: () => Promise<{ success: boolean; error?: string }>
      install: () => Promise<{ success: boolean; command?: string; error?: string }>
      exportBat: () => Promise<{ success: boolean; error?: string }>
    }
  }
}
