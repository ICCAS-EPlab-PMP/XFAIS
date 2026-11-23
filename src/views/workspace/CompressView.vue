<template>
  <section class="compress-page" :data-testid="testIds.compressPage">
    <!-- Header / 页头 -->
    <header class="cp-header">
      <div>
        <h1>{{ t('compress.title') }}</h1>
        <p class="cp-subtitle">{{ t('compress.subtitle') }}</p>
      </div>
      <span class="cp-badge">v0.5.0</span>
    </header>

    <!-- Step rail / 步骤条 -->
    <ol class="cp-steps">
      <li
        v-for="(label, index) in stepLabels"
        :key="label"
        class="cp-step"
        :class="{ 'cp-step--active': step === index + 1, 'cp-step--done': step > index + 1 }"
      >
        <span class="cp-step-index">{{ index + 1 }}</span>
        <span class="cp-step-label">{{ label }}</span>
      </li>
    </ol>

    <!-- ================= Step 1: select input ================= -->
    <section class="cp-card">
      <div class="cp-card-head">
        <h2>{{ t('compress.source.title') }}</h2>
        <div class="cp-mode-switch" role="tablist">
          <button
            type="button"
            class="cp-mode"
            :class="{ 'cp-mode--active': mode === 'folder' }"
            :data-testid="testIds.compressModeFolder"
            @click="switchMode('folder')"
          >
            {{ t('compress.source.modeFolder') }}
          </button>
          <button
            type="button"
            class="cp-mode"
            :class="{ 'cp-mode--active': mode === 'files' }"
            :data-testid="testIds.compressModeFiles"
            @click="switchMode('files')"
          >
            {{ t('compress.source.modeFiles') }}
          </button>
        </div>
      </div>

      <!-- Folder mode / 文件夹模式 -->
      <div v-if="mode === 'folder'" class="cp-field">
        <span class="cp-label">{{ t('compress.source.folderLabel') }}</span>
        <div v-if="isDesktop" class="cp-pick-row">
          <button
            type="button"
            class="cp-btn"
            :data-testid="testIds.compressPickFolder"
            @click="pickFolder"
          >
            {{ t('compress.source.pickFolder') }}
          </button>
          <span class="cp-path" :title="inputDir">{{ inputDir || '—' }}</span>
          <button v-if="inputDir" type="button" class="cp-clear" @click="inputDir = ''">✕</button>
        </div>
        <template v-else>
          <ServerPickerButton
            mode="folder"
            @picked-folder="dir => (inputDir = dir)"
          />
          <input
            v-model="inputDir"
            type="text"
            class="cp-input cp-input--path"
            :data-testid="testIds.compressFolderInput"
            placeholder="/data/sample"
          />
          <p class="cp-hint">{{ t('compress.source.webPathHint') }}</p>
        </template>
        <label class="cp-check">
          <input
            v-model="recursive"
            type="checkbox"
            class="cp-checkbox"
            :data-testid="testIds.compressRecursive"
          />
          <span>{{ t('compress.source.recursive') }}</span>
        </label>
      </div>

      <!-- Files mode / 文件模式 -->
      <div v-else class="cp-field">
        <span class="cp-label">{{ t('compress.source.filesLabel') }}</span>
        <div class="cp-pick-row">
          <button
            type="button"
            class="cp-btn"
            :data-testid="testIds.compressPickFiles"
            @click="pickFiles"
          >
            {{ t('compress.source.pickFiles') }}
          </button>
          <span class="cp-path">
            {{ files.length > 0 ? t('compress.source.selectedFiles', { n: files.length }) : '—' }}
          </span>
          <button v-if="files.length > 0" type="button" class="cp-clear" @click="files = []">✕</button>
        </div>
        <ul v-if="files.length > 0" class="cp-file-chips">
          <li v-for="file in files.slice(0, 12)" :key="file" :title="file">{{ basename(file) }}</li>
          <li v-if="files.length > 12" class="cp-file-chip-more">+{{ files.length - 12 }}</li>
        </ul>
      </div>

      <!-- Scan / 扫描 -->
      <div class="cp-actions">
        <button
          type="button"
          class="cp-btn cp-btn--primary"
          :disabled="scanning || busy"
          :data-testid="testIds.compressScanBtn"
          @click="handleScan"
        >
          {{ scanning ? t('compress.source.scanning') : (probe ? t('compress.source.rescan') : t('compress.source.scan')) }}
        </button>
        <span v-if="!probe && !scanning" class="cp-hint">{{ t('compress.source.empty') }}</span>
      </div>

      <!-- Stats / 统计 -->
      <div v-if="probe" class="cp-stats" :data-testid="testIds.compressStats">
        <div class="cp-stat">
          <span class="cp-stat-label">{{ t('compress.source.tiffCount') }}</span>
          <strong class="cp-stat-value">{{ probe.stats.tiffCount ?? 0 }}</strong>
          <span class="cp-stat-sub">{{ humanBytes(probe.stats.tiffBytes ?? 0) }}</span>
        </div>
        <div class="cp-stat">
          <span class="cp-stat-label">{{ t('compress.source.hdf5Count') }}</span>
          <strong class="cp-stat-value">{{ probe.stats.hdf5Count ?? 0 }}</strong>
          <span class="cp-stat-sub">{{ humanBytes(probe.stats.hdf5Bytes ?? 0) }}</span>
        </div>
        <div class="cp-stat">
          <span class="cp-stat-label">{{ t('compress.source.totalSize') }}</span>
          <strong class="cp-stat-value">{{ humanBytes(probe.stats.totalBytes ?? 0) }}</strong>
          <span class="cp-stat-sub">{{ t('compress.source.fileCount', { n: probe.stats.totalCount ?? 0 }) }}</span>
        </div>
      </div>

      <p v-if="probe && (probe.stats.totalCount ?? 0) === 0" class="cp-warning">
        {{ t('compress.source.noFiles') }}
      </p>
      <p v-if="probe && probe.skippedCount > 0" class="cp-hint">
        {{ t('compress.source.unsupported', { n: probe.skippedCount }) }}
      </p>

      <details v-if="probe && probe.sample.length > 0" class="cp-sample">
        <summary>{{ t('compress.source.sampleTitle', { n: probe.sample.length }) }}</summary>
        <ul>
          <li v-for="item in probe.sample" :key="item.path">
            <span class="cp-kind">{{ item.kind === 'tiff' ? 'TIFF' : 'HDF5' }}</span>
            <span class="cp-sample-name" :title="item.path">{{ item.name }}</span>
            <span class="cp-sample-size">{{ humanBytes(item.size) }}</span>
          </li>
        </ul>
        <p v-if="probe.truncated" class="cp-hint">
          {{ t('compress.source.truncated', { n: probe.stats.totalCount }) }}
        </p>
      </details>
    </section>

    <!-- ================= Step 2: trial ================= -->
    <section v-if="step >= 2 && probe && (probe.stats.totalCount ?? 0) > 0" class="cp-card">
      <div class="cp-card-head">
        <h2>{{ t('compress.trial.title') }}</h2>
      </div>
      <p class="cp-hint">{{ t('compress.trial.description') }}</p>

      <div class="cp-actions">
        <button
          type="button"
          class="cp-btn cp-btn--primary"
          :disabled="busy"
          :data-testid="testIds.compressTrialBtn"
          @click="handleTrial"
        >
          {{ trial ? t('compress.trial.rerun') : t('compress.trial.run') }}
        </button>
        <span v-if="trialRunning" class="cp-hint">{{ t('compress.trial.running') }}</span>
      </div>

      <div v-if="trial" class="cp-trial" :data-testid="testIds.compressTrialResult">
        <div class="cp-trial-head">
          <span class="cp-trial-file" :title="trial.path">{{ trial.checkedFile || basename(trial.path) }}</span>
          <span class="cp-pill" :class="trial.verified ? 'cp-pill--ok' : 'cp-pill--bad'">
            {{ trial.verified ? t('compress.trial.verified') : t('compress.trial.failed') }}
          </span>
        </div>

        <dl class="cp-kv">
          <div><dt>{{ t('compress.trial.algorithm') }}</dt><dd>{{ trial.algorithm }}</dd></div>
          <div><dt>{{ t('compress.trial.original') }}</dt><dd>{{ humanBytes(trial.originalBytes) }}</dd></div>
          <div><dt>{{ t('compress.trial.compressed') }}</dt><dd>{{ humanBytes(trial.compressedBytes) }}</dd></div>
          <div>
            <dt>{{ t('compress.trial.ratio') }}</dt>
            <dd class="cp-ratio">{{ formatRatio(trial.ratio) }}</dd>
          </div>
        </dl>

        <p v-if="trial.note" class="cp-hint">{{ trial.note }}</p>

        <div v-if="Object.keys(trial.checks).length > 0" class="cp-checks">
          <span class="cp-label">{{ t('compress.trial.checksTitle') }}</span>
          <ul>
            <li v-for="(value, key) in trial.checks" :key="key">
              <span class="cp-check-icon" :class="value ? 'cp-ok' : 'cp-bad'">{{ value ? '✓' : '✕' }}</span>
              {{ checkLabel(String(key)) }}
            </li>
          </ul>
          <p v-if="trial.pages" class="cp-hint">{{ t('compress.trial.pagesValue', { n: trial.pages }) }}</p>
          <p v-if="trial.compressedDatasets" class="cp-hint">
            {{ t('compress.trial.datasetsValue', { n: trial.compressedDatasets }) }}
          </p>
        </div>

        <div class="cp-actions">
          <button
            type="button"
            class="cp-btn cp-btn--primary"
            :data-testid="testIds.compressConfirmBtn"
            @click="goToBatch"
          >
            {{ t('compress.trial.confirm') }}
          </button>
        </div>
      </div>
    </section>

    <!-- ================= Step 3: batch ================= -->
    <section v-if="step >= 3" class="cp-card">
      <div class="cp-card-head">
        <h2>{{ t('compress.batch.title') }}</h2>
      </div>

      <div class="cp-field">
        <span class="cp-label">{{ t('compress.batch.outputLabel') }}</span>
        <div v-if="isDesktop" class="cp-pick-row">
          <button
            type="button"
            class="cp-btn"
            :data-testid="testIds.compressOutputInput"
            @click="pickOutputFolder"
          >
            {{ t('compress.source.pickFolder') }}
          </button>
          <span class="cp-path" :title="outputDir">{{ outputDir || '—' }}</span>
          <button v-if="outputDir" type="button" class="cp-clear" @click="outputDir = ''">✕</button>
        </div>
        <template v-else>
          <input
            v-model="outputDir"
            type="text"
            class="cp-input cp-input--path"
            :data-testid="testIds.compressOutputInput"
            placeholder="/data/compressed"
          />
          <p class="cp-hint">{{ t('compress.batch.webOutputHint') }}</p>
        </template>
        <p class="cp-hint">{{ t('compress.batch.outputHint') }}</p>
      </div>

      <div class="cp-actions">
        <button
          type="button"
          class="cp-btn cp-btn--primary"
          :disabled="batchRunning || !outputDir"
          :data-testid="testIds.compressStartBtn"
          @click="handleBatch"
        >
          {{ batchRunning ? t('compress.batch.running') : t('compress.batch.start') }}
        </button>
        <span v-if="cancelling" class="cp-hint">{{ t('compress.batch.cancelling') }}</span>
      </div>

      <TaskProgressBar
        v-if="batchRunning"
        :task-id="taskId"
        :progress="progress"
        :message="progressMessage"
        @cancel="cancelling = true"
      />

      <div v-if="report" class="cp-report" :data-testid="testIds.compressReport">
        <h3>{{ t('compress.batch.reportTitle') }}</h3>
        <div class="cp-stat-grid">
          <div class="cp-stat cp-stat--ok">
            <span class="cp-stat-label">{{ t('compress.batch.success') }}</span>
            <strong class="cp-stat-value">{{ report.success }}</strong>
          </div>
          <div class="cp-stat" :class="{ 'cp-stat--bad': report.failed > 0 }">
            <span class="cp-stat-label">{{ t('compress.batch.failed') }}</span>
            <strong class="cp-stat-value">{{ report.failed }}</strong>
          </div>
          <div class="cp-stat">
            <span class="cp-stat-label">{{ t('compress.batch.skipped') }}</span>
            <strong class="cp-stat-value">{{ report.skipped }}</strong>
          </div>
          <div class="cp-stat">
            <span class="cp-stat-label">{{ t('compress.batch.original') }}</span>
            <strong class="cp-stat-value">{{ humanBytes(report.originalBytes) }}</strong>
          </div>
          <div class="cp-stat">
            <span class="cp-stat-label">{{ t('compress.batch.compressed') }}</span>
            <strong class="cp-stat-value">{{ humanBytes(report.compressedBytes) }}</strong>
          </div>
          <div class="cp-stat">
            <span class="cp-stat-label">{{ t('compress.batch.ratio') }}</span>
            <strong class="cp-stat-value cp-ratio">{{ formatRatio(report.ratio) }}</strong>
          </div>
          <div class="cp-stat">
            <span class="cp-stat-label">{{ t('compress.batch.saved') }}</span>
            <strong class="cp-stat-value">{{ humanBytes(report.savedBytes) }}</strong>
          </div>
          <div class="cp-stat">
            <span class="cp-stat-label">{{ t('compress.batch.elapsed') }}</span>
            <strong class="cp-stat-value">{{ report.elapsed.toFixed(1) }} s</strong>
          </div>
        </div>

        <p v-if="report.cancelled" class="cp-warning">
          {{ t('compress.batch.cancelNotice', { n: report.success }) }}
        </p>
        <p class="cp-notice">{{ t('compress.batch.deleteNotice') }}</p>
        <p class="cp-hint">{{ t('compress.batch.hdf5Note') }}</p>

        <div v-if="report.failed > 0" class="cp-failures" :data-testid="testIds.compressFailures">
          <h4>{{ t('compress.batch.failuresTitle') }}</h4>
          <ul>
            <li v-for="failure in report.failures" :key="failure.path">
              <span class="cp-fail-path" :title="failure.path">{{ failure.path }}</span>
              <span class="cp-fail-reason">{{ failure.reason }}</span>
            </li>
          </ul>
        </div>
        <p v-else class="cp-hint">{{ t('compress.batch.noFailures') }}</p>

        <div class="cp-table-wrap">
          <h4>{{ t('compress.batch.filesTitle') }}</h4>
          <table class="cp-table" :data-testid="testIds.compressTable">
            <thead>
              <tr>
                <th>{{ t('compress.table.file') }}</th>
                <th>{{ t('compress.table.kind') }}</th>
                <th class="cp-num">{{ t('compress.table.original') }}</th>
                <th class="cp-num">{{ t('compress.table.compressed') }}</th>
                <th class="cp-num">{{ t('compress.table.ratio') }}</th>
                <th>{{ t('compress.table.status') }}</th>
                <th>{{ t('compress.table.message') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in visibleRows" :key="row.path">
                <td class="cp-cell-path" :title="row.path">{{ basename(row.path) }}</td>
                <td>{{ row.kind === 'tiff' ? 'TIFF' : 'HDF5' }}</td>
                <td class="cp-num">{{ humanBytes(row.originalBytes) }}</td>
                <td class="cp-num">{{ row.compressedBytes > 0 ? humanBytes(row.compressedBytes) : '—' }}</td>
                <td class="cp-num cp-ratio">{{ row.ratio > 0 ? formatRatio(row.ratio) : '—' }}</td>
                <td>
                  <span class="cp-pill" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
                </td>
                <td class="cp-cell-msg">{{ row.message }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="report.filesOmitted > 0" class="cp-hint">
            {{ t('compress.batch.filesOmitted', { n: report.filesOmitted }) }}
          </p>
        </div>

        <div class="cp-actions">
          <button
            v-if="isDesktop && report.outputDir"
            type="button"
            class="cp-btn"
            :data-testid="testIds.compressOpenFolder"
            @click="openOutputFolder"
          >
            {{ t('compress.batch.openFolder') }}
          </button>
          <button type="button" class="cp-btn" @click="resetAll">
            {{ t('compress.batch.newBatch') }}
          </button>
        </div>
      </div>

      <p v-if="!report && !batchRunning" class="cp-hint">{{ t('compress.batch.emptyReport') }}</p>
    </section>
  </section>
</template>

<script setup lang="ts">
/**
 * CompressView.vue — 数据无损压缩向导（v0.5.0）
 * Lossless data compression wizard (v0.5.0)
 *
 * 三步：选择输入（扫描统计）→ 试压缩第一个文件（四项无损校验）→ 批量压缩
 * 并生成报告。原始文件全程只读，输出目录结构映射自输入目录。
 */
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ServerPickerButton from '@/components/business/ServerPickerButton.vue'
import { useToast } from '@/lib/toast'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'

interface ProbeStats {
  totalCount: number
  tiffCount: number
  hdf5Count: number
  totalBytes: number
  tiffBytes: number
  hdf5Bytes: number
}

interface SampleRow {
  path: string
  name: string
  kind: string
  size: number
}

interface ProbeData {
  action: string
  stats: ProbeStats
  sample: SampleRow[]
  truncated: boolean
  skippedCount: number
}

interface TrialData {
  action: string
  path: string
  checkedFile: string
  algorithm: string
  originalBytes: number
  compressedBytes: number
  ratio: number
  verified: boolean
  checks: Record<string, unknown>
  note: string
  pages: number
  compressedDatasets: number
  sourceCount: number
}

interface FileRow {
  path: string
  outputPath: string
  kind: string
  originalBytes: number
  compressedBytes: number
  ratio: number
  status: string
  message: string
}

interface BatchData {
  action: string
  outputDir: string
  total: number
  success: number
  failed: number
  skipped: number
  originalBytes: number
  compressedBytes: number
  ratio: number
  savedBytes: number
  elapsed: number
  files: FileRow[]
  filesOmitted: number
  failures: Array<{ path: string; reason: string }>
  cancelled: boolean
  hdf5ReaderNote: string
}

type Mode = 'folder' | 'files'

const { t } = useI18n()
const transport = useTransport()
const toast = useToast()

const isDesktop = transport.isDesktop()
const stepLabels = computed(() => [
  t('compress.steps.select'),
  t('compress.steps.trial'),
  t('compress.steps.batch'),
])

// ── Selection / 输入选择 ────────────────────────────────────────────────────
const mode = ref<Mode>('folder')
const inputDir = ref('')
const files = ref<string[]>([])
const recursive = ref(true)

// ── Task state / 任务状态 ────────────────────────────────────────────────────
const step = ref(1)
const scanning = ref(false)
const trialRunning = ref(false)
const batchRunning = ref(false)
const cancelling = ref(false)
const busy = computed(() => scanning.value || trialRunning.value || batchRunning.value)

const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)

const probe = ref<ProbeData | null>(null)
const trial = ref<TrialData | null>(null)
const report = ref<BatchData | null>(null)
const outputDir = ref('')

let cleanups: Array<() => void> = []

function clearTaskListeners(): void {
  for (const off of cleanups) off()
  cleanups = []
}

onUnmounted(() => clearTaskListeners())

// ── Helpers / 辅助 ──────────────────────────────────────────────────────────
function basename(path: string): string {
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  const parts = path.split(sep)
  return parts[parts.length - 1] || path
}

function humanBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return index === 0 ? `${Math.round(size)} B` : `${size.toFixed(2)} ${units[index]}`
}

function formatRatio(value: number): string {
  return value > 0 ? `${value.toFixed(2)}×` : '—'
}

function checkLabel(key: string): string {
  if (key === 'pixels') return t('compress.trial.checks.pixels')
  if (key === 'description') return t('compress.trial.checks.description')
  if (key === 'tags') return t('compress.trial.checks.tags')
  if (key === 'pages') return t('compress.trial.checks.pages')
  if (key === 'noDupJsonDescription') return t('compress.trial.checks.noDupJsonDescription')
  if (key === 'datasets') return t('compress.trial.checks.datasets')
  if (key === 'attrs') return t('compress.trial.checks.attrs')
  return key
}

function statusLabel(status: string): string {
  if (status === 'ok') return t('compress.table.statusOk')
  if (status === 'skipped') return t('compress.table.statusSkipped')
  return t('compress.table.statusFailed')
}

function statusClass(status: string): string {
  if (status === 'ok') return 'cp-pill--ok'
  if (status === 'skipped') return 'cp-pill--skip'
  return 'cp-pill--bad'
}

const visibleRows = computed<FileRow[]>(() => {
  if (!report.value) return []
  return report.value.files.slice(0, 300)
})

function switchMode(next: Mode): void {
  if (next === mode.value) return
  mode.value = next
  probe.value = null
  trial.value = null
  report.value = null
  step.value = 1
}

function selectionParams(): Record<string, unknown> {
  return mode.value === 'folder'
    ? { inputDir: inputDir.value.trim(), files: [], recursive: recursive.value }
    : { inputDir: '', files: [...files.value], recursive: false }
}

/**
 * Submit one compress task and resolve with the adapted report.
 * 提交一个压缩任务并返回适配后的报告。
 */
async function runTask(params: Record<string, unknown>): Promise<Record<string, unknown>> {
  clearTaskListeners()
  const response = await transport.submitTask('compress', params)
  taskId.value = response.taskId
  return await new Promise<Record<string, unknown>>((resolve, reject) => {
    const offProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? ''
    })
    const offResult = transport.onTaskResult(response.taskId, (payload) => {
      cleanup()
      resolve((payload.data ?? {}) as Record<string, unknown>)
    })
    const offError = transport.onTaskError(response.taskId, (payload) => {
      cleanup()
      reject(new Error(payload.error || 'Task failed'))
    })
    const cleanup = (): void => {
      offProgress()
      offResult()
      offError()
      cleanups = cleanups.filter((fn) => fn !== cleanup)
      if (taskId.value === response.taskId) taskId.value = null
    }
    cleanups.push(cleanup)
  })
}

