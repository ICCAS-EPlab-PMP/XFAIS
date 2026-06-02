<template>
  <section class="h5extract-page" :data-testid="testIds.h5extractPage">
    <h1>{{ t('h5extract.title') }}</h1>
    <p class="page-subtitle">{{ t('h5extract.subtitle') }}</p>

    <!-- Directory selection / 目录选择 -->
    <fieldset class="h5e-fieldset">
      <legend>{{ t('h5extract.dirSection') }}</legend>
      <FileDialogButton
        v-model="sourceDir"
        mode="openFolder"
        :label="t('h5extract.sourceDir')"
        :data-testid="testIds.h5extractSourceDir"
      />
      <FileDialogButton
        v-model="targetDir"
        mode="openFolder"
        :label="t('h5extract.targetDir')"
        :data-testid="testIds.h5extractTargetDir"
      />
      <label class="h5e-checkbox-label">
        <input v-model="recursive" type="checkbox" />
        {{ t('h5extract.recursive') }}
      </label>
    </fieldset>

    <!-- File list preview / 文件列表预览 -->
    <fieldset class="h5e-fieldset">
      <legend>{{ t('h5extract.fileList.title') }}</legend>
      <div class="h5e-actions">
        <button
          type="button"
          class="h5e-btn"
          :disabled="!sourceDir || scanBusy"
          @click="handleScanFiles"
        >
          {{ scanBusy ? t('h5extract.fileList.scanning') : t('h5extract.fileList.scanBtn') }}
        </button>
        <span v-if="scannedFiles.length" class="h5e-hint">
          {{ t('h5extract.fileList.totalFiles', { total: scannedFiles.length }) }}
        </span>
      </div>

      <template v-if="scannedFiles.length">
        <details class="h5e-file-list-details" open>
          <summary class="h5e-file-list-summary">
            {{ t('h5extract.fileList.collapse') }}
          </summary>
          <div class="h5e-file-list-scroll">
            <table class="h5e-file-table">
              <thead>
                <tr>
                  <th class="col-idx">{{ t('h5extract.fileList.colIndex') }}</th>
                  <th class="col-name">{{ t('h5extract.fileList.colFileName') }}</th>
                  <th class="col-path">{{ t('h5extract.fileList.colPath') }}</th>
                  <th class="col-size">{{ t('h5extract.fileList.colSize') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(file, idx) in pagedFiles" :key="file.path">
                  <td class="col-idx">{{ (currentPage - 1) * PAGE_SIZE + idx + 1 }}</td>
                  <td class="col-name" :title="file.name">{{ file.name }}</td>
                  <td class="col-path" :title="file.path">{{ file.parentDir }}</td>
                  <td class="col-size">{{ formatSize(file.size) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="totalPages > 1" class="h5e-pagination">
            <button
              type="button"
              class="h5e-btn h5e-btn-sm"
              :disabled="currentPage <= 1"
              @click="currentPage--"
            >{{ t('h5extract.fileList.prevPage') }}</button>
            <span class="h5e-pagination-info">
              {{ t('h5extract.fileList.pageOf', { current: currentPage, total: totalPages }) }}
            </span>
            <button
              type="button"
              class="h5e-btn h5e-btn-sm"
              :disabled="currentPage >= totalPages"
              @click="currentPage++"
            >{{ t('h5extract.fileList.nextPage') }}</button>
          </div>
        </details>
      </template>
      <p v-else-if="scanBusy" class="h5e-hint">{{ t('h5extract.fileList.scanning') }}</p>
    </fieldset>

    <!-- Extraction rules / 提取规则 -->
    <fieldset class="h5e-fieldset">
      <legend>{{ t('h5extract.rulesSection') }}</legend>
      <div class="h5e-row">
        <label class="h5e-label" for="h5e-suffix">{{ t('h5extract.suffixFilter') }}</label>
        <input
          id="h5e-suffix"
          v-model="suffixFilter"
          class="h5e-input"
          type="text"
          :placeholder="t('h5extract.suffixPlaceholder')"
          :data-testid="testIds.h5extractSuffix"
        />
        <span class="h5e-hint">{{ t('h5extract.suffixHint') }}</span>
      </div>

      <label class="h5e-checkbox-label">
        <input
          v-model="prependFolder"
          type="checkbox"
          :data-testid="testIds.h5extractPrependFolder"
        />
        {{ t('h5extract.prependFolder') }}
      </label>

      <!-- Optional prefix / 可选前缀 -->
      <div class="h5e-row">
        <label class="h5e-label" for="h5e-prefix">{{ t('h5extract.prefix') }}</label>
        <input
          id="h5e-prefix"
          v-model="prefix"
          class="h5e-input"
          type="text"
          :placeholder="t('h5extract.prefixPlaceholder')"
          :data-testid="testIds.h5extractPrefix"
        />
      </div>

      <!-- Conflict resolution / 冲突处理 -->
      <div class="h5e-row">
        <label class="h5e-label">{{ t('h5extract.conflictPolicy') }}</label>
        <select
          v-model="conflictPolicy"
          class="h5e-select"
          :data-testid="testIds.h5extractConflictPolicy"
        >
          <option value="rename">{{ t('h5extract.conflictRename') }}</option>
          <option value="skip">{{ t('h5extract.conflictSkip') }}</option>
          <option value="overwrite">{{ t('h5extract.conflictOverwrite') }}</option>
        </select>
      </div>
    </fieldset>

    <!-- Start extraction / 开始提取 -->
    <div class="h5e-actions">
      <button
        type="button"
        class="h5e-btn h5e-btn-primary"
        :disabled="!canStart"
        :data-testid="testIds.h5extractStartBtn"
        @click="handleStart"
      >
        {{ t('h5extract.startExtract') }}
      </button>
    </div>

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
 * H5ExtractView.vue — H5 文件提取与汇总页面
 * H5 file extraction page: filter by suffix → copy/rename → conflict handling
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ResultSummary from '@/components/business/ResultSummary.vue'
import type { ResultSummaryData } from '@/components/business/ResultSummary.vue'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'

const { t } = useI18n()
const transport = useTransport()

interface ScannedFile {
  path: string
  name: string
  size: number
  parentDir: string
}

const PAGE_SIZE = 20

// Directory state / 目录状态
const sourceDir = ref<string | null>(null)
const targetDir = ref<string | null>(null)
const recursive = ref(true)

// Extraction rules / 提取规则
const suffixFilter = ref('')
const prependFolder = ref(true)
const prefix = ref('')
const conflictPolicy = ref<'rename' | 'skip' | 'overwrite'>('rename')

// Task state / 任务状态
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const resultSummary = ref<ResultSummaryData | null>(null)

// Scan state / 扫描状态
const scannedFiles = ref<ScannedFile[]>([])
const scanBusy = ref(false)
const currentPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(scannedFiles.value.length / PAGE_SIZE)))
const pagedFiles = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return scannedFiles.value.slice(start, start + PAGE_SIZE)
})

