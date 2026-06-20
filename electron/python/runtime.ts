import { createHash } from 'node:crypto'
import { fork, spawn, type ChildProcess } from 'node:child_process'
import { appendFileSync, existsSync } from 'node:fs'
import { access, mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const EMBEDDED_PYTHON_VERSION = '3.11.9'

const isWindows = process.platform === 'win32'
const isDarwin = process.platform === 'darwin'

export const PYTHON_RUNTIME_SUFFIX = isDarwin
  ? (process.arch === 'arm64' ? 'macos-arm64' : 'macos-x64')
  : 'win32-x64'
export const EMBEDDED_PYTHON_RUNTIME_DIR = `python-${EMBEDDED_PYTHON_VERSION}-${PYTHON_RUNTIME_SUFFIX}`
export const PYTHON_EXECUTABLE = isWindows ? 'python.exe' : 'python3'

export const EMBEDDED_PYTHON_INSTALLER = isWindows
  ? `python-${EMBEDDED_PYTHON_VERSION}-amd64.exe`
  : `python-${EMBEDDED_PYTHON_VERSION}-macos.pkg`

export type PythonDependencyStatus = 'ready' | 'missing' | 'outdated'

export interface PythonHealthReport {
  dependency_status: PythonDependencyStatus
  expected_python: string
  health_ok: boolean
  missing_dependencies: string[]
  python_executable: string
  python_version: string
  service_name: string
}

export interface PythonPaths {
  appRoot: string
  isPackaged: boolean
  installerPath: string
  pythonExecutable: string
  requirementsInputPath: string
  requirementsLockPath: string
  resourcesPath: string
  runtimeRoot: string
  serviceScriptPath: string
  stampPath: string
}

export interface EnsurePythonRuntimeOptions {
  appRoot?: string
  isPackaged?: boolean
  logDirectory?: string
  resourcesPath?: string
}

interface RunProcessOptions {
  cwd?: string
  env?: NodeJS.ProcessEnv
  windowsHide?: boolean
}

interface RunProcessResult {
  code: number
  stderr: string
  stdout: string
}

interface RuntimeStamp {
  generatedFromInput: boolean
  pythonVersion: string
  requirementsHash: string
}

const moduleDirectory = path.dirname(fileURLToPath(import.meta.url))

const fileExists = async (targetPath: string): Promise<boolean> => {
  try {
    await access(targetPath)
    return true
  } catch {
    return false
  }
}

const findProjectRoot = (startDirectory = moduleDirectory): string => {
  let currentDirectory = path.resolve(startDirectory)

  for (let index = 0; index < 8; index += 1) {
    if (existsSync(path.join(currentDirectory, 'package.json')) && existsSync(path.join(currentDirectory, 'electron'))) {
      return currentDirectory
    }

    const parentDirectory = path.dirname(currentDirectory)
    if (parentDirectory === currentDirectory) {
      break
    }

    currentDirectory = parentDirectory
  }

  return path.resolve(startDirectory, '../..')
}

const pickExistingPath = (candidatePaths: string[], fallbackPath: string): string => {
  for (const candidatePath of candidatePaths) {
    if (existsSync(candidatePath)) {
      return candidatePath
    }
  }

  return fallbackPath
}

const normalizeOutput = (value: string): string => value.replace(/\r\n/g, '\n').trim()

// Detect paths containing non-ASCII characters (e.g. Chinese, Japanese).
// cmd.exe (used by shell:true) corrupts these via codepage conversion, so we
// must bypass shell:true and/or use the fork-based helper for such paths.
const hasNonAsciiPath = (p: string): boolean => /[^\x00-\x7F]/.test(p)

const MAX_OUTPUT_BUFFER = 50 * 1024 * 1024

// In packaged Electron 35 apps, child_process.spawn with the default
// CreateProcessW path can fail with ENOENT even when the executable exists.
// The root cause is an interaction between ASAR's noAsar flag and libuv's
// CreateProcessW wrapper on certain Windows builds. We work around this by:
//   1. Forcing `shell: true` so the command is launched via cmd.exe, which
//      uses a different process-creation code path that is unaffected.
//   2. Prepending Windows system directories to PATH so cmd.exe itself is
//      resolvable. The augmented PATH is also used to locate sibling DLLs
//      (python311.dll, vcruntime140.dll, etc.) required by the embedded
//      Python runtime.
// Resolve the Windows installation root from the environment (SystemRoot is
// the canonical var; windir is a legacy fallback). Hardcoding C:\WINDOWS is
// wrong on machines where Windows lives on a different drive, which breaks
// cmd.exe / system-tool resolution.
const WINDOWS_ROOT = isWindows
  ? (process.env.SystemRoot || process.env.windir || 'C:\\WINDOWS').replace(/[\\/]+$/, '')
  : 'C:\\WINDOWS'

const SYSTEM_PATH_PREFIXES = isWindows
  ? [`${WINDOWS_ROOT}\\system32`, WINDOWS_ROOT, `${WINDOWS_ROOT}\\System32\\Wbem`]
  : []

const buildAugmentedPath = (exeDir: string, env: NodeJS.ProcessEnv): string => {
  const currentPath = env.PATH ?? env.Path ?? ''
  // Order matters: exe dir first (for sibling DLLs), then system paths
  // (for cmd.exe resolution), then the inherited user PATH.
  return [exeDir, ...SYSTEM_PATH_PREFIXES, currentPath]
    .filter((entry) => typeof entry === 'string' && entry.length > 0)
    .join(path.delimiter)
}

// ── ASAR-safe process launcher via fork() ──────────────────────────────
// In packaged Electron 35 apps, child_process.spawn/exec are intercepted by
// the ASAR wrapper and may fail with ENOENT even for paths outside ASAR.
// child_process.fork() is NOT patched, so we use it with ELECTRON_RUN_AS_NODE=1
// to launch a plain Node.js helper that runs commands on our behalf.

let helperScriptPath = ''
let helperProcess: ChildProcess | null = null
let helperReady = false
let helperCommandId = 0
const helperPending = new Map<number, {
  resolve: (result: RunProcessResult) => void
  reject: (err: Error) => void
}>()

const setHelperScriptPath = (resourcesPath: string, projectRoot: string): void => {
  // In packaged mode the helper is in extraResources; in dev mode it's in resources/
  const packagedPath = path.join(resourcesPath, 'run-command.mjs')
  const devPath = path.join(projectRoot, 'resources', 'run-command.mjs')
  helperScriptPath = existsSync(packagedPath) ? packagedPath : devPath
}

const ensureHelperProcess = (): Promise<void> => {
  if (helperProcess && helperReady) return Promise.resolve()

  return new Promise<void>((resolve, reject) => {
    const env = {
      ...process.env,
      ELECTRON_RUN_AS_NODE: '1'
    } as Record<string, string>

    helperProcess = fork(helperScriptPath, [], {
      env,
      stdio: ['ignore', 'pipe', 'pipe', 'ipc']
    })

    helperProcess.stdout?.on('data', () => {}) // consume to prevent blocking
    helperProcess.stderr?.on('data', () => {})

    helperProcess.once('message', (msg: any) => {
      if (msg?.type === 'ready') {
        helperReady = true
        resolve()
      }
    })

    helperProcess.on('message', (msg: any) => {
      if (msg?.id == null) return
      const pending = helperPending.get(msg.id)
      if (!pending) return
      helperPending.delete(msg.id)

      if (msg.error) {
        pending.reject(new Error(`${msg.error} (${msg.code ?? 'UNKNOWN'})`))
      } else {
        pending.resolve({
          code: msg.code ?? 0,
          stderr: normalizeOutput(msg.stderr ?? ''),
          stdout: normalizeOutput(msg.stdout ?? '')
        })
      }
    })

    helperProcess.once('error', (err) => {
      helperProcess = null
      helperReady = false
      for (const [, p] of helperPending) p.reject(err)
      helperPending.clear()
      reject(err)
    })

    helperProcess.once('exit', () => {
      helperProcess = null
      helperReady = false
      for (const [, p] of helperPending) {
        p.reject(new Error('Helper process exited unexpectedly'))
      }
      helperPending.clear()
    })

    // Timeout for helper startup
    setTimeout(() => {
      if (!helperReady) {
        helperProcess?.kill()
        helperProcess = null
        reject(new Error('Helper process startup timed out'))
      }
    }, 10000)
  })
}

const runViaHelper = async (
  executable: string,
  argumentsList: string[],
  options: RunProcessOptions = {}
): Promise<RunProcessResult> => {
  await ensureHelperProcess()
  const id = ++helperCommandId

  return new Promise<RunProcessResult>((resolve, reject) => {
    helperPending.set(id, { resolve, reject })
    const cwd = options.cwd ?? path.dirname(executable)
    const env = options.env ?? process.env
    const augmentedPath = buildAugmentedPath(path.dirname(executable), env)

    helperProcess!.send({
      type: 'run',
      id,
      cmd: executable,
      args: argumentsList,
      cwd,
      env: { ...env, PATH: augmentedPath, Path: augmentedPath }
    })

    // Timeout for individual commands (10 minutes for pip install)
    setTimeout(() => {
      if (helperPending.has(id)) {
        helperPending.delete(id)
        reject(new Error('Command execution timed out'))
      }
    }, 600000)
  })
}

const killHelperProcess = (): void => {
  if (helperProcess) {
    helperProcess.kill()
    helperProcess = null
    helperReady = false
  }
}

const runProcess = async (
  executable: string,
  argumentsList: string[],
  options: RunProcessOptions = {}
): Promise<RunProcessResult> => {
  // For paths containing non-ASCII characters (e.g. Chinese), cmd.exe used by
  // shell:true cannot reliably handle the path due to codepage limitations.
  // Prefer the fork-based helper which uses Node.js APIs with full Unicode support.
  if (hasNonAsciiPath(executable) && helperScriptPath && existsSync(helperScriptPath)) {
    try {
      return await runViaHelper(executable, argumentsList, options)
    } catch (helperError: any) {
      // Fall through to direct spawn as last resort (without shell:true — see runProcessDirect)
    }
  }

  // Direct spawn with retry. In packaged Electron the asar-aware spawn can
  // intermittently return ENOENT for an existing executable (the helper serve
  // spawn in manager.ts proves direct spawn *can* work; the failure is
  // transient). The file genuinely exists, so a short backoff-retry almost
  // always succeeds on the next attempt.
  const MAX_DIRECT_ATTEMPTS = 4
  for (let attempt = 1; attempt <= MAX_DIRECT_ATTEMPTS; attempt += 1) {
    try {
      return await runProcessDirect(executable, argumentsList, options)
    } catch (directError: any) {
      const msg = directError?.message ?? ''
      const isTransientEnoent = msg.includes('ENOENT')
      const canRetry = isTransientEnoent && attempt < MAX_DIRECT_ATTEMPTS
      if (canRetry) {
        await new Promise((resolve) => { setTimeout(resolve, 250 * attempt) })
        continue
      }

      // Exhausted retries (or a non-ENOENT error). Try the fork-based helper
      // as a final fallback if it is available.
      if (isTransientEnoent && helperScriptPath && existsSync(helperScriptPath)) {
        try {
          return await runViaHelper(executable, argumentsList, options)
        } catch (helperError: any) {
          throw new Error(
            `Direct spawn failed: ${msg}\nHelper fallback also failed: ${helperError?.message ?? String(helperError)}`
          )
        }
      }
      throw directError
    }
  }

  // Unreachable: the loop either returns or throws.
  throw new Error('runProcess: exhausted all direct spawn attempts without a result.')
}

const runProcessDirect = async (
  executable: string,
  argumentsList: string[],
  options: RunProcessOptions = {}
): Promise<RunProcessResult> =>
  await new Promise((resolve, reject) => {
    const cwd = options.cwd ?? path.dirname(executable)
    const env = options.env ?? process.env
    const augmentedPath = buildAugmentedPath(path.dirname(executable), env)

    // Disable ASAR wrapping during spawn to prevent interception of
    // child_process calls in packaged Electron apps.
    const previousNoAsar = process.noAsar
    process.noAsar = true

    let child
    try {
      // Spawn the executable directly via Node.js's CreateProcessW (which is
      // Unicode-safe, so non-ASCII install paths work fine). We intentionally
      // do NOT use shell:true:
      //   - shell:true routes through cmd.exe, whose codepage corrupts
      //     non-ASCII paths AND which itself fails with ENOENT on Windows
      //     setups where cmd.exe isn't resolvable at the expected system path
      //     (the user-facing "spawn C:\WINDOWS\system32\cmd.exe ENOENT" error).
      //   - process.noAsar=true (set above) is sufficient to stop ASAR from
      //     intercepting this spawn in packaged Electron — the same approach
      //     already used by manager.ts for the long-lived serve process and by
      //     safeSpawn() in main.ts.
      child = spawn(executable, argumentsList, {
        cwd,
        env: {
          ...env,
          PATH: augmentedPath,
          Path: augmentedPath
        },
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: options.windowsHide ?? true
      })
    } catch (spawnError) {
      process.noAsar = previousNoAsar
      reject(spawnError)
      return
    }

    process.noAsar = previousNoAsar

    let stdoutChunks = ''
    let stderrChunks = ''
    let outputOverflow = false

    child.stdout?.setEncoding('utf8')
    child.stderr?.setEncoding('utf8')

    child.stdout?.on('data', (chunk: string) => {
      if (stdoutChunks.length < MAX_OUTPUT_BUFFER) {
        stdoutChunks += chunk
      } else {
        outputOverflow = true
      }
    })
    child.stderr?.on('data', (chunk: string) => {
      if (stderrChunks.length < MAX_OUTPUT_BUFFER) {
        stderrChunks += chunk
      } else {
        outputOverflow = true
      }
    })

    child.once('error', (err) => {
      reject(err)
    })

    child.once('close', (code) => {
      if (outputOverflow) {
        reject(new Error('Process output exceeded maximum buffer size.'))
        return
      }
      resolve({
        code: code ?? 0,
        stderr: normalizeOutput(stderrChunks),
        stdout: normalizeOutput(stdoutChunks)
      })
    })
  })

const computeRequirementsHash = async (requirementsPath: string): Promise<string> => {
  const content = await readFile(requirementsPath, 'utf8')
  return createHash('sha256').update(content).digest('hex')
}

const ensurePipAvailable = async (pythonExecutable: string): Promise<void> => {
  const result = await runProcess(pythonExecutable, ['-m', 'ensurepip', '--upgrade'])
  if (result.code !== 0) {
    throw new Error(result.stderr || 'Embedded Python ensurepip failed.')
  }
}

const hasPipAvailable = async (pythonExecutable: string): Promise<boolean> => {
  const result = await runProcess(pythonExecutable, ['-m', 'pip', '--version'])
  return result.code === 0
}

const installEmbeddedPython = async (pythonPaths: PythonPaths): Promise<void> => {
  if (!(await fileExists(pythonPaths.installerPath))) {
    throw new Error(`Python installer not found: ${pythonPaths.installerPath}`)
  }

  await mkdir(pythonPaths.runtimeRoot, { recursive: true })

  if (isWindows) {
    const result = await runProcess(
      pythonPaths.installerPath,
      [
        '/quiet',
        'InstallAllUsers=0',
        'AssociateFiles=0',
        'CompileAll=0',
        'Include_doc=0',
        'Include_launcher=0',
        'Include_pip=1',
        'Include_test=0',
        'PrependPath=0',
        'Shortcuts=0',
        `TargetDir=${pythonPaths.runtimeRoot}`
      ],
      { windowsHide: true }
    )

    if (result.code !== 0) {
      throw new Error(result.stderr || 'Embedded Python installer failed.')
    }
  } else if (isDarwin) {
    // macOS: Use the Python.org framework installer or extract standalone build
    // The .pkg installer places Python in /Library/Frameworks/Python.framework
    // For embedded use, we expect a pre-built standalone Python in the runtime directory.
    // You can create one using: https://github.com/gregneagle/relocatable-python
    // or use python-build-standalone: https://github.com/indygreg/python-build-standalone
    //
    // If using a tarball approach (recommended for embedded):
    const result = await runProcess(
      'tar',
      ['-xzf', pythonPaths.installerPath, '-C', pythonPaths.runtimeRoot, '--strip-components=1'],
      {}
    )

    if (result.code !== 0) {
      // Fallback: try pkgutil for .pkg files
      const pkgResult = await runProcess(
        '/usr/sbin/installer',
        ['-pkg', pythonPaths.installerPath, '-target', pythonPaths.runtimeRoot],
        {}
      )
      if (pkgResult.code !== 0) {
        throw new Error(pkgResult.stderr || 'Embedded Python installer failed on macOS.')
      }
    }

    // Ensure python3 is executable
    const pythonExe = path.join(pythonPaths.runtimeRoot, 'bin', PYTHON_EXECUTABLE)
    if (await fileExists(pythonExe)) {
      await runProcess('chmod', ['+x', pythonExe], {})
    }
  } else {
    throw new Error(`Unsupported platform: ${process.platform}`)
  }
}

const installPythonDependencies = async (pythonPaths: PythonPaths, pythonExecutable: string): Promise<void> => {
  const pipUpgrade = await runProcess(pythonExecutable, ['-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pip'])
  if (pipUpgrade.code !== 0) {
    throw new Error(pipUpgrade.stderr || 'Unable to upgrade pip for embedded runtime.')
  }

  const sourceRequirementsPath = (await fileExists(pythonPaths.requirementsLockPath))
    ? pythonPaths.requirementsLockPath
    : pythonPaths.requirementsInputPath

  const installResult = await runProcess(
    pythonExecutable,
    ['-m', 'pip', 'install', '--disable-pip-version-check', '--requirement', sourceRequirementsPath],
    { cwd: pythonPaths.appRoot, windowsHide: true }
  )

  if (installResult.code !== 0) {
    throw new Error(installResult.stderr || 'Unable to install embedded Python dependencies.')
  }

  const freezeResult = await runProcess(pythonExecutable, ['-m', 'pip', 'freeze'])
  if (freezeResult.code !== 0) {
    throw new Error(freezeResult.stderr || 'Unable to freeze embedded Python dependencies.')
  }

  if (!pythonPaths.isPackaged) {
    await writeFile(pythonPaths.requirementsLockPath, `${freezeResult.stdout}\n`, 'utf8')
  }

  const requirementsHash = await computeRequirementsHash(pythonPaths.requirementsLockPath)
  const stamp: RuntimeStamp = {
    generatedFromInput: sourceRequirementsPath === pythonPaths.requirementsInputPath,
    pythonVersion: EMBEDDED_PYTHON_VERSION,
    requirementsHash
  }

  await writeFile(pythonPaths.stampPath, JSON.stringify(stamp, null, 2), 'utf8')
}

export const resolvePythonPaths = (options: EnsurePythonRuntimeOptions = {}): PythonPaths => {
  const projectRoot = options.appRoot ?? findProjectRoot()
  const isPackaged = options.isPackaged ?? false
  const resourcesPath = options.resourcesPath ?? projectRoot

  const packagedPythonAssets = path.join(resourcesPath, 'python')
  const developmentPythonAssets = path.join(projectRoot, 'python')
  const packagedRuntimeRoot = path.join(resourcesPath, 'python-runtime', EMBEDDED_PYTHON_RUNTIME_DIR)
  const developmentRuntimeRoot = path.join(projectRoot, '.python-runtime', EMBEDDED_PYTHON_RUNTIME_DIR)
  const packagedInstallerPath = path.join(resourcesPath, 'python-assets', EMBEDDED_PYTHON_INSTALLER)
  const developmentInstallerPath = path.join(projectRoot, 'ref', 'streamlit_app', EMBEDDED_PYTHON_INSTALLER)

  const assetsRoot = pickExistingPath(
    isPackaged ? [packagedPythonAssets, developmentPythonAssets] : [developmentPythonAssets, packagedPythonAssets],
    isPackaged ? packagedPythonAssets : developmentPythonAssets
  )

  // On macOS, Python framework places the executable in bin/; on Windows it's at root
  const pythonExecutable = isDarwin
    ? path.join(isPackaged ? packagedRuntimeRoot : developmentRuntimeRoot, 'bin', PYTHON_EXECUTABLE)
    : path.join(isPackaged ? packagedRuntimeRoot : developmentRuntimeRoot, PYTHON_EXECUTABLE)

  return {
    appRoot: projectRoot,
    isPackaged,
    installerPath: isPackaged ? packagedInstallerPath : developmentInstallerPath,
    pythonExecutable,
    requirementsInputPath: path.join(assetsRoot, 'requirements.in'),
    requirementsLockPath: path.join(assetsRoot, 'requirements.lock.txt'),
    resourcesPath,
    runtimeRoot: isPackaged ? packagedRuntimeRoot : developmentRuntimeRoot,
    serviceScriptPath: path.join(assetsRoot, 'service_launcher.py'),
    stampPath: path.join(isPackaged ? packagedRuntimeRoot : developmentRuntimeRoot, '.deps-stamp.json')
  }
}

export const readPythonHealth = async (pythonPaths: PythonPaths, pythonExecutable?: string): Promise<PythonHealthReport> => {
  const activePython = pythonExecutable ?? pythonPaths.pythonExecutable
  const result = await runProcess(activePython, [
    pythonPaths.serviceScriptPath,
    'health',
    '--expected-python',
    EMBEDDED_PYTHON_VERSION,
    '--requirements-lock',
    pythonPaths.requirementsLockPath
  ])

  if (result.code !== 0) {
    throw new Error(result.stderr || result.stdout || 'Python health command failed.')
  }

  return JSON.parse(result.stdout) as PythonHealthReport
}

export const ensureEmbeddedPython = async (options: EnsurePythonRuntimeOptions = {}): Promise<{ health: PythonHealthReport; paths: PythonPaths }> => {
  const pythonPaths = resolvePythonPaths(options)
  const pythonExecutable = pythonPaths.pythonExecutable

  // Set up the ASAR-safe helper script path
  setHelperScriptPath(options.resourcesPath ?? pythonPaths.resourcesPath, pythonPaths.appRoot)

  const logDiag = (msg: string): void => {
    if (options.logDirectory) {
      try {
        const logPath = path.join(options.logDirectory, 'python-service.log')
        appendFileSync(logPath, `[runtime] ${msg}\n`)
      } catch { /* best effort */ }
    }
  }
  logDiag(`ensureEmbeddedPython: exe=${pythonExecutable} isPackaged=${pythonPaths.isPackaged}`)

  const runtimeReady = await fileExists(pythonExecutable)
  logDiag(`runtimeReady=${runtimeReady}`)

  if (!runtimeReady) {
    const installerExists = await fileExists(pythonPaths.installerPath)
    if (!installerExists) {
      const pathsSummary = [
        `pythonExecutable: ${pythonExecutable}`,
        `installerPath: ${pythonPaths.installerPath}`,
        `runtimeRoot: ${pythonPaths.runtimeRoot}`,
        `resourcesPath: ${pythonPaths.resourcesPath}`,
        `isPackaged: ${pythonPaths.isPackaged}`
      ].join('\n')
      throw new Error(
        `Embedded Python runtime not found and cannot be reinstalled — both runtime and installer are missing.\n` +
        `${pathsSummary}\n\n` +
        `应用安装不完整：内置 Python 运行时缺失且安装器也不存在。\n` +
        `请尝试重新安装 X-FAIS。如果问题持续，请检查安装包完整性。`
      )
    }
    await installEmbeddedPython(pythonPaths)
  }

  // In packaged mode the runtime AND its dependencies are shipped pre-installed
  // (site-packages is bundled, and afterPack may trim pip/setuptools). We must
  // NOT run ensurepip or `pip install` here: pip may be absent, and reinstalling
  // would try to mutate the locked, shipped environment (and the many spawns it
  // requires are what exposed the intermittent asar/spawn ENOENT). The shipped
  // runtime is authoritative — we just verify the lock is present and trust it.
  if (!pythonPaths.isPackaged) {
    if (!(await hasPipAvailable(pythonExecutable))) {
      logDiag('pip not available, running ensurepip...')
      await ensurePipAvailable(pythonExecutable)
    } else {
      logDiag('pip OK')
    }

    const lockExists = await fileExists(pythonPaths.requirementsLockPath)

    const activeRequirementsPath = lockExists ? pythonPaths.requirementsLockPath : pythonPaths.requirementsInputPath
    const activeRequirementsHash = await computeRequirementsHash(activeRequirementsPath)
    const stampExists = await fileExists(pythonPaths.stampPath)

    let shouldInstallDependencies = !lockExists
    if (stampExists) {
      const stampContent = await readFile(pythonPaths.stampPath, 'utf8')
      const stamp = JSON.parse(stampContent) as RuntimeStamp
      shouldInstallDependencies = shouldInstallDependencies || stamp.requirementsHash !== activeRequirementsHash || stamp.pythonVersion !== EMBEDDED_PYTHON_VERSION
    } else {
      shouldInstallDependencies = true
    }

    if (shouldInstallDependencies) {
      await installPythonDependencies(pythonPaths, pythonExecutable)
    }
  } else {
    const lockExists = await fileExists(pythonPaths.requirementsLockPath)
    if (!lockExists) {
      throw new Error(`Packaged requirements lock is missing: ${pythonPaths.requirementsLockPath}`)
    }
    logDiag('packaged mode: shipped runtime is authoritative, skipping pip/dependency install')
  }

  const health = await readPythonHealth(pythonPaths, pythonExecutable)
  logDiag(`health OK: ${health.health_ok} version=${health.python_version}`)
  killHelperProcess() // Clean up helper process after successful completion
  return { health, paths: pythonPaths }
}

export const formatPythonHealthReport = (health: PythonHealthReport): string => [
  `embedded-python: ${health.python_executable}`,
  `python-version: ${health.python_version}`,
  `dependency-status: ${health.dependency_status}`,
  `missing-dependencies: ${health.missing_dependencies.length > 0 ? health.missing_dependencies.join(', ') : 'none'}`,
  `health-ok: ${health.health_ok ? 'true' : 'false'}`
].join('\n')
