// remoteSftpSession.ts — 共享的 SFTP 会话 composable（多服务器）
// 供 RemoteDataView（浏览/下载，可切换服务器）、RemoteFilePicker（固定
// 用主服务器）、SettingsView（测试连接）复用：连接、列表、下载、断开。
//
// 连接参数来自本机多服务器档案（remoteSftpProfile）；口令经 safeStorage
// 加密按服务器分文件读取（仅桌面版）。所有动作走 remoteData 任务
// （后端桌面专用）。
import { ref } from 'vue'
import { useTransport } from '@/lib/transport'
import {
  loadRememberedPassword,
  primaryServer,
  useRemoteSftpProfile,
  type RemoteSftpServer
} from '@/lib/remoteSftpProfile'

export interface RemoteEntry {
  name: string
  isDir: boolean
  size: number
  mtime: number
}

export interface DownloadOutcome {
  status: 'ok' | 'cancelled' | 'error'
  message?: string
  downloaded: string[]
  skipped: number
  failed: { path: string; reason: string }[]
  outputDir: string
}

/** 提交一个 remoteData 任务并等待结果（progress 可选回调）。

   参数在提交前经 JSON 往返剥离 Vue reactive Proxy——结构化克隆
   （Electron IPC）无法序列化 Proxy，reactive 数组/对象直接 invoke 会抛
   "An object could not be cloned"（JSON 往返同时丢掉 undefined 字段，
   后端 get 缺键等价 None，语义不变）。
 */
