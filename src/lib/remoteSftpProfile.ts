// remoteSftpProfile.ts — multiple remembered SFTP servers (v2)
// 多远端服务器记忆档案（v2）。
//
// Storage layout / 存储布局:
//   xfaos.remoteSftp.v1 → 旧单档案（自动迁移为 v2 的首个服务器）
//   xfaos.remoteSftp.v2 → { servers: RemoteSftpServer[], primaryId }
//   <userData>/remote-sftp-<id>.secret → 每服务器一份可选记住的口令
//   （经 safeStorage/DPAPI 加密，由 Electron 主进程读写；**绝不**明文进
//   localStorage）
//
// 主服务器（primaryId）供各处理页的「远端选择」弹窗使用；传输页
// （RemoteDataView）可在任意服务器之间切换工作，并可改设主服务器。
// 所有连接信息仅记忆在用户本机，绝不进入任何代码仓库。
import { reactive, watch } from 'vue'

const STORAGE_KEY_V1 = 'xfaos.remoteSftp.v1'
const STORAGE_KEY = 'xfaos.remoteSftp.v2'

/** Auth mode of a server profile / 服务器档案的认证方式 */
export type RemoteSftpAuthMode = 'password' | 'key'

export interface RemoteSftpServer {
  /** Stable id (uuid) / 稳定标识 */
  id: string
  /** Display label / 显示名 */
  label: string
  /** Host (hostname or IP) / 主机地址 */
  host: string
  /** Port / 端口 */
  port: number
  /** Username / 用户名 */
  username: string
  /** Auth mode / 认证方式 */
  authMode: RemoteSftpAuthMode
  /** Private-key path (authMode === 'key') / 私钥路径 */
  keyPath: string
  /** Remote directory opened last time / 上次浏览的远端目录 */
  remoteDir: string
  /** Local download destination / 本地下载目录 */
  localDir: string
  /** Whether the user opted into remembering the passphrase (encrypted
   * via safeStorage, desktop only). / 是否记住口令（加密存储，仅桌面版） */
  rememberPassphrase: boolean
  /** Pinned host-key fingerprint (TOFU). / 固定的主机指纹（TOFU） */
  hostFingerprint: string
}

export interface RemoteSftpStore {
  servers: RemoteSftpServer[]
  /** Primary server id: used by the「远端选择」pickers on all pages. / 主服务器 */
  primaryId: string | null
}

