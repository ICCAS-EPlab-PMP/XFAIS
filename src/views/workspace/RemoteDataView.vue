<template>
  <div class="remote-data-view" :data-testid="testIds.remoteDataPage">
    <!-- Web 模式空态：功能桌面版专用 / desktop-only feature -->
    <div v-if="!isDesktop" class="rd-desktop-only" :data-testid="testIds.remoteDataDesktopOnly">
      <h2>{{ t('remoteData.desktopOnlyTitle') }}</h2>
      <p>{{ t('remoteData.desktopOnlyBody') }}</p>
    </div>

    <div v-else class="rd-layout">
      <!-- 左栏：连接状态（配置在设置页；可切换服务器）/ connection status -->
      <section class="rd-card rd-conn">
        <h2>{{ t('remoteData.connectionTitle') }}</h2>

        <template v-if="profile.servers.length === 0">
          <p class="rd-hint">{{ t('remoteData.picker.needSetup') }}</p>
          <router-link class="rd-link" to="/settings">{{ t('remoteData.picker.goSettings') }}</router-link>
        </template>

        <template v-else>
          <!-- 服务器切换 / server switcher -->
          <label class="rd-label">{{ t('remoteData.serverSelect') }}</label>
          <select
            v-model="selectedServerId"
            class="rd-input"
            :data-testid="testIds.remoteDataServerSelect"
            @change="onSwitchServer"
          >
            <option v-for="s in profile.servers" :key="s.id" :value="s.id">
              {{ s.id === profile.primaryId ? '★ ' : '' }}{{ s.label || s.host }}
            </option>
          </select>
          <div class="rd-actions">
            <button
              v-if="selectedServer && selectedServer.id !== profile.primaryId"
              class="rd-btn"
              type="button"
              @click="makePrimaryHere"
            >
              {{ t('remoteData.makePrimary') }}
            </button>
            <router-link class="rd-btn rd-link-btn" to="/settings">
              {{ t('remoteData.picker.goSettings') }}
            </router-link>
          </div>

          <template v-if="!connected">
            <p class="rd-hint">
              {{ connecting ? t('remoteData.connecting') : t('remoteData.autoConnectHint') }}
            </p>
            <p v-if="connectError" class="rd-error">{{ connectError }}</p>
            <div class="rd-actions">
              <button class="rd-btn rd-btn-primary" :disabled="connecting" @click="connectNow">
                {{ connecting ? t('remoteData.connecting') : t('remoteData.connect') }}
              </button>
            </div>
          </template>

          <template v-else>
            <p class="rd-connected">
              {{ t('remoteData.connectedAs', { host: sessionHost, fingerprint: shortFingerprint }) }}
            </p>
            <div class="rd-actions">
              <button class="rd-btn" :data-testid="testIds.remoteDataDisconnectBtn" @click="disconnect">
                {{ t('remoteData.disconnect') }}
              </button>
            </div>
          </template>
        </template>

        <p class="rd-hint">{{ t('remoteData.connectionSectionHint') }}</p>
      </section>

      <!-- 中栏：远端浏览 / remote browser -->
      <section class="rd-card rd-browser">
        <h2>{{ t('remoteData.browserTitle') }}</h2>
        <div class="rd-crumb">
          <input
            v-model="manualPath"
            class="rd-input rd-path"
            type="text"
            :placeholder="t('remoteData.remotePath')"
            @keyup.enter="openDir(manualPath)"
          />
          <button class="rd-btn" :disabled="!connected || listing" @click="openDir(currentPath)">
            {{ t('remoteData.refresh') }}
          </button>
          <button class="rd-btn" :disabled="!connected || !canGoUp" @click="goUp">
            {{ t('remoteData.goUp') }}
          </button>
        </div>

        <div class="rd-list" :data-testid="testIds.remoteDataBrowser">
          <div v-if="entries.length === 0" class="rd-empty">{{ t('remoteData.browserEmpty') }}</div>
          <div
            v-for="entry in entries"
            :key="entry.name"
            class="rd-entry"
            :data-testid="testIds.remoteDataEntry"
          >
            <input
              :checked="isSelected(entry)"
              type="checkbox"
              @change="toggleEntry(entry)"
            />
            <button
              class="rd-name"
              :class="{ 'rd-dir': entry.isDir }"
              type="button"
              :disabled="!connected"
              @click="entry.isDir && openDir(entryPath(entry))"
            >
              {{ entry.isDir ? '📁' : '📄' }} {{ entry.name }}
            </button>
            <span class="rd-size">{{ entry.isDir ? '—' : humanSize(entry.size) }}</span>
          </div>
        </div>
        <p v-if="truncated" class="rd-hint">
          {{ t('remoteData.browserTruncated', { count: entries.length }) }}
        </p>

        <div class="rd-selbar">
          <span class="rd-selcount">
            {{ t('remoteData.selectedCount', { files: selected.length, dirs: selectedDirs }) }}
          </span>
          <button class="rd-btn" :disabled="entries.length === 0" :data-testid="testIds.remoteDataSelectAll" @click="selectAllVisible">
            {{ t('remoteData.selectAll') }}
          </button>
          <button class="rd-btn" :disabled="selected.length === 0" @click="selected = []">
            {{ t('remoteData.clearSelection') }}
          </button>
        </div>
      </section>

      <!-- 右栏：下载 / download -->
      <section class="rd-card rd-dl">
        <h2>{{ t('remoteData.downloadTitle') }}</h2>
        <FileDialogButton v-model="destDir" mode="openFolder" :label="t('remoteData.destDir')" />
        <label class="rd-check">
          <input v-model="skipExisting" type="checkbox" />
          {{ t('remoteData.skipExisting') }}
        </label>
        <label class="rd-check" :data-testid="testIds.remoteDataCompressAfter">
          <input v-model="compressAfter" type="checkbox" />
          {{ t('remoteData.compressAfter') }}
        </label>
        <p v-if="compressAfter" class="rd-compress-hint">
          {{ t('remoteData.compressAfterHint') }}
        </p>
        <button
          class="rd-btn rd-btn-primary"
          :disabled="!canDownload"
          :data-testid="testIds.remoteDataStartBtn"
          @click="startDownload"
        >
          {{ downloading ? t('remoteData.downloadProgress') : t('remoteData.startDownload') }}
        </button>

        <TaskProgressBar
          v-if="downloading"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="cancelDownload"
        />

        <div v-if="lastResult" class="rd-result">
          <p>{{ lastResult.summary }}</p>
          <button v-if="lastResult.dir" class="rd-btn" @click="openLocalFolder(lastResult.dir)">
            {{ t('remoteData.openFolder') }}
          </button>
        </div>
      </section>

      <!-- 缓存池（无损压缩暂存）/ compressed download cache pool -->
      <section class="rd-card rd-cache" data-testid="remote-cache-pool">
        <h2>{{ t('remoteData.cachePool.title') }}</h2>
        <p class="rd-hint">{{ t('remoteData.cachePool.hint', { ttl: cacheTtl }) }}</p>
        <div class="rd-cache-actions">
          <button class="rd-btn" type="button" :disabled="cacheLoading" @click="loadCachePool">
            {{ t('remoteData.cachePool.refresh') }}
          </button>
          <span class="rd-cache-count">
            {{ t('remoteData.picker.selectedFiles', { count: cacheSelected.length }) }}
          </span>
        </div>
        <div class="rd-cache-list" :data-testid="testIds.remoteCachePoolList">
          <p v-if="cacheLoading" class="rd-hint">{{ t('remoteData.cachePool.loading') }}</p>
          <p v-else-if="cacheEntries.length === 0" class="rd-hint">
            {{ t('remoteData.cachePool.empty') }}
          </p>
          <label v-for="entry in cacheEntries" :key="entry.path" class="rd-cache-row">
            <input v-model="cacheSelected" type="checkbox" :value="entry.path" />
            <span class="rd-cache-name" :title="entry.relPath">{{ entry.name }}</span>
            <span class="rd-cache-meta" :title="entry.relPath">{{ entry.relPath }}</span>
            <span class="rd-cache-meta">
              {{ humanCacheSize(entry.size) }} · {{ cacheDate(entry.mtime) }}
            </span>
          </label>
        </div>
        <FileDialogButton
          v-model="cacheDestDir"
          mode="openFolder"
          :label="t('remoteData.cachePool.destDir')"
        />
        <button
          class="rd-btn rd-btn-primary"
          type="button"
          :disabled="cacheSelected.length === 0 || !cacheDestDir || exportingCache"
          :data-testid="testIds.remoteCachePoolExport"
          @click="exportCachePool"
        >
          {{ exportingCache ? t('remoteData.cachePool.exporting') : t('remoteData.cachePool.export') }}
        </button>
        <TaskProgressBar
          v-if="exportingCache"
          :task-id="cacheTaskId"
          :progress="cacheProgress"
          :message="cacheProgressMessage"
          @cancel="cancelCacheExport"
        />
        <div v-if="cacheResultSummary" class="rd-result">
          <p>{{ cacheResultSummary }}</p>
          <button v-if="cacheExportDir" class="rd-btn" @click="openLocalFolder(cacheExportDir)">
            {{ t('remoteData.openFolder') }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * RemoteDataView.vue — 远程数据同步（桌面版专用）
 *
 * 连接配置在设置页（SettingsView）；本页进入时用记忆档案自动连接。
 * 三区布局：连接状态 → 远端目录浏览 → 下载到本地（进度/取消 + 打开
 * 下载目录）。web 模式显示「仅桌面版可用」空态。
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import { useToast } from '@/lib/toast'
import { testIds } from '@/lib/testIds'
import {
  serverById,
  setPrimaryServer,
  updateServer,
  useRemoteSftpProfile
} from '@/lib/remoteSftpProfile'
import { submitRemoteDataTask, useRemoteSftpSession, type CachePoolEntry, type RemoteEntry } from '@/lib/remoteSftpSession'
import { useSettings } from '@/lib/settings'
import { useTransport } from '@/lib/transport'

interface SelectionItem {
  path: string
  isDir: boolean
}

const { t } = useI18n()
const transport = useTransport()
const toast = useToast()
const profile = useRemoteSftpProfile()
const session = useRemoteSftpSession()

const isDesktop = transport.isDesktop()

// ── 缓存池（无损压缩暂存）/ compressed download cache pool ─────────────────
const settingsStore = useSettings()
const cacheEntries = ref<CachePoolEntry[]>([])
const cacheSelected = ref<string[]>([])
const cacheLoading = ref(false)
const cacheDestDir = ref('')
const exportingCache = ref(false)
const cacheTaskId = ref<string | null>(null)
const cacheProgress = ref(0)
const cacheProgressMessage = ref<string | null>(null)
const cacheResultSummary = ref('')
const cacheExportDir = ref('')
const cacheTtl = computed(() => settingsStore.remoteSync?.cache?.ttlMinutes ?? 1440)

// ── 服务器切换 / server switching ──────────────────────────────────────────
const selectedServerId = ref<string>(profile.primaryId ?? profile.servers[0]?.id ?? '')
const selectedServer = computed(() => serverById(selectedServerId.value))

function onSwitchServer(): void {
  connectError.value = ''
  entries.value = []
  selected.value = []
  void connectNow()
}

function makePrimaryHere(): void {
  if (selectedServer.value) {
    setPrimaryServer(selectedServer.value.id)
    toast.push({ title: t('remoteData.title'), message: t('settings.remoteSync.primarySet'), tone: 'success' })
  }
}

// ── 连接状态 ────────────────────────────────────────────────────────────────
const connecting = ref(false)
const connectError = ref('')
const connected = computed(() => session.connected())
const sessionHost = computed(() => session.host.value)
const shortFingerprint = computed(() =>
  selectedServer.value?.hostFingerprint
    ? selectedServer.value.hostFingerprint.slice(7, 19) + '…'
    : ''
)

// ── 浏览状态 ────────────────────────────────────────────────────────────────
const currentPath = ref('/')
const manualPath = ref('/')
const entries = ref<RemoteEntry[]>([])
const truncated = ref(false)
const listing = ref(false)
const selected = ref<SelectionItem[]>([])
const canGoUp = computed(() => currentPath.value !== '/')

// ── 下载状态 ────────────────────────────────────────────────────────────────
const destDir = ref(selectedServer.value?.localDir ?? '')
const skipExisting = ref(true)
/** 下载后在本机无损压缩（TIFF/HDF5）；传输本身不压缩，压缩发生在下载完成后。 */
const compressAfter = ref(false)
const downloading = ref(false)
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const lastResult = ref<{ summary: string; dir: string } | null>(null)
const selectedDirs = computed(() => selected.value.filter(s => s.isDir).length)
const canDownload = computed(
  () => connected.value && selected.value.length > 0 && !!destDir.value && !downloading.value
)

onMounted(() => {
  if (isDesktop && selectedServer.value) {
    void connectNow()
  }
})

async function connectNow(): Promise<void> {
  connecting.value = true
  connectError.value = ''
  try {
    const err = await session.connect(selectedServerId.value)
    if (err) {
      const mismatch = err.includes('不匹配') || err.toLowerCase().includes('mismatch')
      connectError.value = mismatch ? t('remoteData.fingerprintChanged') : err
      return
    }
    // 回填指纹（TOFU 首连）/ persist fingerprint on first connect
    if (session.fingerprint.value) {
      updateServer(selectedServerId.value, { hostFingerprint: session.fingerprint.value })
    }
    currentPath.value = selectedServer.value?.remoteDir || '/'
    manualPath.value = currentPath.value
    await openDir(currentPath.value)
  } finally {
    connecting.value = false
  }
}

async function disconnect(): Promise<void> {
  entries.value = []
  selected.value = []
  await session.disconnect()
}

function entryPath(entry: RemoteEntry): string {
  const base = currentPath.value === '/' ? '' : currentPath.value
  return `${base}/${entry.name}`
}

function isSelected(entry: RemoteEntry): boolean {
  return selected.value.some(s => s.path === entryPath(entry))
}

function toggleEntry(entry: RemoteEntry): void {
  const path = entryPath(entry)
  const idx = selected.value.findIndex(s => s.path === path)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push({ path, isDir: entry.isDir })
  }
}

