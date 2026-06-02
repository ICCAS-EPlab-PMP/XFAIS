import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { execSync, spawn } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { APP_NAME, APP_VERSION, IPC_CHANNELS } from './constants'
import { PythonServiceManager, type PythonServiceStatus } from './python/manager'
import type {
  ClientMessage,
  DialogOpenFileOptions,
  DialogSaveFileOptions,
  HealthReport,
  ServerMessage,
  TaskCancelRequest,
  TaskErrorPayload,
  TaskProgressPayload,
  TaskResultPayload,
  TaskSubmitRequest,
  TaskSubmitResponse
} from '../src/types/ipc'
import { normalizeTaskParams, adaptTaskResult } from '../src/lib/task-adapter'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

let mainWindow: BrowserWindow | null = null
let pythonManager: PythonServiceManager | null = null
let isQuitting = false

const getLogDirectory = (): string => path.join(app.getPath('userData'), 'logs')

const publishPythonStatus = (status: PythonServiceStatus): void => {
  mainWindow?.webContents.send(IPC_CHANNELS.pythonStatusChanged, status)
}

const createMainWindow = async (): Promise<void> => {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1180,
    minHeight: 760,
    show: false,
    autoHideMenuBar: true,
    title: APP_NAME,
    backgroundColor: '#F8FAFC',
    webPreferences: {
      preload: path.resolve(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  const devServerUrl = process.env.VITE_DEV_SERVER_URL
  if (devServerUrl) {
    await mainWindow.loadURL(devServerUrl)
    return
  }

  await mainWindow.loadFile(path.resolve(__dirname, '../../dist/index.html'))
}

const registerAppMeta = (): void => {
  ipcMain.handle(IPC_CHANNELS.appMeta, () => ({
    appName: APP_NAME,
    appVersion: APP_VERSION,
    logDirectory: getLogDirectory(),
    platform: process.platform
  }))
}

const registerPythonRuntime = (): void => {
  pythonManager = new PythonServiceManager({
    allowTestCrash: !app.isPackaged,
    appRoot: app.getAppPath(),
    isPackaged: app.isPackaged,
    logDirectory: getLogDirectory(),
    onStatusChange: publishPythonStatus,
    resourcesPath: process.resourcesPath
  })

  ipcMain.handle(IPC_CHANNELS.pythonStatus, () => pythonManager?.getStatus() ?? null)
  ipcMain.handle(IPC_CHANNELS.pythonRestart, async () => await pythonManager?.restart())
  ipcMain.handle(IPC_CHANNELS.pythonCrashForTest, async () => {
    await pythonManager?.crashForTest()
    return true
  })
}

const registerDialogHandlers = (): void => {
  ipcMain.handle(
    IPC_CHANNELS.dialogOpenFile,
    async (_event, options?: DialogOpenFileOptions): Promise<string | string[] | null> => {
      const win = BrowserWindow.getFocusedWindow()
      const { canceled, filePaths } = await dialog.showOpenDialog(win ?? undefined!, {
        properties: ['openFile' as const, ...(options?.multiSelections ? ['multiSelections' as const] : [])],
        filters: options?.filters,
        defaultPath: options?.defaultPath
      })
      if (canceled) return null
      return options?.multiSelections ? filePaths : (filePaths[0] ?? null)
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.dialogSaveFile,
    async (_event, options?: DialogSaveFileOptions): Promise<string | null> => {
      const win = BrowserWindow.getFocusedWindow()
      const { canceled, filePath } = await dialog.showSaveDialog(win ?? undefined!, {
        filters: options?.filters,
        defaultPath: options?.defaultPath
      })
      return canceled ? null : filePath ?? null
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.dialogOpenFolder,
    async (_event, defaultPath?: string): Promise<string | null> => {
      const win = BrowserWindow.getFocusedWindow()
      const { canceled, filePaths } = await dialog.showOpenDialog(win ?? undefined!, {
        properties: ['openDirectory'],
        defaultPath
      })
      return canceled ? null : filePaths[0] ?? null
    }
  )
}

interface PendingTask {
  taskId: string
  command: string
  route: string | null
}

const activeTasks = new Map<string, PendingTask>()

// ── pyFAI 工具处理 / pyFAI tool handlers ───────────────────────────────────

const getEmbeddedPythonRoot = (): string => {
  const appRoot = app.getAppPath()
  const embeddedDir = 'python-3.11.9-win32-x64'
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'python-runtime', embeddedDir)
  }
  return path.join(appRoot, '.python-runtime', embeddedDir)
}

const getEmbeddedPythonScriptsDir = (): string => {
  return path.join(getEmbeddedPythonRoot(), 'Scripts')
}

const getEmbeddedPythonExe = (): string => {
  return path.join(getEmbeddedPythonRoot(), 'python.exe')
}

interface PyfaiCheckResult {
  embedded: { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean }
  system: { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean }
  overall: 'available' | 'embedded_only' | 'system_only' | 'not_found'
}

const checkQtBindingAvailable = (pythonExe: string): boolean => {
  try {
    execSync(`"${pythonExe}" -c "from PySide6 import QtWidgets; print('ok')" 2>nul`, {
      timeout: 8000,
      encoding: 'utf-8',
      windowsHide: true
    })
    return true
  } catch {
    try {
      execSync(`"${pythonExe}" -c "from PyQt6 import QtWidgets; print('ok')" 2>nul`, {
        timeout: 8000,
        encoding: 'utf-8',
        windowsHide: true
      })
      return true
    } catch {
      return false
    }
  }
}

const checkPyfaiEmbedded = (): { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean } => {
  const scriptsDir = getEmbeddedPythonScriptsDir()
  const calib2Exe = path.join(scriptsDir, 'pyFAI-calib2.exe')
  const calib2Path = existsSync(calib2Exe) ? calib2Exe : null

  const pythonExe = getEmbeddedPythonExe()
  let version: string | null = null
  try {
    const output = execSync(`"${pythonExe}" -c "import pyFAI; print(pyFAI.version)"`, {
      timeout: 10000,
      encoding: 'utf-8',
      windowsHide: true
    }).trim()
    version = output || null
  } catch {
    // pyFAI not importable in embedded Python
  }

  const hasQtBinding = calib2Path !== null ? checkQtBindingAvailable(pythonExe) : false

  return { available: version !== null || calib2Path !== null, version, calib2Path, hasQtBinding }
}

const checkPyfaiSystem = (): { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean } => {
  let calib2Path: string | null = null

  // Method 1: 在 PATH 中查找 calib2 exe
  try {
    const output = execSync('where pyFAI-calib2.exe 2>nul', {
      timeout: 5000, encoding: 'utf-8', windowsHide: true
    }).trim()
    if (output) calib2Path = output.split('\n')[0].trim()
  } catch { /* not on PATH */ }

  // Method 2: 通过 python 获取版本并搜索 Scripts 目录
  let version: string | null = null
  try {
    const output = execSync('python -c "import pyFAI; print(pyFAI.version)" 2>nul', {
      timeout: 10000, encoding: 'utf-8', windowsHide: true
    }).trim()
    if (output) version = output
  } catch { /* not importable via python */ }

  // 如果版本找到了但没找到 exe，通过 Python 定位 Scripts 目录
  if (version && !calib2Path) {
    for (const pyCmd of ['python', 'py']) {
      try {
        const userBase = execSync(
          `${pyCmd} -c "import site; print(site.getuserbase())" 2>nul`,
          { timeout: 5000, encoding: 'utf-8', windowsHide: true }
        ).trim()
        if (userBase) {
          // Try Python{sys.version}\Scripts pattern
          const verStr = execSync(
            `${pyCmd} -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>nul`,
            { timeout: 5000, encoding: 'utf-8', windowsHide: true }
          ).trim()
          const candidate = path.join(userBase, `Python${verStr}`, 'Scripts', 'pyFAI-calib2.exe')
          if (existsSync(candidate)) { calib2Path = candidate; break }
        }
      } catch { /* continue */ }

      try {
        const prefix = execSync(
          `${pyCmd} -c "import sys; print(sys.prefix)" 2>nul`,
          { timeout: 5000, encoding: 'utf-8', windowsHide: true }
        ).trim()
        const candidate = path.join(prefix, 'Scripts', 'pyFAI-calib2.exe')
        if (existsSync(candidate)) { calib2Path = candidate; break }
      } catch { /* continue */ }
    }
  }

  // Method 3: 尝试 py launcher（若 python 命令未找到 pyFAI）
  if (!version) {
    try {
      const output = execSync('py -c "import pyFAI; print(pyFAI.version)" 2>nul', {
        timeout: 10000, encoding: 'utf-8', windowsHide: true
      }).trim()
      if (output) version = output
    } catch { /* py launcher not available */ }
  }

  // Method 4: 全局 Python 安装目录搜索
  if (!calib2Path) {
    try {
      const localAppData = process.env.LOCALAPPDATA
      if (localAppData) {
        const dirOutput = execSync(
          `dir /b /ad "${localAppData}\\Programs\\Python\\Python*" 2>nul`,
          { timeout: 5000, encoding: 'utf-8', windowsHide: true }
        ).trim()
        if (dirOutput) {
          for (const d of dirOutput.split('\n')) {
            const dirName = d.trim()
            if (!dirName) continue
            const candidate = path.join(localAppData, 'Programs', 'Python', dirName, 'Scripts', 'pyFAI-calib2.exe')
            if (existsSync(candidate)) { calib2Path = candidate; break }
          }
        }
      }
    } catch { /* not found */ }
  }

  let hasQtBinding = false
  if (calib2Path) {
    try {
      execSync('python -c "from PySide6 import QtWidgets; print(\'ok\')" 2>nul', {
        timeout: 8000, encoding: 'utf-8', windowsHide: true
      })
      hasQtBinding = true
    } catch {
      try {
        execSync('python -c "from PyQt6 import QtWidgets; print(\'ok\')" 2>nul', {
          timeout: 8000, encoding: 'utf-8', windowsHide: true
        })
        hasQtBinding = true
      } catch {
        // continue
      }
    }
  }

  return { available: version !== null || calib2Path !== null, version, calib2Path, hasQtBinding }
}

const registerPyfaiHandlers = (): void => {
  ipcMain.handle('pyfai:check', async (): Promise<PyfaiCheckResult> => {
    const embeddedResult = checkPyfaiEmbedded()
    const systemResult = checkPyfaiSystem()

    let overall: PyfaiCheckResult['overall']
    if (embeddedResult.available && systemResult.available) {
      overall = 'available'
    } else if (embeddedResult.available) {
      overall = 'embedded_only'
    } else if (systemResult.available) {
      overall = 'system_only'
    } else {
      overall = 'not_found'
    }

    return { embedded: embeddedResult, system: systemResult, overall }
  })

  ipcMain.handle('pyfai:launch', async (): Promise<{ success: boolean; error?: string }> => {
    const embedded = checkPyfaiEmbedded()
    const system = checkPyfaiSystem()

    // 优先使用系统 Python 的 pyFAI-calib2（系统 Python 有 PySide6 Qt 绑定）
    // 仅当系统不可用时才尝试嵌入式 Python
    let exePath: string | null = null
    let pythonCmd: string | null = null

    if (system.calib2Path && existsSync(system.calib2Path)) {
      // 系统 Python 的 pyFAI-calib2.exe（它关联的 Python 有 PySide6）
      exePath = system.calib2Path
    } else if (system.available) {
      // 系统 Python 可用但找不到 exe，用 python -m
      pythonCmd = 'python'
    } else if (embedded.calib2Path && existsSync(embedded.calib2Path)) {
      // 嵌入式 Python 的 pyFAI-calib2.exe
      exePath = embedded.calib2Path
    } else if (embedded.available) {
      // 嵌入式 Python 可用但找不到 exe
      pythonCmd = getEmbeddedPythonExe()
    } else {
      return { success: false, error: '未找到可用的 pyFAI-calib2。请先安装 pyFAI。' }
    }

    try {
      const child = exePath
        ? spawn(exePath, [], { detached: true, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: false })
        : spawn(pythonCmd!, ['-m', 'pyFAI.app.calib2'], { detached: true, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: false })

      let startupFailed = false
      let startupError = ''

      child.stderr?.setEncoding('utf8')
      child.stderr?.on('data', (chunk: string) => {
        startupError += chunk
      })

      child.on('error', (err) => {
        startupFailed = true
        startupError = err.message
      })

      child.unref()

      await new Promise(resolve => setTimeout(resolve, 800))

      if (startupFailed || (child.exitCode !== null && child.exitCode !== 0)) {
        const errorMsg = startupError.includes('Qt wrapper')
          ? 'pyFAI-calib2 需要 Qt 绑定（PySide6 或 PyQt6），但当前 Python 环境中未安装。\n请在终端运行: pip install PySide6'
          : `pyFAI-calib2 启动失败: ${startupError || `进程退出码 ${child.exitCode}`}`
        return { success: false, error: errorMsg }
      }

      return { success: true }
    } catch (err) {
      return { success: false, error: `启动 pyFAI-calib2 失败: ${(err as Error).message}` }
    }
  })

  ipcMain.handle('pyfai:install', async (): Promise<{ success: boolean; command?: string; error?: string }> => {
    const embedded = checkPyfaiEmbedded()
    if (embedded.available) {
      return { success: true, command: 'pyFAI 已安装在嵌入式 Python 中。' }
    }

    return {
      success: false,
      command: 'pip install pyfai',
      error: '请打开终端（CMD 或 PowerShell），运行以下命令安装 pyFAI：'
    }
  })

  ipcMain.handle('pyfai:exportBat', async (): Promise<{ success: boolean; error?: string }> => {
    const batContent = generateBatScript()

    const win = BrowserWindow.getFocusedWindow()
    const { canceled, filePath } = await dialog.showSaveDialog(win ?? undefined!, {
      title: '导出 pyFAI-calib2 启动脚本',
      defaultPath: 'pyFAI-calib2-launcher.bat',
      filters: [
        { name: '批处理脚本', extensions: ['bat'] },
        { name: '所有文件', extensions: ['*'] }
      ]
    })

    if (canceled || !filePath) {
      return { success: false, error: '用户取消导出' }
    }

    try {
      const fs = await import('node:fs/promises')
      await fs.writeFile(filePath, batContent, 'utf-8')
      return { success: true }
    } catch (err) {
      return { success: false, error: `导出失败: ${(err as Error).message}` }
    }
  })
}

const generateBatScript = (): string => {
  return `@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   pyFAI-calib2 启动器 / Launcher
echo ============================================
echo.

REM 检查 Python 是否可用
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM 获取 Python 版本
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [信息] Python 版本: %PYTHON_VERSION%

REM 检查 pyFAI 是否安装
python -c "import pyFAI" >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未安装 pyFAI
    echo.
    echo 请运行以下命令安装:
    echo   pip install pyFAI fabio
    echo.
    pause
    exit /b 1
)

REM 获取 pyFAI 版本
for /f "delims=" %%i in ('python -c "import pyFAI; print(pyFAI.version)" 2^>^&1') do set PYFAI_VERSION=%%i
echo [信息] pyFAI 版本: %PYFAI_VERSION%

REM 检查 Qt 绑定
set QT_BINDING=none
python -c "from PySide6 import QtWidgets; print('PySide6')" >nul 2>&1
if %errorlevel% equ 0 (
    set QT_BINDING=PySide6
    goto :found_qt
)

python -c "from PyQt6 import QtWidgets; print('PyQt6')" >nul 2>&1
if %errorlevel% equ 0 (
    set QT_BINDING=PyQt6
    goto :found_qt
)

python -c "from PyQt5 import QtWidgets; print('PyQt5')" >nul 2>&1
if %errorlevel% equ 0 (
    set QT_BINDING=PyQt5
    goto :found_qt
)

:found_qt
if "%QT_BINDING%"=="none" (
    echo.
    echo [警告] 未找到 Qt 绑定，pyFAI-calib2 需要以下任一库:
    echo   - PySide6  (推荐)
    echo   - PyQt6
    echo   - PyQt5
    echo.
    echo 请运行以下命令安装 PySide6:
    echo   pip install PySide6
    echo.
    echo 或者安装 PyQt6:
    echo   pip install PyQt6
    echo.
    pause
    exit /b 1
)

echo [信息] Qt 绑定: %QT_BINDING%
echo.

REM 查找 pyFAI-calib2 可执行文件
set CALIB2_PATH=

REM 方法 1: 在 PATH 中查找
where pyFAI-calib2 >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where pyFAI-calib2 2^>^&1') do (
        set CALIB2_PATH=%%i
        goto :found_calib2
    )
)

REM 方法 2: 在 Python Scripts 目录中查找
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)" 2^>^&1') do (
    set PYTHON_PREFIX=%%i
)
if exist "%PYTHON_PREFIX%\\Scripts\\pyFAI-calib2.exe" (
    set CALIB2_PATH=%PYTHON_PREFIX%\\Scripts\\pyFAI-calib2.exe
    goto :found_calib2
)
if exist "%PYTHON_PREFIX%\\Scripts\\pyFAI-calib2" (
    set CALIB2_PATH=%PYTHON_PREFIX%\\Scripts\\pyFAI-calib2
    goto :found_calib2
)

REM 方法 3: 使用 python -m
set CALIB2_PATH=python -m pyFAI.app.calib2

:found_calib2
echo [信息] 启动 pyFAI-calib2...
echo.

REM 启动 pyFAI-calib2
if "%CALIB2_PATH:~0,6%"=="python" (
    %CALIB2_PATH%
) else (
    start "" "%CALIB2_PATH%"
)

endlocal
`
}

const COMMAND_ROUTE_MAP: Record<string, string> = {
  integrate1d: '/api/integrate1d',
  integrate_azimuth: '/api/integrate_azimuth',
  integrate_cake: '/api/integrate_cake',
  integrate_fiber: '/api/integrate_fiber',
  viewer_config: '/api/viewer_config',
      h5convert: '/api/h5convert',
      h5convert_scan: '/api/h5convert_scan',
      h5_extract: '/api/h5_extract',
      h5_list_files: '/api/h5_list_files',
  png_generate: '/api/png_generate',
  export_integration: '/api/export_integration',
  calibrant_generate: '/api/calibrant_generate',
  cell_calibrant_generate: '/api/cell_calibrant_generate',
  manual_calibrant_generate: '/api/manual_calibrant_generate',
  list_space_groups: '/api/list_space_groups'
}



let sharedTaskSocket: WebSocket | null = null
let sharedTaskSocketPromise: Promise<WebSocket> | null = null

const emitTaskProgress = (payload: TaskProgressPayload): void => {
  mainWindow?.webContents.send(IPC_CHANNELS.taskOnProgress, payload)
}

const emitTaskResult = (payload: TaskResultPayload): void => {
  activeTasks.delete(payload.taskId)
  mainWindow?.webContents.send(IPC_CHANNELS.taskOnResult, payload)
}

const emitTaskError = (payload: TaskErrorPayload): void => {
  activeTasks.delete(payload.taskId)
  mainWindow?.webContents.send(IPC_CHANNELS.taskOnError, payload)
}

const getRouteOrThrow = (command: string): string => {
  if (command === 'load_preview') {
    return '/api/viewer_config'
  }
  const route = COMMAND_ROUTE_MAP[command]
  if (!route) {
    throw new Error(`Unsupported task command: ${command}`)
  }
  return route
}

const failAllPendingTasks = (error: string, code = 'TASK_SOCKET_CLOSED'): void => {
  for (const taskId of activeTasks.keys()) {
    emitTaskError({ taskId, error, code } satisfies TaskErrorPayload)
  }
}

const getPythonHttpPort = (): number => {
  const port = pythonManager?.getStatus().port
  if (!port) {
    throw new Error('Python service is not running.')
  }
  return port
}

const getTaskWebSocketPort = async (): Promise<number> => {
  const port = getPythonHttpPort()

  try {
    const response = await fetch(`http://127.0.0.1:${port}/health`)
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status} ${response.statusText}`)
    }

    const report = await response.json() as HealthReport
    return typeof report.ws_port === 'number' ? report.ws_port : port + 1
  } catch {
    return port + 1
  }
}

const handleTaskSocketMessage = (message: ServerMessage): void => {
  switch (message.type) {
    case 'task_accepted':
      return
    case 'task_progress':
      if (!activeTasks.has(message.task_id)) return
      emitTaskProgress({
        taskId: message.task_id,
        progress: message.progress,
        message: message.message
      } satisfies TaskProgressPayload)
      return
    case 'task_complete':
      if (!activeTasks.has(message.task_id)) return
      {
        const pendingTask = activeTasks.get(message.task_id)
        if (!pendingTask) return
        const adapted = adaptTaskResult(pendingTask.command, message.result)
        if (adapted.kind === 'error') {
          emitTaskError({
            taskId: message.task_id,
            error: adapted.error,
            code: adapted.code ?? 'TASK_FAILED'
          } satisfies TaskErrorPayload)
          return
        }
        emitTaskResult({
          taskId: message.task_id,
          data: adapted.data
        } satisfies TaskResultPayload)
      }
      return
    case 'task_error':
      if (!activeTasks.has(message.task_id)) return
      emitTaskError({
        taskId: message.task_id,
        error: message.error,
        code: message.code
      } satisfies TaskErrorPayload)
      return
    case 'task_cancelled':
      if (!activeTasks.has(message.task_id)) return
      emitTaskError({
        taskId: message.task_id,
        error: 'Task cancelled',
        code: 'TASK_CANCELLED'
      } satisfies TaskErrorPayload)
      return
  }
}

const handleBinaryFrame = (data: Buffer): void => {
  const headerLen = data.readUInt32BE(0)
  const headerStr = data.subarray(4, 4 + headerLen).toString('utf-8')
  const header = JSON.parse(headerStr) as Record<string, unknown>
  const pngData = data.subarray(4 + headerLen)

  const taskId = typeof header.task_id === 'string' ? header.task_id : ''
  if (!taskId || !activeTasks.has(taskId)) return

  const pendingTask = activeTasks.get(taskId)
  if (!pendingTask) return

  const command = pendingTask.command
  const adapted = adaptTaskResult(command, {
    status: header.status ?? 'ok',
    imageData: header.imageData ?? null,
    fullImageB64: `__binary_blob__`,
    metadata: header.metadata,
    stats: header.stats,
    contrast: header.contrast,
    thumbnails: header.thumbnails,
    nextStart: header.nextStart,
    chunkSize: header.chunkSize,
    previewB64: `__binary_blob__`,
    origHeight: header.origHeight ?? header.height,
    origWidth: header.origWidth ?? header.width
  })

  if (adapted.kind === 'error') {
    emitTaskError({
      taskId,
      error: adapted.error,
      code: adapted.code ?? 'TASK_FAILED'
    } satisfies TaskErrorPayload)
    return
  }

  mainWindow?.webContents.send(IPC_CHANNELS.taskBinaryData, {
    taskId,
    mime: header.mime ?? 'image/png',
    frame: header.frame ?? 0,
    width: header.width ?? 0,
    height: header.height ?? 0,
    data: pngData.buffer.slice(pngData.byteOffset, pngData.byteOffset + pngData.byteLength)
  })

  emitTaskResult({
    taskId,
    data: adapted.data
  } satisfies TaskResultPayload)
}

const attachTaskSocketListeners = (socket: WebSocket): void => {
  socket.addEventListener('message', (event) => {
    try {
      if (Buffer.isBuffer(event.data)) {
        handleBinaryFrame(event.data)
        return
      }

      if (event.data instanceof Blob) {
        event.data.arrayBuffer().then((ab) => {
          handleBinaryFrame(Buffer.from(ab))
        })
        return
      }

      const raw = typeof event.data === 'string' ? event.data : String(event.data)
      const message = JSON.parse(raw) as ServerMessage
      handleTaskSocketMessage(message)
    } catch (error) {
      failAllPendingTasks(
        error instanceof Error ? `Invalid task socket message: ${error.message}` : 'Invalid task socket message',
        'TASK_SOCKET_PROTOCOL_ERROR'
      )
      socket.close()
    }
  })

  socket.addEventListener('close', () => {
    if (sharedTaskSocket === socket) {
      sharedTaskSocket = null
    }
    sharedTaskSocketPromise = null

    if (!isQuitting) {
      failAllPendingTasks('Task bridge disconnected unexpectedly.', 'TASK_SOCKET_CLOSED')
    }
  })

  socket.addEventListener('error', () => {
    // Close handler centralizes pending task failure and reconnection state reset.
  })
}

const ensureTaskSocket = async (): Promise<WebSocket> => {
  if (sharedTaskSocket && sharedTaskSocket.readyState === WebSocket.OPEN) {
    return sharedTaskSocket
  }

  if (sharedTaskSocketPromise) {
    return sharedTaskSocketPromise
  }

  sharedTaskSocketPromise = (async () => {
    const wsPort = await getTaskWebSocketPort()
    const socket = new WebSocket(`ws://127.0.0.1:${wsPort}`)

    await new Promise<void>((resolve, reject) => {
      const handleOpen = (): void => {
        socket.removeEventListener('open', handleOpen)
        socket.removeEventListener('error', handleError)
        resolve()
      }

      const handleError = (): void => {
        socket.removeEventListener('open', handleOpen)
        socket.removeEventListener('error', handleError)
        reject(new Error('Failed to connect to the Python task WebSocket.'))
      }

      socket.addEventListener('open', handleOpen, { once: true })
      socket.addEventListener('error', handleError, { once: true })
    })

    sharedTaskSocket = socket
    attachTaskSocketListeners(socket)
    return socket
  })()

  try {
    return await sharedTaskSocketPromise
  } catch (error) {
    sharedTaskSocketPromise = null
    throw error
  }
}

