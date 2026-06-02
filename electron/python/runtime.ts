import { createHash } from 'node:crypto'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { access, mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const EMBEDDED_PYTHON_VERSION = '3.11.9'
export const EMBEDDED_PYTHON_RUNTIME_DIR = `python-${EMBEDDED_PYTHON_VERSION}-win32-x64`
export const EMBEDDED_PYTHON_INSTALLER = `python-${EMBEDDED_PYTHON_VERSION}-amd64.exe`

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

  return {
    appRoot: projectRoot,
    isPackaged,
    installerPath: isPackaged ? packagedInstallerPath : developmentInstallerPath,
    requirementsInputPath: path.join(assetsRoot, 'requirements.in'),
    requirementsLockPath: path.join(assetsRoot, 'requirements.lock.txt'),
    resourcesPath,
    runtimeRoot: isPackaged ? packagedRuntimeRoot : developmentRuntimeRoot,
    serviceScriptPath: path.join(assetsRoot, 'service_launcher.py'),
    stampPath: path.join(isPackaged ? packagedRuntimeRoot : developmentRuntimeRoot, '.deps-stamp.json')
  }
}

export const readPythonHealth = async (pythonPaths: PythonPaths, pythonExecutable?: string): Promise<PythonHealthReport> => {
  const activePython = pythonExecutable ?? path.join(pythonPaths.runtimeRoot, 'python.exe')
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
  const pythonExecutable = path.join(pythonPaths.runtimeRoot, 'python.exe')
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
