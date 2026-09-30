<template>
  <section class="h5toolkit-page" :data-testid="testIds.h5convertPage">
    <h1>{{ t('h5toolkit.title') }}</h1>
    <p class="page-subtitle">{{ t('h5toolkit.subtitle') }}</p>

    <!-- Shared: source directory selection / 共享：源目录选择 -->
    <fieldset class="h5t-fieldset">
      <legend>{{ t('h5toolkit.sourceSection') }}</legend>
      <FileDialogButton
        v-model="sourceDir"
        mode="openFolder"
        :label="t('h5toolkit.sourceDir')"
        :data-testid="testIds.h5convertSourceDir"
      />
      <label class="h5t-checkbox-label">
        <input v-model="recursive" type="checkbox" />
        {{ t('h5toolkit.recursive') }}
      </label>
    </fieldset>

    <!-- Tab switcher / Tab 切换 -->
    <div class="h5t-tabs" role="tablist">
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'convert'"
        :class="['h5t-tab', { 'h5t-tab-active': activeTab === 'convert' }]"
        @click="activeTab = 'convert'"
      >{{ t('h5toolkit.tabConvert') }}</button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'extract'"
        :class="['h5t-tab', { 'h5t-tab-active': activeTab === 'extract' }]"
        @click="activeTab = 'extract'"
      >{{ t('h5toolkit.tabExtract') }}</button>
    </div>

    <!-- ════════ Tab 1: Format conversion / 格式转换 ════════ -->
    <div v-if="activeTab === 'convert'" class="h5t-tab-panel">
      <!-- Output directory / 输出目录 -->
      <fieldset class="h5t-fieldset">
        <legend>{{ t('h5toolkit.convert.step2') }}</legend>
        <FileDialogButton
          v-model="outputDir"
          mode="openFolder"
          :label="t('h5toolkit.convert.outputDir')"
          :data-testid="testIds.h5convertOutputDir"
        />
        <div class="h5t-row">
          <label class="h5t-label" for="h5t-suffix">{{ t('h5toolkit.convert.refSuffix') }}</label>
          <input
            id="h5t-suffix"
            v-model="refSuffix"
            class="h5t-input"
            type="text"
            placeholder="_master"
            :data-testid="testIds.h5convertSuffix"
          />
        </div>
        <button
          type="button"
          class="h5t-btn"
          :disabled="!sourceDir || scanning"
          :data-testid="testIds.h5convertScanBtn"
          @click="handleConvertScan"
        >
          {{ scanning ? t('h5toolkit.convert.scanning') : t('h5toolkit.convert.scanBtn') }}
        </button>
        <p v-if="scanInfo" class="h5t-info" :data-testid="testIds.h5convertScanInfo">{{ scanInfo }}</p>
      </fieldset>

      <!-- File list preview / 文件列表预览 -->
      <fieldset v-if="scannedFiles.length > 0" class="h5t-fieldset">
        <legend>{{ t('h5toolkit.convert.fileList.title') }}</legend>
        <span class="h5t-info">
          {{ t('h5toolkit.convert.fileList.totalFiles', { total: scannedFiles.length }) }}
        </span>
        <details class="h5t-file-list-details" open>
          <summary class="h5t-file-list-summary">
            {{ t('h5toolkit.convert.fileList.collapse') }}
          </summary>
          <div class="h5t-file-list-scroll">
            <table class="h5t-file-table">
              <thead>
                <tr>
                  <th class="col-idx">{{ t('h5toolkit.convert.fileList.colIndex') }}</th>
                  <th class="col-name">{{ t('h5toolkit.convert.fileList.colFileName') }}</th>
                  <th class="col-path">{{ t('h5toolkit.convert.fileList.colPath') }}</th>
                  <th class="col-size">{{ t('h5toolkit.convert.fileList.colSize') }}</th>
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
          <div v-if="fileTotalPages > 1" class="h5t-pagination">
            <button
              type="button"
              class="h5t-btn-sm"
              :disabled="fileListPage <= 1"
              @click="fileListPage--"
            >{{ t('h5toolkit.convert.fileList.prevPage') }}</button>
            <span class="h5t-pagination-info">
              {{ t('h5toolkit.convert.fileList.pageOf', { current: fileListPage, total: fileTotalPages }) }}
            </span>
            <button
              type="button"
              class="h5t-btn-sm"
              :disabled="fileListPage >= fileTotalPages"
              @click="fileListPage++"
            >{{ t('h5toolkit.convert.fileList.nextPage') }}</button>
          </div>
        </details>
      </fieldset>

      <!-- Dataset selection / 数据集选择 -->
      <fieldset v-if="datasets.length > 0" class="h5t-fieldset">
        <legend>{{ t('h5toolkit.convert.step3') }}</legend>
        <div class="h5t-ds-actions">
          <button type="button" class="h5t-btn-sm" @click="selectAll">{{ t('h5toolkit.convert.selectAll') }}</button>
          <button type="button" class="h5t-btn-sm" @click="deselectAll">{{ t('h5toolkit.convert.deselectAll') }}</button>
        </div>
        <div class="h5t-ds-tree">
          <div
            v-for="group in datasetGroups"
            :key="group.key"
            class="h5t-ds-group"
          >
            <details class="h5t-ds-details">
              <summary class="h5t-ds-folder">
                <span class="h5t-ds-folder-icon">📁</span>
                <span class="h5t-ds-folder-path">{{ group.key || '/' }}</span>
                <span class="h5t-ds-folder-count">{{ group.items.length }}</span>
              </summary>
              <div v-for="ds in group.items" :key="ds.path" class="h5t-ds-item">
                <label class="h5t-ds-item-label">
                  <input
                    type="checkbox"
                    :checked="ds.export"
                    @change="toggleDataset(ds.path)"
                  />
                  <span class="h5t-ds-item-name">{{ ds.path.split('/').pop() }}</span>
                  <span class="h5t-ds-item-badge" :class="ds.ndim >= 2 ? 'h5t-badge-image' : 'h5t-badge-table'">
                    {{ ds.ndim >= 2 ? t('h5toolkit.convert.kindImage') : t('h5toolkit.convert.kindTable') }}
                  </span>
                  <span class="h5t-ds-item-shape">{{ ds.shape }}</span>
                </label>
                <div v-if="ds.ndim === 4 && ds.export" class="h5t-channels">
                  <label v-for="ch in ds.totalChannels" :key="ch" class="h5t-ch-label">
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

      <!-- Export settings / 导出设置 -->
      <fieldset v-if="datasets.length > 0" class="h5t-fieldset">
        <legend>{{ t('h5toolkit.convert.step4') }}</legend>
        <div v-if="hasImageDatasets" class="h5t-format-row">
          <span class="h5t-format-label">{{ t('h5toolkit.convert.imageFormat') }}</span>
          <select v-model="imageFormat" class="h5t-select">
            <option value="tiff">TIFF</option>
            <option value="edf">EDF</option>
          </select>
        </div>
        <div v-if="hasImageDatasets" class="h5t-format-row">
          <span class="h5t-format-label">{{ t('h5toolkit.convert.namingMode') }}</span>
          <select
            v-model="namingMode"
            class="h5t-select"
            :data-testid="testIds.h5convertNamingMode"
          >
            <option value="parent_folder">{{ t('h5toolkit.convert.namingByFolder') }}</option>
            <option value="file_name">{{ t('h5toolkit.convert.namingByFile') }}</option>
            <option value="dataset">{{ t('h5toolkit.convert.namingByDataset') }}</option>
          </select>
          <span class="h5t-hint">{{ t('h5toolkit.convert.namingHint') }}</span>
        </div>
        <label v-if="hasImageDatasets" class="h5t-checkbox-label">
          <input
            v-model="flatOutput"
            type="checkbox"
            :data-testid="testIds.h5convertFlatOutput"
          />
          {{ t('h5toolkit.convert.flatOutput') }}
        </label>
        <p v-if="convertEstimateText" class="h5t-info" :data-testid="testIds.h5convertEstimate">
          {{ convertEstimateText }}
        </p>
        <div v-if="hasNonImageDatasets" class="h5t-format-row">
          <span class="h5t-format-label">{{ t('h5toolkit.convert.tableFormat') }}</span>
          <select v-model="tableFormat" class="h5t-select">
            <option value="csv">CSV</option>
            <option value="dat">DAT</option>
          </select>
        </div>
        <button
          type="button"
          class="h5t-btn h5t-btn-primary"
          :disabled="!canStartConvert"
          :data-testid="testIds.h5convertStartBtn"
          @click="handleStartConvert"
        >
          {{ t('h5toolkit.convert.startExport') }}
        </button>
      </fieldset>

      <!-- Progress / 进度条 -->
      <TaskProgressBar
        v-if="convertTaskId"
        :task-id="convertTaskId"
        :progress="convertProgress"
        :message="convertProgressMessage"
        @cancel="handleCancelConvert"
      />

      <!-- Result summary / 结果摘要 -->
      <ResultSummary
        v-if="convertResultSummary"
        :summary="convertResultSummary"
      />
    </div>

    <!-- ════════ Tab 2: File extraction / 文件提取 ════════ -->
    <div v-if="activeTab === 'extract'" class="h5t-tab-panel">
      <!-- File list preview / 文件列表预览 -->
      <fieldset class="h5t-fieldset">
        <legend>{{ t('h5toolkit.extract.fileList.title') }}</legend>
        <div class="h5t-actions">
          <button
            type="button"
            class="h5t-btn"
            :disabled="!sourceDir || extractScanBusy"
            @click="handleScanExtractFiles"
          >
            {{ extractScanBusy ? t('h5toolkit.extract.fileList.scanning') : t('h5toolkit.extract.fileList.scanBtn') }}
          </button>
          <span v-if="extractFiles.length" class="h5t-hint">
            {{ t('h5toolkit.extract.fileList.totalFiles', { total: extractFiles.length }) }}
          </span>
        </div>

        <template v-if="extractFiles.length">
          <details class="h5t-file-list-details" open>
            <summary class="h5t-file-list-summary">
              {{ t('h5toolkit.extract.fileList.collapse') }}
            </summary>
            <div class="h5t-file-list-scroll">
              <table class="h5t-file-table">
                <thead>
                  <tr>
                    <th class="col-idx">{{ t('h5toolkit.extract.fileList.colIndex') }}</th>
                    <th class="col-name">{{ t('h5toolkit.extract.fileList.colFileName') }}</th>
                    <th class="col-path">{{ t('h5toolkit.extract.fileList.colPath') }}</th>
                    <th class="col-size">{{ t('h5toolkit.extract.fileList.colSize') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(file, idx) in pagedExtractFiles" :key="file.path">
                    <td class="col-idx">{{ (extractPage - 1) * EXTRACT_PAGE_SIZE + idx + 1 }}</td>
                    <td class="col-name" :title="file.name">{{ file.name }}</td>
                    <td class="col-path" :title="file.path">{{ file.parentDir }}</td>
                    <td class="col-size">{{ formatSize(file.size) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="extractTotalPages > 1" class="h5t-pagination">
              <button
                type="button"
                class="h5t-btn-sm"
                :disabled="extractPage <= 1"
                @click="extractPage--"
              >{{ t('h5toolkit.extract.fileList.prevPage') }}</button>
              <span class="h5t-pagination-info">
                {{ t('h5toolkit.extract.fileList.pageOf', { current: extractPage, total: extractTotalPages }) }}
              </span>
              <button
                type="button"
                class="h5t-btn-sm"
                :disabled="extractPage >= extractTotalPages"
                @click="extractPage++"
              >{{ t('h5toolkit.extract.fileList.nextPage') }}</button>
            </div>
          </details>
        </template>
        <p v-else-if="extractScanBusy" class="h5t-hint">{{ t('h5toolkit.extract.fileList.scanning') }}</p>
      </fieldset>

      <!-- Extraction rules / 提取规则 -->
      <fieldset class="h5t-fieldset">
        <legend>{{ t('h5toolkit.extract.rulesSection') }}</legend>
        <FileDialogButton
          v-model="extractTargetDir"
          mode="openFolder"
          :label="t('h5toolkit.extract.targetDir')"
          :data-testid="testIds.h5extractTargetDir"
        />
        <div class="h5t-row">
          <label class="h5t-label" for="h5e-suffix">{{ t('h5toolkit.extract.suffixFilter') }}</label>
          <input
            id="h5e-suffix"
            v-model="extractSuffixFilter"
            class="h5t-input"
            type="text"
            :placeholder="t('h5toolkit.extract.suffixPlaceholder')"
            :data-testid="testIds.h5extractSuffix"
          />
          <span class="h5t-hint">{{ t('h5toolkit.extract.suffixHint') }}</span>
        </div>

        <label class="h5t-checkbox-label">
          <input
            v-model="extractPrependFolder"
            type="checkbox"
            :data-testid="testIds.h5extractPrependFolder"
          />
          {{ t('h5toolkit.extract.prependFolder') }}
        </label>

        <!-- Optional prefix / 可选前缀 -->
        <div class="h5t-row">
          <label class="h5t-label" for="h5e-prefix">{{ t('h5toolkit.extract.prefix') }}</label>
          <input
            id="h5e-prefix"
            v-model="extractPrefix"
            class="h5t-input"
            type="text"
            :placeholder="t('h5toolkit.extract.prefixPlaceholder')"
            :data-testid="testIds.h5extractPrefix"
          />
        </div>

        <!-- Conflict resolution / 冲突处理 -->
        <div class="h5t-row">
          <label class="h5t-label">{{ t('h5toolkit.extract.conflictPolicy') }}</label>
          <select
            v-model="extractConflictPolicy"
            class="h5t-select"
            :data-testid="testIds.h5extractConflictPolicy"
          >
            <option value="rename">{{ t('h5toolkit.extract.conflictRename') }}</option>
            <option value="skip">{{ t('h5toolkit.extract.conflictSkip') }}</option>
            <option value="overwrite">{{ t('h5toolkit.extract.conflictOverwrite') }}</option>
          </select>
        </div>
      </fieldset>

      <!-- Start extraction / 开始提取 -->
      <div class="h5t-actions">
        <button
          type="button"
          class="h5t-btn h5t-btn-primary"
          :disabled="!canStartExtract"
          :data-testid="testIds.h5extractStartBtn"
          @click="handleStartExtract"
        >
          {{ t('h5toolkit.extract.startExtract') }}
        </button>
      </div>

      <!-- Progress / 进度条 -->
      <TaskProgressBar
        v-if="extractTaskId"
        :task-id="extractTaskId"
        :progress="extractProgress"
        :message="extractProgressMessage"
        @cancel="handleCancelExtract"
      />

      <!-- Result summary / 结果摘要 -->
      <ResultSummary
        v-if="extractResultSummary"
        :summary="extractResultSummary"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * H5ToolkitView.vue — H5 格式处理（格式转换 + 文件提取）
 * Unified H5 toolkit page: two tabs sharing one source directory.
 *   - Tab "convert": batch convert H5 datasets → TIFF/EDF/CSV/DAT
 *   - Tab "extract": filter/copy/rename H5 files into a flat output dir
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ResultSummary from '@/components/business/ResultSummary.vue'
import type { ResultSummaryData } from '@/components/business/ResultSummary.vue'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'
import { useToast } from '@/lib/toast'

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
const EXTRACT_PAGE_SIZE = 20

const { t } = useI18n()
const transport = useTransport()
const toast = useToast()

// ── Shared state / 共享状态 ─────────────────────────────────────────────
const sourceDir = ref<string | null>(null)
const recursive = ref(true)
const activeTab = ref<'convert' | 'extract'>('convert')

// ── Convert state / 格式转换状态 ────────────────────────────────────────
const outputDir = ref<string | null>(null)
const refSuffix = ref('_master')

const scanning = ref(false)
const scanInfo = ref<string | null>(null)

const scannedFiles = ref<ScannedFile[]>([])
const fileListPage = ref(1)

const fileTotalPages = computed(() => Math.max(1, Math.ceil(scannedFiles.value.length / FILE_PAGE_SIZE)))
const pagedFiles = computed(() => {
  const start = (fileListPage.value - 1) * FILE_PAGE_SIZE
  return scannedFiles.value.slice(start, start + FILE_PAGE_SIZE)
})

const datasets = ref<DatasetEntry[]>([])

const imageFormat = ref<'tiff' | 'edf'>('tiff')
const tableFormat = ref<'csv' | 'dat'>('csv')
/** Image export first-level folder naming / 图像导出第一层文件夹命名 */
const namingMode = ref<'parent_folder' | 'file_name' | 'dataset'>('parent_folder')
/** Flat export: no subfolders, folder names fold into the file name / 扁平导出：不建子文件夹，文件夹名并入文件名 */
const flatOutput = ref(false)
/** Files the converter will process (honest count from scan) / 转换器将处理的文件数 */
const scanTargetH5 = ref(0)
const convertTaskId = ref<string | null>(null)
const convertProgress = ref(0)
const convertProgressMessage = ref<string | null>(null)
const convertResultSummary = ref<ResultSummaryData | null>(null)

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

/** Nexus convention: entry/instrument/** holds detector metadata (pixel
 * masks, flatfield tables) — never the science data; never auto-select it.
 * Nexus 约定：entry/instrument/** 存放探测器元数据（像素掩码、平场表），
 * 不是科学数据；默认绝不勾选。 */
function isInstrumentMetadata(path: string): boolean {
  return path.split('/').includes('instrument')
}

/** Estimated output file count for the current selection / 按当前勾选估算产出文件数 */
const convertEstimateText = computed(() => {
  if (datasets.value.length === 0 || scanTargetH5.value === 0) return ''
  let images = 0
  let hasTable = false
  for (const ds of datasets.value) {
    if (!ds.export) continue
    if (ds.ndim < 2) {
      hasTable = true
      continue
    }
    const dims = ds.shape.replace(/[()\s]/g, '').split(',').map(s => parseInt(s, 10) || 0)
    if (ds.ndim === 2) {
      images += 1
    } else if (ds.ndim === 3) {
      images += dims[0]
    } else if (ds.ndim === 4) {
      images += (dims[0] || 0) * ds.selectedChannels.filter(c => c < (dims[1] || 0)).length
    }
  }
  const base = t('h5toolkit.convert.estimate', { count: images * scanTargetH5.value, files: scanTargetH5.value })
  return hasTable ? `${base}${t('h5toolkit.convert.estimateTable')}` : base
})

const canStartConvert = computed(() => {
  return (
    sourceDir.value &&
    outputDir.value &&
    datasets.value.some(ds => ds.export) &&
    !convertTaskId.value
  )
})

// ── Extract state / 文件提取状态 ────────────────────────────────────────
const extractFiles = ref<ScannedFile[]>([])
const extractScanBusy = ref(false)
const extractPage = ref(1)

const extractTotalPages = computed(() => Math.max(1, Math.ceil(extractFiles.value.length / EXTRACT_PAGE_SIZE)))
const pagedExtractFiles = computed(() => {
  const start = (extractPage.value - 1) * EXTRACT_PAGE_SIZE
  return extractFiles.value.slice(start, start + EXTRACT_PAGE_SIZE)
})

const extractTargetDir = ref<string | null>(null)
const extractSuffixFilter = ref('')
const extractPrependFolder = ref(true)
const extractPrefix = ref('')
const extractConflictPolicy = ref<'rename' | 'skip' | 'overwrite'>('rename')

const extractTaskId = ref<string | null>(null)
const extractProgress = ref(0)
const extractProgressMessage = ref<string | null>(null)
const extractResultSummary = ref<ResultSummaryData | null>(null)

const canStartExtract = computed(() => {
  return sourceDir.value && extractTargetDir.value && !extractTaskId.value
})

// ── Lifecycle / 生命周期 ────────────────────────────────────────────────
// Cleanup listeners on unmount / 卸载时清理监听器
let cleanupFns: Array<() => void> = []
onUnmounted(() => {
  cleanupFns.forEach(fn => fn())
  cleanupFns = []
})

// ── Shared helpers / 共享工具 ───────────────────────────────────────────
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

// ════════ Convert tab logic / 格式转换逻辑 ══════════════════════════════
/** Determine dataset kind label from ndim / 根据 ndim 判断数据集类型 */
function datasetKind(ndim: number): string {
  switch (ndim) {
    case 0: return t('h5toolkit.convert.kindScalar')
    case 1: return t('h5toolkit.convert.kind1d')
    case 2: return t('h5toolkit.convert.kind2d')
    case 3: return t('h5toolkit.convert.kind3d')
    case 4: return t('h5toolkit.convert.kind4d')
    default: return `${ndim}D`
  }
}

/** Scan H5 directory for datasets / 扫描 H5 目录中数据集 */
async function handleConvertScan(): Promise<void> {
  if (!sourceDir.value) return
  scanning.value = true
  scanInfo.value = null
  datasets.value = []
  scannedFiles.value = []
  fileListPage.value = 1

  // Launch file list scan in parallel / 并行启动文件列表扫描
  try {
    const fileResult = await transport.submitTask('h5_list_files', {
      sourceDir: sourceDir.value,
      suffix: refSuffix.value ? refSuffix.value : null,
      recursive: recursive.value,
    })
    const unsubFileResult = transport.onTaskResult(fileResult.taskId, (payload) => {
      const data = payload.data as { files: ScannedFile[]; total: number }
      scannedFiles.value = data.files
    })
    const unsubFileError = transport.onTaskError(fileResult.taskId, () => { /* keep silent */ })
    cleanupFns.push(unsubFileResult, unsubFileError)
  } catch {
    /* file list optional */
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
        status?: string
        message?: string
        datasets: Array<{
          path: string
          shape: string
          dtype: string
          ndim: number
          kind: string
        }>
        totalH5: number
        targetH5: number
        suffixMatched?: boolean
        refFile: string
      }

      // Backend signals a failed scan (no files / bad dir) inside an OK task
      // result — show the reason instead of a misleading "0 files" summary.
      // 后端在正常任务结果内用 status:'error' 表示扫描失败——显示原因，
      // 而不是误导性的「共 0 个」摘要。
      if (data.status === 'error') {
        datasets.value = []
        scannedFiles.value = []
        scanTargetH5.value = 0
        scanInfo.value = data.message
          ? t('h5toolkit.convert.scanResultError', { message: data.message })
          : t('h5toolkit.convert.scanFailed')
        scanning.value = false
        return
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
        // Default to image-like science data only: Nexus instrument metadata
        // (pixel masks, flatfields) and 1D logs/scalars stay unchecked;
        // 全选 button still selects everything explicitly.
        // 默认只勾选图像类科学数据：Nexus 仪器元数据（像素掩码、平场）与
        // 1D 日志/标量不勾；需要时可用「全选」或手动勾选。
        export: ds.ndim >= 2 && !isInstrumentMetadata(ds.path),
      }))

      scanTargetH5.value = data.targetH5
      scanInfo.value = data.suffixMatched === false
        ? t('h5toolkit.convert.scanResultAll', {
            total: data.totalH5,
            target: data.targetH5,
            ref: data.refFile,
          })
        : t('h5toolkit.convert.scanResult', {
            total: data.totalH5,
            target: data.targetH5,
            ref: data.refFile,
          })
      scanning.value = false
    })

    const unsubError = transport.onTaskError(result.taskId, () => {
      scanInfo.value = t('h5toolkit.convert.scanFailed')
      scanning.value = false
    })

    cleanupFns.push(unsubProgress, unsubResult, unsubError)
  } catch {
    scanInfo.value = t('h5toolkit.convert.scanFailed')
    scanning.value = false
  }
}

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
async function handleStartConvert(): Promise<void> {
  if (!sourceDir.value || !outputDir.value) return

  const selected = datasets.value
    .filter(ds => ds.export)
    .map(ds => ({
      path: ds.path,
      // Array.from copies out of the reactive Proxy: Electron IPC structured
      // clone rejects Proxy objects ("An object could not be cloned").
      // Array.from 把响应式 Proxy 数组拷成普通数组：Electron IPC 结构化克隆
      // 拒绝 Proxy 对象（"An object could not be cloned"）。
      channels: ds.ndim === 4 ? Array.from(ds.selectedChannels) : undefined,
    }))

  if (selected.length === 0) return

  convertResultSummary.value = null
  convertProgress.value = 0
  convertProgressMessage.value = null

  let submit: { taskId: string }
  try {
    submit = await transport.submitTask('h5convert', {
      sourceDir: sourceDir.value,
      outputDir: outputDir.value,
      refSuffix: refSuffix.value || '_master',
      imageFormat: imageFormat.value,
      tableFormat: tableFormat.value,
      namingMode: namingMode.value,
      flatOutput: flatOutput.value,
      datasets: selected,
    })
  } catch (error) {
    toast.push({
      title: t('h5toolkit.convert.startExport'),
      message: error instanceof Error ? error.message : String(error),
      tone: 'error',
    })
    return
  }

  convertTaskId.value = submit.taskId

  const unsubProgress = transport.onTaskProgress(submit.taskId, (payload) => {
    convertProgress.value = payload.progress
    convertProgressMessage.value = payload.message ?? null
  })

  const unsubResult = transport.onTaskResult(submit.taskId, (payload) => {
    const data = payload.data as {
      total: number
      success: number
      failed: number
      elapsed: number
    }
    convertResultSummary.value = {
      total: data.total,
      success: data.success,
      failed: data.failed,
      elapsed: data.elapsed,
    }
    convertTaskId.value = null
  })

  const unsubError = transport.onTaskError(submit.taskId, (payload) => {
    convertProgressMessage.value = payload.error
    convertTaskId.value = null
  })

  cleanupFns.push(unsubProgress, unsubResult, unsubError)
}