export function submitRemoteDataTask(
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
      .submitTask('remoteData', plainParams)
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

/** 连接覆盖项（测试连接时传临时口令等）。 */
export interface ConnectOverride {
  passphrase?: string
  keyPassphrase?: string
  /** 保存表单尚未落库时，直接给完整服务器参数。 */
  server?: RemoteSftpServer
}

/** 缓存池条目（cache_pool_list 返回）。 */
export interface CachePoolEntry {
  path: string
  relPath: string
  serverKey: string
  name: string
  size: number
  mtime: number
}

/** 缓存池条目（cache_pool_list 返回；path 为本机绝对路径）。 */
export interface CachePoolEntry {
  path: string
  relPath: string
  serverKey: string
  name: string
  size: number
  mtime: number
}

export interface SftpSessionState {
  connId: ReturnType<typeof ref<string | null>>
  host: ReturnType<typeof ref<string>>
  /** 当前连接的服务器档案 id（null = 未连接）。 */
  activeServerId: ReturnType<typeof ref<string | null>>
  /** 最近一次连接成功获得的主机指纹（TOFU 存档用）。 */
  fingerprint: ReturnType<typeof ref<string>>
  connected: () => boolean
  /** 连接指定服务器；缺省用主服务器（primaryId）。返回错误消息或 null。 */
  connect: (serverId?: string, override?: ConnectOverride) => Promise<string | null>
  list: (path: string) => Promise<{ ok: boolean; path?: string; entries: RemoteEntry[]; truncated?: boolean; message?: string }>
  /** 下载到指定本地目录、系统临时缓存（useTemp）或无损压缩缓存池（cachePool）。 */
  download: (paths: string[], basePath: string, opts?: { destDir?: string; useTemp?: boolean; skipExisting?: boolean; onProgress?: (p: number, m: string) => void; cachePool?: boolean; cacheDir?: string; cacheCompress?: boolean; cacheTtlMinutes?: number; serverKey?: string }) => Promise<DownloadOutcome>
  disconnect: () => Promise<void>
}

/** 创建一个 SFTP 会话（连接缓存持有 connId；不自动连接）。 */
export function useRemoteSftpSession(): SftpSessionState {
  const transport = useTransport()
  const profile = useRemoteSftpProfile()
  const connId = ref<string | null>(null)
  const host = ref('')
  const activeServerId = ref<string | null>(null)
  const fingerprint = ref('')

  async function connect(
    serverId?: string,
    override?: ConnectOverride
  ): Promise<string | null> {
    const server = override?.server
      ?? profile.servers.find(s => s.id === (serverId ?? profile.primaryId))
      ?? null
    if (!server || !server.host || !server.username) {
      return 'no server configured / 未配置服务器'
    }
    let passphrase = override?.passphrase ?? ''
    if (server.authMode === 'password' && !passphrase) {
      const remembered = await loadRememberedPassword(server.id)
      if (remembered) passphrase = remembered
    }
    const result = await submitRemoteDataTask(transport, {
      action: 'connect',
      host: server.host.trim(),
      port: server.port,
      username: server.username.trim(),
      password: server.authMode === 'password' ? passphrase : '',
      keyPath: server.authMode === 'key' ? server.keyPath.trim() : '',
      keyPassphrase: server.authMode === 'key' ? (override?.keyPassphrase ?? '') : '',
      hostFingerprint: server.hostFingerprint || undefined
    })
    if (result.status === 'error') {
      return String(result.message ?? 'connect failed')
    }
    connId.value = String(result.connId ?? '')
    host.value = String(result.host ?? server.host)
    activeServerId.value = server.id
    fingerprint.value = String(result.hostFingerprint ?? '')
    return null
  }

  async function list(path: string): Promise<{
    ok: boolean
    path?: string
    entries: RemoteEntry[]
    truncated?: boolean
    message?: string
  }> {
    if (!connId.value) return { ok: false, entries: [], message: 'not connected' }
    const result = await submitRemoteDataTask(transport, {
      action: 'list',
      connId: connId.value,
      path
    })
    if (result.status === 'error') {
      return { ok: false, entries: [], message: String(result.message ?? '') }
    }
    return {
      ok: true,
      path: String(result.path ?? path),
      entries: Array.isArray(result.entries) ? (result.entries as RemoteEntry[]) : [],
      truncated: Boolean(result.truncated)
    }
  }

  async function download(
    paths: string[],
    basePath: string,
    opts?: { destDir?: string; useTemp?: boolean; skipExisting?: boolean; onProgress?: (p: number, m: string) => void; cachePool?: boolean; cacheDir?: string; cacheCompress?: boolean; cacheTtlMinutes?: number; serverKey?: string }
  ): Promise<DownloadOutcome> {
    if (!connId.value) {
      return { status: 'error', message: 'not connected', downloaded: [], skipped: 0, failed: [], outputDir: '' }
    }
    // 缓存池参数（仅 cachePool 时下发；压缩/目录/TTL 来自总设置）
    const cacheParams: Record<string, unknown> = opts?.cachePool
      ? {
          cachePool: true,
          cacheDir: opts.cacheDir ?? '',
          cacheCompress: opts.cacheCompress !== false,
          cacheTtlMinutes: opts.cacheTtlMinutes ?? 1440,
          serverKey: opts.serverKey ?? ''
        }
      : {}
    const result = await submitRemoteDataTask(
      transport,
      {
        action: 'download',
        connId: connId.value,
        paths,
        basePath,
        destDir: opts?.useTemp ? '' : (opts?.destDir ?? ''),
        useTempDir: Boolean(opts?.useTemp),
        skipExisting: opts?.skipExisting ?? true,
        ...cacheParams
      },
      opts?.onProgress
    )
    if (result.status === 'error') {
      return {
        status: 'error',
        message: String(result.message ?? ''),
        downloaded: [], skipped: 0, failed: [], outputDir: ''
      }
    }
    return {
      status: (result.status === 'cancelled' ? 'cancelled' : 'ok'),
      message: result.message ? String(result.message) : undefined,
      downloaded: Array.isArray(result.downloaded) ? (result.downloaded as string[]) : [],
      skipped: Number(result.skipped ?? 0),
      failed: Array.isArray(result.failed) ? (result.failed as { path: string; reason: string }[]) : [],
      outputDir: String(result.outputDir ?? '')
    }
  }

  async function disconnect(): Promise<void> {
    const id = connId.value
    connId.value = null
    activeServerId.value = null
    if (id) {
      await submitRemoteDataTask(transport, { action: 'disconnect', connId: id })
    }
  }

  return {
    connId,
    host,
    activeServerId,
    fingerprint,
    connected: () => connId.value !== null,
    connect,
    list,
    download,
    disconnect
  }
}
