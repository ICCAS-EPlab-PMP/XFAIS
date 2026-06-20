import { spawn, type ChildProcess } from 'node:child_process'
import { createWriteStream, type WriteStream } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import net from 'node:net'
import path from 'node:path'
import { EMBEDDED_PYTHON_VERSION, ensureEmbeddedPython, type PythonDependencyStatus, type PythonHealthReport, type PythonPaths } from './runtime'

const isWindows = process.platform === 'win32'

export type PythonServiceState = 'starting' | 'healthy' | 'error' | 'stopped' | 'restarting'

export interface PythonServiceStatus {
  canRetry: boolean
  dependencyStatus: PythonDependencyStatus | 'unknown'
  detail: string
  lastExitCode: number | null
  port: number | null
  pythonPath: string | null
  pythonVersion: string | null
  state: PythonServiceState
}

export interface PythonManagerOptions {
  allowTestCrash: boolean
  appRoot: string
  isPackaged: boolean
  logDirectory: string
  onStatusChange: (status: PythonServiceStatus) => void
  resourcesPath: string
}

const wait = async (durationMs: number): Promise<void> => {
  await new Promise((resolve) => {
    setTimeout(resolve, durationMs)
  })
}

const reservePort = async (): Promise<number> =>
  await new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (!address || typeof address === 'string') {
        server.close(() => reject(new Error('Unable to reserve a Python service port.')))
        return
      }

      const { port } = address
      server.close((error) => {
        if (error) {
          reject(error)
          return
        }

        resolve(port)
      })
    })
  })

const buildDefaultStatus = (): PythonServiceStatus => ({
  canRetry: false,
  dependencyStatus: 'unknown',
  detail: 'Python runtime is waiting to start.',
  lastExitCode: null,
  port: null,
  pythonPath: null,
  pythonVersion: EMBEDDED_PYTHON_VERSION,
  state: 'stopped'
})

const openLogStream = async (logDirectory: string): Promise<WriteStream> => {
  await mkdir(logDirectory, { recursive: true })
  return createWriteStream(path.join(logDirectory, 'python-service.log'), { flags: 'a' })
}

export class PythonServiceManager {
  private readonly allowTestCrash: boolean
  private readonly appRoot: string
  private child: ChildProcess | null = null
  private shuttingDown = false
  private readonly isPackaged: boolean
  private lastHealth: PythonHealthReport | null = null
  private readonly logDirectory: string
  private logStream: WriteStream | null = null
  private readonly onStatusChange: (status: PythonServiceStatus) => void
  private port: number | null = null
  private readonly resourcesPath: string
  private runtimePaths: PythonPaths | null = null
  private status: PythonServiceStatus = buildDefaultStatus()

  public constructor(options: PythonManagerOptions) {
    this.allowTestCrash = options.allowTestCrash
    this.appRoot = options.appRoot
    this.isPackaged = options.isPackaged
    this.logDirectory = options.logDirectory
    this.onStatusChange = options.onStatusChange
    this.resourcesPath = options.resourcesPath
  }

  public getStatus(): PythonServiceStatus {
    return { ...this.status }
  }

  public async start(): Promise<void> {
    if (this.child || this.status.state === 'starting' || this.status.state === 'restarting') {
      return
    }

    await this.launch('starting', 'Starting embedded Python runtime...')
  }

  public async restart(): Promise<PythonServiceStatus> {
    this.setStatus({
      canRetry: false,
      detail: 'Restarting embedded Python runtime...',
      state: 'restarting'
    })
    await this.stopProcess('manual restart')
    await this.launch('restarting', 'Restarting embedded Python runtime...')
    return this.getStatus()
  }

  public async shutdown(): Promise<void> {
    this.shuttingDown = true
    await this.stopProcess('application shutdown')
    this.setStatus({
      canRetry: false,
      detail: 'Python runtime stopped with the application.',
      port: null,
      state: 'stopped'
    })
    this.logStream?.end()
    this.logStream = null
  }

  public async crashForTest(): Promise<void> {
    if (!this.allowTestCrash) {
      throw new Error('Python crash hook is disabled outside dev/test mode.')
    }

    if (this.port === null) {
      throw new Error('Python service is not running.')
    }

    await fetch(`http://127.0.0.1:${this.port}/crash`, {
      method: 'POST'
    })
  }

