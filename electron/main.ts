import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { execSync, spawn, type SpawnOptions } from 'node:child_process'
import { existsSync, mkdirSync, readdirSync, writeFileSync, appendFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { APP_NAME, APP_VERSION, IPC_CHANNELS } from './constants'
import { PythonServiceManager, pythonLaunchOverrides, type PythonServiceStatus } from './python/manager'
import { resolvePythonPaths } from './python/runtime'

// ── ASAR-safe child_process wrappers ────────────────────────────────────
// In packaged Electron apps the ASAR layer intercepts child_process calls.
// Setting process.noAsar = true before each call prevents the wrapper
// from interfering with commands that run outside the ASAR archive.

/**
 * ASAR-safe execSync — NOT injection-safe by itself: `command` is handed to a
 * shell, so callers must never interpolate untrusted or environment-derived
 * values into it. Use literal command strings here, or safeSpawn with an
 * args array (no shell) whenever a value varies.
 * ASAR 安全的 execSync——其本身不保证注入安全：命令串会交给 shell，
 * 调用方严禁内插不可信或环境变量来源的值；需要变量时改用 safeSpawn
 * 的参数数组形式（不经 shell）。
 */
const safeExecSync = (command: string, options?: Parameters<typeof execSync>[1]): string => {
  const prev = process.noAsar
  process.noAsar = true
  try {
    return execSync(command, options) as string
  } finally {
    process.noAsar = prev
  }
}

const safeSpawn = (command: string, args?: readonly string[], options?: SpawnOptions): ReturnType<typeof spawn> => {
  const prev = process.noAsar
  process.noAsar = true
  try {
    return options
      ? spawn(command, args as string[] ?? [], options)
      : spawn(command, args as string[] ?? [])
  } finally {
    process.noAsar = prev
  }
}

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

const isWindows = process.platform === 'win32'
const isDarwin = process.platform === 'darwin'
const DEV_NULL = isWindows ? '2>nul' : '2>/dev/null'

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
  // Settings → launch env overrides (OMP thread cap etc.). Stored in the
  // manager module; consumed on the NEXT Python spawn — OpenMP reads the env
  // at interpreter start, so changes require a runtime restart (UI notes this).
  // 设置 → 启动环境覆盖（OMP 线程数等）。保存在 manager 模块；下一次拉起
  // Python 时生效——OpenMP 在解释器启动时读取环境变量，修改后需重启运行时。
  ipcMain.handle(
    IPC_CHANNELS.settingsSetPythonLaunchEnv,
    async (_event: Electron.IpcMainInvokeEvent, env: { ompThreads?: number } | undefined) => {
      const omp = env?.ompThreads
      pythonLaunchOverrides.ompThreads =
        typeof omp === 'number' && Number.isFinite(omp) && omp > 0 ? Math.floor(omp) : undefined
      return { ok: true, ompThreads: pythonLaunchOverrides.ompThreads ?? null }
    }
  )
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

  // Read a UTF-8 text file (e.g. a pasted azimuthal profile CSV) into the
  // renderer. Used by the curves-input mode of orientation analysis.
  // 读取 UTF-8 文本文件（如方位角分布 CSV）到渲染进程。供取向分析的曲线输入模式使用。
  ipcMain.handle(
    IPC_CHANNELS.readTextFile,
    async (_event, filePath?: string): Promise<string> => {
      if (!filePath || typeof filePath !== 'string') {
        throw new Error('readTextFile requires a file path. / readTextFile 需要文件路径。')
      }
      const { readFile } = await import('node:fs/promises')
      return readFile(filePath, 'utf-8')
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

const getEmbeddedPythonPaths = (): { pythonExe: string; scriptsDir: string } => {
  const paths = resolvePythonPaths({
    appRoot: app.getAppPath(),
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath
  })
  return {
    pythonExe: paths.pythonExecutable,
    scriptsDir: isDarwin
      ? path.join(paths.runtimeRoot, 'bin')
      : path.join(paths.runtimeRoot, 'Scripts')
  }
}

interface PyfaiCheckResult {
  embedded: { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean }
  system: { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean }
  overall: 'available' | 'embedded_only' | 'system_only' | 'not_found'
}

const checkQtBindingAvailable = (pythonExe: string): boolean => {
  const shellOpts = isWindows ? { windowsHide: true as const } : {}
  try {
    safeExecSync(`"${pythonExe}" -c "from PySide6 import QtWidgets; print('ok')" ${DEV_NULL}`, {
      timeout: 8000,
      encoding: 'utf-8',
      ...shellOpts
    })
    return true
  } catch {
    try {
      safeExecSync(`"${pythonExe}" -c "from PyQt6 import QtWidgets; print('ok')" ${DEV_NULL}`, {
        timeout: 8000,
        encoding: 'utf-8',
        ...shellOpts
      })
      return true
    } catch {
      return false
    }
  }
}

const checkPyfaiEmbedded = (): { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean } => {
  const { pythonExe, scriptsDir } = getEmbeddedPythonPaths()
  const calib2Name = isWindows ? 'pyFAI-calib2.exe' : 'pyFAI-calib2'
  const calib2Exe = path.join(scriptsDir, calib2Name)
  const calib2Path = existsSync(calib2Exe) ? calib2Exe : null
  let version: string | null = null
  const shellOpts = isWindows ? { windowsHide: true as const } : {}
  try {
    const output = safeExecSync(`"${pythonExe}" -c "import pyFAI; print(pyFAI.version)"`, {
      timeout: 10000,
      encoding: 'utf-8',
      ...shellOpts
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
  const shellOpts = isWindows ? { windowsHide: true as const } : {}
  const calib2Name = isWindows ? 'pyFAI-calib2.exe' : 'pyFAI-calib2'
  const findCmd = isWindows ? 'where' : 'which'
  const pythonCmds = isWindows ? ['python', 'py'] : ['python3', 'python']

  // Method 1: Find calib2 in PATH
  try {
    const output = safeExecSync(`${findCmd} ${calib2Name} ${DEV_NULL}`, {
      timeout: 5000, encoding: 'utf-8', ...shellOpts
    }).trim()
    if (output) calib2Path = output.split('\n')[0].trim()
  } catch { /* not on PATH */ }

  // Method 2: Try to import pyFAI via python and search Scripts directories
  let version: string | null = null
  for (const pyCmd of pythonCmds) {
    try {
      const output = safeExecSync(`${pyCmd} -c "import pyFAI; print(pyFAI.version)" ${DEV_NULL}`, {
        timeout: 10000, encoding: 'utf-8', ...shellOpts
      }).trim()
      if (output) { version = output; break }
    } catch { /* not importable via this python */ }
  }

  // If version found but no exe, locate Scripts directory via Python
  if (version && !calib2Path) {
    for (const pyCmd of pythonCmds) {
      try {
        const userBase = safeExecSync(
          `${pyCmd} -c "import site; print(site.getuserbase())" ${DEV_NULL}`,
          { timeout: 5000, encoding: 'utf-8', ...shellOpts }
        ).trim()
        if (userBase) {
          if (isWindows) {
            const verStr = safeExecSync(
              `${pyCmd} -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" ${DEV_NULL}`,
              { timeout: 5000, encoding: 'utf-8', ...shellOpts }
            ).trim()
            const candidate = path.join(userBase, `Python${verStr}`, 'Scripts', calib2Name)
            if (existsSync(candidate)) { calib2Path = candidate; break }
          } else {
            const candidate = path.join(userBase, 'bin', calib2Name)
            if (existsSync(candidate)) { calib2Path = candidate; break }
          }
        }
      } catch { /* continue */ }

      try {
        const prefix = safeExecSync(
          `${pyCmd} -c "import sys; print(sys.prefix)" ${DEV_NULL}`,
          { timeout: 5000, encoding: 'utf-8', ...shellOpts }
        ).trim()
        const scriptsDir = isWindows ? 'Scripts' : 'bin'
        const candidate = path.join(prefix, scriptsDir, calib2Name)
        if (existsSync(candidate)) { calib2Path = candidate; break }
      } catch { /* continue */ }
    }
  }

  // Method 3: Platform-specific Python installation search
  if (!calib2Path) {
    if (isWindows) {
      try {
        const localAppData = process.env.LOCALAPPDATA
        if (localAppData) {
          // v0.3.0 hardening: enumerate via fs instead of a shell `dir`
          // command — environment-derived values never enter a command
          // string. / v0.3.0 加固：改用 fs 枚举目录，环境变量不再进入命令串。
          const pythonRoot = path.join(localAppData, 'Programs', 'Python')
          let dirEntries: string[] = []
          try {
            dirEntries = readdirSync(pythonRoot, { withFileTypes: true })
              .filter((entry) => entry.isDirectory() && entry.name.startsWith('Python'))
              .map((entry) => entry.name)
          } catch { /* python root missing / Python 根目录不存在 */ }
          for (const dirName of dirEntries) {
            const candidate = path.join(pythonRoot, dirName, 'Scripts', calib2Name)
            if (existsSync(candidate)) { calib2Path = candidate; break }
          }
        }
      } catch { /* not found */ }
    } else if (isDarwin) {
      // macOS: Check common Python framework locations
      const macSearchPaths = [
        '/Library/Frameworks/Python.framework/Versions',
        path.join(process.env.HOME ?? '', 'Library', 'Python'),
        '/usr/local/opt/python',
        '/opt/homebrew/opt/python'
      ]
      for (const searchPath of macSearchPaths) {
        if (!existsSync(searchPath)) continue
        try {
          const entries = readdirSync(searchPath)
          for (const entry of entries) {
            const candidate = path.join(searchPath, entry, 'bin', calib2Name)
            if (existsSync(candidate)) { calib2Path = candidate; break }
            // Framework layout: Versions/X.Y/bin/
            const fwCandidate = path.join(searchPath, entry, 'bin', calib2Name)
            if (existsSync(fwCandidate)) { calib2Path = fwCandidate; break }
          }
        } catch { /* continue */ }
        if (calib2Path) break
      }
    }
  }

  let hasQtBinding = false
  if (calib2Path) {
    for (const pyCmd of pythonCmds) {
      try {
        safeExecSync(`${pyCmd} -c "from PySide6 import QtWidgets; print('ok')" ${DEV_NULL}`, {
          timeout: 8000, encoding: 'utf-8', ...shellOpts
        })
        hasQtBinding = true
        break
      } catch {
        try {
          safeExecSync(`${pyCmd} -c "from PyQt6 import QtWidgets; print('ok')" ${DEV_NULL}`, {
            timeout: 8000, encoding: 'utf-8', ...shellOpts
          })
          hasQtBinding = true
          break
        } catch {
          // continue
        }
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
      pythonCmd = getEmbeddedPythonPaths().pythonExe
    } else {
      return { success: false, error: '未找到可用的 pyFAI-calib2。请先安装 pyFAI。' }
    }

    try {
      // Detach calib2 COMPLETELY: stdio pipes to this process are a leak —
      // `unref()` only drops the process handle, the open pipes keep the
      // Electron event loop referenced, so quitting X-FAIS while calib2 runs
      // would leave a zombie X-FAIS.exe (reproduced empirically). Instead,
      // stderr goes to a temp log file: no parent-side handles, calib2 can
      // never block on a full pipe, and the early-failure message is still
      // captured for the 800 ms startup check.
      // 完全脱离 calib2：与本进程相连的 stdio 管道是泄漏点——`unref()`
      // 只解除进程句柄，未关闭的管道会挂住 Electron 事件循环，导致开着
      // calib2 时退出 X-FAIS 留下僵尸进程（已实证复现）。改为 stderr 重定向
      // 到临时日志文件：父进程零句柄、calib2 绝不会因管道写满而阻塞，且
      // 800ms 启动检测仍能读取失败信息。
      const fsSync = await import('node:fs')
      const osMod = await import('node:os')
      const calibLogPath = path.join(
        osMod.tmpdir(),
        `x-fais-calib2-${Date.now()}.log`
      )
      const errFd = fsSync.openSync(calibLogPath, 'a')
      const spawnOpts = isWindows
        ? { detached: true, stdio: ['ignore' as const, 'ignore' as const, errFd], windowsHide: false }
        : { detached: true, stdio: ['ignore' as const, 'ignore' as const, errFd] }
      const child = exePath
        ? safeSpawn(exePath, [], spawnOpts)
        : safeSpawn(pythonCmd!, ['-m', 'pyFAI.app.calib2'], spawnOpts)
      child.unref()
      // The child inherited the fd; close our copy so this process holds
      // nothing of calib2's. / 子进程已继承 fd；关闭自身副本，父进程不持有。
      fsSync.closeSync(errFd)

      let startupError = ''
      child.on('error', (err) => {
        startupError = err.message
      })

      await new Promise(resolve => setTimeout(resolve, 800))

      const exitedEarly = child.exitCode !== null && child.exitCode !== 0
      if (startupError || exitedEarly) {
        // Read the captured stderr for the failure reason (e.g. missing Qt).
        // 读取捕获的 stderr 以获取失败原因（如缺少 Qt 绑定）。
        let logTail = ''
        try {
          logTail = fsSync.readFileSync(calibLogPath, 'utf-8')
        } catch { /* log may be unreadable — fall back to exit code */ }
        const combined = `${startupError}\n${logTail}`
        const errorMsg = combined.includes('Qt wrapper') || combined.includes('qt.binding') || combined.includes('QtBinding')
          ? 'pyFAI-calib2 需要 Qt 绑定（PySide6 或 PyQt6），但当前 Python 环境中未安装。\n请在终端运行: pip install PySide6'
          : `pyFAI-calib2 启动失败: ${combined.trim() || `进程退出码 ${child.exitCode}`}`
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

  // One-click dependency install: pip install pyFAI + PySide6 into the
  // EMBEDDED runtime (guaranteed present & pip-enabled in desktop builds).
  // Runs via async spawn so the renderer stays responsive during the multi-
  // minute download (a synchronous execSync would freeze ALL IPC for the
  // whole install). / 一键依赖安装：向内嵌运行时 pip 安装 pyFAI + PySide6。
  // 用异步 spawn 执行，数分钟的下载期间渲染器保持响应（同步 execSync 会把
  // 整个 IPC 阻塞到安装结束，应用假死）。
  ipcMain.handle('pyfai:installDeps', async (): Promise<{ success: boolean; output?: string; error?: string }> => {
    const { pythonExe } = getEmbeddedPythonPaths()
    if (!existsSync(pythonExe)) {
      return {
        success: false,
        error: '未找到内置 Python 运行时。请在系统 Python 中手动运行: pip install pyfai PySide6，或打开官方下载页面获取。'
      }
    }
    const shellOpts = isWindows ? { windowsHide: true as const } : {}
    const runAsync = (args: string[], timeoutMs: number): Promise<string> =>
      new Promise((resolve) => {
        let out = ''
        let settled = false
        const finish = (ok: boolean) => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          resolve(ok ? out : `${out}\n[exit != 0]`)
        }
        const timer = setTimeout(() => finish(false), timeoutMs)
        const previousNoAsar = process.noAsar
        process.noAsar = true
        let child: ReturnType<typeof spawn>
        try {
          child = spawn(pythonExe, args, { stdio: ['ignore', 'pipe', 'pipe'], ...shellOpts })
        } catch (err) {
          process.noAsar = previousNoAsar
          finish(false)
          return
        } finally {
          process.noAsar = previousNoAsar
        }
        child.stdout?.setEncoding('utf8')
        child.stderr?.setEncoding('utf8')
        child.stdout?.on('data', (c: string) => { out += c })
        child.stderr?.on('data', (c: string) => { out += c })
        child.on('error', (err) => { out += `\n${(err as Error).message}`; finish(false) })
        child.on('close', (code) => finish(code === 0))
      })

    try {
      // Self-heal: if pip itself is missing (trimmed runtime / broken install),
      // restore it from ensurepip's bundled wheel before installing.
      // 自愈：若 pip 缺失（被裁剪的运行时/损坏安装），先用 ensurepip 内置
      // wheel 恢复，再执行安装。
      const probeOk = await new Promise<boolean>((resolve) => {
        const previousNoAsar = process.noAsar
        process.noAsar = true
        let child: ReturnType<typeof spawn>
        try {
          child = spawn(pythonExe, ['-c', 'import pip'], { stdio: 'ignore', ...shellOpts })
        } catch {
          process.noAsar = previousNoAsar
          resolve(false)
          return
        } finally {
          process.noAsar = previousNoAsar
        }
        child.on('error', () => resolve(false))
        child.on('close', (code) => resolve(code === 0))
      })
      if (!probeOk) {
        await runAsync(['-m', 'ensurepip', '--upgrade'], 5 * 60 * 1000)
      }
      const output = await runAsync(
        ['-m', 'pip', 'install', '--disable-pip-version-check', 'pyfai', 'PySide6'],
        20 * 60 * 1000,
      )
      const failed = output.includes('[exit != 0]')
      return failed
        ? { success: false, error: output.slice(-2000) }
        : { success: true, output: output.slice(-2000) }
    } catch (err) {
      return { success: false, error: (err as Error).message }
    }
  })

  ipcMain.handle('pyfai:exportBat', async (): Promise<{ success: boolean; error?: string }> => {
    const scriptContent = isWindows ? generateBatScript() : generateShellScript()
    const defaultFileName = isWindows ? 'pyFAI-calib2-launcher.bat' : 'pyFAI-calib2-launcher.sh'
    const fileFilters = isWindows
      ? [{ name: '批处理脚本', extensions: ['bat'] }, { name: '所有文件', extensions: ['*'] }]
      : [{ name: 'Shell 脚本', extensions: ['sh'] }, { name: '所有文件', extensions: ['*'] }]

    const win = BrowserWindow.getFocusedWindow()
    const { canceled, filePath } = await dialog.showSaveDialog(win ?? undefined!, {
      title: '导出 pyFAI-calib2 启动脚本',
      defaultPath: defaultFileName,
      filters: fileFilters
    })

    if (canceled || !filePath) {
      return { success: false, error: '用户取消导出' }
    }

    try {
      const fs = await import('node:fs/promises')
      await fs.writeFile(filePath, scriptContent, 'utf-8')
      // On macOS, make the script executable
      if (!isWindows) {
        await fs.chmod(filePath, 0o755)
      }
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

const generateShellScript = (): string => {
  return `#!/usr/bin/env bash
# pyFAI-calib2 启动器 / Launcher (macOS)

echo "============================================"
echo "  pyFAI-calib2 启动器 / Launcher"
echo "============================================"
echo ""

# 检查 Python 是否可用
if ! command -v python3 &>/dev/null; then
    echo "[错误] 未找到 Python 3，请先安装"
    echo "下载地址: https://www.python.org/downloads/"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "[信息] $PYTHON_VERSION"

# 检查 pyFAI 是否安装
if ! python3 -c "import pyFAI" 2>/dev/null; then
    echo "[错误] 未安装 pyFAI"
    echo ""
    echo "请运行以下命令安装:"
    echo "  pip3 install pyFAI fabio"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

PYFAI_VERSION=$(python3 -c "import pyFAI; print(pyFAI.version)" 2>/dev/null)
echo "[信息] pyFAI 版本: $PYFAI_VERSION"

# 检查 Qt 绑定
QT_BINDING="none"
if python3 -c "from PySide6 import QtWidgets; print('PySide6')" 2>/dev/null; then
    QT_BINDING="PySide6"
elif python3 -c "from PyQt6 import QtWidgets; print('PyQt6')" 2>/dev/null; then
    QT_BINDING="PyQt6"
elif python3 -c "from PyQt5 import QtWidgets; print('PyQt5')" 2>/dev/null; then
    QT_BINDING="PyQt5"
fi

if [ "$QT_BINDING" = "none" ]; then
    echo ""
    echo "[警告] 未找到 Qt 绑定，pyFAI-calib2 需要以下任一库:"
    echo "  - PySide6  (推荐)"
    echo "  - PyQt6"
    echo "  - PyQt5"
    echo ""
    echo "请运行以下命令安装 PySide6:"
    echo "  pip3 install PySide6"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

echo "[信息] Qt 绑定: $QT_BINDING"
echo ""

# 查找 pyFAI-calib2 可执行文件
CALIB2_PATH=""

if command -v pyFAI-calib2 &>/dev/null; then
    CALIB2_PATH=$(which pyFAI-calib2)
fi

if [ -z "$CALIB2_PATH" ]; then
    PYTHON_PREFIX=$(python3 -c "import sys; print(sys.prefix)" 2>/dev/null)
    if [ -x "$PYTHON_PREFIX/bin/pyFAI-calib2" ]; then
        CALIB2_PATH="$PYTHON_PREFIX/bin/pyFAI-calib2"
    fi
fi

echo "[信息] 启动 pyFAI-calib2..."
echo ""

if [ -n "$CALIB2_PATH" ]; then
    "$CALIB2_PATH" &
else
    python3 -m pyFAI.app.calib2 &
fi
`
}

const COMMAND_ROUTE_MAP: Record<string, string> = {
  integrate1d: '/api/integrate1d',
  integrate_azimuth: '/api/integrate_azimuth',
  integrate_cake: '/api/integrate_cake',
  integrate_fiber: '/api/integrate_fiber',
  viewer_config: '/api/viewer_config',
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
  image_math: '/api/image_math',
  image_stitch: '/api/image_stitch',
  orientation_analysis: '/api/orientation_analysis',
  lamellar_analysis: '/api/lamellar_analysis',
  poni_importer: '/api/poni_importer',
  calibration: '/api/calibration'
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

  // Create a clean Buffer copy that is guaranteed structured-clone compatible.
  // Node.js Buffers backed by a shared pool produce ArrayBuffers that fail
  // Electron's structured clone algorithm ("An object could not be cloned").
  // Using Buffer.from() creates a new Uint8Array subclass with its own backing
  // store, which Electron 35+ handles reliably in main→renderer IPC.
  const cleanBuf = Buffer.from(pngData)

  mainWindow?.webContents.send(IPC_CHANNELS.taskBinaryData, {
    taskId,
    mime: header.mime ?? 'image/png',
    frame: header.frame ?? 0,
    width: header.width ?? 0,
    height: header.height ?? 0,
    data: cleanBuf
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

    const normalized = normalizeTaskParams(request.command, request.params)
    // Signal to Python backend that this is a desktop (Electron) connection.
    // This relaxes security checks that only apply to web mode (e.g. session tmp dir restrictions).
    normalized._is_desktop = true

    const message: ClientMessage = {
      type: 'task_submit',
      task_id: taskId,
      route,
      payload: normalized
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
  const bootLogPath = path.join(getLogDirectory(), 'boot.log')
  try {
    writeFileSync(bootLogPath, `isPackaged=${app.isPackaged} getAppPath=${app.getAppPath()} resourcesPath=${process.resourcesPath}\n`, 'utf8')
    appendFileSync(bootLogPath, `execPath=${process.execPath} cwd=${process.cwd()}\n`, 'utf8')
  } catch (bootErr) {
    // 如果连 boot.log 都写不了，说明 userData 路径有问题
  }

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

  // Hard-exit backstop: whatever happens in the python shutdown (hung HTTP,
  // stuck child), closing the window must ALWAYS terminate X-FAIS.exe — a
  // lingering process is what makes the next installer abort with
  // "X-FAIS 无法关闭，请手动关闭它".
  // 强退兜底：无论 python 关闭流程发生什么（HTTP 挂起、子进程卡死），
  // 关闭窗口后 X-FAIS.exe 必须真正退出——残留进程正是下次安装报
  // “X-FAIS 无法关闭，请手动关闭它”的原因。
  const hardExitTimer = setTimeout(() => {
    app.exit(0)
  }, 15000)
  hardExitTimer.unref()

  void Promise.race([
    pythonManager?.shutdown() ?? Promise.resolve(),
    new Promise<void>((resolve) => {
      const t = setTimeout(resolve, 10000)
      t.unref()
    }),
  ]).finally(() => {
    clearTimeout(hardExitTimer)
    app.quit()
  })
})
