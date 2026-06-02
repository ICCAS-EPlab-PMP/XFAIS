<template>
  <section :data-testid="testIds.fiberPage" class="fiber-page">
    <!-- Header / 页头 -->
    <header class="fiber-header">
      <h1>{{ t('integrateFiber.title') }}</h1>
      <p>{{ t('integrateFiber.subtitle') }}</p>
    </header>

    <div class="fiber-layout">
      <!-- ═══════ Sidebar ═══════ -->
      <aside class="fiber-sidebar">
        <GeometryForm v-model="geometry" />

        <!-- Mask Import (collapsible, collapsed by default) / 掩膜导入（可折叠，默认收起） -->
        <div class="fib-collapsible">
          <div class="fib-section-toggle" @click="maskExpanded = !maskExpanded">
            <span class="fib-toggle-icon">{{ maskExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.maskImport') }}</span>
          </div>
          <div v-show="maskExpanded" class="fib-collapsible-body">
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </div>
        </div>

        <PolarizationForm v-model="polarizationFactor" />

        <!-- Fiber rotation overrides / 纤维旋转参数 -->
        <fieldset class="fib-section">
          <legend>{{ t('integrateFiber.rotSection') }}</legend>
          <div class="fib-grid">
            <label class="fib-field">
              <span class="fib-label">rot1 (°)</span>
              <input
                type="number"
                class="fib-input"
                step="0.001"
                :value="fiberParams.rot1Deg"
                :data-testid="testIds.fiberRot1"
                @input="onFiberParam('rot1Deg', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">rot2 (°)</span>
              <input
                type="number"
                class="fib-input"
                step="0.001"
                :value="fiberParams.rot2Deg"
                :data-testid="testIds.fiberRot2"
                @input="onFiberParam('rot2Deg', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">rot3 (°)</span>
              <input
                type="number"
                class="fib-input"
                step="0.001"
                :value="fiberParams.rot3Deg"
                :data-testid="testIds.fiberRot3"
                @input="onFiberParam('rot3Deg', $event)"
              />
            </label>
          </div>
        </fieldset>

        <!-- Sample orientation / 样品方向 -->
        <fieldset class="fib-section">
          <legend>{{ t('integrateFiber.sampleSection') }}</legend>
          <div class="fib-grid">
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.sampleOrientation') }}</span>
              <select
                class="fib-select"
                :value="fiberParams.sampleOrientation"
                :data-testid="testIds.fiberOrientation"
                @change="onSelectParam('sampleOrientation', $event)"
              >
                <option v-for="o in 8" :key="o" :value="o">{{ o }}</option>
              </select>
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.incidentAngle') }}</span>
              <input
                type="number"
                class="fib-input"
                step="0.001"
                :value="fiberParams.incidentAngleDeg"
                :data-testid="testIds.fiberIncidentAngle"
                @input="onFiberParam('incidentAngleDeg', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.tiltAngle') }}</span>
              <input
                type="number"
                class="fib-input"
                step="0.001"
                :value="fiberParams.tiltAngleDeg"
                :data-testid="testIds.fiberTiltAngle"
                @input="onFiberParam('tiltAngleDeg', $event)"
              />
            </label>
          </div>
        </fieldset>

        <!-- Coordinate units / 坐标单位 -->
        <fieldset class="fib-section">
          <legend>{{ t('integrateFiber.unitsSection') }}</legend>
          <div class="fib-grid">
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.unitIp') }}</span>
              <select
                class="fib-select"
                :value="fiberParams.unitIp"
                :data-testid="testIds.fiberUnitIp"
                @change="onSelectParam('unitIp', $event)"
              >
                <option v-for="u in unitIpOptions" :key="u.value" :value="u.value">
                  {{ u.label }}
                </option>
              </select>
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.unitOop') }}</span>
              <select
                class="fib-select"
                :value="fiberParams.unitOop"
                :data-testid="testIds.fiberUnitOop"
                @change="onSelectParam('unitOop', $event)"
              >
                <option v-for="u in unitOopOptions" :key="u.value" :value="u.value">
                  {{ u.label }}
                </option>
              </select>
            </label>
          </div>
        </fieldset>

        <!-- Integration range / 积分范围 -->
        <fieldset class="fib-section">
          <legend>{{ t('integrateFiber.rangeSection') }}</legend>
          <label class="fib-toggle">
            <input
              type="checkbox"
              :checked="fiberParams.autoRange"
              :data-testid="testIds.fiberAutoRange"
              @change="onToggleAutoRange"
            />
            <span class="fib-toggle-label">{{ t('integrateFiber.autoRange') }}</span>
          </label>

          <div v-if="!fiberParams.autoRange" class="fib-grid fib-range-grid">
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.ipMin') }}</span>
              <input
                type="number"
                class="fib-input"
                step="0.1"
                :value="fiberParams.ipMin"
                :data-testid="testIds.fiberIpMin"
                @input="onFiberParam('ipMin', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.ipMax') }}</span>
              <input
                type="number"
                class="fib-input"
                step="0.1"
                :value="fiberParams.ipMax"
                :data-testid="testIds.fiberIpMax"
                @input="onFiberParam('ipMax', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.oopMin') }}</span>
              <input
                type="number"
                class="fib-input"
                step="0.1"
                :value="fiberParams.oopMin"
                :data-testid="testIds.fiberOopMin"
                @input="onFiberParam('oopMin', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.oopMax') }}</span>
              <input
                type="number"
                class="fib-input"
                step="0.1"
                :value="fiberParams.oopMax"
                :data-testid="testIds.fiberOopMax"
                @input="onFiberParam('oopMax', $event)"
              />
            </label>
          </div>
        </fieldset>

        <!-- npt_ip / npt_oop / 点数 -->
        <fieldset class="fib-section">
          <legend>{{ t('integrateFiber.nptSection') }}</legend>
          <div class="fib-grid">
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.nptIp') }}</span>
              <input
                type="number"
                class="fib-input"
                min="50"
                step="50"
                :value="fiberParams.nptIp"
                :data-testid="testIds.fiberNptIp"
                @input="onFiberParam('nptIp', $event)"
              />
            </label>
            <label class="fib-field">
              <span class="fib-label">{{ t('integrateFiber.nptOop') }}</span>
              <input
                type="number"
                class="fib-input"
                min="50"
                step="50"
                :value="fiberParams.nptOop"
                :data-testid="testIds.fiberNptOop"
                @input="onFiberParam('nptOop', $event)"
              />
            </label>
          </div>
        </fieldset>

        <!-- Solid angle / 立体角 -->
        <fieldset class="fib-section">
          <label class="fib-toggle">
            <input
              type="checkbox"
              :checked="correctSolidAngle"
              :data-testid="testIds.fiberSolidAngle"
              @change="correctSolidAngle = !correctSolidAngle"
            />
            <span class="fib-toggle-label">{{ t('integrateFiber.correctSolidAngle') }}</span>
          </label>
        </fieldset>

        <!-- Display settings (collapsible, default collapsed) / 显示设置（可折叠，默认收起） -->
        <div class="fib-collapsible">
          <div class="fib-section-toggle" @click="displayExpanded = !displayExpanded">
            <span class="fib-toggle-icon">{{ displayExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.displaySettings') }}</span>
          </div>
          <div v-show="displayExpanded" class="fib-collapsible-body">
            <div class="fib-field">
              <label class="fib-label">{{ t('business.display.colormap') }}</label>
              <select v-model="colormap" class="fib-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">
                  {{ getColormapDisplayName(cm) }}
                </option>
              </select>
            </div>
            <label class="fib-toggle">
              <input v-model="useLog" type="checkbox" />
              <span class="fib-toggle-label">{{ t('business.display.logScale') }}</span>
            </label>
          </div>
        </div>
      </aside>

      <!-- ═══════ Main content area ═══════ -->
      <main class="fiber-main">
        <!-- File selection / 文件选择 -->
        <div class="fib-file-section">
          <h2 class="fib-section-title">{{ t('integrate1d.dataFiles') }}</h2>
          <div class="fib-file-buttons">
            <button type="button" class="fib-file-btn" @click="handleChooseFiles">
              {{ t('business.fileSelection.selectFiles') }}
            </button>
            <button
              type="button"
              class="fib-file-btn"
              :disabled="!transport.isDesktop()"
              :title="!transport.isDesktop() ? t('business.fileSelection.folderNotAvailableInWeb') : ''"
              @click="handleImportFolder"
            >
              {{ t('business.fileSelection.importFolder') }}
            </button>
            <label class="fib-toggle">
              <input v-model="isRecursive" type="checkbox" />
              <span class="fib-toggle-label">{{ t('business.fileSelection.recursive') }}</span>
            </label>
            <div class="fib-import-mode">
              <span class="fib-import-mode-label">{{ t('business.fileSelection.importMode') }}</span>
              <label class="fib-radio-label" :title="t('business.fileSelection.replaceTooltip')">
                <input v-model="importMode" type="radio" value="replace" />
                <span>{{ t('business.fileSelection.replace') }}</span>
              </label>
              <label class="fib-radio-label" :title="t('business.fileSelection.appendTooltip')">
                <input v-model="importMode" type="radio" value="append" />
                <span>{{ t('business.fileSelection.append') }}</span>
              </label>
            </div>
          </div>

          <!-- File count indicator / 文件计数指示器 -->
          <div v-if="files.length > 0" class="fib-file-info-bar">
            <span class="fib-file-name">
              {{ t('business.fileSelection.filesSelected', { count: files.length }) }}
            </span>
            <button type="button" class="fib-clear-btn" @click="clearAllFiles">
              {{ t('business.fileSelection.clearAll') }}
            </button>
          </div>
          <div v-else class="fib-file-info-bar fib-file-info-bar--muted">
            <span>{{ t('business.fileSelection.noFiles') }}</span>
          </div>
        </div>

        <!-- Image preview (collapsible) / 图像预览（可折叠） -->
        <div class="fib-collapsible">
          <div class="fib-section-toggle" @click="onPreviewToggle">
            <span class="fib-toggle-icon">{{ previewExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.imagePreview') }}</span>
          </div>
          <div v-show="previewExpanded" class="fib-collapsible-body">
            <div v-if="previewLoading" class="fib-preview-loading">
              {{ t('business.sections.loading') }}
            </div>
            <div v-else-if="previewB64" class="fib-preview-area">
              <div class="fib-preview-image">
                <ImagePreview
                  :image-b64="previewB64"
                  :overlays="beamCenterOverlay"
                  :show-colorbar="true"
                  :colorbar-gradient="colorbarGradient"
                  :colorbar-min-label="colorbarMinLabel"
                  :colorbar-max-label="colorbarMaxLabel"
                  :placeholder="t('business.sections.noImage')"
                />
              </div>
              <div class="fib-preview-info">
                <h4 class="fib-info-title">{{ t('business.sections.imageInfo') }}</h4>
                <div v-if="currentPreviewFileName" class="fib-info-item">
                  <span class="fib-info-label">{{ t('business.sections.fileName') }}</span>
                  <span class="fib-info-value">{{ currentPreviewFileName }}</span>
                </div>
                <template v-if="previewStats">
                  <div class="fib-info-item">
                    <span class="fib-info-label">Min</span>
                    <span class="fib-info-value">{{ formatSci(previewStats.min) }}</span>
                  </div>
                  <div class="fib-info-item">
                    <span class="fib-info-label">Max</span>
                    <span class="fib-info-value">{{ formatSci(previewStats.max) }}</span>
                  </div>
                  <div class="fib-info-item">
                    <span class="fib-info-label">Std</span>
                    <span class="fib-info-value">{{ formatSci(previewStats.std) }}</span>
                  </div>
                </template>
                <template v-if="autoContrast">
                  <div class="fib-info-item">
                    <span class="fib-info-label">Auto range</span>
                    <span class="fib-info-value">{{ formatSci(autoContrast.autoMin) }} – {{ formatSci(autoContrast.autoMax) }}</span>
                  </div>
                </template>
                <div v-if="resolvedBeamCenter" class="fib-info-item">
                  <span class="fib-info-label">{{ t('business.sections.beamCenter') }}</span>
                  <span class="fib-info-value">{{ beamCenterLabel }}</span>
                </div>
              </div>
            </div>
            <div v-else class="fib-preview-empty">
              {{ t('business.fileSelection.expandAfterSelect') }}
            </div>
          </div>
        </div>

        <!-- Thumbnail strip (collapsible, default collapsed) / 缩略图（可折叠，默认收起） -->
        <div class="fib-collapsible">
          <div class="fib-section-toggle" @click="onThumbToggle">
            <span class="fib-toggle-icon">{{ thumbExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.thumbnails') }}</span>
          </div>
          <div v-show="thumbExpanded" class="fib-collapsible-body">
            <ThumbnailStrip
              :items="thumbnailItems"
              :selected-index="selectedPreviewIndex"
              :current-page="thumbCurrentPage"
              :total-pages="thumbTotalPages"
              :page-size="thumbPageSize"
              :loading="thumbLoading"
              :sync-with-main="false"
              :columns-per-row="thumbColsPerRow"
              @select="handleThumbSelect"
              @prev-page="handleThumbPrevPage"
              @next-page="handleThumbNextPage"
              @jump-to-page="handleThumbJumpToPage"
              @page-size-change="handleThumbPageSizeChange"
              @update:columns-per-row="thumbColsPerRow = $event"
            />
          </div>
        </div>

        <!-- Run buttons / 执行按钮 -->
        <div class="fib-run-section">
          <button
            type="button"
            class="fib-run-btn"
            :disabled="!canRun || isPreviewRunning || isBatchRunning"
            :data-testid="testIds.fiberRunBtn"
            @click="runPreviewIntegration"
          >
            {{ isPreviewRunning ? t('integrateFiber.running') : t('integrateFiber.preview') }}
          </button>
          <label class="fib-batch-format">
            <span class="fib-batch-format-label">{{ t('business.sections.format') }}</span>
            <select v-model="batchExportFormat" class="fib-select" style="width:auto;min-width:70px">
              <option value="npy">NPY</option>
              <option value="hdf5">HDF5</option>
              <option value="tiff">TIFF</option>
              <option value="edf">EDF</option>
            </select>
          </label>
          <button
            type="button"
            class="fib-run-btn fib-batch-btn"
            :disabled="!canRun || isBatchRunning || isPreviewRunning"
            @click="onBatchToFolder"
          >
            {{ isBatchRunning ? t('business.taskProgress.processing') : t('integrateFiber.batchExportFolder') }}
          </button>
          <span v-if="validationError" class="fib-error" :data-testid="testIds.fiberError">
            {{ validationError }}
          </span>
        </div>

        <!-- Preview progress / 预览进度 -->
        <TaskProgressBar
          v-if="isPreviewRunning"
          :task-id="previewTaskId"
          :progress="previewProgress"
          :message="previewProgressMessage"
          @cancel="onCancelPreview"
        />

        <!-- Batch progress / 批量进度 -->
        <TaskProgressBar
          v-if="isBatchRunning"
          :task-id="batchTaskId"
          :progress="batchProgress"
          :message="batchProgressMessage"
          @cancel="onCancelBatch"
        />

        <div v-if="previewError" class="fib-error-box">
          <p>{{ previewError }}</p>
        </div>
        <div v-if="batchError" class="fib-error-box">
          <p>{{ batchError }}</p>
        </div>

        <!-- 2D Heatmap / 二维热力图 -->
        <section v-if="result" class="fib-result">
          <div class="fib-result-header">
            <div>
              <h2>{{ t('integrateFiber.result2dTitle') }}</h2>
              <p class="fib-result-meta">
                {{ result.filename ?? resultSummaries[currentResultIndex]?.filename ?? `Result ${currentResultIndex + 1}` }}
                <span v-if="resultSummaries.length > 1">（{{ currentResultIndex + 1 }} / {{ resultSummaries.length }}）</span>
              </p>
            </div>
          </div>

          <div v-if="resultSummaries.length > 1" class="fib-result-thumbs">
            <ThumbnailStrip
              :items="resultThumbnailItems"
              :selected-index="currentResultIndex"
              :current-page="resultThumbCurrentPage"
              :total-pages="resultThumbTotalPages"
              :page-size="resultThumbPageSize"
              :loading="resultThumbLoading"
              :sync-with-main="false"
              :columns-per-row="resultThumbColsPerRow"
              @select="loadFiberResult"
              @prev-page="() => { if (resultThumbCurrentPage > 1) { resultThumbCurrentPage -= 1; loadFiberResultThumbnails() } }"
              @next-page="() => { if (resultThumbCurrentPage < resultThumbTotalPages) { resultThumbCurrentPage += 1; loadFiberResultThumbnails() } }"
              @jump-to-page="(page) => { resultThumbCurrentPage = page; loadFiberResultThumbnails(page) }"
              @page-size-change="(size) => { resultThumbPageSize = size; resultThumbCurrentPage = 1; loadFiberResultThumbnails(1) }"
              @update:columns-per-row="resultThumbColsPerRow = $event"
            />
          </div>

          <div class="fib-chart-container">
            <ImagePreview
              :image-b64="result.previewB64"
              :show-colorbar="true"
              :colorbar-gradient="colorbarGradient"
              :colorbar-min-label="heatmapZMin !== undefined ? formatSci(heatmapZMin) : colorbarMinLabel"
              :colorbar-max-label="heatmapZMax !== undefined ? formatSci(heatmapZMax) : colorbarMaxLabel"
              :title="t('integrateFiber.heatmapTitle')"
              :data-testid="testIds.fiberHeatmap"
            />
          </div>

          <div class="fib-chart-controls">
            <label class="fib-toggle">
              <input
                type="checkbox"
                :checked="logScale"
                @change="logScale = !logScale"
              />
              <span class="fib-toggle-label">{{ t('integrateFiber.logScale') }}</span>
            </label>
            <label class="fib-field fib-contrast-field">
              <span class="fib-label">{{ t('business.sections.contrastMode') }}</span>
              <select v-model="resultClimMode" class="fib-select">
                <option value="auto">{{ t('business.display.climAuto') }}</option>
                <option value="manual">{{ t('business.display.climManual') }}</option>
              </select>
            </label>
            <label v-if="resultClimMode === 'manual'" class="fib-field fib-contrast-field">
              <span class="fib-label">{{ t('business.display.climMin') }}</span>
              <input v-model.number="resultClimMin" type="number" class="fib-input" step="any" />
            </label>
            <label v-if="resultClimMode === 'manual'" class="fib-field fib-contrast-field">
              <span class="fib-label">{{ t('business.display.climMax') }}</span>
              <input v-model.number="resultClimMax" type="number" class="fib-input" step="any" />
            </label>
          </div>

          <!-- Export / 导出 -->
          <ExportDialog
            :formats="exportFormats"
            :data-testid="testIds.fiberExport"
            @export="onExport"
          />
        </section>

        <!-- ═══════ Batch-to-folder results / 批量导出结果 ═══════ -->
        <section v-if="exportedFiles.length > 0" class="fib-exported-section">
          <div class="fib-result-header">
            <h2>{{ t('integrateFiber.batchExportComplete') }}</h2>
          </div>
          <div class="fib-memory-warning">
            {{ t('integrateFiber.memoryWarning') }}
          </div>
          <div class="fib-exported-list">
            <div v-for="(file, i) in exportedFiles.slice(0, exportedPreviewLimit)" :key="i" class="fib-exported-item">
              <span class="fib-exported-name" :title="file">{{ file.replace(/^.*[\\/]/, '') }}</span>
              <button
                type="button"
                class="fib-file-btn"
                :disabled="viewingExported"
                @click="viewExportedResult(file)"
              >
                {{ t('integrateFiber.loadToView') }}
              </button>
            </div>
            <div v-if="exportedFiles.length > exportedPreviewLimit" class="fib-exported-more">
              {{ t('integrateFiber.moreFiles', { count: exportedFiles.length - exportedPreviewLimit }) }}
            </div>
          </div>
        </section>

        <!-- Empty state / 空状态 -->
        <div v-else-if="!isPreviewRunning && !isBatchRunning && !result && !previewError && !batchError" class="fib-empty">
          <p>{{ t('integrateFiber.emptyHint') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * IntegrateFiberView.vue — GIWAXS 纤维衍射 2D 积分页面
 * GIWAXS Fiber 2-D Integration page
 *
 * Performs 2-D grazing-incidence integration (qip × qoop map)
 * using pyFAI's FiberIntegrator via the desktop task bridge.
 */
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { testIds } from '@/lib/testIds'
import { COLORMAP_PRESETS, COLORMAP_DISPLAY_NAMES, resolveColorbarGradient } from '@/lib/chart-utils'
import type { ColormapName } from '@/lib/chart-utils'

import type { GeometryParams } from '@/components/business/GeometryForm.vue'
import type { MaskConfig } from '@/components/business/MaskBuilderForm.vue'
import type { ExportFormat, ExportMode } from '@/components/business/ExportDialog.vue'
import GeometryForm from '@/components/business/GeometryForm.vue'
import MaskBuilderForm from '@/components/business/MaskBuilderForm.vue'
import PolarizationForm from '@/components/business/PolarizationForm.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ExportDialog from '@/components/business/ExportDialog.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'
import type { Overlay } from '@/components/charts/ImagePreview.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'

// === Type definitions / 类型定义 ===

interface PreviewMetadata {
  stats?: { min: number; max: number; adjustedMax: number; std: number }
  contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
  shape?: [number, number]
  width?: number
  height?: number
  metadata?: {
    width?: number
    height?: number
  }
}

interface GeometryCenterResult {
  centerX?: number
  centerY?: number
}

interface ScanFolderResult {
  files?: string[]
}

// ── Unit definitions (mirrored from Streamlit reference) ─────────────────
// 单位定义（与 Streamlit 参考保持一致）

const FIBER_UNITS_IP = [
  'qip_nm^-1', 'qip_A^-1',
  'qxgi_nm^-1', 'qygi_nm^-1', 'qzgi_nm^-1', 'qtot_nm^-1',
  'qxgi_A^-1', 'qygi_A^-1', 'qzgi_A^-1', 'qtot_A^-1',
  'scattering_angle_horz_rad', 'exit_angle_horz_rad', 'exit_angle_horz_deg',
  'chigi_rad', 'chigi_deg',
] as const

const FIBER_UNITS_OOP = [
  'qoop_nm^-1', 'qoop_A^-1',
  'qxgi_nm^-1', 'qygi_nm^-1', 'qzgi_nm^-1', 'qtot_nm^-1',
  'qxgi_A^-1', 'qygi_A^-1', 'qzgi_A^-1', 'qtot_A^-1',
  'scattering_angle_vert_rad', 'exit_angle_vert_rad', 'exit_angle_vert_deg',
  'chigi_rad', 'chigi_deg',
] as const

type FiberUnitIp = (typeof FIBER_UNITS_IP)[number]
type FiberUnitOop = (typeof FIBER_UNITS_OOP)[number]

const UNIT_LABELS: Record<string, string> = {
  'qip_nm^-1':                'q_ip (nm⁻¹)',
  'qoop_nm^-1':               'q_oop (nm⁻¹)',
  'qip_A^-1':                 'q_ip (Å⁻¹)',
  'qoop_A^-1':                'q_oop (Å⁻¹)',
  'qxgi_nm^-1':               'q_xgi (nm⁻¹)',
  'qygi_nm^-1':               'q_ygi (nm⁻¹)',
  'qzgi_nm^-1':               'q_zgi (nm⁻¹)',
  'qtot_nm^-1':               'q_tot (nm⁻¹)',
  'qxgi_A^-1':                'q_xgi (Å⁻¹)',
  'qygi_A^-1':                'q_ygi (Å⁻¹)',
  'qzgi_A^-1':                'q_zgi (Å⁻¹)',
  'qtot_A^-1':                'q_tot (Å⁻¹)',
  'scattering_angle_horz_rad':'2θ_horz (rad)',
  'scattering_angle_vert_rad':'2θ_vert (rad)',
  'exit_angle_horz_rad':      'α_horz (rad)',
  'exit_angle_vert_rad':      'α_vert (rad)',
  'exit_angle_horz_deg':      'α_horz (°)',
  'exit_angle_vert_deg':      'α_vert (°)',
  'chigi_rad':                'χ_gi (rad)',
  'chigi_deg':                'χ_gi (°)',
}

/** Default range hints per unit key / 各单位默认范围 */
const UNIT_RANGE_HINT: Record<string, [number, number]> = {
  'qip_nm^-1':                [-20, 20],
  'qoop_nm^-1':               [-20, 20],
  'qip_A^-1':                 [-2, 2],
  'qoop_A^-1':                [-2, 2],
  'qxgi_nm^-1':               [-20, 20],
  'qygi_nm^-1':               [-20, 20],
  'qzgi_nm^-1':               [-20, 20],
  'qtot_nm^-1':               [0, 30],
  'qxgi_A^-1':                [-2, 2],
  'qygi_A^-1':                [-2, 2],
  'qzgi_A^-1':                [-2, 2],
  'qtot_A^-1':                [0, 3],
  'scattering_angle_horz_rad':[-0.5, 0.5],
  'scattering_angle_vert_rad':[-0.5, 0.5],
  'exit_angle_horz_rad':      [-0.5, 0.5],
  'exit_angle_vert_rad':      [-0.5, 0.5],
  'exit_angle_horz_deg':      [-30, 30],
  'exit_angle_vert_deg':      [-30, 30],
  'chigi_rad':                [-3.14, 3.14],
  'chigi_deg':                [-180, 180],
}

// ── Types ─────────────────────────────────────────────────────────────────

/** Fiber integration result from backend / 后端纤维积分结果 */
interface FiberResult {
  previewB64?: string | null
  intensity: (number | null)[][]
  axisIp: number[]
  axisOop: number[]
  unitIp: string
  unitOop: string
  filename?: string
  batchCachePath?: string
}

interface FiberResultSummary {
  stem?: string
  filename?: string
  intensity_shape?: number[]
}

/** Fiber-specific parameters / 纤维专用参数 */
interface FiberParams {
  rot1Deg: number
  rot2Deg: number
  rot3Deg: number
  sampleOrientation: number
  incidentAngleDeg: number
  tiltAngleDeg: number
  unitIp: FiberUnitIp
  unitOop: FiberUnitOop
  autoRange: boolean
  ipMin: number
  ipMax: number
  oopMin: number
  oopMax: number
  nptIp: number
  nptOop: number
}

// ── i18n ──────────────────────────────────────────────────────────────────

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// ── Colormap options / 色图选项 ──

const colormapOptions = [
  'smooth_WAXS_foxtrot',
  'smooth_WAXS_fit2D',
  ...Object.keys(COLORMAP_PRESETS).filter(k => k !== 'foxtrot' && k !== 'fit2d'),
] as string[]

function getColormapDisplayName(key: string): string {
  if (key === 'smooth_WAXS_foxtrot') return 'Foxtrot (WAXS)'
  if (key === 'smooth_WAXS_fit2D') return 'FIT2D (WAXS)'
  if (key in COLORMAP_DISPLAY_NAMES) return COLORMAP_DISPLAY_NAMES[key as ColormapName]
  return key
}

// ── State ─────────────────────────────────────────────────────────────────

const filePath = ref<string | null>(null)

// === File state / 文件状态 ===

const files = ref<string[]>([])
const isRecursive = ref(false)
const importFolderPath = ref<string | null>(null)
type ImportMode = 'replace' | 'append'
const importMode = ref<ImportMode>('replace')

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

/** Preview selection index — must be declared before activeFilePath / 预览选择索引 — 必须在 activeFilePath 之前声明 */
const selectedPreviewIndex = ref(0)

/** Current active file derived from selected preview index / 当前活动文件由预览选择索引派生 */
const activeFilePath = computed(() => files.value[selectedPreviewIndex.value] ?? null)

/** Keep filePath in sync for backward compat / 保持 filePath 同步以兼容 */
watch(activeFilePath, (v) => { filePath.value = v }, { immediate: true })

const fileName = computed(() => {
  if (!filePath.value) return ''
  const sep = filePath.value.includes('/') ? '/' : '\\'
  return filePath.value.split(sep).pop() ?? filePath.value
})

const currentPreviewFileName = computed(() => {
  const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  return path.split(sep).pop() ?? path
})

function clearAllFiles(): void {
  files.value = []
  importFolderPath.value = null
  if (previewB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewB64.value)
  }
  previewB64.value = null
  previewStats.value = null
  autoContrast.value = null
  previewImageSize.value = null
  selectedPreviewIndex.value = 0
  thumbnailItems.value = []
  result.value = null
  batchCachePath.value = null
  resultSummaries.value = []
  currentResultIndex.value = 0
  resultThumbnailItems.value = []
  resultContrast.value = null
}

const geometry = ref<GeometryParams>({
  pixel1: 172,
  pixel2: 172,
  distance: 200,
  wavelength: 1.5418,
  centerX: 512,
  centerY: 512,
})

const fiberParams = reactive<FiberParams>({
  rot1Deg: 0,
  rot2Deg: 0,
  rot3Deg: 0,
  sampleOrientation: 1,
  incidentAngleDeg: 0,
  tiltAngleDeg: 0,
  unitIp: 'qip_nm^-1',
  unitOop: 'qoop_nm^-1',
  autoRange: false,
  ipMin: -20,
  ipMax: 20,
  oopMin: -20,
  oopMax: 20,
  nptIp: 800,
  nptOop: 800,
})

const maskConfig = ref<MaskConfig>({
  valueRangeMin: 0,
  valueRangeMax: 1e10,
  deadPixelThreshold: 0,
  customMaskPath: null,
})

const polarizationFactor = ref<number | null>(null)
const correctSolidAngle = ref(true)

// ── Preview (single-file) mode / 预览积分 ──
const isPreviewRunning = ref(false)
const previewTaskId = ref<string | null>(null)
const previewProgress = ref(0)
const previewProgressMessage = ref<string | null>(null)
const previewError = ref<string | null>(null)

// ── Batch-to-folder mode / 积分到文件夹 ──
const isBatchRunning = ref(false)
const batchTaskId = ref<string | null>(null)
const batchProgress = ref(0)
const batchProgressMessage = ref<string | null>(null)
const batchError = ref<string | null>(null)

// ── Exported file list / 已导出文件列表 ──
const exportedFiles = ref<string[]>([])
const exportedDir = ref<string | null>(null)
const exportedFormat = ref<string>('npy')
const batchExportFormat = ref<string>('npy')
const exportedPreviewLimit = ref(20)
const viewingExported = ref(false)

// ── Result state / 结果状态 ──
const result = ref<FiberResult | null>(null)
const logScale = ref(false)
const batchCachePath = ref<string | null>(null)
const resultSummaries = ref<FiberResultSummary[]>([])
const currentResultIndex = ref(0)
const resultThumbnailItems = ref<ThumbnailItem[]>([])
const resultThumbLoading = ref(false)
const resultThumbCurrentPage = ref(1)
const resultThumbPageSize = ref(10)
const resultThumbColsPerRow = ref(10)
const resultContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const resultClimMode = ref<'auto' | 'manual'>('auto')
const resultClimMin = ref<number | null>(null)
const resultClimMax = ref<number | null>(null)

// ── Preview state / 预览状态 ──

const previewB64 = ref<string | null>(null)
const previewStats = ref<{ min: number; max: number; adjustedMax: number; std: number } | null>(null)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const previewLoading = ref(false)
const resolvedBeamCenter = ref<{ x: number; y: number } | null>(
  { x: geometry.value.centerX, y: geometry.value.centerY }
)
const previewImageSize = ref<{ width: number; height: number; origWidth: number; origHeight: number } | null>(null)

// ── Display settings / 显示设置 ──

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(true)

// ── Collapsible section state / 折叠区域状态 ──

const previewExpanded = ref(true)
const thumbExpanded = ref(false)
const displayExpanded = ref(false)
const maskExpanded = ref(false)

// ── Thumbnail state / 缩略图状态 ──

const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbCurrentPage = ref(1)
const thumbPageSize = ref(10)
const thumbColsPerRow = ref(10)
const thumbLoading = ref(false)

// Cleanup / 清理
let cleanupPreviewBinary: (() => void) | null = null
let cleanupPreviewResult: (() => void) | null = null
let cleanupPreviewError: (() => void) | null = null

// ── Unit select options / 单位选择项 ──────────────────────────────────────

const unitIpOptions = computed(() =>
  FIBER_UNITS_IP.map((u) => ({ value: u, label: UNIT_LABELS[u] ?? u }))
)
const unitOopOptions = computed(() =>
  FIBER_UNITS_OOP.map((u) => ({ value: u, label: UNIT_LABELS[u] ?? u }))
)

// ── Sync range defaults when unit changes / 单位变更时同步范围默认值 ────

watch(() => fiberParams.unitIp, (newUnit) => {
  const hint = UNIT_RANGE_HINT[newUnit]
  if (hint) {
    fiberParams.ipMin = hint[0]
    fiberParams.ipMax = hint[1]
  }
})

watch(() => fiberParams.unitOop, (newUnit) => {
  const hint = UNIT_RANGE_HINT[newUnit]
  if (hint) {
    fiberParams.oopMin = hint[0]
    fiberParams.oopMax = hint[1]
  }
})

// ── Computed ──────────────────────────────────────────────────────────────

const exportFormats: ExportFormat[] = ['tiff', 'edf', 'npy', 'hdf5', 'csv', 'xy']

/** Parameter validation / 参数校验 */
const validationError = computed<string | null>(() => {
  if (files.value.length === 0) return t('integrateFiber.errorNoFile')
  if (!geometry.value.poniPath && geometry.value.distance <= 0) {
    return t('integrateFiber.errorNoGeometry')
  }
  if (!fiberParams.autoRange) {
    if (fiberParams.ipMin >= fiberParams.ipMax) {
      return t('integrateFiber.errorIpRange')
    }
    if (fiberParams.oopMin >= fiberParams.oopMax) {
      return t('integrateFiber.errorOopRange')
    }
  }
  if (fiberParams.nptIp < 50 || fiberParams.nptOop < 50) {
    return t('integrateFiber.errorNpt')
  }
  return null
})

const canRun = computed(() => files.value.length > 0 && !validationError.value)

const thumbTotalPages = computed(() =>
  Math.max(1, Math.ceil(files.value.length / thumbPageSize.value))
)

const resultThumbTotalPages = computed(() =>
  Math.max(1, Math.ceil(resultSummaries.value.length / resultThumbPageSize.value))
)

const heatmapZMin = computed(() => {
  if (resultClimMode.value !== 'manual') {
    if (!resultContrast.value) return undefined
    return useLog.value ? resultContrast.value.logMin : resultContrast.value.autoMin
  }
  return resultClimMin.value ?? undefined
})

const heatmapZMax = computed(() => {
  if (resultClimMode.value !== 'manual') {
    if (!resultContrast.value) return undefined
    return useLog.value ? resultContrast.value.logMax : resultContrast.value.autoMax
  }
  return resultClimMax.value ?? undefined
})

const colorbarGradient = computed(() => resolveColorbarGradient(colormap.value))

const colorbarMinLabel = computed(() => {
  if (!autoContrast.value) return '0'
  return useLog.value
    ? autoContrast.value.logMin.toExponential(3)
    : autoContrast.value.autoMin.toExponential(3)
})

const colorbarMaxLabel = computed(() => {
  if (!autoContrast.value) return '1'
  return useLog.value
    ? autoContrast.value.logMax.toExponential(3)
    : autoContrast.value.autoMax.toExponential(3)
})

const beamCenterOverlay = computed<Overlay[]>(() => {
  if (!resolvedBeamCenter.value || !previewImageSize.value) return []
  const px = resolvedBeamCenter.value.x
  const py = resolvedBeamCenter.value.y
  if (!Number.isFinite(px) || !Number.isFinite(py)) return []
  return [{ type: 'beamCenter', x: px, y: py }]
})

const beamCenterLabel = computed(() => {
  if (!resolvedBeamCenter.value) return '—'
  return `(${resolvedBeamCenter.value.x.toFixed(2)}, ${resolvedBeamCenter.value.y.toFixed(2)})`
})

// ── Helpers ───────────────────────────────────────────────────────────────

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

function unitLabel(unitKey: string): string {
  return UNIT_LABELS[unitKey] ?? unitKey
}

function submitAndWait(route: string, params: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      transport.onTaskResult(response.taskId, (p) => resolve(p.data))
      transport.onTaskError(response.taskId, (p) => reject(new Error(p.error)))
    }).catch(reject)
  })
}

async function loadFiberResult(index: number): Promise<void> {
  if (!batchCachePath.value) return
  const raw = await submitAndWait('viewer_config', {
    action: 'fiber_result_preview',
    batchCachePath: batchCachePath.value,
    resultIndex: index,
    settings: {
      cmap: colormap.value,
      use_log: useLog.value,
      clim_mode: resultClimMode.value,
      clim: resultClimMode.value === 'manual'
        ? [resultClimMin.value, resultClimMax.value]
        : [null, null],
    },
  })
  const data = raw as {
    displayB64?: string
    imageData?: (number | null)[][]
    axisIp?: number[]
    axisOop?: number[]
    filename?: string
    contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
  }
  result.value = {
    previewB64: data.displayB64 ?? null,
    intensity: data.imageData ?? [],
    axisIp: data.axisIp ?? [],
    axisOop: data.axisOop ?? [],
    unitIp: fiberParams.unitIp,
    unitOop: fiberParams.unitOop,
    filename: data.filename,
    batchCachePath: batchCachePath.value ?? undefined,
  }
  resultContrast.value = data.contrast ?? null
  if (resultClimMode.value === 'auto' && resultContrast.value) {
    resultClimMin.value = useLog.value ? resultContrast.value.logMin : resultContrast.value.autoMin
    resultClimMax.value = useLog.value ? resultContrast.value.logMax : resultContrast.value.autoMax
  }
  currentResultIndex.value = index

}

async function loadFiberResultThumbnails(page?: number): Promise<void> {
  if (!batchCachePath.value || resultSummaries.value.length === 0) return
  const currentPage = page ?? resultThumbCurrentPage.value
  const start = (currentPage - 1) * resultThumbPageSize.value
  const count = resultThumbPageSize.value
  const slice = resultSummaries.value.slice(start, start + count)
  resultThumbLoading.value = true
  try {
    const items: ThumbnailItem[] = []
    for (let i = 0; i < slice.length; i++) {
      const idx = start + i
      const raw = await submitAndWait('viewer_config', {
        action: 'fiber_result_preview',
        batchCachePath: batchCachePath.value,
        resultIndex: idx,
        thumbnailOnly: true,
        settings: {
          cmap: colormap.value,
          use_log: useLog.value,
          clim_mode: 'auto',
          clim: [null, null],
        },
      })
      const data = raw as { previewB64?: string; filename?: string }
      items.push({
        index: idx,
        b64: data.previewB64 ?? '',
        label: data.filename ?? slice[i]?.filename ?? `Result ${idx + 1}`,
      })
    }
    resultThumbnailItems.value = items
  } catch {
    resultThumbnailItems.value = []
  } finally {
    resultThumbLoading.value = false
  }
}

function buildRenderSettings(): Record<string, unknown> {
  return {
    cmap: colormap.value,
    use_log: useLog.value,
    clim_mode: 'auto',
    clim: [null, null],
    preview_scale: 1.0,
  }
}

function buildGeometryPayload(): Record<string, unknown> {
  return {
    poniPath: geometry.value.poniPath ?? undefined,
    pixel1: geometry.value.pixel1,
    pixel2: geometry.value.pixel2,
    distance: geometry.value.distance,
    wavelength: geometry.value.wavelength,
    centerX: geometry.value.centerX,
    centerY: geometry.value.centerY,
  }
}

async function resolveBeamCenter(): Promise<void> {
  try {
    const result = await submitAndWait('viewer_config', {
      action: 'resolve_geometry_center',
      geometry: buildGeometryPayload(),
    })
    const center = result as GeometryCenterResult
    if (typeof center.centerX === 'number' && typeof center.centerY === 'number') {
      resolvedBeamCenter.value = { x: center.centerX, y: center.centerY }
      return
    }
  } catch {
    // Fallback to current form values / 失败时回退到当前表单值
  }
  resolvedBeamCenter.value = { x: geometry.value.centerX, y: geometry.value.centerY }
}

// ── File handlers / 文件处理 ──

async function handleChooseFiles(): Promise<void> {
  const res = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!res) return
  const paths = Array.isArray(res) ? res : [res]
  if (importMode.value === 'append') {
    const existingSet = new Set(files.value)
    const newFiles = paths.filter(p => !existingSet.has(p))
    files.value = [...files.value, ...newFiles]
  } else {
    files.value = paths
  }
  importFolderPath.value = null
  selectedPreviewIndex.value = 0
  thumbnailItems.value = []
  result.value = null
  await loadPreviewIfExpanded()
  loadThumbnailPageIfExpanded()
}

async function handleImportFolder(): Promise<void> {
  const folder = await transport.selectFolder()
  if (!folder) return
  importFolderPath.value = folder
  await rescanFolder()
}

async function rescanFolder(): Promise<void> {
  if (!importFolderPath.value) return
  try {
    const scanResult = await submitAndWait('viewer_config', {
      action: 'scan_folder',
      folder: importFolderPath.value,
      recursive: isRecursive.value,
    })
    const scanned = scanResult as ScanFolderResult
    const found = Array.isArray(scanned?.files) ? scanned.files.filter(Boolean) : []
    if (importMode.value === 'append') {
      const existingSet = new Set(files.value)
      const newFiles = found.filter(p => !existingSet.has(p))
      files.value = [...files.value, ...newFiles]
    } else {
      files.value = found
    }
    selectedPreviewIndex.value = 0
    thumbnailItems.value = []
    result.value = null
    await loadPreviewIfExpanded()
    loadThumbnailPageIfExpanded()
  } catch (err) {
    toast.push({
      title: t('integrateFiber.title'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// ── Preview loading / 预览加载 ──

async function loadPreview(path: string): Promise<void> {
  previewLoading.value = true
  if (previewB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewB64.value)
  }
  previewB64.value = null
  previewStats.value = null
  autoContrast.value = null
  previewImageSize.value = null

  cleanupPreviewListeners()

  try {
    await resolveBeamCenter()
    const response = await transport.submitTask('viewer_config', {
      action: 'open_file',
      filePath: path,
      frame: 0,
      settings: buildRenderSettings(),
    })

    cleanupPreviewBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
      if (payload.data) {
        const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
        if (previewB64.value?.startsWith('blob:')) {
          URL.revokeObjectURL(previewB64.value)
        }
        previewB64.value = URL.createObjectURL(blob)
      }
    })

    cleanupPreviewResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as PreviewMetadata
      if (data.stats) previewStats.value = data.stats
      if (data.contrast) autoContrast.value = data.contrast
      previewImageSize.value = {
        width: 0,
        height: 0,
        origWidth: data.metadata?.width ?? 0,
        origHeight: data.metadata?.height ?? 0,
      }
      previewLoading.value = false
    })

    cleanupPreviewError = transport.onTaskError(response.taskId, (payload) => {
      previewLoading.value = false
      console.warn('Preview load error:', payload.error)
    })
  } catch (err) {
    previewLoading.value = false
    console.warn('Preview load failed:', err)
  }
}

async function loadPreviewIfExpanded(): Promise<void> {
  if (previewExpanded.value && activeFilePath.value) {
    await loadPreview(activeFilePath.value)
  }
}

function onPreviewToggle(): void {
  previewExpanded.value = !previewExpanded.value
  if (previewExpanded.value && activeFilePath.value && !previewB64.value) {
    loadPreview(activeFilePath.value)
  }
}

function cleanupPreviewListeners(): void {
  cleanupPreviewBinary?.()
  cleanupPreviewBinary = null
  cleanupPreviewResult?.()
  cleanupPreviewResult = null
  cleanupPreviewError?.()
  cleanupPreviewError = null
}

// ── Thumbnail loading / 缩略图加载 ──

function buildThumbRenderSettings(): Record<string, unknown> {
  return {
    cmap: colormap.value,
    use_log: useLog.value,
  }
}

async function loadThumbnailPage(page?: number): Promise<void> {
  if (files.value.length === 0) return

  const currentPage = page ?? thumbCurrentPage.value
  const start = (currentPage - 1) * thumbPageSize.value
  const count = thumbPageSize.value
  const slice = files.value.slice(start, start + count)

  thumbLoading.value = true
  const items: ThumbnailItem[] = []

  try {
    for (let i = 0; i < slice.length; i++) {
      const path = slice[i]
      if (!path) continue

      const sep = path.includes('/') ? '/' : '\\'
      const parts = path.split(sep)
      const label = parts[parts.length - 1] || path

      const thumbResult = await submitAndWait('viewer_config', {
        action: 'preview',
        filePath: path,
        thumb_render_settings: buildThumbRenderSettings(),
      })

      const thumbData = thumbResult as { b64?: string; previewB64?: string }
      items.push({
        index: start + i,
        b64: typeof thumbData?.b64 === 'string'
          ? thumbData.b64
          : (typeof thumbData?.previewB64 === 'string' ? thumbData.previewB64 : ''),
        label,
      })
    }

    thumbnailItems.value = items
  } catch {
    thumbnailItems.value = []
  } finally {
    thumbLoading.value = false
  }
}

function loadThumbnailPageIfExpanded(): void {
  if (thumbExpanded.value && files.value.length > 0) {
    loadThumbnailPage()
  }
}

function onThumbToggle(): void {
  thumbExpanded.value = !thumbExpanded.value
  if (thumbExpanded.value && files.value.length > 0 && thumbnailItems.value.length === 0) {
    loadThumbnailPage()
  }
}

function handleThumbSelect(index: number): void {
  selectedPreviewIndex.value = index
  const fPath = files.value[index]
  if (fPath) {
    loadPreview(fPath)
  }
}

function handleThumbPrevPage(): void {
  if (thumbCurrentPage.value <= 1) return
  thumbCurrentPage.value -= 1
  loadThumbnailPage()
}

function handleThumbNextPage(): void {
  if (thumbCurrentPage.value >= thumbTotalPages.value) return
  thumbCurrentPage.value += 1
  loadThumbnailPage()
}

function handleThumbJumpToPage(page: number): void {
  const clamped = Math.max(1, Math.min(thumbTotalPages.value, page))
  if (clamped === thumbCurrentPage.value) return
  thumbCurrentPage.value = clamped
  loadThumbnailPage(clamped)
}

function handleThumbPageSizeChange(size: number): void {
  thumbPageSize.value = size
  thumbCurrentPage.value = 1
  if (files.value.length > 0) {
    loadThumbnailPage()
  }
}

// ── Event handlers ────────────────────────────────────────────────────────

function onFiberParam(field: keyof FiberParams, event: Event): void {
  const raw = (event.target as HTMLInputElement).value
  const num = parseFloat(raw)
  if (isNaN(num)) return
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(fiberParams as any)[field] = num
}

function onSelectParam(field: keyof FiberParams, event: Event): void {
  const val = (event.target as HTMLSelectElement).value
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(fiberParams as any)[field] = field === 'sampleOrientation' ? parseInt(val, 10) : val
}

function onToggleAutoRange(): void {
  fiberParams.autoRange = !fiberParams.autoRange
}

// ── Build submission params / 构建提交参数 ───────────────────────────────

function buildParams(previewOnly = false): Record<string, unknown> {
  const firstFile = activeFilePath.value ?? files.value[0] ?? null
  const fileList = previewOnly
    ? (activeFilePath.value ? [activeFilePath.value] : files.value.slice(0, 1))
    : [...files.value]
  const geo = geometry.value
  return {
    filePath: firstFile,
    files: fileList,
    geometry: geo.poniPath
      ? { poniPath: geo.poniPath }
      : {
          pixel1: geo.pixel1,
          pixel2: geo.pixel2,
          distance: geo.distance,
          wavelength: geo.wavelength,
          centerX: geo.centerX,
          centerY: geo.centerY,
        },
    rot1Deg: fiberParams.rot1Deg,
    rot2Deg: fiberParams.rot2Deg,
    rot3Deg: fiberParams.rot3Deg,
    sampleOrientation: fiberParams.sampleOrientation,
    incidentAngleDeg: fiberParams.incidentAngleDeg,
    tiltAngleDeg: fiberParams.tiltAngleDeg,
    unitIp: fiberParams.unitIp,
    unitOop: fiberParams.unitOop,
    autoRange: fiberParams.autoRange,
    ipRange: fiberParams.autoRange
      ? null
      : [fiberParams.ipMin, fiberParams.ipMax],
    oopRange: fiberParams.autoRange
      ? null
      : [fiberParams.oopMin, fiberParams.oopMax],
    nptIp: fiberParams.nptIp,
    nptOop: fiberParams.nptOop,
    mask: {
      valueRangeMin: maskConfig.value.valueRangeMin,
      valueRangeMax: maskConfig.value.valueRangeMax,
      deadPixelThreshold: maskConfig.value.deadPixelThreshold,
      customMaskPath: maskConfig.value.customMaskPath,
    },
    polarizationFactor: polarizationFactor.value,
    correctSolidAngle: correctSolidAngle.value,
  }
}

// ── Run preview integration (single file) / 执行预览积分 ────────────────

async function runPreviewIntegration(): Promise<void> {
  if (!canRun.value) return

  isPreviewRunning.value = true
  previewProgress.value = 0
  previewProgressMessage.value = null
  previewError.value = null
  result.value = null

  const params = buildParams(true) // previewOnly = true

  try {
    const response = await transport.submitTask('integrate_fiber', params)
    previewTaskId.value = response.taskId

    const taskResult = await pollTask(response.taskId, {
      onProgress: (p, msg) => {
        previewProgress.value = p
        if (msg) previewProgressMessage.value = msg
      },
    })

    if (taskResult) {
      batchCachePath.value = (taskResult.batchCachePath as string | undefined) ?? null
      resultSummaries.value = Array.isArray(taskResult.results_summary)
        ? taskResult.results_summary as FiberResultSummary[]
        : []
      if (batchCachePath.value && resultSummaries.value.length > 0) {
        await loadFiberResult(0)
      }
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    previewProgressMessage.value = message
    previewError.value = message
    toast.push({ title: t('integrateFiber.title'), message, tone: 'error' })
  } finally {
    isPreviewRunning.value = false
    previewTaskId.value = null
  }
}

// ── Batch to folder: select output, then integrate + export ─────────

async function onBatchToFolder(): Promise<void> {
  const folderResult = await transport.selectFolder()
  if (!folderResult) return
  await runBatchToFolder(folderResult, batchExportFormat.value)
}

async function runBatchToFolder(outputPath: string, format: string): Promise<void> {
  isBatchRunning.value = true
  batchProgress.value = 0
  batchProgressMessage.value = null
  batchError.value = null

  const params = buildParams(false)
  params.outputPath = outputPath
  params.outputFormat = format

  try {
    const response = await transport.submitTask('integrate_fiber', params)
    batchTaskId.value = response.taskId

    const taskResult = await pollTask(response.taskId, {
      onProgress: (p, msg) => {
        batchProgress.value = p
        if (msg) batchProgressMessage.value = msg
      },
    })

    if (taskResult) {
      const generated = (taskResult.generated as string[]) ?? []
      const errors = (taskResult.errors as string[]) ?? []
      exportedFiles.value = generated
      exportedDir.value = outputPath
      exportedFormat.value = format

      const msg = `${generated.length} 个文件导出到 / files exported to ${outputPath}`
      toast.push({
        title: t('integrateFiber.title'),
        message: msg,
        tone: 'success',
      })
      if (errors.length > 0) {
        toast.push({
          title: t('integrateFiber.title'),
          message: `${errors.length} 个文件出错 / files had errors`,
          tone: 'error',
        })
      }
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    batchProgressMessage.value = message
    batchError.value = message
    toast.push({ title: t('integrateFiber.title'), message, tone: 'error' })
  } finally {
    isBatchRunning.value = false
    batchTaskId.value = null
  }
}

// ── View exported result from disk / 从磁盘加载导出的结果 ────────────

async function viewExportedResult(filePath: string): Promise<void> {
  if (viewingExported.value) return

  // Memory warning for large loads / 大量加载内存提示
  if (exportedFiles.value.length > exportedPreviewLimit.value) {
    const ok = confirm(
      `当前共 ${exportedFiles.value.length} 个导出文件，加载大量文件到内存可能导致系统卡顿。\n` +
      `建议只加载需要的文件。确定加载 ${filePath.replace(/^.*[\\/]/, '')} 吗？\n\n` +
      `${exportedFiles.value.length} files exported. Loading many files may cause memory pressure. ` +
      `Load "${filePath.replace(/^.*[\\/]/, '')}"?`
    )
    if (!ok) return
  }

  viewingExported.value = true
  try {
    // Use viewer_config to load the exported result for preview
    const raw = await submitAndWait('viewer_config', {
      action: 'fiber_exported_preview',
      filePath,
      settings: {
        cmap: colormap.value,
        use_log: useLog.value,
        clim_mode: 'auto',
        clim: [null, null],
      },
    })
    const data = raw as {
      displayB64?: string
      imageData?: (number | null)[][]
      axisIp?: number[]
      axisOop?: number[]
      contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
    }
    if (data.displayB64 || data.imageData) {
      result.value = {
        previewB64: data.displayB64 ?? null,
        intensity: data.imageData ?? [],
        axisIp: data.axisIp ?? [],
        axisOop: data.axisOop ?? [],
        unitIp: fiberParams.unitIp,
        unitOop: fiberParams.unitOop,
        filename: filePath.replace(/^.*[\\/]/, ''),
      }
      resultContrast.value = data.contrast ?? null
    }
  } catch (err) {
    toast.push({
      title: t('integrateFiber.title'),
      message: `加载失败 / Load failed: ${err instanceof Error ? err.message : String(err)}`,
      tone: 'error',
    })
  } finally {
    viewingExported.value = false
  }
}

/** Poll task progress until complete / 轮询任务进度直到完成 */
async function pollTask(
  id: string,
  callbacks?: { onProgress?: (p: number, msg?: string) => void },
): Promise<Record<string, unknown> | null> {
  return new Promise((resolve, reject) => {
    const removeProgress = transport.onTaskProgress(id, (payload) => {
      const p = payload.progress
      const msg = payload.message
      if (callbacks?.onProgress) callbacks.onProgress(p, msg)
    })

    const removeResult = transport.onTaskResult(id, (payload) => {
      cleanup()
      resolve(payload.data as Record<string, unknown> ?? null)
    })

    const removeError = transport.onTaskError(id, (payload) => {
      cleanup()
      reject(new Error(payload.error ?? 'Integration failed'))
    })

    function cleanup() {
      removeProgress()
      removeResult()
      removeError()
    }
  })
}

// ── Cancel / 取消 ──────────────────────────────────────────────────────

async function onCancelPreview(): Promise<void> {
  if (previewTaskId.value) {
    try { await transport.cancelTask(previewTaskId.value) } catch { /* ok */ }
  }
  isPreviewRunning.value = false
  previewTaskId.value = null
}

async function onCancelBatch(): Promise<void> {
  if (batchTaskId.value) {
    try { await transport.cancelTask(batchTaskId.value) } catch { /* ok */ }
  }
  isBatchRunning.value = false
  batchTaskId.value = null
}

// ── Export / 导出 ─────────────────────────────────────────────────────────

async function onExport(payload: { format: ExportFormat; path: string; mode: ExportMode }): Promise<void> {
  if (!result.value) return

  const params = JSON.parse(JSON.stringify({
    format: payload.format,
    outputPath: payload.path,
    dataType: 'fiber',
    mode: payload.mode,
    intensity: result.value.intensity,
    axisIp: result.value.axisIp,
    axisOop: result.value.axisOop,
    unitIp: result.value.unitIp,
    unitOop: result.value.unitOop,
    batchCachePath: batchCachePath.value ?? result.value.batchCachePath,
    sourceFile: fileName.value,
  }))

  try {
    const response = await transport.submitTask('export_integration', params)

    const removeOk = transport.onTaskResult(response.taskId, (r) => {
      const d = r.data as { success?: boolean; error?: string; path?: string }
      if (d?.success) {
        toast.push({
          title: t('integrateFiber.title'),
          message: `${payload.format.toUpperCase()} → ${d.path ?? payload.path}`,
          tone: 'success',
        })
      } else {
        toast.push({ title: t('integrateFiber.title'), message: d?.error ?? 'Export failed', tone: 'error' })
      }
      removeOk(); removeErr()
    })
    const removeErr = transport.onTaskError(response.taskId, (e) => {
      toast.push({ title: t('integrateFiber.title'), message: e.error ?? 'Export failed', tone: 'error' })
      removeOk(); removeErr()
    })
  } catch (err) {
    toast.push({ title: t('integrateFiber.title'), message: String(err), tone: 'error' })
  }
}

// === Watchers / 监听器 ===

/** Re-render preview when display settings change / 显示设置变更时重新渲染预览 */
watch([colormap, useLog], () => {
  if (activeFilePath.value && previewExpanded.value) {
    loadPreview(activeFilePath.value)
  }
  if (files.value.length > 0 && thumbExpanded.value) {
    loadThumbnailPage()
  }
  if (batchCachePath.value && result.value) {
    void loadFiberResult(currentResultIndex.value)
    void loadFiberResultThumbnails(resultThumbCurrentPage.value)
  }
})

watch([resultClimMode, resultClimMin, resultClimMax], () => {
  if (resultClimMode.value === 'manual' && batchCachePath.value && result.value) {
    void loadFiberResult(currentResultIndex.value)
  }
})

watch(
  () => [
    geometry.value.poniPath,
    geometry.value.pixel1,
    geometry.value.pixel2,
    geometry.value.distance,
    geometry.value.wavelength,
    geometry.value.centerX,
    geometry.value.centerY,
  ],
  () => {
    if (activeFilePath.value && previewExpanded.value) {
      void loadPreviewIfExpanded()
    }
  },
)

/** Re-scan folder when recursive toggle changes / 递归开关变更时重新扫描文件夹 */
watch(isRecursive, () => {
  if (importFolderPath.value) {
    rescanFolder()
  }
})

onUnmounted(() => {
  if (previewB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewB64.value)
  }
  cleanupPreviewListeners()
})
</script>

<style scoped>
.fiber-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.fiber-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
}

.fiber-header p {
  color: var(--text-secondary);
  font-size: 0.9375rem;
  margin: 0;
}

.fiber-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* ── Sidebar ── */

.fiber-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fib-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fib-section > legend {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

/* ── File section (1D-style, in main area) / 文件选择区（1D风格，主区域） ── */

.fib-file-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fib-section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 10px;
  color: var(--text-primary);
}

.fib-file-buttons {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.fib-file-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.fib-file-btn:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

/* Import mode toggle / 导入模式切换 */
.fib-import-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
  font-size: 0.8125rem;
}

.fib-import-mode-label {
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.fib-radio-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: var(--text-primary);
  white-space: nowrap;
}

.fib-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

.fib-file-info-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
}

.fib-file-info-bar--muted {
  background: transparent;
  padding: 4px 10px;
}

.fib-file-name {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fib-file-info-bar--muted span {
  color: var(--text-muted);
  font-style: italic;
}

.fib-clear-btn {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 4px 10px;
  transition: border-color var(--transition-fast);
  white-space: nowrap;
}

.fib-clear-btn:hover {
  border-color: var(--border-hover);
  color: var(--error);
}

/* ── Collapsible sections / 折叠区域 ── */

.fib-collapsible {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.fib-section-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-surface);
  transition: background var(--transition-fast);
}

.fib-section-toggle:hover {
  background: var(--bg-surface-alt);
}

.fib-toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
  width: 14px;
  text-align: center;
}

.fib-collapsible-body {
  padding: 14px;
  border-top: 1px solid var(--border);
}

/* ── Image preview area / 图像预览区域 ── */

.fib-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.fib-preview-area {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 200px;
  gap: 14px;
}

.fib-preview-image {
  border-radius: var(--radius-md);
  overflow: hidden;
}

.fib-preview-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Preview info panel / 预览信息面板 */
.fib-preview-info {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: start;
}

.fib-info-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.fib-info-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.75rem;
  gap: 6px;
}

.fib-info-label {
  color: var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
}

.fib-info-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  text-align: right;
  word-break: break-all;
}