function selectAllVisible(): void {
  for (const entry of entries.value) {
    const path = entryPath(entry)
    if (!selected.value.some(s => s.path === path)) {
      selected.value.push({ path, isDir: entry.isDir })
    }
  }
}

function humanSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

// ── 浏览 ────────────────────────────────────────────────────────────────────
async function openDir(path: string): Promise<void> {
  if (!connected.value) return
  listing.value = true
  try {
    const result = await session.list(path)
    if (!result.ok) {
      connectError.value = result.message ?? ''
      return
    }
    connectError.value = ''
    currentPath.value = result.path ?? path
    manualPath.value = currentPath.value
    entries.value = result.entries
    truncated.value = Boolean(result.truncated)
    updateServer(selectedServerId.value, { remoteDir: currentPath.value })
  } finally {
    listing.value = false
  }
}

function goUp(): void {
  if (currentPath.value === '/') return
  const parent = currentPath.value.replace(/\/[^/]+$/, '') || '/'
  void openDir(parent)
}

// ── 下载 ────────────────────────────────────────────────────────────────────
async function startDownload(): Promise<void> {
  if (!connected.value) {
    toast.push({ title: t('remoteData.downloadTitle'), message: t('remoteData.needConnect'), tone: 'warning' })
    return
  }
  if (selected.value.length === 0) {
    toast.push({ title: t('remoteData.downloadTitle'), message: t('remoteData.needSelection'), tone: 'warning' })
    return
  }
  if (!destDir.value) {
    toast.push({ title: t('remoteData.downloadTitle'), message: t('remoteData.needDest'), tone: 'warning' })
    return
  }
  downloading.value = true
  progress.value = 0
  progressMessage.value = null
  updateServer(selectedServerId.value, { localDir: destDir.value })
  const base = currentPath.value
  try {
    const result = await session.download(
      selected.value.map(s => s.path),
      base,
      {
        destDir: destDir.value,
        skipExisting: skipExisting.value,
        onProgress: (p, m) => {
          progress.value = p
          progressMessage.value = m
        }
      }
    )
    if (result.status === 'error') {
      toast.push({ title: t('remoteData.taskErrorTitle'), message: result.message ?? '', tone: 'error' })
      return
    }
    if (result.status === 'cancelled') {
      lastResult.value = {
        summary: t('remoteData.downloadCancelled', { count: result.downloaded.length }),
        dir: result.outputDir
      }
      toast.push({ title: t('remoteData.downloadTitle'), message: lastResult.value.summary, tone: 'info' })
    } else {
      progress.value = 1
      lastResult.value = {
        summary: t('remoteData.downloadDoneMessage', {
          count: result.downloaded.length,
          skipped: result.skipped,
          failed: result.failed.length
        }),
        dir: result.outputDir
      }
      toast.push({
        title: t('remoteData.downloadDoneTitle'),
        message: lastResult.value.summary,
        tone: result.failed.length > 0 ? 'warning' : 'success'
      })
      // 下载后本机无损压缩（可选）：只处理 v0.5.0 引擎支持的 TIFF/HDF5，
      // 其余格式（EDF 等）保持原样并提示。
      if (compressAfter.value && result.downloaded.length > 0) {
        const compressible = result.downloaded.filter(p => COMPRESSIBLE_FILE_RE.test(p))
        if (compressible.length > 0) {
          await runLocalCompression(compressible, result.outputDir)
        } else {
          toast.push({
            title: t('remoteData.compressTitle'),
            message: t('remoteData.compressNothing'),
            tone: 'info'
          })
        }
      }
    }
  } finally {
    downloading.value = false
    taskId.value = null
  }
}

