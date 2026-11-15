/**
 * Browser-side download helpers (web mode, 2026-11-04).
 *
 * In the desktop build every export goes through a native save dialog and
 * the Python side writes straight to the picked path. The browser cannot do
 * that, so web-mode exports fall into two families:
 *
 * 1. the backend already returned the bytes/PNG/JSON in the task result →
 *    turn them into a Blob and hand it to the browser (``downloadBlob``);
 * 2. the backend wrote a file into the session temp tree → fetch it through
 *    ``transport.downloadFile`` (``/api/download``) under a friendly name
 *    (``fileNameFromPath``).
 *
 * 浏览器侧下载工具（web 模式，2026-11-04）。桌面版导出走原生保存对话框、
 * 由 Python 直接写盘；浏览器做不到，因此 web 导出分两类：① 后端已在任务
 * 结果里回带字节/PNG/JSON → 转 Blob 交给浏览器下载；② 后端把文件写进会话
 * 临时目录 → 经 ``transport.downloadFile``（/api/download）以友好文件名取回。
 */

/** Extract the last path component, handling both ``/`` and ``\`` separators. */
export function fileNameFromPath(path: string): string {
  const normalized = String(path ?? '').replace(/\\/g, '/')
  const idx = normalized.lastIndexOf('/')
  const name = idx >= 0 ? normalized.slice(idx + 1) : normalized
  return name || 'download'
}

/** Trigger a browser download for an in-memory Blob. */
export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName || 'download'
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

/** Trigger a browser download for a text payload (CSV/JSON/TXT…). */
export function downloadText(
  text: string,
  fileName: string,
  mime = 'text/plain;charset=utf-8',
): void {
  downloadBlob(new Blob([text], { type: mime }), fileName)
}

/** Decode a (possibly data-URL-prefixed) base64 string into a Blob. */
export function base64ToBlob(base64: string, mime: string): Blob {
  const payload = String(base64 ?? '').replace(/^data:[^,]*,/, '')
  const binary = atob(payload)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Blob([bytes], { type: mime })
}

/** Trigger a browser download for a base64-encoded binary payload (PNG…). */
export function downloadBase64(
  base64: string,
  fileName: string,
  mime: string,
): void {
  downloadBlob(base64ToBlob(base64, mime), fileName)
}

/** Fetch server-side files through /api/download under friendly names. */
export function downloadServerPaths(
  serverPaths: readonly string[] | null | undefined,
  fetchAndSave: (serverPath: string, fileName: string) => Promise<void>,
  onError?: (serverPath: string, fileName: string, error: unknown) => void,
): void {
  for (const serverPath of serverPaths ?? []) {
    if (!serverPath) continue
    const name = fileNameFromPath(serverPath)
    fetchAndSave(serverPath, name).catch((error) => onError?.(serverPath, name, error))
  }
}
