<template>
  <div
    v-if="visible"
    class="rfp-backdrop"
    :data-testid="testIds.remotePickerBackdrop"
    @click.self="$emit('close')"
  >
    <div class="rfp-dialog">
      <header class="rfp-header">
        <h3>{{ t('remoteData.picker.title') }}</h3>
        <button class="rfp-close" type="button" @click="$emit('close')">×</button>
      </header>

      <!-- 用户要求的常显提示（仅远端页签）/ always-on notice (remote tab only) -->
      <p v-if="tab === 'remote'" class="rfp-notice" :data-testid="testIds.remotePickerNotice">
        ⚠ {{ t('remoteData.picker.notice') }}
      </p>

      <!-- 页签：远端目录 / 缓存池 / remote browse vs cache pool -->
      <div class="rfp-tabs" data-testid="remote-picker-tabs">
        <button
          type="button"
          class="rfp-tab"
          :class="{ 'rfp-tab--active': tab === 'remote' }"
          @click="switchTab('remote')"
        >
          {{ t('remoteData.picker.tabRemote') }}
        </button>
        <button
          type="button"
          class="rfp-tab"
          :class="{ 'rfp-tab--active': tab === 'cache' }"
          @click="switchTab('cache')"
        >
          {{ t('remoteData.picker.tabCache') }}
        </button>
      </div>

      <!-- 未配置远端服务器 / server not configured -->
      <div v-if="!hasProfile" class="rfp-empty">
        <p>{{ t('remoteData.picker.needSetup') }}</p>
        <router-link class="rfp-link" to="/settings">
          {{ t('remoteData.picker.goSettings') }}
        </router-link>
      </div>

      <!-- 缓存池页签：无损压缩暂存，免下载直接选用 / cache pool tab -->
      <template v-else-if="tab === 'cache'">
        <div
          ref="cacheListEl"
          class="rfp-list"
          :class="{ 'rfp-boxing': boxSel?.kind === 'cache' }"
          data-testid="remote-picker-cache-list"
          @pointerdown="onListPointerDown($event, 'cache')"
        >
          <div v-if="cacheLoading" class="rfp-empty">
            {{ t('remoteData.picker.cacheLoading') }}
          </div>
          <div v-else-if="cacheEntries.length === 0" class="rfp-empty">
            {{ t('remoteData.picker.cacheEmpty') }}
          </div>
          <label
            v-for="entry in cacheEntries"
            :key="entry.path"
            class="rfp-entry"
            :class="{ 'rfp-filtered': isCacheFiltered(entry) }"
            :data-key="entry.path"
          >
            <input
              v-if="!isCacheFiltered(entry)"
              type="checkbox"
              :checked="cacheSelected.includes(entry.path)"
              @change="toggleCache(entry)"
            />
            <span v-else class="rfp-radio-spacer" />
            <span class="rfp-name rfp-name--plain">📄 {{ entry.name }}</span>
            <span class="rfp-size">{{ humanSize(entry.size) }} · {{ cacheDate(entry.mtime) }}</span>
          </label>
        </div>
        <p class="rfp-cache-hint">{{ t('remoteData.picker.cacheHint', { ttl: cacheTtlMinutes }) }}</p>
        <div class="rfp-status">
          <span class="rfp-mini-actions">
            <button
              class="rfp-mini-btn"
              type="button"
              :disabled="cacheLoading || cacheEntries.length === 0"
              :data-testid="testIds.remotePickerSelectAll"
              @click="selectAllCache"
            >
              {{ t('remoteData.picker.selectAll') }}
            </button>
            <button
              class="rfp-mini-btn"
              type="button"
              :disabled="cacheSelected.length === 0"
              @click="cacheSelected = []"
            >
              {{ t('remoteData.picker.clearSelection') }}
            </button>
          </span>
          <span>{{ t('remoteData.picker.selectedFiles', { count: cacheSelected.length }) }}</span>
        </div>
        <footer class="rfp-footer">
          <button class="rfp-btn" type="button" @click="$emit('close')">
            {{ t('remoteData.picker.cancel') }}
          </button>
          <button
            class="rfp-btn rfp-btn-primary"
            type="button"
            :disabled="cacheSelected.length === 0"
            :data-testid="testIds.remotePickerCacheConfirm"
            @click="confirmCache"
          >
            {{ t('remoteData.picker.confirm') }}
          </button>
        </footer>
      </template>

      <template v-else>
        <!-- 连接中/失败 / connecting or failed -->
        <div v-if="!session.connected()" class="rfp-connecting">
          <p v-if="connecting">{{ t('remoteData.connecting') }}</p>
          <template v-else-if="connectError">
            <p class="rfp-error">{{ connectError }}</p>
            <button class="rfp-btn" type="button" @click="ensureConnected">
              {{ t('remoteData.picker.retry') }}
            </button>
          </template>
        </div>

        <!-- 浏览 / browse -->
        <template v-else>
          <div class="rfp-crumb">
            <input
              v-model="manualPath"
              class="rfp-input"
              type="text"
              @keyup.enter="openDir(manualPath)"
            />
            <button class="rfp-btn" type="button" :disabled="loading" @click="openDir(currentPath)">
              {{ t('remoteData.refresh') }}
            </button>
            <button class="rfp-btn" type="button" :disabled="currentPath === '/'" @click="goUp">
              {{ t('remoteData.goUp') }}
            </button>
          </div>

          <div
            ref="remoteListEl"
            class="rfp-list"
            :class="{ 'rfp-boxing': boxSel?.kind === 'remote' }"
            :data-testid="testIds.remotePickerList"
            @pointerdown="onListPointerDown($event, 'remote')"
          >
            <div v-if="entries.length === 0 && !loading" class="rfp-empty">
              {{ t('remoteData.browserEmpty') }}
            </div>
            <label
              v-for="entry in entries"
              :key="entry.name"
              class="rfp-entry"
              :class="{ 'rfp-dir': entry.isDir, 'rfp-filtered': isFiltered(entry) }"
              :data-key="entryPath(entry)"
            >
              <input
                v-if="(mode === 'files' || entry.isDir) && !isFiltered(entry)"
                :checked="isSelected(entry)"
                type="checkbox"
                @change="toggle(entry)"
              />
              <span v-else class="rfp-radio-spacer" />
              <button
                class="rfp-name"
                type="button"
                @click="onRowNameClick(entry)"
              >
                {{ entry.isDir ? '📁' : '📄' }} {{ entry.name }}
              </button>
              <span class="rfp-size">{{ entry.isDir ? '—' : humanSize(entry.size) }}</span>
            </label>
          </div>

          <div class="rfp-status">
            <span v-if="mode === 'files'" class="rfp-mini-actions">
              <button
                class="rfp-mini-btn"
                type="button"
                :disabled="loading || entries.length === 0"
                @click="selectAllRemote"
              >
                {{ t('remoteData.picker.selectAll') }}
              </button>
              <button
                class="rfp-mini-btn"
                type="button"
                :disabled="selected.length === 0"
                @click="selected = []"
              >
                {{ t('remoteData.picker.clearSelection') }}
              </button>
              {{ t('remoteData.picker.selectedFiles', { count: selected.length }) }}
            </span>
            <span v-else>
              {{ selected ? selected : t('remoteData.picker.noFolderSelected') }}
            </span>
            <span v-if="downloading" class="rfp-progress">
              {{ Math.round(progress * 100) }}% {{ progressMessage }}
            </span>
          </div>

          <footer class="rfp-footer">
            <button class="rfp-btn" type="button" :disabled="downloading" @click="$emit('close')">
              {{ t('remoteData.picker.cancel') }}
            </button>
            <button
              class="rfp-btn rfp-btn-primary"
              type="button"
              :disabled="!canConfirm || downloading"
              :data-testid="testIds.remotePickerConfirm"
              @click="confirm"
            >
              {{ downloading ? t('remoteData.downloadProgress') : t('remoteData.picker.confirm') }}
            </button>
          </footer>
        </template>
      </template>
    </div>
    <!-- 长按框选矩形（fixed，覆盖于弹窗之上）/ long-press box-selection rect -->
    <div v-if="boxSel" class="rfp-box-rect" :style="boxRectStyle" />
  </div>