const submitTaskToPython = async (taskId: string, request: TaskSubmitRequest): Promise<void> => {
  const route = getRouteOrThrow(request.command)

  try {
    const socket = await ensureTaskSocket()
    if (!activeTasks.has(taskId)) {
      return
    }

    const message: ClientMessage = {
      type: 'task_submit',
      task_id: taskId,
      route,
      payload: normalizeTaskParams(request.command, request.params)
    }
    socket.send(JSON.stringify(message))
  } catch (error) {
    emitTaskError({
      taskId,
      error: error instanceof Error ? error.message : String(error),
      code: 'TASK_SUBMIT_FAILED'
    } satisfies TaskErrorPayload)
  }
}

const cancelTaskInPython = async (taskId: string): Promise<void> => {
  const task = activeTasks.get(taskId)
  if (!task) {
    return
  }

  if (!task.route) {
    activeTasks.delete(taskId)
    queueMicrotask(() => {
      mainWindow?.webContents.send(IPC_CHANNELS.taskOnError, {
        taskId,
        error: 'Task cancelled',
        code: 'TASK_CANCELLED'
      } satisfies TaskErrorPayload)
    })
    return
  }

  try {
    const socket = await ensureTaskSocket()
    const message: ClientMessage = {
      type: 'task_cancel',
      task_id: taskId
    }
    socket.send(JSON.stringify(message))
  } catch {
    activeTasks.delete(taskId)
    queueMicrotask(() => {
      mainWindow?.webContents.send(IPC_CHANNELS.taskOnError, {
        taskId,
        error: 'Task cancelled',
        code: 'TASK_CANCELLED'
      } satisfies TaskErrorPayload)
    })
  }
}

