// build/afterPack.cjs
//
// electron-builder afterPack hook: trims unused site-packages from the BUNDLED
// Python runtime so the shipped installer is smaller.
//
// IMPORTANT: this ONLY touches the packaged copy under
//   context.appOutDir/resources/python-runtime/...
// The dev source tree (BETA/.python-runtime) is never modified, so `npm run
// test:python` and all local development keep the full runtime.
//
// The deletion list below was derived empirically: none of these packages are
// imported (transitively) by any KEPT package during backend startup or a real
// pyFAI integrate1d / integrate_azimuth / integrate_cake run against the
// test/h5test sample. pyarrow is intentionally KEPT — pandas 3.x imports it
// unconditionally at import time.
//
// This hook is fault-tolerant: a failure to remove a single package only emits
// a warning and never aborts the build.

const fs = require('fs')
const path = require('path')

// Verified-unused top-level packages (old Streamlit web stack + science +
// dev tooling). Each entry maps to a directory name under site-packages.
const UNUSED_PACKAGES = [
  // Old Streamlit web-UI stack
  'streamlit', 'plotly', 'pydeck', 'altair', 'narwhals', 'tornado',
  // Materials-science stack (not referenced by pyFAI / fabio / silx)
  'pymatgen', 'spglib',
  // Symbolic math — only referenced by scipy/special/_precompute (dev scripts)
  // and scipy/special/tests, never at runtime
  'sympy', 'mpmath',
  // Graph lib — orphan, not imported by any kept package
  'networkx',
  // Syntax highlighting — orphan (Streamlit / IPython dependency)
  'pygments',
  // Package / runtime tooling — never needed by the shipped app at runtime.
  // NOTE: pytest (+ _pytest, iniconfig, pluggy) is intentionally KEPT — it is
  // listed in requirements.in, so the runtime health check (which validates
  // every entry of requirements.lock.txt) expects it to be importable.
  'pip', 'coverage', 'build', 'git', 'gitdb',
]

function dirSizeBytes(dir) {
  let total = 0
  const walk = (d) => {
    let entries
    try {
      entries = fs.readdirSync(d, { withFileTypes: true })
    } catch {
      return
    }
    for (const e of entries) {
      const full = path.join(d, e.name)
      if (e.isDirectory()) {
        walk(full)
      } else {
        try {
          total += fs.statSync(full).size
        } catch {
          /* ignore */
        }
      }
    }
  }
  walk(dir)
  return total
}

function bytesToMB(b) {
  return b / (1024 * 1024)
}

module.exports = async function afterPack(context) {
  const sitePackages = path.join(
    context.appOutDir,
    'resources',
    'python-runtime',
    'python-3.11.9-win32-x64',
    'Lib',
    'site-packages',
  )

  if (!fs.existsSync(sitePackages)) {
    console.log(`[afterPack] site-packages not found at ${sitePackages}; skipping trim.`)
    return
  }

  const before = dirSizeBytes(sitePackages)
  console.log(`[afterPack] trimming bundled site-packages: ${bytesToMB(before).toFixed(0)} MB before`)
  console.log(`[afterPack]   located at: ${sitePackages}`)

  // Collect .dist-info / .egg-info dirs to sweep after removing package dirs.
  const metadataDirsToRemove = new Set()
  const allEntries = fs.readdirSync(sitePackages)

  let removedCount = 0
  let removedBytes = 0

  for (const name of UNUSED_PACKAGES) {
    const pkgDir = path.join(sitePackages, name)
    if (!fs.existsSync(pkgDir) || !fs.statSync(pkgDir).isDirectory()) {
      continue
    }

    const sz = dirSizeBytes(pkgDir)
    try {
      fs.rmSync(pkgDir, { recursive: true, force: true })
      removedBytes += sz
      removedCount++
      console.log(`[afterPack]   removed ${name}/ (${bytesToMB(sz).toFixed(1)} MB)`)

      // Queue matching metadata dirs (case-insensitive prefix match).
      for (const entry of allEntries) {
        const lc = entry.toLowerCase()
        if (
          lc.startsWith(name.toLowerCase() + '-') &&
          (lc.endsWith('.dist-info') || lc.endsWith('.egg-info'))
        ) {
          metadataDirsToRemove.add(entry)
        }
      }
    } catch (err) {
      console.warn(`[afterPack]   WARNING: could not remove ${name}: ${err.message}`)
    }
  }

  // Remove the queued .dist-info / .egg-info metadata dirs (tiny, but tidy).
  for (const entry of metadataDirsToRemove) {
    const full = path.join(sitePackages, entry)
    try {
      fs.rmSync(full, { recursive: true, force: true })
      console.log(`[afterPack]   removed ${entry}`)
    } catch (err) {
      console.warn(`[afterPack]   WARNING: could not remove ${entry}: ${err.message}`)
    }
  }

  const after = dirSizeBytes(sitePackages)
  console.log(
    `[afterPack] done: removed ${removedCount} packages ` +
      `(${bytesToMB(removedBytes).toFixed(0)} MB of package code). ` +
      `site-packages ${bytesToMB(before).toFixed(0)} MB -> ${bytesToMB(after).toFixed(0)} MB ` +
      `(-${bytesToMB(before - after).toFixed(0)} MB total incl. metadata).`,
  )
}