// ── Pickers / 选择器 ────────────────────────────────────────────────────────
async function pickFolder(): Promise<void> {
  try {
    const path = await transport.selectFolder()
    if (path) {
      inputDir.value = path
      probe.value = null
      trial.value = null
      report.value = null
      step.value = 1
    }
  } catch (error) {
    toast.push({ title: t('compress.title'), message: String(error), tone: 'error' })
  }
}

async function pickFiles(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: true,
      filters: [
        { name: 'TIFF / HDF5', extensions: ['tif', 'tiff', 'h5', 'hdf5', 'nxs', 'hdf'] },
      ],
    })
    if (!result) return
    files.value = Array.isArray(result) ? result : [result]
    probe.value = null
    trial.value = null
    report.value = null
    step.value = 1
  } catch (error) {
    toast.push({ title: t('compress.title'), message: String(error), tone: 'error' })
  }
}

async function pickOutputFolder(): Promise<void> {
  try {
    const path = await transport.selectFolder()
    if (path) outputDir.value = path
  } catch (error) {
    toast.push({ title: t('compress.title'), message: String(error), tone: 'error' })
  }
}

async function openOutputFolder(): Promise<void> {
  if (!report.value?.outputDir) return
  const ok = await transport.openPath(report.value.outputDir)
  if (!ok) {
    toast.push({ title: t('compress.batch.openFolder'), message: report.value.outputDir, tone: 'info' })
  }
}