const registerTaskBridge = (): void => {
  ipcMain.handle(
    IPC_CHANNELS.taskSubmit,
    async (_event, request: TaskSubmitRequest): Promise<TaskSubmitResponse> => {
      const taskId = randomUUID()
      // Validate route synchronously — if unsupported, IPC invoke throws
      // immediately and the renderer catches it in try/catch (no race condition).
      const route = getRouteOrThrow(request.command)
      activeTasks.set(taskId, { taskId, command: request.command, route })
      void submitTaskToPython(taskId, request)

      return { taskId }
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.taskCancel,
    async (_event, request: TaskCancelRequest): Promise<void> => {
      await cancelTaskInPython(request.taskId)
    }
  )

  ipcMain.on(IPC_CHANNELS.taskOnProgress, (_event, payload: TaskProgressPayload) => {
    win().webContents.send(IPC_CHANNELS.taskOnProgress, payload)
  })
  ipcMain.on(IPC_CHANNELS.taskOnResult, (_event, payload: TaskResultPayload) => {
    activeTasks.delete(payload.taskId)
    win().webContents.send(IPC_CHANNELS.taskOnResult, payload)
  })
  ipcMain.on(IPC_CHANNELS.taskOnError, (_event, payload: TaskErrorPayload) => {
    activeTasks.delete(payload.taskId)
    win().webContents.send(IPC_CHANNELS.taskOnError, payload)
  })
}

const win = (): BrowserWindow => {
  if (!mainWindow) throw new Error('Main window is not available.')
  return mainWindow
}

app.whenReady().then(async () => {
  mkdirSync(getLogDirectory(), { recursive: true })
  registerAppMeta()
  registerPythonRuntime()
  registerDialogHandlers()
  registerTaskBridge()
  registerPyfaiHandlers()
  void pythonManager?.start()
  await createMainWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void createMainWindow()
    }

    void pythonManager?.start()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', (event) => {
  if (isQuitting) {
    return
  }

  event.preventDefault()
  isQuitting = true
  void pythonManager?.shutdown().finally(() => {
    app.quit()
  })
})