</template>

<script setup lang="ts">
/**
 * RemoteFilePicker.vue — 「从远端服务器选择数据」通用弹窗
 *
 * 浏览 SFTP 远端目录 → 勾选文件/目录 → 下载到本机临时文件夹
 * （系统 temp 的 xfais-remote-cache/，同尺寸跳过）→ 把本地路径交回
 * 调用方视图的既有处理流程。常显提示：不建议大规模处理。
 * mode='files'：多选，返回下载后的本地文件绝对路径列表；
 * mode='folder'：仅目录单选，返回下载后的本地目录路径。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'
import { primaryServer } from '@/lib/remoteSftpProfile'
import { useSettings } from '@/lib/settings'
import { useTransport } from '@/lib/transport'
import {
  submitRemoteDataTask,
  useRemoteSftpSession,
  type CachePoolEntry,
  type RemoteEntry
} from '@/lib/remoteSftpSession'

const props = withDefaults(defineProps<{
  visible: boolean
  mode?: 'files' | 'folder'
  /** 仅允许这些扩展名的文件（不含点，如 ['poni']）；空 = 不过滤。 */
  extensions?: string[]
}>(), {
  visible: false,
  mode: 'files',
  extensions: () => []
})

const emit = defineEmits<{
  close: []
  /** files 模式：本地文件绝对路径列表；folder 模式：目录路径。 */
  picked: [payload: { files: string[]; folder: string | null }]
}>()