// ── Actions / 动作 ──────────────────────────────────────────────────────────
async function handleScan(): Promise<void> {
  if (mode.value === 'folder' && !inputDir.value.trim()) {
    toast.push({
      title: t('compress.title'),
      message: isDesktop ? t('compress.source.folderRequired') : t('compress.source.webFolderRequired'),
      tone: 'error',
    })
    return
  }
  if (mode.value === 'files' && files.value.length === 0) {
    toast.push({ title: t('compress.title'), message: t('compress.source.filesRequired'), tone: 'error' })
    return
  }
  scanning.value = true
  progress.value = 0
  try {
    const data = await runTask({ action: 'probe', ...selectionParams() })
    probe.value = data as unknown as ProbeData
    trial.value = null
    report.value = null
    step.value = 2
    if ((probe.value.stats?.totalCount ?? 0) === 0) {
      toast.push({ title: t('compress.source.title'), message: t('compress.source.noFiles'), tone: 'info' })
    }
  } catch (error) {
    toast.push({
      title: t('compress.source.title'),
      message: error instanceof Error ? error.message : String(error),
      tone: 'error',
    })
  } finally {
    scanning.value = false
  }
}

async function handleTrial(): Promise<void> {
  trialRunning.value = true
  progress.value = 0
  try {
    const data = await runTask({ action: 'trial', ...selectionParams() })
    trial.value = data as unknown as TrialData
    toast.push({
      title: t('compress.trial.title'),
      message: `${formatRatio(trial.value.ratio)} · ${humanBytes(trial.value.compressedBytes)}`,
      tone: trial.value.verified ? 'success' : 'error',
    })
  } catch (error) {
    trial.value = null
    toast.push({
      title: t('compress.trial.failed'),
      message: error instanceof Error ? error.message : String(error),
      tone: 'error',
    })
  } finally {
    trialRunning.value = false
  }
}

