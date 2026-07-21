/**
 * run-command.mjs — ASAR-safe process launcher helper.
 *
 * Launched via child_process.fork() with ELECTRON_RUN_AS_NODE=1 so that
 * this script runs as plain Node.js. It still MAY inherit Electron's
 * asar-aware child_process patch when forked from the main process, so we
 * force process.noAsar = true below to be safe.
 * Receives a command via IPC, spawns it, and sends back the result.
 *
 * Protocol (IPC messages):
 *   Parent → Child:  { cmd: string, args: string[], cwd: string, env: object }
 *   Child  → Parent: { stdout: string, stderr: string, code: number }
 *                   | { error: string }
 */
import { spawn } from 'node:child_process';

// Defense-in-depth: when this helper is forked from Electron's main process it
// may inherit the asar-aware child_process patch. Forcing noAsar disables any
// asar interception of our spawn, so the external executable launches via the
// plain CreateProcessW path. (In a fresh ELECTRON_RUN_AS_NODE process this
// property is undefined and the line is a harmless no-op.)
try { process.noAsar = true; } catch {}

process.on('message', (msg) => {
  if (!msg || msg.type !== 'run') return;

  const { id, cmd, args, cwd, env } = msg;

  const MAX_BUF = 50 * 1024 * 1024;
  let stdoutBuf = '';
  let stderrBuf = '';

  try {
    // This helper runs as plain Node.js (ELECTRON_RUN_AS_NODE=1), so there is
    // no ASAR wrapper to intercept the spawn — spawn directly via CreateProcessW
    // (Unicode-safe). Do NOT use shell:true: it routes through cmd.exe, which
    // corrupts non-ASCII paths via codepage conversion and can itself fail with
    // ENOENT when cmd.exe isn't resolvable at the expected system path.
    const child = spawn(cmd, args, {
      cwd,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');

    child.stdout.on('data', (chunk) => {
      if (stdoutBuf.length < MAX_BUF) stdoutBuf += chunk;
    });
    child.stderr.on('data', (chunk) => {
      if (stderrBuf.length < MAX_BUF) stderrBuf += chunk;
    });

    child.once('error', (err) => {
      process.send({ id, error: err.message, code: err.code ?? 'UNKNOWN' });
    });

    child.once('close', (code) => {
      process.send({ id, stdout: stdoutBuf, stderr: stderrBuf, code: code ?? 0 });
    });
  } catch (err) {
    process.send({ id, error: err.message, code: 'SPAWN_FAILED' });
  }
});

// Signal readiness
process.send({ type: 'ready' });