/** v0.5.0 无损压缩引擎支持的格式（TIFF / HDF5）。 */
const COMPRESSIBLE_FILE_RE = /\.(tif|tiff|h5|hdf5)$/i

/** 提交本机 compress batch 任务（压缩到 <dest>/compressed/），进度复用下载进度条。 */
function submitCompressBatch(files: string[], outputDir: string): Promise<Record<string, unknown>> {
  return new Promise(resolve => {
    let offProgress: (() => void) | null = null
    let offResult: (() => void) | null = null
    let offError: (() => void) | null = null
    const settle = (r: Record<string, unknown>): void => {
      offProgress?.()
      offResult?.()
      offError?.()
      resolve(r)
    }
    void transport
      .submitTask('compress', { action: 'batch', files, outputDir })
      .then(response => {
        const id = response.taskId
        taskId.value = id
        offProgress = transport.onTaskProgress(id, payload => {
          progress.value = payload.progress
          progressMessage.value = payload.message ?? ''
        })
        offResult = transport.onTaskResult(id, payload => {
          settle((payload.data ?? {}) as Record<string, unknown>)
        })
        offError = transport.onTaskError(id, payload => {
          settle({ status: 'error', message: payload.error })
        })
      })
      .catch(err => settle({ status: 'error', message: String(err) }))
  })
}