  private async ensureLogStream(): Promise<WriteStream> {
    if (!this.logStream) {
      this.logStream = await openLogStream(this.logDirectory)
    }

    return this.logStream
  }

  private async launch(nextState: Extract<PythonServiceState, 'starting' | 'restarting'>, detail: string): Promise<void> {
    try {
      this.setStatus({
        canRetry: false,
        detail,
        state: nextState
      })

      const stream = await this.ensureLogStream()
      stream.write(`[manager] ${new Date().toISOString()} ${detail}\n`)
      stream.write(`[debug] appRoot=${this.appRoot} isPackaged=${this.isPackaged} resourcesPath=${this.resourcesPath}\n`)

      let health, paths: import('./runtime').PythonPaths
      try {
        const result = await ensureEmbeddedPython({
          appRoot: this.appRoot,
          isPackaged: this.isPackaged,
          logDirectory: this.logDirectory,
          resourcesPath: this.resourcesPath
        })
        health = result.health
        paths = result.paths
        stream.write(`[debug] ensureEmbeddedPython OK: python=${paths.pythonExecutable}\n`)
      } catch (ensureError) {
        const msg = ensureError instanceof Error ? ensureError.message : String(ensureError)
        stream.write(`[debug] ensureEmbeddedPython FAILED: ${msg}\n`)
        throw ensureError
      }

      this.lastHealth = health
      this.runtimePaths = paths
      this.port = await reservePort()

      const exeDir = path.dirname(paths.pythonExecutable)
      // Mirror the same PATH augmentation used in runtime.ts runProcessDirect
      // so Python's sibling DLLs (python311.dll, vcruntime140.dll, etc.) are
      // resolvable. The Windows system paths are kept for general OS tooling.
      // Derive the Windows root from the env (SystemRoot / windir) instead of
      // hardcoding C:\WINDOWS — wrong on machines where Windows is on another
      // drive.
      const windowsRoot = isWindows
        ? (process.env.SystemRoot || process.env.windir || 'C:\\WINDOWS').replace(/[\\/]+$/, '')
        : 'C:\\WINDOWS'
      const systemPathPrefixes = isWindows
        ? [`${windowsRoot}\\system32`, windowsRoot, `${windowsRoot}\\System32\\Wbem`]
        : []
      const pathEnv = process.env.PATH ?? process.env.Path ?? ''
      const augmentedPath = [exeDir, ...systemPathPrefixes, pathEnv]
        .filter((entry): entry is string => typeof entry === 'string' && entry.length > 0)
        .join(path.delimiter)
      stream.write(`[debug] spawn exe=${paths.pythonExecutable} cwd=${exeDir}\n`)

      const spawnEnv: Record<string, string> = {
        ...(process.env as Record<string, string>),
        PATH: augmentedPath,
        Path: augmentedPath,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUNBUFFERED: '1',
        PYTHONUTF8: '1'
      }

      stream.write(`[debug] spawning python: exe=${paths.pythonExecutable} shell=false noAsar=true\n`)

      // Disable ASAR wrapping during spawn to prevent child_process
      // interception in packaged Electron apps.
      // shell:true is intentionally omitted: it routes through cmd.exe which
      // corrupts non-ASCII paths (e.g. Chinese install directories).
      // Node.js's CreateProcessW supports Unicode paths natively, and
      // process.noAsar=true already handles the ASAR ENOENT workaround.
      const previousNoAsar = process.noAsar
      process.noAsar = true
      try {
        this.child = spawn(
          paths.pythonExecutable,
          [
            paths.serviceScriptPath,
            'serve',
            '--host',
            '127.0.0.1',
            '--port',
            String(this.port),
            '--expected-python',
            EMBEDDED_PYTHON_VERSION,
            '--requirements-lock',
            paths.requirementsLockPath
          ],
          {
            cwd: exeDir,
            env: spawnEnv,
            stdio: ['ignore', 'pipe', 'pipe'],
            ...(isWindows ? { windowsHide: true } : {})
          }
        )
      } finally {
        process.noAsar = previousNoAsar
      }

      this.child.stdout!.setEncoding('utf8')
      this.child.stderr!.setEncoding('utf8')
      this.child.stdout!.on('data', (chunk) => {
        stream.write(`[stdout] ${chunk}`)
      })
      this.child.stderr!.on('data', (chunk) => {
        stream.write(`[stderr] ${chunk}`)
      })
      this.child.once('exit', (code, signal) => {
        void this.handleUnexpectedExit(code, signal)
      })

      await this.waitForHealthyPort(this.port)

      this.setStatus({
        canRetry: false,
        dependencyStatus: health.dependency_status,
        detail: `Embedded Python ${health.python_version} is healthy on port ${this.port}.`,
        lastExitCode: null,
        port: this.port,
        pythonPath: health.python_executable,
        pythonVersion: health.python_version,
        state: 'healthy'
      })
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : 'Embedded Python startup failed.'
      this.child = null
      this.port = null

      // ENOENT → python.exe 路径不存在，提供友好的恢复指引
      const isFileNotFound = rawMessage.includes('ENOENT') || rawMessage.includes('not found')
      const detail = isFileNotFound
        ? `内置 Python 运行时不可用（${rawMessage}）。内置运行时可以在不依赖系统 Python 的前提下恢复。点击重试即可重新拉起。`
        : rawMessage

      this.setStatus({
        canRetry: true,
        dependencyStatus: this.lastHealth?.dependency_status ?? 'unknown',
        detail,
        port: null,
        state: 'error'
      })
    }
  }