function goToBatch(): void {
  step.value = 3
}

function normalizeDir(value: string): string {
  return value.trim().replace(/[\\/]+$/, '').toLowerCase()
}

async function handleBatch(): Promise<void> {
  if (!outputDir.value.trim()) {
    toast.push({ title: t('compress.batch.title'), message: t('compress.batch.requireOutput'), tone: 'error' })
    return
  }
  if (mode.value === 'folder' && normalizeDir(inputDir.value) === normalizeDir(outputDir.value)) {
    toast.push({ title: t('compress.batch.title'), message: t('compress.batch.sameDir'), tone: 'error' })
    return
  }

  batchRunning.value = true
  cancelling.value = false
  report.value = null
  progress.value = 0
  progressMessage.value = null
  try {
    const data = await runTask({
      action: 'batch',
      ...selectionParams(),
      outputDir: outputDir.value.trim(),
    })
    report.value = data as unknown as BatchData
    if (report.value.cancelled) {
      toast.push({
        title: t('compress.batch.cancelling'),
        message: t('compress.batch.cancelNotice', { n: report.value.success }),
        tone: 'info',
      })
    } else {
      toast.push({
        title: t('compress.batch.reportTitle'),
        message: `${t('compress.batch.success')} ${report.value.success} · ${formatRatio(report.value.ratio)}`,
        tone: report.value.failed > 0 ? 'error' : 'success',
      })
    }
  } catch (error) {
    toast.push({
      title: t('compress.batch.failed'),
      message: error instanceof Error ? error.message : String(error),
      tone: 'error',
    })
  } finally {
    batchRunning.value = false
    cancelling.value = false
  }
}