async function runLocalCompression(files: string[], downloadDir: string): Promise<void> {
  const outputDir = `${downloadDir.replace(/[\\/]+$/, '')}/compressed`
  downloading.value = true
  progress.value = 0
  progressMessage.value = t('remoteData.compressStarting')
  try {
    const report = await submitCompressBatch(files, outputDir)
    if (report.status === 'error') {
      toast.push({
        title: t('remoteData.compressTitle'),
        message: String(report.message ?? ''),
        tone: 'error'
      })
      return
    }
    const r = report as { success?: number; failed?: number; skipped?: number; ratio?: number }
    lastResult.value = {
      summary: t('remoteData.compressDone', {
        success: r.success ?? 0,
        failed: r.failed ?? 0,
        skipped: r.skipped ?? 0,
        ratio: r.ratio != null ? Number(r.ratio).toFixed(2) : '—'
      }),
      dir: outputDir
    }
    toast.push({ title: t('remoteData.compressTitle'), message: lastResult.value.summary, tone: 'success' })
  } finally {
    downloading.value = false
    taskId.value = null
  }
}

function cancelDownload(): void {
  if (taskId.value) {
    void transport.cancelTask(taskId.value)
  }
}

async function openLocalFolder(dir: string): Promise<void> {
  await transport.openPath(dir)
}

