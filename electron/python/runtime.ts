import { createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
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

const runProcess = async (
  executable: string,
  argumentsList: string[],
  options: RunProcessOptions = {}
): Promise<RunProcessResult> =>
  await new Promise((resolve, reject) => {
    const child = spawn(executable, argumentsList, {
      cwd: options.cwd,
      env: options.env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: options.windowsHide ?? true
    })

    let stdout = ''
    let stderr = ''

    child.stdout?.setEncoding('utf8')
    child.stderr?.setEncoding('utf8')
    child.stdout?.on('data', (chunk) => {
      stdout += chunk
    })
    child.stderr?.on('data', (chunk) => {
      stderr += chunk
    })
    child.on('error', reject)
    child.on('exit', (code) => {
      resolve({
        code: code ?? 0,
        stderr: normalizeOutput(stderr),
        stdout: normalizeOutput(stdout)
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
  const runtimeReady = await fileExists(pythonExecutable)

  if (!runtimeReady) {
    await installEmbeddedPython(pythonPaths)
  }

  if (!(await hasPipAvailable(pythonExecutable))) {
    await ensurePipAvailable(pythonExecutable)
  }

  const lockExists = await fileExists(pythonPaths.requirementsLockPath)
  if (!lockExists && options.isPackaged) {
    throw new Error(`Packaged requirements lock is missing: ${pythonPaths.requirementsLockPath}`)
  }

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

  const health = await readPythonHealth(pythonPaths, pythonExecutable)
  return { health, paths: pythonPaths }
}

export const formatPythonHealthReport = (health: PythonHealthReport): string => [
  `embedded-python: ${health.python_executable}`,
  `python-version: ${health.python_version}`,
  `dependency-status: ${health.dependency_status}`,
  `missing-dependencies: ${health.missing_dependencies.length > 0 ? health.missing_dependencies.join(', ') : 'none'}`,
  `health-ok: ${health.health_ok ? 'true' : 'false'}`
].join('\n')
