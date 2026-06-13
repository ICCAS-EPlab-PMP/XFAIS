/**
 * run-command.mjs — ASAR-safe process launcher helper.
 *
 * Launched via child_process.fork() with ELECTRON_RUN_AS_NODE=1 so that
 * this script runs as plain Node.js (no Electron, no ASAR wrapper).
 * Receives a command via IPC, spawns it, and sends back the result.
 *
 * Protocol (IPC messages):
 *   Parent → Child:  { cmd: string, args: string[], cwd: string, env: object }
 *   Child  → Parent: { stdout: string, stderr: string, code: number }
 *                   | { error: string }
 */
import { spawn } from 'node:child_process';

process.on('message', (msg) => {
  if (!msg || msg.type !== 'run') return;

  const { id, cmd, args, cwd, env } = msg;

  const MAX_BUF = 50 * 1024 * 1024;
  let stdoutBuf = '';
  let stderrBuf = '';

  try {
    const child = spawn(cmd, args, {
      cwd,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      // shell:true is required on Windows in packaged Electron 35 apps;
      // the parent runtime.ts/manager.ts pre-augment PATH with
      // C:\WINDOWS\system32 so cmd.exe is resolvable.
      shell: true,
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