  private async handleUnexpectedExit(code: number | null, signal: NodeJS.Signals | null): Promise<void> {
    const exitCode = typeof code === 'number' ? code : null
    this.child = null
    this.port = null

    if (this.shuttingDown) {
      return
    }

    const detail = signal
      ? `Embedded Python exited unexpectedly with signal ${signal}.`
      : `Embedded Python exited unexpectedly with code ${exitCode ?? 'unknown'}.`

    this.setStatus({
      canRetry: true,
      detail,
      lastExitCode: exitCode,
      port: null,
      state: 'error'
    })
  }

  private setStatus(nextStatus: Partial<PythonServiceStatus>): void {
    this.status = {
      ...this.status,
      ...nextStatus
    }
    this.onStatusChange(this.getStatus())
  }

  private async stopProcess(reason: string): Promise<void> {
    const activeChild = this.child
    if (!activeChild) {
      return
    }

    const processId = activeChild.pid
    this.child = null

    if (this.port !== null) {
      try {
        await fetch(`http://127.0.0.1:${this.port}/shutdown`, { method: 'POST' })
      } catch {
        // Fall back to process termination below.
      }
    }

    for (let attempt = 0; attempt < 25; attempt += 1) {
      if (activeChild.exitCode !== null || activeChild.killed) {
        this.port = null
        return
      }

      await wait(200)
    }

    if (isWindows && typeof processId === 'number') {
      await new Promise<void>((resolve) => {
        const previousNoAsar = process.noAsar
        process.noAsar = true
        let killer
        try {
          killer = spawn('taskkill', ['/pid', String(processId), '/T', '/F'], {
            stdio: 'ignore',
            windowsHide: true
          })
        } finally {
          process.noAsar = previousNoAsar
        }
        killer.once('exit', () => resolve())
        killer.once('error', () => resolve())
      })
    } else {
      activeChild.kill('SIGTERM')
    }

    const stream = await this.ensureLogStream()
    stream.write(`[manager] ${new Date().toISOString()} stopped python process (${reason})\n`)
    this.port = null
  }

  private async waitForHealthyPort(port: number): Promise<void> {
    for (let attempt = 0; attempt < 60; attempt += 1) {
      if (!this.child) {
        throw new Error('Embedded Python stopped before reaching healthy state.')
      }

      try {
        const response = await fetch(`http://127.0.0.1:${port}/health`)
        if (response.ok) {
          return
        }
      } catch {
        // Continue polling until timeout.
      }

      await wait(500)
    }

    throw new Error('Timed out waiting for embedded Python health endpoint.')
  }
}