// Cleanup listeners on unmount / 卸载时清理监听器
let cleanupFns: Array<() => void> = []
onUnmounted(() => {
  cleanupFns.forEach(fn => fn())
  cleanupFns = []
})

const canStart = computed(() => {
  return sourceDir.value && targetDir.value && !taskId.value
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

async function handleScanFiles(): Promise<void> {
  if (!sourceDir.value) return
  scanBusy.value = true
  scannedFiles.value = []
  currentPage.value = 1

  try {
    const result = await transport.submitTask('h5_list_files', {
      sourceDir: sourceDir.value,
      suffix: suffixFilter.value || null,
      recursive: recursive.value,
    })

    const unsubResult = transport.onTaskResult(result.taskId, (payload) => {
      const data = payload.data as { files: ScannedFile[]; total: number }
      scannedFiles.value = data.files
      scanBusy.value = false
    })

    const unsubError = transport.onTaskError(result.taskId, () => {
      scanBusy.value = false
    })

    cleanupFns.push(unsubResult, unsubError)
  } catch {
    scanBusy.value = false
  }
}

watch(sourceDir, (newVal) => {
  if (newVal) {
    handleScanFiles()
  } else {
    scannedFiles.value = []
  }
})

/** Start extraction task / 开始提取任务 */
async function handleStart(): Promise<void> {
  if (!sourceDir.value || !targetDir.value) return

  resultSummary.value = null
  progress.value = 0
  progressMessage.value = null

  const result = await transport.submitTask('h5_extract', {
    sourceDir: sourceDir.value,
    targetDir: targetDir.value,
    suffix: suffixFilter.value || null,
    prependFolder: prependFolder.value,
    prefix: prefix.value || null,
    conflictPolicy: conflictPolicy.value,
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
.h5extract-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-subtitle {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
}

.h5e-fieldset {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.h5e-fieldset > legend {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--text-primary);
  padding: 0 8px;
}

.h5e-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.h5e-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
}

.h5e-input {
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

.h5e-input:focus {
  outline: none;
  border-color: var(--primary-light);
}

.h5e-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.h5e-select {
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.h5e-checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.h5e-actions {
  display: flex;
  gap: 12px;
}

.h5e-btn {
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

.h5e-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
}

.h5e-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.h5e-btn-primary {
  background: var(--primary-light);
  color: var(--text-inverse);
  border-color: var(--primary-light);
}

.h5e-btn-primary:hover:not(:disabled) {
  border-color: var(--primary);
}

.h5e-file-list-details {
  margin-top: 8px;
}

.h5e-file-list-summary {
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 4px 0;
  user-select: none;
}

.h5e-file-list-scroll {
  max-height: 420px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-top: 8px;
}

.h5e-file-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.h5e-file-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface);
  font-weight: 600;
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  z-index: 1;
}

.h5e-file-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 0;
}

.h5e-file-table tr:hover td {
  background: var(--bg-hover);
}

.col-idx { width: 48px; text-align: center; }
.col-name { width: 35%; }
.col-path { width: auto; }
.col-size { width: 90px; text-align: right; }

.h5e-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 10px;
}

.h5e-pagination-info {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.h5e-btn-sm {
  padding: 4px 12px;
  font-size: 0.75rem;
}
</style>