/* ── Fieldset form controls ── */

.fib-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}

.fib-range-grid {
  grid-template-columns: 1fr 1fr;
}

.fib-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fib-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.fib-input,
.fib-select {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.fib-input:focus,
.fib-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.fib-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.fib-toggle input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

.fib-toggle-label {
  font-size: 0.8125rem;
  color: var(--text-primary);
  font-weight: 500;
}

/* ── Main ── */

.fiber-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.fib-run-section {
  display: flex;
  align-items: center;
  gap: 14px;
}

.fib-run-btn {
  padding: 12px 32px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.fib-run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fib-run-btn:not(:disabled):hover {
  opacity: 0.9;
}

.fib-error {
  font-size: 0.8125rem;
  color: var(--error);
  font-weight: 500;
}

.fib-error-box {
  padding: 12px 14px;
  border: 1px solid rgba(220, 38, 38, 0.25);
  background: rgba(220, 38, 38, 0.08);
  border-radius: var(--radius-md);
  color: var(--error);
}

.fib-error-box p {
  margin: 0;
  font-size: 0.875rem;
}

/* ── Batch format selector / 批量导出格式选择 ── */

.fib-batch-format {
  display: flex;
  align-items: center;
  gap: 4px;
}

.fib-batch-format-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.fib-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.fib-result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}

.fib-result-meta {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.fib-result-thumbs {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
}

.fib-result h2 {
  font-size: 1.125rem;
  margin: 0;
}

.fib-chart-container {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  min-height: 400px;
}

.fib-chart-controls {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}

.fib-contrast-field {
  min-width: 140px;
}

/* ── Line profiles ── */

.fib-profiles {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.fib-profile-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fib-profile-card h3 {
  font-size: 0.9375rem;
  font-weight: 600;
  margin: 0;
}

.fib-profile-picker {
  max-width: 200px;
}

/* ── Empty state ── */

.fib-empty {
  padding: 48px 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.875rem;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
}

/* ── Batch button (secondary style) / 批量按钮（次要样式） ── */

.fib-batch-btn {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
}

.fib-batch-btn:not(:disabled):hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* ── Batch exported results / 批量导出结果 ── */

.fib-exported-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fib-memory-warning {
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: var(--text-primary);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.fib-exported-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.fib-exported-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface-alt);
}

.fib-exported-name {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fib-exported-more {
  text-align: center;
  font-size: 0.75rem;
  color: var(--text-muted);
  padding: 6px;
}

.fib-exported-item .fib-file-btn {
  padding: 3px 10px;
  font-size: 0.75rem;
  flex-shrink: 0;
}

@media (max-width: 960px) {
  .fiber-layout {
    grid-template-columns: 1fr;
  }

  .fib-preview-area {
    grid-template-columns: 1fr;
  }

  .fib-profiles {
    grid-template-columns: 1fr;
  }
}
</style>