const { t } = useI18n()
const session = useRemoteSftpSession()
const transport = useTransport()
const settingsState = useSettings()

const hasProfile = computed(() => {
  const primary = primaryServer()
  return Boolean(primary?.host && primary?.username)
})
const connecting = ref(false)
const connectError = ref('')
const loading = ref(false)
const currentPath = ref('/')
const manualPath = ref('/')
const entries = ref<RemoteEntry[]>([])
const selected = ref<string[]>([])
const downloading = ref(false)
const progress = ref(0)
const progressMessage = ref('')

const canConfirm = computed(() =>
  props.mode === 'files' ? selected.value.length > 0 : selected.value.length === 1
)

// ── 缓存池页签（无损压缩暂存；免下载直接选用）───────────────────────────
const tab = ref<'remote' | 'cache'>('remote')
const cacheEntries = ref<CachePoolEntry[]>([])
const cacheLoading = ref(false)
const cacheSelected = ref<string[]>([])
const cacheTtlMinutes = computed(() => settingsState.remoteSync?.cache?.ttlMinutes ?? 1440)
const cacheDir = computed(() => settingsState.remoteSync?.cache?.dir ?? '')
const cacheCompress = computed(() => settingsState.remoteSync?.cache?.compress !== false)

function switchTab(next: 'remote' | 'cache'): void {
  tab.value = next
  if (next === 'cache') void loadCachePool()
}

