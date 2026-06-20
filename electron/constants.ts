export const APP_NAME = 'X-FAIS'
export const APP_VERSION = '0.2.1'
export const IPC_CHANNELS = {
  appMeta: 'app:meta',
  pythonStatus: 'python:status',
  pythonRestart: 'python:restart',
  pythonCrashForTest: 'python:crash-for-test',
  pythonStatusChanged: 'python:status-changed',
  // 文件对话框 / File dialogs
  dialogOpenFile: 'dialog:openFile',
  dialogSaveFile: 'dialog:saveFile',
  dialogOpenFolder: 'dialog:openFolder',
  // 任务桥接 / Task bridge (renderer ↔ Python WebSocket)
  taskSubmit: 'task:submit',
  taskCancel: 'task:cancel',
  taskOnProgress: 'task:onProgress',
  taskOnResult: 'task:onResult',
  taskOnError: 'task:onError',
  taskBinaryData: 'task:binaryData',
  // pyFAI 工具 / pyFAI tools
  pyfaiCheck: 'pyfai:check',
  pyfaiLaunch: 'pyfai:launch',
  pyfaiInstall: 'pyfai:install'
} as const
