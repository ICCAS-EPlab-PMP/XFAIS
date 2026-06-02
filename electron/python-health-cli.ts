import { EMBEDDED_PYTHON_VERSION, ensureEmbeddedPython, formatPythonHealthReport } from './python/runtime'

const quietMode = process.argv.includes('--quiet')

const run = async (): Promise<void> => {
  const { health } = await ensureEmbeddedPython({
    appRoot: process.cwd(),
    isPackaged: false,
    resourcesPath: process.cwd()
  })

  if (!quietMode) {
    process.stdout.write(`${formatPythonHealthReport(health)}\n`)
  }

  if (!health.health_ok || !health.python_version.startsWith(EMBEDDED_PYTHON_VERSION)) {
    process.exitCode = 1
  }
}

void run()
