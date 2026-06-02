import { contextBridge, ipcRenderer } from 'electron'
import { IPC_CHANNELS } from './constants'
import type {
  DialogOpenFileOptions,
  DialogOpenFileResult,
  DialogSaveFileOptions,
  TaskSubmitRequest,
  TaskSubmitResponse,
  TaskProgressPayload,
  TaskResultPayload,
  TaskErrorPayload
} from '../src/types/ipc'

export interface DesktopAppMeta {
  appName: string
  appVersion: string
  logDirectory: string
  platform: string
}

export interface DesktopPythonStatus {
  canRetry: boolean
  dependencyStatus: 'ready' | 'missing' | 'outdated' | 'unknown'
  detail: string
  lastExitCode: number | null
  port: number | null
  pythonPath: string | null
  pythonVersion: string | null
  state: 'starting' | 'healthy' | 'error' | 'stopped' | 'restarting'
}

const desktopApi = {
  getAppMeta: (): Promise<DesktopAppMeta> => ipcRenderer.invoke(IPC_CHANNELS.appMeta) as Promise<DesktopAppMeta>,
  dialog: {
    openFile: (options?: DialogOpenFileOptions): Promise<DialogOpenFileResult> =>
      ipcRenderer.invoke(IPC_CHANNELS.dialogOpenFile, options) as Promise<DialogOpenFileResult>,
    saveFile: (options?: DialogSaveFileOptions): Promise<string | null> =>
      ipcRenderer.invoke(IPC_CHANNELS.dialogSaveFile, options) as Promise<string | null>,
    openFolder: (defaultPath?: string): Promise<string | null> =>
      ipcRenderer.invoke(IPC_CHANNELS.dialogOpenFolder, defaultPath) as Promise<string | null>
  },
  python: {
    crashForTest: (): Promise<boolean> => ipcRenderer.invoke(IPC_CHANNELS.pythonCrashForTest) as Promise<boolean>,
    getStatus: (): Promise<DesktopPythonStatus> => ipcRenderer.invoke(IPC_CHANNELS.pythonStatus) as Promise<DesktopPythonStatus>,
    onStatusChange: (listener: (status: DesktopPythonStatus) => void): (() => void) => {
      const subscription = (_event: Electron.IpcRendererEvent, status: DesktopPythonStatus) => {
        listener(status)
      }

      ipcRenderer.on(IPC_CHANNELS.pythonStatusChanged, subscription)

      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.pythonStatusChanged, subscription)
      }
    },
    restart: (): Promise<DesktopPythonStatus> => ipcRenderer.invoke(IPC_CHANNELS.pythonRestart) as Promise<DesktopPythonStatus>
  },
  task: {
    submit: (command: string, params: Record<string, unknown>): Promise<TaskSubmitResponse> =>
      ipcRenderer.invoke(IPC_CHANNELS.taskSubmit, { command, params } satisfies TaskSubmitRequest) as Promise<TaskSubmitResponse>,
    cancel: (taskId: string): Promise<void> =>
      ipcRenderer.invoke(IPC_CHANNELS.taskCancel, { taskId }) as Promise<void>,
    onProgress: (taskId: string, callback: (payload: TaskProgressPayload) => void): (() => void) => {
      const subscription = (_event: Electron.IpcRendererEvent, payload: TaskProgressPayload) => {
        if (payload.taskId === taskId) callback(payload)
      }
      ipcRenderer.on(IPC_CHANNELS.taskOnProgress, subscription)
      return () => { ipcRenderer.removeListener(IPC_CHANNELS.taskOnProgress, subscription) }
    },
    onResult: (taskId: string, callback: (payload: TaskResultPayload) => void): (() => void) => {
      const subscription = (_event: Electron.IpcRendererEvent, payload: TaskResultPayload) => {
        if (payload.taskId === taskId) callback(payload)
      }
      ipcRenderer.on(IPC_CHANNELS.taskOnResult, subscription)
      return () => { ipcRenderer.removeListener(IPC_CHANNELS.taskOnResult, subscription) }
    },
    onError: (taskId: string, callback: (payload: TaskErrorPayload) => void): (() => void) => {
      const subscription = (_event: Electron.IpcRendererEvent, payload: TaskErrorPayload) => {
        if (payload.taskId === taskId) callback(payload)
      }
      ipcRenderer.on(IPC_CHANNELS.taskOnError, subscription)
      return () => { ipcRenderer.removeListener(IPC_CHANNELS.taskOnError, subscription) }
    },
    onBinaryData: (taskId: string, callback: (payload: { taskId: string; mime: string; frame: number; width: number; height: number; data: ArrayBuffer }) => void): (() => void) => {
      const subscription = (_event: Electron.IpcRendererEvent, payload: any) => {
        if (payload.taskId === taskId) callback(payload)
      }
      ipcRenderer.on(IPC_CHANNELS.taskBinaryData, subscription)
      return () => { ipcRenderer.removeListener(IPC_CHANNELS.taskBinaryData, subscription) }
    }
  }
}

const desktopApiWithPyfai = {
  ...desktopApi,
  pyfai: {
    check: (): Promise<{
      embedded: { available: boolean; version: string | null; calib2Path: string | null }
      system: { available: boolean; version: string | null; calib2Path: string | null }
      overall: 'available' | 'embedded_only' | 'system_only' | 'not_found'
    }> => ipcRenderer.invoke(IPC_CHANNELS.pyfaiCheck) as Promise<any>,
    launch: (): Promise<{ success: boolean }> =>
      ipcRenderer.invoke(IPC_CHANNELS.pyfaiLaunch) as Promise<{ success: boolean }>,
    install: (): Promise<{ success: boolean; command?: string; error?: string }> =>
      ipcRenderer.invoke(IPC_CHANNELS.pyfaiInstall) as Promise<{ success: boolean; command?: string; error?: string }>
  }
}

contextBridge.exposeInMainWorld('desktop', desktopApiWithPyfai)