function resetAll(): void {
  clearTaskListeners()
  step.value = 1
  probe.value = null
  trial.value = null
  report.value = null
  progress.value = 0
  progressMessage.value = null
}
</script>

<style scoped>
.compress-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1180px;
}

/* Header / 页头 */
.cp-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.cp-header h1 {
  margin: 0 0 6px;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.cp-subtitle {
  margin: 0;
  max-width: 900px;
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.cp-badge {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--primary-bg);
  color: var(--primary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
}

/* Step rail / 步骤条 */
.cp-steps {
  display: flex;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
  flex-wrap: wrap;
}

.cp-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  background: var(--bg-surface);
}

.cp-step--active {
  border-color: var(--primary-light);
  color: var(--primary);
  font-weight: 600;
  background: var(--primary-bg);
}

.cp-step--done {
  color: var(--secondary);
  border-color: rgba(16, 185, 129, 0.35);
}

.cp-step-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--bg-surface-alt);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  font-weight: 600;
}

.cp-step--active .cp-step-index {
  background: var(--primary);
  color: var(--text-inverse);
}

.cp-step--done .cp-step-index {
  background: var(--secondary);
  color: var(--text-inverse);
}

/* Card / 卡片 */
.cp-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cp-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.cp-card-head h2 {
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Mode switch / 模式切换 */
.cp-mode-switch {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--bg-surface-alt);
}