// ── 缓存池：列表 / 转化到本地 ───────────────────────────────────────────────
async function loadCachePool(): Promise<void> {
  cacheLoading.value = true
  try {
    const result = await submitRemoteDataTask(transport, {
      action: 'cache_pool_list',
      cacheDir: settingsStore.remoteSync?.cache?.dir ?? '',
      cacheTtlMinutes: cacheTtl.value
    })
    cacheEntries.value =
      result.status === 'ok' && Array.isArray(result.entries)
        ? (result.entries as CachePoolEntry[])
        : []
    cacheSelected.value = []
  } finally {
    cacheLoading.value = false
  }
}

function submitCachePoolExport(paths: string[], destDir: string): Promise<Record<string, unknown>> {
  return new Promise(resolve => {
    let offProgress: (() => void) | null = null
    let offResult: (() => void) | null = null
    let offError: (() => void) | null = null
    const settle = (r: Record<string, unknown>): void => {
      offProgress?.()
      offResult?.()
      offError?.()
      resolve(r)
    }
    void transport
      .submitTask('remoteData', {
        action: 'cache_pool_export',
        paths,
        destDir,
        cacheDir: settingsStore.remoteSync?.cache?.dir ?? '',
        cacheTtlMinutes: cacheTtl.value
      })
      .then(response => {
        const id = response.taskId
        cacheTaskId.value = id
        offProgress = transport.onTaskProgress(id, payload => {
          cacheProgress.value = payload.progress
          cacheProgressMessage.value = payload.message ?? ''
        })
        offResult = transport.onTaskResult(id, payload => {
          settle((payload.data ?? {}) as Record<string, unknown>)
        })
        offError = transport.onTaskError(id, payload => {
          settle({ status: 'error', message: payload.error })
        })
      })
      .catch(err => settle({ status: 'error', message: String(err) }))
  })
}