function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `srv-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function readJson(key: string): Record<string, unknown> | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Record<string, unknown>
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

/** v1 单档案 → v2 服务器（一次性迁移） / migrate legacy single profile. */
function migrateV1(): RemoteSftpStore | null {
  const v1 = readJson(STORAGE_KEY_V1)
  if (!v1 || typeof v1.host !== 'string' || !v1.host) return null
  const server: RemoteSftpServer = {
    id: newId(),
    label: String(v1.host),
    host: String(v1.host),
    port: Number(v1.port) || 22,
    username: String(v1.username ?? ''),
    authMode: v1.authMode === 'key' ? 'key' : 'password',
    keyPath: String(v1.keyPath ?? ''),
    remoteDir: String(v1.remoteDir ?? ''),
    localDir: String(v1.localDir ?? ''),
    rememberPassphrase: Boolean(v1.rememberPassword),
    hostFingerprint: String(v1.hostFingerprint ?? '')
  }
  try {
    localStorage.removeItem(STORAGE_KEY_V1)
  } catch {
    /* best-effort */
  }
  return { servers: [server], primaryId: server.id }
}

function loadStore(): RemoteSftpStore {
  const v2 = readJson(STORAGE_KEY)
  if (v2 && Array.isArray(v2.servers)) {
    const servers = (v2.servers as Record<string, unknown>[]).map(s => normalizeServer(s))
    const primaryId = typeof v2.primaryId === 'string' ? v2.primaryId : null
    const store: RemoteSftpStore = {
      servers,
      primaryId: primaryId && servers.some(s => s.id === primaryId) ? primaryId : (servers[0]?.id ?? null)
    }
    return store
  }
  return migrateV1() ?? { servers: [], primaryId: null }
}

function normalizeServer(raw: Record<string, unknown>): RemoteSftpServer {
  return {
    id: typeof raw.id === 'string' && raw.id ? raw.id : newId(),
    label: typeof raw.label === 'string' ? raw.label : String(raw.host ?? ''),
    host: typeof raw.host === 'string' ? raw.host : '',
    port: Number(raw.port) || 22,
    username: typeof raw.username === 'string' ? raw.username : '',
    authMode: raw.authMode === 'key' ? 'key' : 'password',
    keyPath: typeof raw.keyPath === 'string' ? raw.keyPath : '',
    remoteDir: typeof raw.remoteDir === 'string' ? raw.remoteDir : '',
    localDir: typeof raw.localDir === 'string' ? raw.localDir : '',
    rememberPassphrase: Boolean(raw.rememberPassphrase),
    hostFingerprint: typeof raw.hostFingerprint === 'string' ? raw.hostFingerprint : ''
  }
}

const state = reactive<RemoteSftpStore>(loadStore())

function persist(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* storage full/blocked — keep in-memory state / 存储异常时仅保留内存态 */
  }
}

watch(state, persist, { deep: true })

/** Reactive multi-server store. / 多服务器响应式档案。 */
export function useRemoteSftpProfile(): RemoteSftpStore {
  return state
}

/** The primary server (used by all「远端选择」pickers), or null. / 主服务器。 */
export function primaryServer(): RemoteSftpServer | null {
  return state.servers.find(s => s.id === state.primaryId) ?? null
}

export function serverById(id: string | null): RemoteSftpServer | null {
  if (!id) return null
  return state.servers.find(s => s.id === id) ?? null
}

/** Add or update a server (by id; new id when absent). Returns the id. */
export function upsertServer(server: RemoteSftpServer): string {
  const idx = state.servers.findIndex(s => s.id === server.id)
  if (idx >= 0) {
    state.servers[idx] = server
  } else {
    state.servers.push(server)
  }
  if (state.primaryId === null) {
    state.primaryId = server.id
  }
  return server.id
}

export function removeServer(id: string): void {
  const idx = state.servers.findIndex(s => s.id === id)
  if (idx < 0) return
  state.servers.splice(idx, 1)
  if (state.primaryId === id) {
    state.primaryId = state.servers[0]?.id ?? null
  }
}

/** Set the primary server (used by remote pickers on all pages). / 设主服务器。 */
export function setPrimaryServer(id: string): void {
  if (state.servers.some(s => s.id === id)) {
    state.primaryId = id
  }
}

/** Update fields of one server (merged). / 合并更新单个服务器。 */
export function updateServer(id: string, patch: Partial<RemoteSftpServer>): void {
  const idx = state.servers.findIndex(s => s.id === id)
  if (idx >= 0) {
    state.servers[idx] = { ...state.servers[idx], ...patch }
  }
}

export function createEmptyServer(): RemoteSftpServer {
  return {
    id: newId(),
    label: '',
    host: '',
    port: 22,
    username: '',
    authMode: 'password',
    keyPath: '',
    remoteDir: '',
    localDir: '',
    rememberPassphrase: false,
    hostFingerprint: ''
  }
}

// ── Per-server remembered passphrase (safeStorage/DPAPI, desktop only) ───────

const desktop = (): typeof window.desktop | undefined =>
  typeof window !== 'undefined' ? window.desktop : undefined

/** Load the remembered passphrase for one server (desktop only). / 按服务器读取记住的口令。 */
export async function loadRememberedPassword(serverId: string): Promise<string | null> {
  const load = desktop()?.sftpSecret?.load
  if (typeof load !== 'function') return null
  try {
    return await load(serverId)
  } catch {
    return null
  }
}

/** Legacy single-slot password (v1 migration source). / 旧单文件口令（迁移用）。 */
export async function loadLegacyRememberedPassword(): Promise<string | null> {
  const load = desktop()?.sftpSecret?.load
  if (typeof load !== 'function') return null
  try {
    return await load('')
  } catch {
    return null
  }
}

/** Persist the passphrase for one server via safeStorage (opt-in). / 按服务器记住口令。 */
export async function saveRememberedPassword(serverId: string, value: string): Promise<boolean> {
  const store = desktop()?.sftpSecret?.store
  if (typeof store !== 'function') return false
  try {
    const result = await store(serverId, value)
    return result.ok
  } catch {
    return false
  }
}

/** Forget the remembered passphrase for one server (empty key = legacy file). */
export async function deleteRememberedPassword(serverId: string): Promise<void> {
  const remove = desktop()?.sftpSecret?.delete
  if (typeof remove !== 'function') return
  try {
    await remove(serverId)
  } catch {
    /* best-effort / 尽力而为 */
  }
}