.cp-mode {
  padding: 6px 16px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.cp-mode--active {
  background: var(--bg-surface);
  color: var(--primary);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

/* Fields / 字段 */
.cp-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cp-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cp-pick-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.cp-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.cp-input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.cp-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.cp-input--path {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
}

.cp-clear {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.875rem;
  padding: 4px;
}

.cp-clear:hover {
  color: var(--error);
}

.cp-hint {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.cp-warning {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.08);
  color: #92400e;
  font-size: 0.8125rem;
}

.cp-notice {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.08);
  color: #065f46;
  font-size: 0.8125rem;
  line-height: 1.6;
}

/* Buttons / 按钮 */
.cp-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.cp-btn {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast), opacity var(--transition-fast);
}

.cp-btn:not(:disabled):hover {
  border-color: var(--border-hover);
}

.cp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cp-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.cp-btn--primary:not(:disabled):hover {
  opacity: 0.9;
}

/* Checkbox / 复选框 */
.cp-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.cp-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
}

/* File chips / 文件标签 */
.cp-file-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.cp-file-chips li {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-surface-alt);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-family: var(--font-mono);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cp-file-chip-more {
  color: var(--primary) !important;
  font-weight: 600;
}

/* Stats / 统计 */
.cp-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.cp-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
}

.cp-stat--ok {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.06);
}