async function exportCachePool(): Promise<void> {
  if (cacheSelected.value.length === 0 || !cacheDestDir.value || exportingCache.value) return
  exportingCache.value = true
  cacheProgress.value = 0
  cacheProgressMessage.value = null
  cacheResultSummary.value = ''
  cacheExportDir.value = ''
  try {
    const result = await submitCachePoolExport([...cacheSelected.value], cacheDestDir.value)
    if (result.status === 'error') {
      toast.push({
        title: t('remoteData.cachePool.title'),
        message: String(result.message ?? ''),
        tone: 'error'
      })
      return
    }
    const exported = Array.isArray(result.exported)
      ? (result.exported as { filename: string }[])
      : []
    const failedN = Array.isArray(result.failed) ? result.failed.length : 0
    cacheExportDir.value = String(result.outputDir ?? cacheDestDir.value)
    cacheResultSummary.value = t('remoteData.cachePool.exportDone', {
      count: exported.length,
      failed: failedN,
      dir: cacheExportDir.value
    })
    toast.push({
      title: t('remoteData.cachePool.title'),
      message: cacheResultSummary.value,
      tone: failedN > 0 ? 'warning' : 'success'
    })
    void loadCachePool()
  } finally {
    exportingCache.value = false
    cacheTaskId.value = null
  }
}

