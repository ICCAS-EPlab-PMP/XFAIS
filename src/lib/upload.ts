/**
 * upload.ts — 全局上传进度 store（Web 模式）。
 * Global upload progress store (web mode).
 *
 * transport.web.ts 的每次 uploadFile 都会自动在此登记进度，
 * UploadProgressHost.vue 渲染为右下角进度面板；
 * 各业务视图无需任何改动即可获得上传进度反馈。
 * Desktop mode never uploads (paths are used directly), so the store stays empty.
 */

import { reactive } from 'vue'

export type UploadStatus = 'uploading' | 'done' | 'error'

export interface UploadItem {
  id: number
  name: string
  loaded: number
  total: number
  status: UploadStatus
  error?: string
  /** Exponential moving average of transfer speed, bytes/second. */
  speedBps: number
  startedAt: number
  lastTickAt: number
}

interface UploadStore {
  items: UploadItem[]
  begin: (name: string, total: number) => number
  progress: (id: number, loaded: number, total: number) => void
  complete: (id: number) => void
  fail: (id: number, error: string) => void
  remove: (id: number) => void
}

let seed = 0

/** Auto-dismiss delays: succeeded entries vanish quickly, errors linger. */
const DONE_TTL_MS = 1500
const ERROR_TTL_MS = 8000

export const uploadStore = reactive<UploadStore>({
  items: [],

  begin(name, total) {
    const id = ++seed
    const now = performance.now()
    uploadStore.items.push({
      id,
      name,
      loaded: 0,
      total,
      status: 'uploading',
      speedBps: 0,
      startedAt: now,
      lastTickAt: now,
    })
    if (uploadStore.items.length > 12) {
      // Keep the panel bounded when a huge batch uploads concurrently.
      uploadStore.items.splice(0, uploadStore.items.length - 12)
    }
    return id
  },

  progress(id, loaded, total) {
    const item = uploadStore.items.find((i) => i.id === id)
    if (!item || item.status !== 'uploading') return
    const now = performance.now()
    const dt = (now - item.lastTickAt) / 1000
    if (dt > 0.2 && loaded > item.loaded) {
      const instant = (loaded - item.loaded) / dt
      item.speedBps = item.speedBps === 0 ? instant : item.speedBps * 0.7 + instant * 0.3
      item.lastTickAt = now
    }
    item.loaded = loaded
    if (total > 0) item.total = total
  },

  complete(id) {
    const item = uploadStore.items.find((i) => i.id === id)
    if (!item) return
    item.status = 'done'
    item.loaded = item.total
    window.setTimeout(() => uploadStore.remove(id), DONE_TTL_MS)
  },

  fail(id, error) {
    const item = uploadStore.items.find((i) => i.id === id)
    if (!item) return
    item.status = 'error'
    item.error = error
    window.setTimeout(() => uploadStore.remove(id), ERROR_TTL_MS)
  },

  remove(id) {
    const index = uploadStore.items.findIndex((i) => i.id === id)
    if (index >= 0) uploadStore.items.splice(index, 1)
  },
})

/** Format a byte count as a compact human-readable string (e.g. 12.3 MB). */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B'
  if (bytes < 1024) return `${Math.round(bytes)} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = -1
  do {
    value /= 1024
    unit += 1
  } while (value >= 1024 && unit < units.length - 1)
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`
}

/**
 * Run async tasks with bounded concurrency, returning results in input order.
 * 以有限并发执行异步任务，结果按输入顺序返回。
 */
export async function runLimited<T>(
  tasks: Array<() => Promise<T>>,
  limit = 3,
): Promise<T[]> {
  const results = new Array<T>(tasks.length)
  let next = 0
  const workers = Array.from({ length: Math.min(limit, tasks.length) }, async () => {
    while (next < tasks.length) {
      const index = next
      next += 1
      results[index] = await tasks[index]()
    }
  })
  await Promise.all(workers)
  return results
}