/** Cancel running convert task / 取消运行中的转换任务 */
async function handleCancelConvert(): Promise<void> {
  const tid = convertTaskId.value
  convertTaskId.value = null
  convertProgress.value = 0
  if (tid) {
    try { await transport.cancelTask(tid) } catch { /* already finished */ }
  }
}

// ════════ Extract tab logic / 文件提取逻辑 ══════════════════════════════
async function handleScanExtractFiles(): Promise<void> {
  if (!sourceDir.value) return
  extractScanBusy.value = true
  extractFiles.value = []
  extractPage.value = 1

  try {
    const result = await transport.submitTask('h5_list_files', {
      sourceDir: sourceDir.value,
      suffix: extractSuffixFilter.value || null,
      recursive: recursive.value,
    })

    const unsubResult = transport.onTaskResult(result.taskId, (payload) => {
      const data = payload.data as { files: ScannedFile[]; total: number }
      extractFiles.value = data.files
      extractScanBusy.value = false
    })

    const unsubError = transport.onTaskError(result.taskId, () => {
      extractScanBusy.value = false
    })

    cleanupFns.push(unsubResult, unsubError)
  } catch {
    extractScanBusy.value = false
  }
}

/** Start extraction task / 开始提取任务 */
async function handleStartExtract(): Promise<void> {
  if (!sourceDir.value || !extractTargetDir.value) return

  extractResultSummary.value = null
  extractProgress.value = 0
  extractProgressMessage.value = null

  let submit: { taskId: string }
  try {
    submit = await transport.submitTask('h5_extract', {
      sourceDir: sourceDir.value,
      targetDir: extractTargetDir.value,
      suffix: extractSuffixFilter.value || null,
      prependFolder: extractPrependFolder.value,
      prefix: extractPrefix.value || null,
      conflictPolicy: extractConflictPolicy.value,
    })
  } catch (error) {
    toast.push({
      title: t('h5toolkit.extract.startExtract'),
      message: error instanceof Error ? error.message : String(error),
      tone: 'error',
    })
    return
  }

  extractTaskId.value = submit.taskId

  const unsubProgress = transport.onTaskProgress(submit.taskId, (payload) => {
    extractProgress.value = payload.progress
    extractProgressMessage.value = payload.message ?? null
  })

  const unsubResult = transport.onTaskResult(submit.taskId, (payload) => {
    const data = payload.data as {
      total: number
      success: number
      failed: number
      elapsed: number
    }
    extractResultSummary.value = {
      total: data.total,
      success: data.success,
      failed: data.failed,
      elapsed: data.elapsed,
    }
    extractTaskId.value = null
  })

  const unsubError = transport.onTaskError(submit.taskId, (payload) => {
    extractProgressMessage.value = payload.error
    extractTaskId.value = null
  })

  cleanupFns.push(unsubProgress, unsubResult, unsubError)
}