.cp-stat--bad {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.06);
}

.cp-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.cp-stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.cp-stat-value {
  font-family: var(--font-mono);
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cp-stat-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.cp-ratio {
  color: var(--primary);
}

/* Sample list / 样本列表 */
.cp-sample {
  border-top: 1px dashed var(--border);
  padding-top: 10px;
}

.cp-sample summary {
  cursor: pointer;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.cp-sample ul {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cp-sample li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.cp-kind {
  flex-shrink: 0;
  width: 46px;
  font-family: var(--font-mono);
  color: var(--text-muted);
}

.cp-sample-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
}

.cp-sample-size {
  flex-shrink: 0;
  font-family: var(--font-mono);
  color: var(--text-muted);
}

/* Trial / 试压缩 */
.cp-trial {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-primary);
}

.cp-trial-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.cp-trial-file {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cp-kv {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin: 0;
}

.cp-kv div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cp-kv dt {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.cp-kv dd {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cp-checks ul {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 6px;
}

.cp-checks li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8125rem;
  color: var(--text-primary);
}

.cp-check-icon {
  font-family: var(--font-mono);
  font-weight: 700;
}

.cp-ok {
  color: var(--secondary);
}

.cp-bad {
  color: var(--error);
}

/* Pills / 状态徽章 */
.cp-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 600;
  white-space: nowrap;
}

.cp-pill--ok {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.cp-pill--skip {
  background: rgba(100, 116, 139, 0.12);
  color: #475569;
}

.cp-pill--bad {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

/* Report / 报告 */
.cp-report {
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}

.cp-report h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cp-report h4 {
  margin: 0 0 8px;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cp-failures {
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.cp-failures ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.cp-failures li {
  display: flex;
  gap: 10px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.cp-fail-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono);
  color: var(--error);
}

.cp-fail-reason {
  flex-shrink: 0;
  max-width: 55%;
  color: var(--text-secondary);
}

/* Table / 表格 */
.cp-table-wrap {
  overflow-x: auto;
}

.cp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.cp-table th,
.cp-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  white-space: nowrap;
}

.cp-table th {
  color: var(--text-secondary);
  font-weight: 600;
  background: var(--bg-surface-alt);
}

.cp-table td {
  color: var(--text-primary);
}

.cp-num {
  text-align: right;
  font-family: var(--font-mono);
}

.cp-cell-path {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--font-mono);
}

.cp-cell-msg {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .cp-header {
    flex-direction: column;
  }
}
</style>
