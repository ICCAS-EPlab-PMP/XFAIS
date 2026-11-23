/**
 * serverFs.ts — server_fs（服务器开放目录）前端适配层（仅 web 模式使用）。
 *
 * 后端 /api/server_fs 提供三个只读动作：
 *   list_roots       管理员经 XFAIS_INPUT_ROOTS 开放的目录清单
 *   list             浏览白名单树内目录（条目 name/kind/size）
 *   download_prepare 把所选文件暂存进会话工作区（可选无损压缩），
 *                    返回 /api/download 可回传的 output_files
 * 桌面模式使用本地文件对话框，不经过本适配层。
 */
import { useTransport } from './transport'

/** 管理员开放目录（XFAIS_INPUT_ROOTS 的一项）。 */
export interface ServerFsRoot {
  path: string
  name: string
}

/** 目录条目（浏览白名单树）。 */
export interface ServerFsEntry {
  name: string
  kind: 'dir' | 'file'
  size?: number
}

/** 暂存产物（/api/download 可回传）。 */
export interface ServerFsDownloadItem {
  path: string
  filename: string
  size?: number
}

export interface ServerFsDownloadOutcome {
  status: string
  compressed: boolean
  outputDir: string
  files: ServerFsDownloadItem[]
  report?: {
    total?: number
    success?: number
    failed?: number
    skipped?: number
    ratio?: number
  }
  skippedUnsupported?: number
  message?: string
}

/** 提交 serverFs 任务并等待结果（与 submitRemoteDataTask 同款 JSON 剥离）。 */
function submitServerFsTask(
  transport: ReturnType<typeof useTransport>,
  params: Record<string, unknown>,
  onProgress?: (progress: number, message: string) => void
): Promise<Record<string, unknown>> {
  const plainParams = JSON.parse(JSON.stringify(params)) as Record<string, unknown>
  return new Promise(resolve => {
    let offProgress: (() => void) | null = null
    let offResult: (() => void) | null = null
    let offError: (() => void) | null = null
    const settle = (result: Record<string, unknown>): void => {
      offProgress?.()
      offResult?.()
      offError?.()
      resolve(result)
    }
    void transport
      .submitTask('serverFs', plainParams)
      .then(response => {
        const id = response.taskId
        if (onProgress) {
          offProgress = transport.onTaskProgress(id, payload => {
            onProgress(payload.progress, payload.message ?? '')
          })
        }
        offResult = transport.onTaskResult(id, payload => {
          settle((payload.data ?? {}) as Record<string, unknown>)
        })
        offError = transport.onTaskError(id, payload => {
          settle({ status: 'error', message: payload.error })
        })
      })
      .catch(err => {
        settle({ status: 'error', message: String(err) })
      })
  })
}

/** 列出管理员开放的目录；未配置时 configured=false。 */
export async function listServerRoots(
  transport: ReturnType<typeof useTransport>
): Promise<{ configured: boolean; roots: ServerFsRoot[]; message?: string }> {
  const result = await submitServerFsTask(transport, { action: 'list_roots' })
  if (result.status === 'error') {
    return {
      configured: false,
      roots: [],
      message: String(result.message ?? 'list_roots failed'),
    }
  }
  return {
    configured: result.configured === true,
    roots: (result.roots ?? []) as ServerFsRoot[],
  }
}

/** 浏览白名单树内目录。 */
export async function listServerDir(
  transport: ReturnType<typeof useTransport>,
  path: string
): Promise<{
  ok: boolean
  path?: string
  entries: ServerFsEntry[]
  truncated?: boolean
  message?: string
}> {
  const result = await submitServerFsTask(transport, { action: 'list', path })
  if (result.status === 'error') {
    return { ok: false, entries: [], message: String(result.message ?? 'list failed') }
  }
  return {
    ok: true,
    path: result.path as string | undefined,
    entries: (result.entries ?? []) as ServerFsEntry[],
    truncated: result.truncated === true,
  }
}

/** 暂存所选文件（可选无损压缩），返回 /api/download 可回传的清单。 */
export async function prepareServerDownload(
  transport: ReturnType<typeof useTransport>,
  paths: string[],
  compress: boolean,
  onProgress?: (progress: number, message: string) => void
): Promise<ServerFsDownloadOutcome> {
  const result = await submitServerFsTask(
    transport,
    { action: 'download_prepare', paths, compress },
    onProgress
  )
  if (result.status === 'error') {
    return {
      status: 'error',
      compressed: false,
      outputDir: '',
      files: [],
      message: String(result.message ?? 'download_prepare failed'),
    }
  }
  return {
    status: 'ok',
    compressed: result.compressed === true,
    outputDir: String(result.outputDir ?? ''),
    files: (result.files ?? []) as ServerFsDownloadItem[],
    report: result.report as ServerFsDownloadOutcome['report'],
    skippedUnsupported:
      typeof result.skippedUnsupported === 'number' ? result.skippedUnsupported : 0,
  }
}
