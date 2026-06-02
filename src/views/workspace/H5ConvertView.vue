<template>
  <section class="h5convert-page" :data-testid="testIds.h5convertPage">
    <h1>{{ t('h5convert.title') }}</h1>
    <p class="page-subtitle">{{ t('h5convert.subtitle') }}</p>

    <!-- Step 1: Directory selection / 步骤一：目录选择 -->
    <fieldset class="h5c-fieldset">
      <legend>{{ t('h5convert.step1') }}</legend>
      <FileDialogButton
        v-model="sourceDir"
        mode="openFolder"
        :label="t('h5convert.sourceDir')"
        :data-testid="testIds.h5convertSourceDir"
      />
      <FileDialogButton
        v-model="outputDir"
        mode="openFolder"
        :label="t('h5convert.outputDir')"
        :data-testid="testIds.h5convertOutputDir"
      />
      <label class="h5c-checkbox-label">
        <input v-model="recursive" type="checkbox" />
        {{ t('h5convert.recursive') }}
      </label>
    </fieldset>

    <!-- Step 2: Scan & reference suffix / 步骤二：扫描与参考后缀 -->
    <fieldset class="h5c-fieldset">
      <legend>{{ t('h5convert.step2') }}</legend>
      <div class="h5c-row">
        <label class="h5c-label" for="h5c-suffix">{{ t('h5convert.refSuffix') }}</label>
        <input
          id="h5c-suffix"
          v-model="refSuffix"
          class="h5c-input"
          type="text"
          placeholder="_master"
          :data-testid="testIds.h5convertSuffix"
        />
      </div>
      <button
        type="button"
        class="h5c-btn"
        :disabled="!sourceDir || scanning"
        :data-testid="testIds.h5convertScanBtn"
        @click="handleScan"
      >
        {{ scanning ? t('h5convert.scanning') : t('h5convert.scanBtn') }}
      </button>
      <p v-if="scanInfo" class="h5c-info" :data-testid="testIds.h5convertScanInfo">{{ scanInfo }}</p>
    </fieldset>

    <!-- File list preview / 文件列表预览 -->
    <fieldset v-if="scannedFiles.length > 0" class="h5c-fieldset">
      <legend>{{ t('h5convert.fileList.title') }}</legend>
      <span class="h5c-info">
        {{ t('h5convert.fileList.totalFiles', { total: scannedFiles.length }) }}
      </span>
      <details class="h5c-file-list-details" open>
        <summary class="h5c-file-list-summary">
          {{ t('h5convert.fileList.collapse') }}
        </summary>
        <div class="h5c-file-list-scroll">
          <table class="h5c-file-table">
            <thead>
              <tr>
                <th class="col-idx">{{ t('h5convert.fileList.colIndex') }}</th>
                <th class="col-name">{{ t('h5convert.fileList.colFileName') }}</th>
                <th class="col-path">{{ t('h5convert.fileList.colPath') }}</th>
                <th class="col-size">{{ t('h5convert.fileList.colSize') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(file, idx) in pagedFiles" :key="file.path">
                <td class="col-idx">{{ (fileListPage - 1) * FILE_PAGE_SIZE + idx + 1 }}</td>
                <td class="col-name" :title="file.name">{{ file.name }}</td>
                <td class="col-path" :title="file.path">{{ file.parentDir }}</td>
                <td class="col-size">{{ formatSize(file.size) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="fileTotalPages > 1" class="h5c-pagination">
          <button
            type="button"
            class="h5c-btn-sm"
            :disabled="fileListPage <= 1"
            @click="fileListPage--"
          >{{ t('h5convert.fileList.prevPage') }}</button>
          <span class="h5c-pagination-info">
            {{ t('h5convert.fileList.pageOf', { current: fileListPage, total: fileTotalPages }) }}
          </span>
          <button
            type="button"
            class="h5c-btn-sm"
            :disabled="fileListPage >= fileTotalPages"
            @click="fileListPage++"
          >{{ t('h5convert.fileList.nextPage') }}</button>
        </div>
      </details>
    </fieldset>

    <!-- Step 3: Dataset selection / 步骤三：数据集选择 -->
    <fieldset v-if="datasets.length > 0" class="h5c-fieldset">
      <legend>{{ t('h5convert.step3') }}</legend>
      <div class="h5c-ds-actions">
        <button type="button" class="h5c-btn-sm" @click="selectAll">{{ t('h5convert.selectAll') }}</button>
        <button type="button" class="h5c-btn-sm" @click="deselectAll">{{ t('h5convert.deselectAll') }}</button>
      </div>
      <div class="h5c-ds-tree">
        <div
          v-for="group in datasetGroups"
          :key="group.key"
          class="h5c-ds-group"
        >
          <details class="h5c-ds-details">
            <summary class="h5c-ds-folder">
              <span class="h5c-ds-folder-icon">📁</span>
              <span class="h5c-ds-folder-path">{{ group.key || '/' }}</span>
              <span class="h5c-ds-folder-count">{{ group.items.length }}</span>
            </summary>
            <div v-for="ds in group.items" :key="ds.path" class="h5c-ds-item">
              <label class="h5c-ds-item-label">
                <input
                  type="checkbox"
                  :checked="ds.export"
                  @change="toggleDataset(ds.path)"
                />
                <span class="h5c-ds-item-name">{{ ds.path.split('/').pop() }}</span>
                <span class="h5c-ds-item-badge" :class="ds.ndim >= 2 ? 'h5c-badge-image' : 'h5c-badge-table'">
                  {{ ds.ndim >= 2 ? t('h5convert.kindImage') : t('h5convert.kindTable') }}
                </span>
                <span class="h5c-ds-item-shape">{{ ds.shape }}</span>
              </label>
              <div v-if="ds.ndim === 4 && ds.export" class="h5c-channels">
                <label v-for="ch in ds.totalChannels" :key="ch" class="h5c-ch-label">
                  <input
                    type="checkbox"
                    :checked="ds.selectedChannels.includes(ch)"
                    @change="toggleChannel(ds.path, ch)"
                  />
                  CH{{ ch }}
                </label>
              </div>
            </div>
          </details>
        </div>
      </div>
    </fieldset>

    <!-- Step 4: Export settings / 步骤四：导出设置 -->
    <fieldset v-if="datasets.length > 0" class="h5c-fieldset">
      <legend>{{ t('h5convert.step4') }}</legend>
      <div v-if="hasImageDatasets" class="h5c-format-row">
        <span class="h5c-format-label">{{ t('h5convert.imageFormat') }}</span>
        <select v-model="imageFormat" class="h5c-select">
          <option value="tiff">TIFF</option>
          <option value="edf">EDF</option>
        </select>
      </div>
      <div v-if="hasNonImageDatasets" class="h5c-format-row">
        <span class="h5c-format-label">{{ t('h5convert.tableFormat') }}</span>
        <select v-model="tableFormat" class="h5c-select">
          <option value="csv">CSV</option>
          <option value="dat">DAT</option>
        </select>
      </div>
      <button
        type="button"
        class="h5c-btn h5c-btn-primary"
        :disabled="!canStart"
        :data-testid="testIds.h5convertStartBtn"
        @click="handleStart"
      >
        {{ t('h5convert.startExport') }}
      </button>
    </fieldset>

    <!-- Progress / 进度条 -->
    <TaskProgressBar
      v-if="taskId"
      :task-id="taskId"
      :progress="progress"
      :message="progressMessage"
      @cancel="handleCancel"
    />

    <!-- Result summary / 结果摘要 -->
    <ResultSummary
      v-if="resultSummary"
      :summary="resultSummary"
    />
  </section>
</template>

<script setup lang="ts">
/**
 * H5ConvertView.vue — H5 → TIFF/CSV/DAT 批量转换页面
 * H5 batch conversion page: scan directory → select datasets/channels → convert
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ResultSummary from '@/components/business/ResultSummary.vue'
import type { ResultSummaryData } from '@/components/business/ResultSummary.vue'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'

interface DatasetEntry {
  path: string
  shape: string
  dtype: string
  kind: string
  ndim: number
  totalChannels: number
  selectedChannels: number[]
  export: boolean
}

interface ScannedFile {
  path: string
  name: string
  size: number
  parentDir: string
}

const FILE_PAGE_SIZE = 20

const { t } = useI18n()
const transport = useTransport()

// Directory state / 目录状态
const sourceDir = ref<string | null>(null)
const outputDir = ref<string | null>(null)
const refSuffix = ref('_master')
const recursive = ref(true)

// Scan state / 扫描状态
const scanning = ref(false)
const scanInfo = ref<string | null>(null)

// File list state / 文件列表状态
const scannedFiles = ref<ScannedFile[]>([])
const fileListPage = ref(1)

const fileTotalPages = computed(() => Math.max(1, Math.ceil(scannedFiles.value.length / FILE_PAGE_SIZE)))
const pagedFiles = computed(() => {
  const start = (fileListPage.value - 1) * FILE_PAGE_SIZE
  return scannedFiles.value.slice(start, start + FILE_PAGE_SIZE)
})

// Dataset state / 数据集状态
const datasets = ref<DatasetEntry[]>([])

// Export state / 导出状态
const imageFormat = ref<'tiff' | 'edf'>('tiff')
const tableFormat = ref<'csv' | 'dat'>('csv')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const resultSummary = ref<ResultSummaryData | null>(null)

const hasImageDatasets = computed(() =>
  datasets.value.some(ds => ds.export && ds.ndim >= 2)
)
const hasNonImageDatasets = computed(() =>
  datasets.value.some(ds => ds.export && ds.ndim < 2)
)

/** Group datasets by HDF5 path prefix (all but last segment) / 按 HDF5 路径前缀分组 */
const datasetGroups = computed(() => {
  const groups = new Map<string, DatasetEntry[]>()
  for (const ds of datasets.value) {
    const parts = ds.path.split('/')
    const groupKey = parts.length > 1 ? parts.slice(0, -1).join('/') : '/'
    if (!groups.has(groupKey)) groups.set(groupKey, [])
    groups.get(groupKey)!.push(ds)
  }
  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, items]) => ({ key, items }))
})

// Cleanup listeners on unmount / 卸载时清理监听器
let cleanupFns: Array<() => void> = []
onUnmounted(() => {
  cleanupFns.forEach(fn => fn())
  cleanupFns = []
})

const canStart = computed(() => {
  return (
    sourceDir.value &&
    outputDir.value &&
    datasets.value.some(ds => ds.export) &&
    !taskId.value
  )
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

/** Determine dataset kind label from ndim / 根据 ndim 判断数据集类型 */
function datasetKind(ndim: number): string {
  switch (ndim) {
    case 0: return t('h5convert.kindScalar')
    case 1: return t('h5convert.kind1d')
    case 2: return t('h5convert.kind2d')
    case 3: return t('h5convert.kind3d')
    case 4: return t('h5convert.kind4d')
    default: return `${ndim}D`
  }
}

/** Scan H5 directory for datasets / 扫描 H5 目录中的数据集 */
async function handleScan(): Promise<void> {
  if (!sourceDir.value) return
  scanning.value = true
  scanInfo.value = null
  datasets.value = []
  scannedFiles.value = []
  fileListPage.value = 1

  // Launch file list scan in parallel / 并行启动文件列表扫描
  let fileScanDone = false
  try {
    const fileResult = await transport.submitTask('h5_list_files', {
      sourceDir: sourceDir.value,
      suffix: refSuffix.value ? refSuffix.value : null,
      recursive: recursive.value,
    })
    const unsubFileResult = transport.onTaskResult(fileResult.taskId, (payload) => {
      const data = payload.data as { files: ScannedFile[]; total: number }
      scannedFiles.value = data.files
      fileScanDone = true
    })
    const unsubFileError = transport.onTaskError(fileResult.taskId, () => {
      fileScanDone = true
    })
    cleanupFns.push(unsubFileResult, unsubFileError)
  } catch {
    fileScanDone = true
  }

  try {
    const result = await transport.submitTask('h5convert_scan', {
      sourceDir: sourceDir.value,
      refSuffix: refSuffix.value || '_master',
      recursive: recursive.value,
    })

    const unsubProgress = transport.onTaskProgress(result.taskId, (payload) => {
      scanInfo.value = payload.message ?? null
    })

    const unsubResult = transport.onTaskResult(result.taskId, (payload) => {
      const data = payload.data as {
        datasets: Array<{
          path: string
          shape: string
          dtype: string
          ndim: number
          kind: string
        }>
        totalH5: number
        targetH5: number
        refFile: string
      }

      datasets.value = data.datasets.map(ds => ({
        path: ds.path,
        shape: ds.shape,
        dtype: ds.dtype,
        kind: datasetKind(ds.ndim),
        ndim: ds.ndim,
        totalChannels: ds.ndim === 4 ? parseInt(ds.shape.split(',')[1]?.trim() || '0', 10) : 0,
        selectedChannels: ds.ndim === 4
          ? Array.from({ length: parseInt(ds.shape.split(',')[1]?.trim() || '0', 10) }, (_, i) => i)
          : [],
        export: true,
      }))

      scanInfo.value = t('h5convert.scanResult', {
        total: data.totalH5,
        target: data.targetH5,
        ref: data.refFile,
      })
      scanning.value = false
    })

    const unsubError = transport.onTaskError(result.taskId, () => {
      scanInfo.value = t('h5convert.scanFailed')
      scanning.value = false
    })

    cleanupFns.push(unsubProgress, unsubResult, unsubError)
  } catch {
    scanInfo.value = t('h5convert.scanFailed')
    scanning.value = false
  }
}

watch(sourceDir, (newVal) => {
  if (newVal) {
    handleScan()
  } else {
    datasets.value = []
    scannedFiles.value = []
  }
})

/** Toggle dataset export checkbox / 切换数据集导出勾选 */
function toggleDataset(dsPath: string): void {
  const ds = datasets.value.find(d => d.path === dsPath)
  if (ds) ds.export = !ds.export
}

/** Toggle a single channel in 4D dataset / 切换 4D 数据集的单一通道 */
function toggleChannel(dsPath: string, channel: number): void {
  const ds = datasets.value.find(d => d.path === dsPath)
  if (!ds) return
  const idx = ds.selectedChannels.indexOf(channel)
  if (idx >= 0) {
    ds.selectedChannels.splice(idx, 1)
  } else {
    ds.selectedChannels.push(channel)
  }
}

/** Select all datasets / 全选数据集 */
function selectAll(): void {
  datasets.value.forEach(ds => { ds.export = true })
}

/** Deselect all datasets / 全部取消 */
function deselectAll(): void {
  datasets.value.forEach(ds => { ds.export = false })
}

/** Start batch export / 开始批量导出 */
async function handleStart(): Promise<void> {
  if (!sourceDir.value || !outputDir.value) return

  const selected = datasets.value
    .filter(ds => ds.export)
    .map(ds => ({
      path: ds.path,
      channels: ds.ndim === 4 ? ds.selectedChannels : undefined,
    }))

  if (selected.length === 0) return

  resultSummary.value = null
  progress.value = 0
  progressMessage.value = null

  const result = await transport.submitTask('h5convert', {
    sourceDir: sourceDir.value,
    outputDir: outputDir.value,
    refSuffix: refSuffix.value || '_master',
    imageFormat: imageFormat.value,
    tableFormat: tableFormat.value,
    datasets: selected,
  })

  taskId.value = result.taskId

  const unsubProgress = transport.onTaskProgress(result.taskId, (payload) => {
    progress.value = payload.progress
    progressMessage.value = payload.message ?? null
  })

  const unsubResult = transport.onTaskResult(result.taskId, (payload) => {
    const data = payload.data as {
      total: number
      success: number
      failed: number
      elapsed: number
    }
    resultSummary.value = {
      total: data.total,
      success: data.success,
      failed: data.failed,
      elapsed: data.elapsed,
    }
    taskId.value = null
  })

  const unsubError = transport.onTaskError(result.taskId, (payload) => {
    progressMessage.value = payload.error
    taskId.value = null
  })

  cleanupFns.push(unsubProgress, unsubResult, unsubError)
}

/** Cancel running task / 取消运行中的任务 */
async function handleCancel(): Promise<void> {
  const tid = taskId.value
  taskId.value = null
  progress.value = 0
  if (tid) {
    try { await transport.cancelTask(tid) } catch { /* already finished */ }
  }
}
</script>

<style scoped>
.h5convert-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-subtitle {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
}

.h5c-fieldset {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.h5c-fieldset > legend {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--text-primary);
  padding: 0 8px;
}

.h5c-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.h5c-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

.h5c-input {
  flex: 1;
  max-width: 280px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
}

.h5c-input:focus {
  outline: none;
  border-color: var(--primary-light);
}

.h5c-select {
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.h5c-btn {
  padding: 8px 20px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.h5c-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
}

.h5c-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.h5c-btn-primary {
  background: var(--primary-light);
  color: var(--text-inverse);
  border-color: var(--primary-light);
}

.h5c-btn-primary:hover:not(:disabled) {
  border-color: var(--primary);
}

.h5c-btn-sm {
  padding: 4px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
}

.h5c-btn-sm:hover {
  color: var(--text-primary);
  border-color: var(--border-hover);
}

.h5c-checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.h5c-ds-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.h5c-ds-tree {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 4px 0;
}

.h5c-ds-group {
  border-bottom: 1px solid var(--border);
}

.h5c-ds-group:last-child {
  border-bottom: none;
}

.h5c-ds-details {
  margin: 0;
}

.h5c-ds-folder {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  list-style: none;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}

.h5c-ds-folder:hover {
  background: var(--bg-hover, rgba(0,0,0,0.04));
}

.h5c-ds-folder::before {
  content: '▸';
  font-size: 0.7rem;
  transition: transform 0.15s;
}

.h5c-ds-details[open] .h5c-ds-folder::before {
  content: '▾';
}

.h5c-ds-folder-icon {
  font-size: 0.9rem;
}

.h5c-ds-folder-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  word-break: break-all;
}

.h5c-ds-folder-count {
  font-size: 0.7rem;
  background: var(--bg-tertiary, #e0e0e0);
  padding: 1px 6px;
  border-radius: 10px;
  color: var(--text-secondary);
}

.h5c-ds-item {
  padding: 4px 12px 4px 32px;
  border-bottom: 1px solid var(--border);
}

.h5c-ds-item:last-child {
  border-bottom: none;
}

.h5c-ds-item-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.8rem;
}

.h5c-ds-item-name {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.h5c-ds-item-badge {
  font-size: 0.65rem;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.h5c-badge-image {
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
}

.h5c-badge-table {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.h5c-ds-item-shape {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.h5c-info {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin: 0;
}

.h5c-format-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.h5c-format-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}

.h5c-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.h5c-table th,
.h5c-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}

.h5c-th-check,
.h5c-td-check {
  width: 48px;
  text-align: center;
}

.h5c-td-center {
  text-align: center;
}

.h5c-td-mono {
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.h5c-channels {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
}

.h5c-ch-label {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.75rem;
  cursor: pointer;
}

.h5c-file-list-details {
  margin-top: 8px;
}

.h5c-file-list-summary {
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 4px 0;
  user-select: none;
}

.h5c-file-list-scroll {
  max-height: 420px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-top: 8px;
}

.h5c-file-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.h5c-file-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface);
  font-weight: 600;
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  z-index: 1;
}

.h5c-file-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 0;
}

.h5c-file-table tr:hover td {
  background: var(--bg-hover);
}

.col-idx { width: 48px; text-align: center; }
.col-name { width: 35%; }
.col-path { width: auto; }
.col-size { width: 90px; text-align: right; }

.h5c-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 10px;
}

.h5c-pagination-info {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}
</style>