async function loadCachePool(): Promise<void> {
  cacheLoading.value = true
  try {
    const result = await submitRemoteDataTask(transport, {
      action: 'cache_pool_list',
      cacheDir: cacheDir.value,
      cacheTtlMinutes: cacheTtlMinutes.value
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

function isCacheFiltered(entry: CachePoolEntry): boolean {
  if (props.extensions.length === 0) return false
  const lower = entry.name.toLowerCase()
  return !props.extensions.some(ext => lower.endsWith(`.${ext.toLowerCase()}`))
}

function toggleCache(entry: CachePoolEntry): void {
  if (boxJustApplied) return // 长按框选刚结束，吞掉随行的 click/change
  const idx = cacheSelected.value.indexOf(entry.path)
  if (idx >= 0) cacheSelected.value.splice(idx, 1)
  else cacheSelected.value.push(entry.path)
}

function cacheDate(mtime: number): string {
  const d = new Date(mtime * 1000)
  return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function confirmCache(): void {
  if (cacheSelected.value.length === 0) return
  emit('picked', { files: [...cacheSelected.value], folder: null })
  emit('close')
}

/** 扩展名过滤（客户端显示层）：被过滤的文件置灰且不可勾选。 */
function isFiltered(entry: RemoteEntry): boolean {
  if (entry.isDir || props.extensions.length === 0) return false
  const lower = entry.name.toLowerCase()
  return !props.extensions.some(ext => lower.endsWith(`.${ext.toLowerCase()}`))
}

watch(
  () => props.visible,
  async open => {
    if (!open) {
      selected.value = []
      connectError.value = ''
      cacheSelected.value = []
      return
    }
    if (tab.value === 'cache') {
      void loadCachePool()
      return
    }
    if (session.connected() || !hasProfile.value) return
    connecting.value = true
    try {
      await ensureConnected()
    } finally {
      connecting.value = false
    }
  }
)

async function ensureConnected(): Promise<void> {
  connectError.value = ''
  const err = await session.connect()
  if (err) {
    const mismatch = err.includes('不匹配') || err.toLowerCase().includes('mismatch')
    connectError.value = mismatch ? t('remoteData.fingerprintChanged') : err
    return
  }
  currentPath.value = primaryServer()?.remoteDir || '/'
  manualPath.value = currentPath.value
  await openDir(currentPath.value)
}

async function openDir(path: string): Promise<void> {
  if (!session.connected()) return
  loading.value = true
  try {
    const result = await session.list(path)
    if (!result.ok) {
      connectError.value = result.message ?? 'list failed'
      return
    }
    connectError.value = ''
    currentPath.value = result.path ?? path
    manualPath.value = currentPath.value
    entries.value = result.entries
  } finally {
    loading.value = false
  }
}

function goUp(): void {
  if (currentPath.value === '/') return
  void openDir(currentPath.value.replace(/\/[^/]+$/, '') || '/')
}

function entryPath(entry: RemoteEntry): string {
  const base = currentPath.value === '/' ? '' : currentPath.value
  return `${base}/${entry.name}`
}

function isSelected(entry: RemoteEntry): boolean {
  return selected.value.includes(entryPath(entry))
}

function toggle(entry: RemoteEntry): void {
  if (boxJustApplied) return // 长按框选刚结束，吞掉随行的 click/change
  const path = entryPath(entry)
  if (props.mode === 'folder') {
    // 目录单选 / folder mode: single selection, directories only
    selected.value = entry.isDir ? [path] : []
    return
  }
  const idx = selected.value.indexOf(path)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push(path)
  }
}

// ── 长按框选 / long-press box selection ──────────────────────────────────────
// 按住 400ms 进入框选：拖矩形，松手时与矩形相交且可勾选的行被批量
// 勾选/取消——起始行为已勾选时为「去除」模式（第二次包含 = 去除）。
// Press-and-hold 400ms enters box selection; rows intersecting the rect on
// release are bulk-toggled. When the row under the press start was already
// selected the operation is removal (second containment = deselect).

const remoteListEl = ref<HTMLElement | null>(null)
const cacheListEl = ref<HTMLElement | null>(null)
const boxSel = ref<null | {
  x0: number
  y0: number
  x1: number
  y1: number
  kind: 'remote' | 'cache'
  mode: 'add' | 'remove'
}>(null)
let longPressTimer: number | null = null
let longPressStart: { x: number; y: number; kind: 'remote' | 'cache' } | null = null
let boxJustApplied = false

const boxRectStyle = computed(() => {
  const b = boxSel.value
  if (!b) return {}
  return {
    left: Math.min(b.x0, b.x1) + 'px',
    top: Math.min(b.y0, b.y1) + 'px',
    width: Math.abs(b.x1 - b.x0) + 'px',
    height: Math.abs(b.y1 - b.y0) + 'px',
  }
})

function rowStateAt(kind: 'remote' | 'cache', x: number, y: number): { key: string; checked: boolean } | null {
  const el = document.elementFromPoint(x, y)
  const row = el?.closest('.rfp-entry') as HTMLElement | null
  if (!row) return null
  const key = row.getAttribute('data-key')
  if (!key) return null
  const cb = row.querySelector('input[type="checkbox"]') as HTMLInputElement | null
  return { key, checked: cb?.checked ?? false }
}

function onListPointerDown(e: PointerEvent, kind: 'remote' | 'cache'): void {
  if (e.button !== 0) return
  if ((e.target as HTMLElement).tagName === 'INPUT') return // checkbox 自己的点击
  const startX = e.clientX
  const startY = e.clientY
  longPressStart = { x: startX, y: startY, kind }
  longPressTimer = window.setTimeout(() => {
    longPressTimer = null
    if (!longPressStart) return
    const hit = rowStateAt(kind, startX, startY)
    longPressStart = null
    if (!hit) return
    // 起始行已勾选 → 本次框选为「去除」/ already-selected start = removal
    boxSel.value = {
      x0: startX,
      y0: startY,
      x1: startX,
      y1: startY,
      kind,
      mode: hit.checked ? 'remove' : 'add',
    }
    boxJustApplied = true
  }, 400)
}

function onWindowPointerMove(e: PointerEvent): void {
  if (boxSel.value) {
    boxSel.value = { ...boxSel.value, x1: e.clientX, y1: e.clientY }
    return
  }
  if (longPressStart && longPressTimer !== null) {
    const dx = e.clientX - longPressStart.x
    const dy = e.clientY - longPressStart.y
    if (dx * dx + dy * dy > 36) {
      // 移动超阈值 → 是滚动/拖拽，不是长按，取消待定计时器
      window.clearTimeout(longPressTimer)
      longPressTimer = null
      longPressStart = null
    }
  }
}

function onWindowPointerUp(): void {
  if (longPressTimer !== null) {
    window.clearTimeout(longPressTimer)
    longPressTimer = null
  }
  longPressStart = null
  if (boxSel.value) {
    finalizeBoxSelect(boxSel.value)
    boxSel.value = null
    window.setTimeout(() => {
      boxJustApplied = false
    }, 60)
  }
}

function finalizeBoxSelect(sel: NonNullable<typeof boxSel.value>): void {
  const el = sel.kind === 'remote' ? remoteListEl.value : cacheListEl.value
  if (!el) return
  const lx = Math.min(sel.x0, sel.x1)
  const rx = Math.max(sel.x0, sel.x1)
  const ly = Math.min(sel.y0, sel.y1)
  const ry = Math.max(sel.y0, sel.y1)
  const keys: string[] = []
  for (const row of Array.from(el.querySelectorAll<HTMLElement>('.rfp-entry'))) {
    if (!row.querySelector('input[type="checkbox"]')) continue // 过滤行/无勾选行
    const r = row.getBoundingClientRect()
    const ix = Math.max(0, Math.min(rx, r.right) - Math.max(lx, r.left))
    const iy = Math.max(0, Math.min(ry, r.bottom) - Math.max(ly, r.top))
    const key = row.getAttribute('data-key')
    if (ix > 0 && iy > 0 && key) keys.push(key)
  }
  const target = sel.kind === 'remote' ? selected : cacheSelected
  for (const k of keys) {
    const idx = target.value.indexOf(k)
    if (sel.mode === 'add' && idx < 0) target.value.push(k)
    if (sel.mode === 'remove' && idx >= 0) target.value.splice(idx, 1)
  }
}

function onRowNameClick(entry: RemoteEntry): void {
  if (boxJustApplied) return // 框选刚结束，吞掉随行的 click（防误开目录）
  if (entry.isDir) void openDir(entryPath(entry))
}

function selectAllRemote(): void {
  for (const entry of entries.value) {
    if (entry.isDir && props.mode !== 'files') continue
    if (isFiltered(entry)) continue
    const path = entryPath(entry)
    if (!selected.value.includes(path)) selected.value.push(path)
  }
}

function selectAllCache(): void {
  for (const entry of cacheEntries.value) {
    if (isCacheFiltered(entry)) continue
    if (!cacheSelected.value.includes(entry.path)) cacheSelected.value.push(entry.path)
  }
}

onMounted(() => {
  window.addEventListener('pointermove', onWindowPointerMove)
  window.addEventListener('pointerup', onWindowPointerUp)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onWindowPointerMove)
  window.removeEventListener('pointerup', onWindowPointerUp)
  if (longPressTimer !== null) window.clearTimeout(longPressTimer)
})

function humanSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

async function confirm(): Promise<void> {
  if (!canConfirm.value || downloading.value) return
  downloading.value = true
  progress.value = 0
  progressMessage.value = ''
  try {
    const outcome = await session.download(selected.value, currentPath.value, {
      useTemp: true,
      // 无损压缩缓存池（v0.5.0）：下载入池 + 就地压缩 + TTL 惰性回收；
      // 池内命中直接取用（设置 → 远程数据同步 → 缓存池可关）。
      cachePool: true,
      cacheDir: cacheDir.value,
      cacheCompress: cacheCompress.value,
      cacheTtlMinutes: cacheTtlMinutes.value,
      serverKey: primaryServer()?.id ?? '',
      onProgress: (p, m) => {
        progress.value = p
        progressMessage.value = m
      }
    })
    if (outcome.status === 'error') {
      connectError.value = outcome.message ?? 'download failed'
      return
    }
    if (props.mode === 'folder') {
      emit('picked', { files: [], folder: outcome.outputDir })
    } else {
      emit('picked', { files: outcome.downloaded, folder: null })
    }
    emit('close')
  } finally {
    downloading.value = false
  }
}
</script>

<style scoped>
.rfp-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.rfp-dialog {
  width: min(680px, 92vw);
  max-height: 84vh;
  display: flex;
  flex-direction: column;
  background: var(--color-surface, #fff);
  border-radius: 10px;
  padding: 16px;
}

.rfp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.rfp-header h3 {
  margin: 0;
  font-size: 16px;
}

.rfp-close {
  border: none;
  background: transparent;
  font-size: 20px;
  cursor: pointer;
}

.rfp-notice {
  font-size: 12.5px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(234, 179, 8, 0.12);
  margin: 0 0 10px;
}

.rfp-empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  opacity: 0.85;
}

.rfp-link {
  display: inline-block;
  margin-top: 8px;
  color: var(--color-primary, #1e40af);
}

.rfp-crumb {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.rfp-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  font-size: 13px;
}

.rfp-list {
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  min-height: 180px;
  max-height: 340px;
  overflow: auto;
  flex: 1;
}

.rfp-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  font-size: 13px;
}

.rfp-entry:hover {
  background: rgba(30, 64, 175, 0.06);
}

.rfp-filtered {
  opacity: 0.45;
}

.rfp-entry.rfp-filtered .rfp-name {
  cursor: default;
}

.rfp-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.rfp-tab {
  flex: 1;
  padding: 6px 0;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 13px;
  cursor: pointer;
}

.rfp-tab--active {
  border-color: var(--color-primary, #1e40af);
  color: var(--color-primary, #1e40af);
  font-weight: 600;
}

.rfp-cache-hint {
  font-size: 12px;
  opacity: 0.7;
  margin: 6px 0 0;
}

.rfp-name--plain {
  cursor: default;
}

/* 长按框选：批量勾选矩形 + 拖拽期间禁用文本选择 */
.rfp-box-rect {
  position: fixed;
  border: 1px solid var(--color-primary, #1e40af);
  background: rgba(30, 64, 175, 0.12);
  pointer-events: none;
  z-index: 1100;
}

.rfp-boxing,
.rfp-boxing * {
  user-select: none;
}

/* 全选/清空小按钮 */
.rfp-mini-actions {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.rfp-mini-btn {
  padding: 2px 8px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 4px;
  background: var(--color-surface, #fff);
  font-size: 12px;
  cursor: pointer;
}

.rfp-mini-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.rfp-radio-spacer {
  width: 13px;
}

.rfp-name {
  flex: 1;
  text-align: left;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px 0;
  font-size: 13px;
  color: inherit;
}

.rfp-dir .rfp-name {
  font-weight: 600;
}

.rfp-size {
  opacity: 0.6;
  font-size: 12px;
  white-space: nowrap;
}

.rfp-status {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12.5px;
  margin: 8px 0;
  flex-wrap: wrap;
}

.rfp-progress {
  opacity: 0.75;
}

.rfp-error {
  color: #b91c1c;
  font-size: 13px;
}

.rfp-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.rfp-btn {
  padding: 6px 14px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 13px;
  cursor: pointer;
}

.rfp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.rfp-btn-primary {
  background: var(--color-primary, #1e40af);
  border-color: var(--color-primary, #1e40af);
  color: #fff;
}

.rfp-connecting {
  padding: 20px;
  text-align: center;
  font-size: 13px;
}
</style>
