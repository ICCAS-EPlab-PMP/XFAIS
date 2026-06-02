import { spawn, type ChildProcess } from 'node:child_process'
import { createWriteStream, type WriteStream } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import net from 'node:net'
import path from 'node:path'
import { EMBEDDED_PYTHON_VERSION, ensureEmbeddedPython, type PythonDependencyStatus, type PythonHealthReport, type PythonPaths } from './runtime'

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

      const { health, paths } = await ensureEmbeddedPython({
        appRoot: this.appRoot,
        isPackaged: this.isPackaged,
        logDirectory: this.logDirectory,
        resourcesPath: this.resourcesPath
      })

      this.lastHealth = health
      this.runtimePaths = paths
      this.port = await reservePort()

      this.child = spawn(
        path.join(paths.runtimeRoot, 'python.exe'),
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
          cwd: path.dirname(paths.serviceScriptPath),
          env: {
            ...process.env,
            PYTHONIOENCODING: 'utf-8',
            PYTHONUNBUFFERED: '1',
            PYTHONUTF8: '1'
          },
          stdio: ['ignore', 'pipe', 'pipe'],
          windowsHide: true
        }
      )

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
      const message = error instanceof Error ? error.message : 'Embedded Python startup failed.'
      this.child = null
      this.port = null
      this.setStatus({
        canRetry: true,
        dependencyStatus: this.lastHealth?.dependency_status ?? 'unknown',
        detail: message,
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

    if (process.platform === 'win32' && typeof processId === 'number') {
      await new Promise<void>((resolve) => {
        const killer = spawn('taskkill', ['/pid', String(processId), '/T', '/F'], {
          stdio: 'ignore',
          windowsHide: true
        })
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