/** Cancel running extract task / 取消运行中的提取任务 */
async function handleCancelExtract(): Promise<void> {
  const tid = extractTaskId.value
  extractTaskId.value = null
  extractProgress.value = 0
  if (tid) {
    try { await transport.cancelTask(tid) } catch { /* already finished */ }
  }
}

// ── Watchers / 监听器 ───────────────────────────────────────────────────
// Source dir change only CLEARS previous results — scanning happens
// exclusively via the explicit scan buttons (user request 2026-09-29).
// 源目录变更只清空旧结果——扫描仅由用户点击扫描按钮触发（2026-09-29 用户指令）。
watch(sourceDir, () => {
  datasets.value = []
  scannedFiles.value = []
  fileListPage.value = 1
  scanInfo.value = null
  scanTargetH5.value = 0
  extractFiles.value = []
  extractPage.value = 1
})
</script>

<style scoped>
.h5toolkit-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-subtitle {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
}

/* ── Tabs / 标签切换 ──────────────────────────────────────────────────── */
.h5t-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border);
}

.h5t-tab {
  padding: 8px 20px;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: -1px;
}

.h5t-tab:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.h5t-tab-active {
  color: var(--text-primary);
  background: var(--bg-surface);
  border-color: var(--border);
  border-bottom-color: var(--bg-surface);
  font-weight: 600;
}