function cancelCacheExport(): void {
  if (cacheTaskId.value) void transport.cancelTask(cacheTaskId.value)
}

function humanCacheSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function cacheDate(mtime: number): string {
  const d = new Date(mtime * 1000)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  if (isDesktop) void loadCachePool()
})
</script>

<style scoped>
.remote-data-view {
  padding: 16px;
  max-width: 1400px;
  margin: 0 auto;
}

.rd-desktop-only {
  text-align: center;
  padding: 64px 24px;
  opacity: 0.85;
}

.rd-layout {
  display: grid;
  grid-template-columns: 300px 1fr 320px;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .rd-layout {
    grid-template-columns: 1fr;
  }
}

.rd-card {
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 10px;
  padding: 16px;
  background: var(--color-surface, #fff);
}

.rd-card h2 {
  margin: 0 0 12px;
  font-size: 16px;
}

.rd-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.rd-label {
  display: block;
  font-size: 12px;
  margin: 10px 0 4px;
  opacity: 0.75;
}

.rd-link-btn {
  display: inline-block;
  text-decoration: none;
  color: inherit;
  line-height: 1.5;
}

.rd-link {
  color: var(--color-primary, #1e40af);
}

.rd-error {
  color: #b91c1c;
  font-size: 12.5px;
}

.rd-check {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 12.5px;
  margin: 10px 0;
}

.rd-compress-hint {
  font-size: 12px;
  opacity: 0.75;
  margin: -4px 0 10px;
}

.rd-hint {
  font-size: 12.5px;
  opacity: 0.75;
  margin: 6px 0;
}

.rd-cache-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 8px 0;
}

.rd-cache-count {
  font-size: 12.5px;
  opacity: 0.75;
}

.rd-cache-list {
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  max-height: 220px;
  min-height: 60px;
  overflow: auto;
  margin: 8px 0;
}

.rd-cache-row {
  display: grid;
  grid-template-columns: auto 1fr minmax(120px, 2fr) minmax(110px, 1fr);
  gap: 8px;
  align-items: center;
  padding: 4px 10px;
  font-size: 12.5px;
}

.rd-cache-row:hover {
  background: rgba(30, 64, 175, 0.06);
}

.rd-cache-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rd-cache-meta {
  opacity: 0.65;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rd-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 13px;
  cursor: pointer;
  margin: 4px 6px 4px 0;
}

.rd-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.rd-btn-primary {
  background: var(--color-primary, #1e40af);
  border-color: var(--color-primary, #1e40af);
  color: #fff;
}

.rd-hint {
  font-size: 11.5px;
  opacity: 0.6;
  margin-top: 10px;
}

.rd-connected {
  font-size: 13px;
  margin: 0 0 10px;
  word-break: break-all;
}

.rd-crumb {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.rd-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  font-size: 13px;
}

.rd-path {
  flex: 1;
}

.rd-list {
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  min-height: 220px;
  max-height: 460px;
  overflow: auto;
}

.rd-empty {
  padding: 32px;
  text-align: center;
  opacity: 0.6;
  font-size: 13px;
}

.rd-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  font-size: 13px;
}

.rd-entry:hover {
  background: rgba(30, 64, 175, 0.06);
}

.rd-name {
  flex: 1;
  text-align: left;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px 0;
  font-size: 13px;
  color: inherit;
}

.rd-name.rd-dir {
  font-weight: 600;
}

.rd-size {
  opacity: 0.6;
  font-size: 12px;
  white-space: nowrap;
}

.rd-selbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.rd-selcount {
  font-size: 12.5px;
  opacity: 0.8;
  margin-right: auto;
}

.rd-result {
  margin-top: 14px;
  padding: 10px;
  border-radius: 6px;
  background: rgba(30, 64, 175, 0.06);
  font-size: 13px;
}
</style>
