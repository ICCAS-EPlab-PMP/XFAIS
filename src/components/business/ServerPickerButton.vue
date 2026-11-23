<template>
  <span class="spb-wrap">
    <button
      class="spb-btn"
      type="button"
      :data-testid="testIds.serverPickerButton"
      :title="t('serverData.buttonTitle')"
      @click="open = true"
    >
      🖥 {{ label ?? t('serverData.button') }}
    </button>

    <div
      v-if="open"
      class="spb-backdrop"
      :data-testid="testIds.serverPickerDialog"
      @click.self="open = false"
    >
      <div class="spb-dialog">
        <header class="spb-header">
          <h3>{{ t('serverData.title') }}</h3>
          <button class="spb-close" type="button" @click="open = false">×</button>
        </header>

        <!-- 未配置开放目录 / no input roots configured -->
        <div v-if="rootsLoaded && !configured" class="spb-empty">
          <p>{{ t('serverData.noRoots') }}</p>
        </div>

        <template v-else>
          <!-- 面包屑：根目录层或目录内 / roots level or inside a folder -->
          <div class="spb-crumb">
            <span class="spb-path" :title="currentPath">
              {{ rootsLevel ? t('serverData.rootsLevel') : currentPath }}
            </span>
            <button
              class="spb-btn"
              type="button"
              :disabled="loading || rootsLevel"
              @click="goUp"
            >
              {{ t('remoteData.goUp') }}
            </button>
            <button
              class="spb-btn"
              type="button"
              :disabled="loading"
              @click="openDir(currentPath)"
            >
              {{ t('remoteData.refresh') }}
            </button>
          </div>

          <div class="spb-list" :data-testid="testIds.serverPickerList">
            <template v-if="rootsLevel">
              <label v-for="root in roots" :key="root.path" class="spb-entry spb-dir">
                <span class="spb-spacer" />
                <button class="spb-name" type="button" @click="openDirRoot(root.path)">
                  📁 {{ root.name }}
                </button>
                <span class="spb-size">—</span>
              </label>
            </template>
            <template v-else>
              <div v-if="loading" class="spb-empty">{{ t('serverData.loading') }}</div>
              <div v-else-if="entries.length === 0" class="spb-empty">
                {{ t('serverData.empty') }}
              </div>
              <label
                v-for="entry in entries"
                :key="currentPath + '/' + entry.name"
                class="spb-entry"
                :class="{
                  'spb-dir': entry.kind === 'dir',
                  'spb-filtered': isFiltered(entry)
                }"
              >
                <input
                  v-if="mode === 'files' && entry.kind === 'file' && !isFiltered(entry)"
                  :checked="isSelected(entry)"
                  type="checkbox"
                  @change="toggle(entry)"
                />
                <span v-else class="spb-spacer" />
                <button
                  class="spb-name"
                  type="button"
                  @click="entry.kind === 'dir' && openDir(entryPath(entry))"
                >
                  {{ entry.kind === 'dir' ? '📁' : '📄' }} {{ entry.name }}
                </button>
                <span class="spb-size">
                  {{ entry.kind === 'dir' ? '—' : humanSize(entry.size ?? 0) }}
                </span>
              </label>
            </template>
          </div>

          <p v-if="error" class="spb-error">{{ error }}</p>

          <div class="spb-status">
            <span v-if="mode === 'files'">
              {{ t('remoteData.picker.selectedFiles', { count: selected.length }) }}
            </span>
            <span v-else>{{ rootsLevel ? t('serverData.rootsLevel') : currentPath }}</span>
            <span v-if="preparing" class="spb-progress">
              {{ Math.round(progress * 100) }}% {{ progressMessage }}
            </span>
          </div>

          <footer class="spb-footer">
            <label
              v-if="mode === 'files'"
              class="spb-check"
              :data-testid="testIds.serverPickerCompress"
              :title="t('serverData.downloadHint')"
            >
              <input v-model="compressDownload" type="checkbox" :disabled="preparing" />
              {{ t('serverData.compressToggle') }}
            </label>
            <span class="spb-footer-actions">
              <button
                class="spb-btn"
                type="button"
                :disabled="preparing"
                @click="open = false"
              >
                {{ t('remoteData.picker.cancel') }}
              </button>
              <button
                v-if="mode === 'files'"
                class="spb-btn"
                type="button"
                :disabled="!canDownload || preparing"
                :data-testid="testIds.serverPickerDownload"
                @click="downloadSelected"
              >
                {{ preparing ? t('serverData.preparing') : t('serverData.download') }}
              </button>
              <button
                class="spb-btn spb-btn-primary"
                type="button"
                :disabled="!canConfirm || preparing"
                :data-testid="testIds.serverPickerConfirm"
                @click="confirmSelection"
              >
                {{ mode === 'folder' ? t('serverData.useFolder') : t('serverData.useSelected') }}
              </button>
            </span>
          </footer>
          <p v-if="downloadNote" class="spb-note">{{ downloadNote }}</p>
        </template>
      </div>
    </div>
  </span>