.h5t-tab-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Fieldset & form controls / 表单 ──────────────────────────────────── */
.h5t-fieldset {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.h5t-fieldset > legend {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--text-primary);
  padding: 0 8px;
}

.h5t-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.h5t-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

.h5t-input {
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

.h5t-input:focus {
  outline: none;
  border-color: var(--primary-light);
}

.h5t-select {
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.h5t-btn {
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

.h5t-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
}

.h5t-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.h5t-btn-primary {
  background: var(--primary-light);
  color: var(--text-inverse);
  border-color: var(--primary-light);
}

.h5t-btn-primary:hover:not(:disabled) {
  border-color: var(--primary);
}

.h5t-btn-sm {
  padding: 4px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
}

.h5t-btn-sm:hover {
  color: var(--text-primary);
  border-color: var(--border-hover);
}

.h5t-checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.h5t-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.h5t-info {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin: 0;
}

.h5t-actions {
  display: flex;
  gap: 12px;
}

.h5t-format-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.h5t-format-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* ── Dataset tree / 数据集树 ──────────────────────────────────────────── */
.h5t-ds-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.h5t-ds-tree {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 4px 0;
}

.h5t-ds-group {
  border-bottom: 1px solid var(--border);
}

.h5t-ds-group:last-child {
  border-bottom: none;
}

.h5t-ds-details {
  margin: 0;
}

.h5t-ds-folder {
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

.h5t-ds-folder:hover {
  background: var(--bg-hover, rgba(0,0,0,0.04));
}

.h5t-ds-folder::before {
  content: '▸';
  font-size: 0.7rem;
  transition: transform 0.15s;
}

.h5t-ds-details[open] .h5t-ds-folder::before {
  content: '▾';
}

.h5t-ds-folder-icon {
  font-size: 0.9rem;
}

.h5t-ds-folder-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  word-break: break-all;
}

.h5t-ds-folder-count {
  font-size: 0.7rem;
  background: var(--bg-tertiary, #e0e0e0);
  padding: 1px 6px;
  border-radius: 10px;
  color: var(--text-secondary);
}

.h5t-ds-item {
  padding: 4px 12px 4px 32px;
  border-bottom: 1px solid var(--border);
}

.h5t-ds-item:last-child {
  border-bottom: none;
}

.h5t-ds-item-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.8rem;
}

.h5t-ds-item-name {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.h5t-ds-item-badge {
  font-size: 0.65rem;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.h5t-badge-image {
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
}

.h5t-badge-table {
  background: rgba(34, 197, 94, 0.12);
  color: #22c55e;
}

.h5t-ds-item-shape {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.h5t-channels {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
}

.h5t-ch-label {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.75rem;
  cursor: pointer;
}

/* ── File list table / 文件列表表格 ───────────────────────────────────── */
.h5t-file-list-details {
  margin-top: 8px;
}

.h5t-file-list-summary {
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 4px 0;
  user-select: none;
}

.h5t-file-list-scroll {
  max-height: 420px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-top: 8px;
}

.h5t-file-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.h5t-file-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface);
  font-weight: 600;
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  z-index: 1;
}

.h5t-file-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 0;
}

.h5t-file-table tr:hover td {
  background: var(--bg-hover);
}

.col-idx { width: 48px; text-align: center; }
.col-name { width: 35%; }
.col-path { width: auto; }
.col-size { width: 90px; text-align: right; }

.h5t-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 10px;
}

.h5t-pagination-info {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}
</style>
