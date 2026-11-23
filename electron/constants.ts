import pkg from '../package.json'

export const APP_NAME = 'X-FAIS'
// 单一来源：package.json 的 version（v0.3.2 前此处硬编码漏升，更新检查报旧版）
// Single source of truth: package.json version (previously a stale hardcode)
export const APP_VERSION = pkg.version
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
  readTextFile: 'dialog:readTextFile',
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
  pyfaiInstall: 'pyfai:install',
  pyfaiInstallDeps: 'pyfai:installDeps',
  pyfaiExportBat: 'pyfai:exportBat',
  // SFTP 记住密码（safeStorage/DPAPI 加密，存 userData，不入仓库）
  // SFTP remembered secret (safeStorage/DPAPI encrypted, lives in userData)
  sftpSecretStore: 'sftpSecret:store',
  sftpSecretLoad: 'sftpSecret:load',
  sftpSecretDelete: 'sftpSecret:delete',
  // 在系统资源管理器中打开目录 / reveal a directory in the OS file manager
  shellOpenPath: 'shell:openPath',
  // 设置 → 主进程启动环境覆盖（OMP 线程数等）/ Settings → main-process launch env overrides
  settingsSetPythonLaunchEnv: 'settings:setPythonLaunchEnv'
} as const