</template>

<script setup lang="ts">
/**
 * ServerPickerButton.vue — 「服务器数据…」一行式接入按钮（仅 web 模式渲染）
 *
 * 浏览管理员开放目录（XFAIS_INPUT_ROOTS，经 /api/server_fs 只读动作）：
 * mode='files' 多选文件 → emit picked(服务器绝对路径列表)，交回调用方视图
 * 的既有处理流程（后端读取围栏放行白名单树内路径）；另提供「下载所选」
 * ——可选无损压缩——经会话工作区暂存后由浏览器下载（/api/download）。
 * mode='folder' 单选目录 → emit pickedFolder(服务器目录绝对路径)。
 * 桌面模式不渲染本组件（本地对话框）。
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'
import { testIds } from '@/lib/testIds'
import {
  listServerRoots,
  listServerDir,
  prepareServerDownload,
  type ServerFsEntry,
  type ServerFsRoot,
} from '@/lib/serverFs'

const props = withDefaults(
  defineProps<{
    mode?: 'files' | 'folder'
    /** 仅允许这些扩展名的文件（不含点，如 ['poni']）；空 = 不过滤。 */
    extensions?: string[]
    label?: string
  }>(),
  {
    mode: 'files',
    extensions: () => [],
    label: undefined
  }
)

const emit = defineEmits<{
  /** files 模式：服务器文件绝对路径列表。 */
  picked: [paths: string[]]
  /** folder 模式：服务器目录绝对路径。 */
  pickedFolder: [dir: string]
}>()

const { t } = useI18n()
const transport = useTransport()
const open = ref(false)

const rootsLoaded = ref(false)
const configured = ref(false)
const roots = ref<ServerFsRoot[]>([])
/** true = 顶层显示开放目录清单；false = 已进入某个根目录内部。 */
const rootsLevel = ref(true)
const currentPath = ref('')
const entries = ref<ServerFsEntry[]>([])
const loading = ref(false)
const error = ref('')
const selected = ref<string[]>([])
const compressDownload = ref(true)
const preparing = ref(false)
const progress = ref(0)
const progressMessage = ref('')
const downloadNote = ref('')

const canConfirm = computed(() =>
  props.mode === 'folder'
    ? !rootsLevel.value && Boolean(currentPath.value)
    : selected.value.length > 0
)
const canDownload = computed(() => selected.value.length > 0)

watch(open, async opened => {
  if (!opened) {
    error.value = ''
    downloadNote.value = ''
    return
  }
  // 每次打开都重新拉取根目录（管理员可能改过 XFAIS_INPUT_ROOTS），
  // 并回到根清单层——多根部署时全部根都可进入。
  rootsLoaded.value = false
  configured.value = false
  roots.value = []
  rootsLevel.value = true
  currentPath.value = ''
  entries.value = []
  selected.value = []
  error.value = ''
  downloadNote.value = ''
  const result = await listServerRoots(transport)
  rootsLoaded.value = true
  configured.value = result.configured
  roots.value = result.roots
  if (!result.configured && result.message) {
    error.value = result.message
  }
})

function isRoot(path: string): boolean {
  return roots.value.some(r => r.path === path)
}

function insideWhichRoot(path: string): string | null {
  for (const r of roots.value) {
    const base = r.path.replace(/[\\/]+$/, '')
    if (path === base || path.startsWith(base + '/') || path.startsWith(base + '\\')) {
      return r.path
    }
  }
  return null
}

async function openDirRoot(path: string): Promise<void> {
  rootsLevel.value = false
  await openDir(path)
}

async function openDir(path: string): Promise<void> {
  if (!path) return
  loading.value = true
  error.value = ''
  try {
    const result = await listServerDir(transport, path)
    if (!result.ok) {
      error.value = result.message ?? 'list failed'
      return
    }
    currentPath.value = result.path ?? path
    entries.value = result.entries
    selected.value = []
  } finally {
    loading.value = false
  }
}

function goUp(): void {
  if (rootsLevel.value) return
  if (isRoot(currentPath.value)) {
    rootsLevel.value = true
    return
  }
  const parent = currentPath.value.replace(/[\\/][^\\/]+$/, '')
  const parentInside = parent && insideWhichRoot(parent) ? parent : ''
  if (parentInside) {
    void openDir(parentInside)
  } else {
    rootsLevel.value = true
  }
}

function entryPath(entry: ServerFsEntry): string {
  const base = currentPath.value
  const sep = base.endsWith('/') || base.endsWith('\\') ? '' : '/'
  return `${base}${sep}${entry.name}`
}

function matchesExtensions(entry: ServerFsEntry): boolean {
  if (props.extensions.length === 0) return true
  const lower = entry.name.toLowerCase()
  return props.extensions.some(ext => lower.endsWith(`.${ext.toLowerCase()}`))
}

function isFiltered(entry: ServerFsEntry): boolean {
  return entry.kind === 'file' && !matchesExtensions(entry)
}

function isSelected(entry: ServerFsEntry): boolean {
  return selected.value.includes(entryPath(entry))
}

function toggle(entry: ServerFsEntry): void {
  const path = entryPath(entry)
  const idx = selected.value.indexOf(path)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push(path)
  }
}

function humanSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function confirmSelection(): void {
  if (!canConfirm.value || preparing.value) return
  if (props.mode === 'folder') {
    emit('pickedFolder', currentPath.value)
  } else {
    emit('picked', [...selected.value])
  }
  open.value = false
}

async function downloadSelected(): Promise<void> {
  if (!canDownload.value || preparing.value) return
  preparing.value = true
  progress.value = 0
  progressMessage.value = ''
  downloadNote.value = ''
  try {
    const outcome = await prepareServerDownload(
      transport,
      [...selected.value],
      compressDownload.value,
      (p, m) => {
        progress.value = p
        progressMessage.value = m
      }
    )
    if (outcome.status !== 'ok') {
      error.value = outcome.message ?? 'download failed'
      return
    }
    for (const item of outcome.files) {
      await transport.downloadFile(item.path, item.filename)
    }
    const report = outcome.report
    downloadNote.value = outcome.compressed
      ? t('serverData.downloadDoneCompressed', {
          count: outcome.files.length,
          skipped: report?.skipped ?? 0,
          ratio: report?.ratio != null ? Number(report.ratio).toFixed(2) : '—'
        })
      : t('serverData.downloadDone', { count: outcome.files.length })
    if ((report?.failed ?? 0) > 0) {
      downloadNote.value += ` (${t('serverData.downloadPartFailed', { failed: report?.failed ?? 0 })})`
    }
  } finally {
    preparing.value = false
  }
}
</script>

<style scoped>
.spb-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 13px;
  cursor: pointer;
}

.spb-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spb-btn-primary {
  background: var(--color-primary, #1e40af);
  border-color: var(--color-primary, #1e40af);
  color: #fff;
}

.spb-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.spb-dialog {
  width: min(680px, 92vw);
  max-height: 84vh;
  display: flex;
  flex-direction: column;
  background: var(--color-surface, #fff);
  border-radius: 10px;
  padding: 16px;
}

.spb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.spb-header h3 {
  margin: 0;
  font-size: 16px;
}

.spb-close {
  border: none;
  background: transparent;
  font-size: 20px;
  cursor: pointer;
}

.spb-empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  opacity: 0.85;
}

.spb-crumb {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  align-items: center;
}

.spb-path {
  flex: 1;
  font-size: 12.5px;
  opacity: 0.8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spb-list {
  border: 1px solid var(--color-border, #d0d7de);
  border-radius: 6px;
  min-height: 180px;
  max-height: 340px;
  overflow: auto;
  flex: 1;
}

.spb-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  font-size: 13px;
}

.spb-entry:hover {
  background: rgba(30, 64, 175, 0.06);
}

.spb-entry.spb-filtered {
  opacity: 0.45;
}

.spb-spacer {
  width: 13px;
}

.spb-name {
  flex: 1;
  text-align: left;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px 0;
  font-size: 13px;
  color: inherit;
}

.spb-dir .spb-name {
  font-weight: 600;
}

.spb-entry.spb-filtered .spb-name {
  cursor: default;
}

.spb-size {
  opacity: 0.6;
  font-size: 12px;
  white-space: nowrap;
}

.spb-error {
  color: #b91c1c;
  font-size: 12.5px;
  margin: 6px 0 0;
}

.spb-status {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12.5px;
  margin: 8px 0;
  flex-wrap: wrap;
}

.spb-progress {
  opacity: 0.75;
}

.spb-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.spb-footer-actions {
  display: flex;
  gap: 8px;
}

.spb-check {
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.spb-note {
  font-size: 12px;
  opacity: 0.75;
  margin: 6px 0 0;
}
</style>
