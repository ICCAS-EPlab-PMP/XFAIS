<template>
  <section class="lm-page">
    <!-- Header / 页头 -->
    <header class="lm-header">
      <h1>{{ t('lamellar.title') }}</h1>
      <p class="lm-subtitle">{{ t('lamellar.subtitle') }}</p>
    </header>

    <div class="lm-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="lm-sidebar">
        <!-- Input mode / 输入模式 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.inputMode') }}</h3>
          <div class="lm-radio-row">
            <label class="lm-radio-label">
              <input v-model="inputMode" type="radio" value="image" />
              <span>{{ t('lamellar.modeImage') }}</span>
            </label>
            <label class="lm-radio-label">
              <input v-model="inputMode" type="radio" value="curves" />
              <span>{{ t('lamellar.modeCurves') }}</span>
            </label>
          </div>
        </div>

        <!-- Image-mode inputs / 图像模式输入 -->
        <template v-if="inputMode === 'image'">
          <div
            class="lm-card lm-card--files"
            :class="{ 'lm-card--drop': fileDrop.isDragging.value }"
            @dragenter="fileDrop.onDragEnter"
            @dragover="fileDrop.onDragOver"
            @dragleave="fileDrop.onDragLeave"
            @drop="fileDrop.onDrop"
          >
            <h3 class="lm-card-title">{{ t('lamellar.selectFile') }}</h3>
            <!-- Multi-file selection; the checked file runs first, the rest
                 await the batch apply. / 多文件选择：勾选文件先单跑，其余
                 待“按首个结果批量处理”。 -->
            <div class="lm-btn-row">
              <button type="button" class="lm-btn" data-ai-id="lamellar:files" @click="handleAddFiles">
                {{ t('lamellar.files.add') }}
              </button>
              <button v-if="files.length" type="button" class="lm-btn lm-btn-sm" @click="clearFiles">
                {{ t('lamellar.files.clear') }}
              </button>
            </div>
            <p class="lm-hint">{{ t('business.fileSelection.dropZoneHint') }}</p>
            <p v-if="files.length" class="lm-hint">
              {{ t('lamellar.files.count', { n: files.length }) }}
            </p>
            <p v-if="files.length > 1" class="lm-hint lm-hint-warn">
              {{ t('lamellar.files.singleFirstHint') }}
            </p>
            <ul v-if="files.length" class="lm-file-list">
              <li
                v-for="(f, idx) in files"
                :key="f"
                class="lm-file-item"
                :class="{ 'lm-file-item--active': idx === selectedFileIndex }"
              >
                <label class="lm-radio-label" :title="f">
                  <input
                    v-model="selectedFileIndex"
                    type="radio"
                    :value="idx"
                    name="lm-preview-file"
                  />
                  <span class="lm-file-name">{{ fileName(f) }}</span>
                </label>
                <button
                  type="button"
                  class="lm-btn-icon"
                  :title="t('lamellar.files.remove')"
                  @click="removeFile(idx)"
                >&times;</button>
              </li>
            </ul>
          </div>

          <details class="lm-card lm-details" data-ai-id="lamellar:geometry">
            <summary>{{ t('lamellar.geometry') }}</summary>
            <GeometryForm v-model="geometry" />
          </details>

          <details class="lm-card lm-details">
            <summary>{{ t('lamellar.mask') }}</summary>
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </details>
        </template>

        <!-- Curves-mode inputs / 曲线模式输入 -->
        <div v-else class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.curvesInput') }}</h3>
          <p class="lm-hint">{{ t('lamellar.curvesHint') }}</p>
          <textarea
            v-model="curvesText"
            class="lm-textarea"
            :placeholder="t('lamellar.curvesPlaceholder')"
            rows="6"
          ></textarea>
          <div class="lm-btn-row">
            <button type="button" class="lm-btn lm-btn-sm" @click="parseCurves">
              {{ t('lamellar.parse') }}
            </button>
            <FileDialogButton
              v-model="curvesFilePath"
              mode="openFile"
              :label="t('lamellar.loadFile')"
              :filters="[{ name: 'Data', extensions: ['csv', 'txt', 'dat'] }]"
              @update:model-value="loadCurvesFile"
            />
          </div>
          <p v-if="parsedQ.length > 0" class="lm-hint lm-hint-ok">
            {{ t('lamellar.parsedN', { n: parsedQ.length }) }}
          </p>
        </div>

        <!-- q range: each bound optional, applies to BOTH modes. /
             q 范围：上下限各自可选，两种模式都生效。 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.qRange') }}</h3>
          <div class="lm-field">
            <label class="lm-label">{{ t('lamellar.qUnitLabel') }}</label>
            <select v-model="qUnit" class="lm-select">
              <option value="nm^-1">q (nm⁻¹)</option>
              <option value="A^-1">q (Å⁻¹)</option>
            </select>
          </div>
          <div class="lm-field-row">
            <div class="lm-field">
              <label class="lm-label">{{ t('lamellar.qMin') }}</label>
              <input v-model.number="radialMin" type="number" class="lm-input" step="any" placeholder="—" />
            </div>
            <div class="lm-field">
              <label class="lm-label">{{ t('lamellar.qMax') }}</label>
              <input v-model.number="radialMax" type="number" class="lm-input" step="any" placeholder="—" />
            </div>
          </div>
          <p class="lm-hint">{{ t('lamellar.qRangeHint') }}</p>
          <div v-if="inputMode === 'image'" class="lm-field">
            <label class="lm-label">{{ t('lamellar.npt') }}</label>
            <input v-model.number="npt" type="number" class="lm-input" min="64" step="1" />
          </div>
        </div>

        <!-- Background / 背景 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.background') }}</h3>
          <div class="lm-field">
            <select v-model="bgMode" class="lm-select">
              <option value="auto">{{ t('lamellar.bgAuto') }}</option>
              <option value="constant">{{ t('lamellar.bgConstant') }}</option>
              <option value="none">{{ t('lamellar.bgNone') }}</option>
            </select>
          </div>
          <div v-if="bgMode === 'constant'" class="lm-field">
            <label class="lm-label">{{ t('lamellar.bgLevel') }}</label>
            <input v-model.number="bgConstant" type="number" class="lm-input" step="any" />
          </div>
          <p class="lm-hint">{{ t('lamellar.bgHint') }}</p>
        </div>

        <!-- Minority phase / 少数相 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.minorityPhase') }}</h3>
          <div class="lm-field">
            <select v-model="minorityPhase" class="lm-select">
              <option value="crystalline">{{ t('lamellar.minorityCrystalline') }}</option>
              <option value="amorphous">{{ t('lamellar.minorityAmorphous') }}</option>
            </select>
            <p class="lm-hint">{{ t('lamellar.minorityHint') }}</p>
          </div>
        </div>
      </aside>

      <!-- ===== Main: run + results / 主区：运行 + 结果 ===== -->
      <main class="lm-main">
        <div class="lm-run-row">
          <button
            type="button"
            class="lm-btn lm-btn-primary"
            :disabled="!canRun || isRunning"
            data-ai-id="lamellar:run"
            @click="handleRun"
          >
            {{ isRunning ? t('lamellar.running') : t('lamellar.run') }}
          </button>
          <button v-if="isRunning" type="button" class="lm-btn" @click="handleCancel">
            {{ t('lamellar.cancel') }}
          </button>
          <button v-if="detailData" type="button" class="lm-btn" data-ai-id="lamellar:export" @click="exportCsv">
            {{ t('lamellar.exportCsv') }}
          </button>
        </div>

        <TaskProgressBar v-if="isRunning || progress > 0" :progress="progress" :message="progressMessage ?? ''" />

        <div v-if="errorMessage" class="lm-error">
          <strong>{{ t('lamellar.errorTitle') }}:</strong> {{ errorMessage }}
        </div>

        <!-- Batch apply offer: only after a successful first image-mode run
             with more files waiting. / 批量应用入口：仅在图像模式首个文件
             单跑成功且还有其余文件时出现。 -->
        <div v-if="batchOfferVisible" class="lm-batch-offer">
          <h3 class="lm-card-title">{{ t('lamellar.batch.offerTitle') }}</h3>
          <p class="lm-hint">{{ t('lamellar.batch.offerHint', { n: files.length - 1 }) }}</p>
          <template v-if="!batchConfirming">
            <button type="button" class="lm-btn lm-btn-primary" @click="batchConfirming = true">
              {{ t('lamellar.batch.offer') }}
            </button>
          </template>
          <template v-else>
            <p class="lm-hint lm-hint-warn">{{ t('lamellar.batch.confirmWarn') }}</p>
            <div class="lm-btn-row">
              <button type="button" class="lm-btn lm-btn-primary" @click="handleBatchRun">
                {{ t('lamellar.batch.confirmBtn') }}
              </button>
              <button type="button" class="lm-btn" @click="batchConfirming = false">
                {{ t('lamellar.cancel') }}
              </button>
            </div>
          </template>
        </div>

        <!-- Batch summary / 批量汇总 -->
        <template v-if="batchItems">
          <div class="lm-card">
            <h3 class="lm-card-title">
              {{ t('lamellar.batch.title') }}
              <span class="lm-batch-meta">
                {{ t('lamellar.batch.okCount', { n: batchItems.length }) }}
                <template v-if="failedFiles.length">
                  · {{ t('lamellar.batch.failCount', { m: failedFiles.length }) }}
                </template>
              </span>
            </h3>
            <p class="lm-hint">{{ t('lamellar.batch.hint') }}</p>
            <div class="lm-table-wrap">
              <table class="lm-table">
                <thead>
                  <tr>
                    <th>{{ t('lamellar.batch.file') }}</th>
                    <th>{{ t('lamellar.longPeriod') }} (nm)</th>
                    <th>{{ t('lamellar.lc') }} (nm)</th>
                    <th>{{ t('lamellar.la') }} (nm)</th>
                    <th>{{ t('lamellar.phiC') }}</th>
                    <th>{{ t('lamellar.slopeShort') }} (nm⁻¹)</th>
                    <th>{{ t('lamellar.batch.deviation') }}</th>
                    <th>{{ t('lamellar.batch.warningsCol') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(item, idx) in batchItems"
                    :key="idx"
                    :class="{ 'lm-row--active': idx === selectedResultIndex }"
                    @click="selectBatchRow(idx)"
                  >
                    <td class="lm-file-name" :title="item.sourceLabel ?? ''">{{ fileName(item.sourceLabel ?? '') }}</td>
                    <td>{{ fmt(itemResult(item)?.long_period_nm) }}</td>
                    <td>{{ fmt(itemResult(item)?.l_crystalline_nm) }}</td>
                    <td>{{ fmt(itemResult(item)?.l_amorphous_nm) }}</td>
                    <td>{{ pct(itemResult(item)?.crystallinity_stack) }}</td>
                    <td>{{ fmt(itemResult(item)?.tangent_slope_nm_inv) }}</td>
                    <td>
                      <span v-if="deviationOf(item) !== null" class="lm-dev" :class="{ 'lm-dev--warn': isDeviating(item) }">
                        {{ deviationOf(item) !== null ? `${(deviationOf(item) as number) > 0 ? '+' : ''}${((deviationOf(item) as number) * 100).toFixed(1)}%` : '—' }}
                      </span>
                      <span v-else>—</span>
                    </td>
                    <td>{{ item.warnings?.length ?? 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="lm-btn-row">
              <button type="button" class="lm-btn lm-btn-sm" @click="exportBatchCsv">
                {{ t('lamellar.batch.exportSummary') }}
              </button>
            </div>
            <div v-if="failedFiles.length" class="lm-failed">
              <strong>{{ t('lamellar.batch.failed') }}:</strong>
              <ul>
                <li v-for="(f, idx) in failedFiles" :key="idx">
                  <code>{{ fileName(f.file) }}</code> — {{ f.reason }}
                </li>
              </ul>
            </div>
          </div>
        </template>

        <!-- ===== Detail: single result or the selected batch row ===== -->
        <!-- ===== 明细：单次结果或批量表中选中的行 ===== -->
        <template v-if="detailData">
          <div v-if="detailLabel" class="lm-detail-label">{{ detailLabel }}</div>

          <div v-if="detailData.warnings?.length" class="lm-warnings">
            <h3 class="lm-card-title">{{ t('lamellar.warnings') }}</h3>
            <ul>
              <li v-for="(w, idx) in detailData.warnings" :key="idx">{{ w }}</li>
            </ul>
          </div>

          <!-- Step 1: I(q) / 第一步：原始与扣背景曲线（y 轴默认对数，可切线性） -->
          <div v-if="profileTraces.length > 0" class="lm-chart">
            <h2 class="lm-section-title">{{ t('lamellar.step1Title') }}</h2>
            <!-- Effective window readout: the backend clips I(q) to the q limits
                 BEFORE analysis; this line shows the window actually applied, so
                 a silently-ignored q_min (e.g. stale backend) is visible at once.
                 实际生效窗口读出：后端在分析前按 q 上下限裁剪；此行显示真正
                 生效的窗口，若 q 下限被静默忽略（如残留旧后端）可立即发现。 -->
            <p v-if="appliedWindowLabel" class="lm-hint lm-hint-ok">{{ appliedWindowLabel }}</p>
            <LineChart
              :traces="profileTraces"
              :x-label="qAxisLabel"
              :y-label="t('lamellar.intensityAxis')"
              :title="t('lamellar.step1Title')"
              y-scale="log"
              y-scale-toggle
            />
          </div>

          <!-- Step 2: q²I(q) + Porod extrapolation / 第二步：洛伦兹校正曲线 -->
          <div v-if="zTraces.length > 0" class="lm-chart">
            <h2 class="lm-section-title">{{ t('lamellar.step2Title') }}</h2>
            <p class="lm-hint">{{ porodHint }}</p>
            <LineChart
              :traces="zTraces"
              :x-label="qAxisLabel"
              :y-label="t('lamellar.zAxis')"
              :title="t('lamellar.step2Title')"
            />
          </div>

          <!-- Step 3: γ₁(x) + tangent / 第三步：相关函数与切线 -->
          <div v-if="gammaTraces.length > 0" class="lm-chart">
            <h2 class="lm-section-title">{{ t('lamellar.step3Title') }}</h2>
            <!-- Tangent window: auto-estimated by default; the user may type a
                 window or pick two points on the chart, then re-fit. /
                 切线区间：默认自动预估；可手填，或在图上点选两点后重拟合。 -->
            <div class="lm-tangent-bar">
              <div class="lm-field-row lm-tangent-fields">
                <div class="lm-field">
                  <label class="lm-label">{{ t('lamellar.tangentWindowLabel') }}</label>
                  <input v-model.number="tangentFitMin" type="number" class="lm-input" step="any" placeholder="auto" />
                </div>
                <div class="lm-field">
                  <label class="lm-label">–</label>
                  <input v-model.number="tangentFitMax" type="number" class="lm-input" step="any" placeholder="auto" />
                </div>
              </div>
              <button type="button" class="lm-btn lm-btn-sm lm-btn-primary" :disabled="!canRun || isRunning" @click="handleRun">
                {{ t('lamellar.refit') }}
              </button>
              <button
                type="button"
                class="lm-btn lm-btn-sm"
                :class="{ 'lm-btn-primary': pickActive }"
                @click="togglePick"
              >{{ pickActive ? t('lamellar.pickCancel') : t('lamellar.pickStart') }}</button>
            </div>
            <p class="lm-hint">
              {{ pickActive
                ? (pickFirst !== null ? t('lamellar.pickSecond', { x: fmt(pickFirst) }) : t('lamellar.pickFirstHint'))
                : t('lamellar.tangentWindowHint') }}
            </p>
            <LineChart
              :traces="gammaTraces"
              :x-label="t('lamellar.rAxis')"
              :y-label="t('lamellar.gammaAxis')"
              :title="t('lamellar.step3Title')"
              @plot:click="onGammaClick"
            />
          </div>

          <!-- Step 4a: slope card / 第四步 a：切线斜率卡片 -->
          <div v-if="res" class="lm-card lm-slope-card">
            <h2 class="lm-section-title">{{ t('lamellar.step4Title') }}</h2>
            <div class="lm-slope-grid">
              <div class="lm-slope-main">
                <span class="lm-result-key">{{ t('lamellar.slopeLabel') }}</span>
                <span class="lm-slope-val">{{ fmt(res.tangent_slope_nm_inv) }} nm⁻¹</span>
              </div>
              <div class="lm-result-row">
                <span class="lm-result-key">R²</span>
                <span class="lm-result-val">{{ fmt(res.tangent_r2) }}</span>
              </div>
              <div class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.fitRange') }}</span>
                <span class="lm-result-val">{{ res.tangent_fit_min_nm !== null && res.tangent_fit_min_nm !== undefined ? `${fmt(res.tangent_fit_min_nm)} – ${fmt(res.tangent_fit_max_nm)} nm · ${tangentModeLabel}` : '—' }}</span>
              </div>
              <div class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.xAtZero') }}</span>
                <span class="lm-result-val">{{ fmt(res.x_at_gamma_zero) }} nm</span>
              </div>
              <div class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.xAtGammaMin') }}</span>
                <span class="lm-result-val">{{ fmt(res.x_at_gamma_min) }} nm</span>
              </div>
              <div class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.osLabel') }}</span>
                <span class="lm-result-val">{{ fmt(res.specific_surface_nm_inv) }} nm⁻¹</span>
              </div>
            </div>
          </div>

          <!-- Step 4b: structural results / 第四步 b：结构参数卡片 -->
          <div v-if="res" class="lm-results">
            <h2 class="lm-section-title">{{ t('lamellar.resultsTitle') }}</h2>
            <div class="lm-result-grid">
              <div class="lm-result-card">
                <h3 class="lm-result-method">{{ t('lamellar.mCorrelation') }}</h3>
                <div class="lm-result-row">
                  <span class="lm-result-key">{{ t('lamellar.longPeriod') }}</span>
                  <span class="lm-result-val">{{ fmt(res.long_period_nm) }} nm</span>
                </div>
                <div class="lm-result-row">
                  <span class="lm-result-key">{{ t('lamellar.longPeriod2min') }}</span>
                  <span class="lm-result-val">{{ fmt(res.long_period_2min_nm) }} nm</span>
                </div>
                <div class="lm-result-row">
                  <span class="lm-result-key">{{ t('lamellar.firstMin') }}</span>
                  <span class="lm-result-val">{{ fmt(res.first_min_nm) }} nm</span>
                </div>
                <div class="lm-result-row">
                  <span class="lm-result-key">{{ t('lamellar.lc') }}</span>
                  <span class="lm-result-val">{{ fmt(res.l_crystalline_nm) }} nm</span>
                </div>
                <div class="lm-result-row">
                  <span class="lm-result-key">{{ t('lamellar.la') }}</span>
                  <span class="lm-result-val">{{ fmt(res.l_amorphous_nm) }} nm</span>
                </div>
                <div class="lm-result-row">
                  <span class="lm-result-key">{{ t('lamellar.phiC') }}</span>
                  <span class="lm-result-val">{{ pct(res.crystallinity_stack) }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * LamellarAnalysisView.vue — SAXS 片晶结构分析 (v0.2.6)
 * Correlation-function (Strobl–Schneider) pipeline with per-step curves:
 * I(q) → background → q²I(q) (+Porod extrapolation) → γ₁(x) → tangent fit
 * (slope!) → structural parameters. The Bragg peak method was removed.
 * Image mode supports multi-file batch: tune on the first file, then apply
 * the same conditions to the rest (with a deviation warning).
 * 相关函数（Strobl–Schneider）流水线，逐步展示曲线：I(q) → 背景 → q²I(q)
 * （+Porod 外推）→ γ₁(x) → 切线拟合（斜率）→ 结构参数。已移除 Bragg 峰法。
 * 图像模式支持多文件批量：先在首个文件上调参，再按同条件批处理其余文件
 * （附偏离风险提示）。
 */
import { ref, computed, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { clearWorkspace, reportWorkspace } from '@/lib/workspace-state'
import { createImportDropZone, extensionsFromFilters } from '@/lib/fileDrop'
import GeometryForm from '@/components/business/GeometryForm.vue'
import type { GeometryParams } from '@/components/business/GeometryForm.vue'
import MaskBuilderForm from '@/components/business/MaskBuilderForm.vue'
import type { MaskConfig } from '@/components/business/MaskBuilderForm.vue'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// --- Input mode / 输入模式 ---
const inputMode = ref<'image' | 'curves'>('curves')

// --- Image-mode state / 图像模式状态 ---
const files = ref<string[]>([])
const selectedFileIndex = ref(0)
const geometry = ref<GeometryParams>({
  pixel1: 172, pixel2: 172, distance: 200,
  wavelength: 1.5418, centerX: 512, centerY: 512,
})
const maskConfig = ref<MaskConfig>({
  valueRangeMin: 0, valueRangeMax: 2147483647,
  deadPixelThreshold: 0, customMaskPath: null,
})
const qUnit = ref<'nm^-1' | 'A^-1'>('nm^-1')
// Each bound optional on its own (e.g. mask handles the rest → only q min).
// 上下限各自独立可选（例如其余交给 mask，只填 q 下限）。
const radialMin = ref<number | null>(null)
const radialMax = ref<number | null>(null)
const npt = ref(1000)
const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// --- Curves-mode state / 曲线模式状态 ---
const curvesText = ref('')
const curvesFilePath = ref<string | null>(null)
const parsedQ = ref<number[]>([])
const parsedIntensity = ref<number[]>([])

// --- Background / 背景 ---
const bgMode = ref<'auto' | 'constant' | 'none'>('auto')
const bgConstant = ref<number | null>(null)

// --- Minority phase / 少数相 ---
const minorityPhase = ref<'crystalline' | 'amorphous'>('crystalline')

// --- Tangent fit window (last step): auto-estimated, user-overridable ---
// --- 切线拟合区间（最后一步）：默认自动预估，用户可手动覆盖 ---
const tangentFitMin = ref<number | null>(null)
const tangentFitMax = ref<number | null>(null)
const pickActive = ref(false)
const pickFirst = ref<number | null>(null)

// --- Task state / 任务状态 ---
const isRunning = ref(false)
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
// Single-result payload, or {batch:true, items, failed} in batch mode.
// 单文件结果，或批量模式下的 {batch:true, items, failed}。
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const resultData = ref<Record<string, any> | null>(null)
const selectedResultIndex = ref(0)
const profileTraces = ref<LineTrace[]>([])
const zTraces = ref<LineTrace[]>([])
const gammaTraces = ref<LineTrace[]>([])
const batchConfirming = ref(false)

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null

function cleanupAll(): void {
  cleanupProgress?.()
  cleanupResult?.()
  cleanupError?.()
  cleanupProgress = cleanupResult = cleanupError = null
}

const canRun = computed(() => {
  if (isRunning.value) return false
  if (inputMode.value === 'image') return files.value.length > 0
  return parsedQ.value.length >= 8
})

// Publish progress to the workspace-state bridge for the AI guided tour
// (Jev build); inert in the main build — no AI module is imported.
// 向状态桥上报进度供教学模式使用；主线构建中为惰性。
const lamellarExportedOnce = ref(false)
watch(
  [files, isRunning, errorMessage, resultData, () => geometry.value.poniPath, lamellarExportedOnce],
  () => {
    reportWorkspace('lamellar-analysis', {
      filesCount: files.value.length,
      hasPoni: Boolean(geometry.value.poniPath),
      canRun: canRun.value,
      phase: isRunning.value
        ? 'running'
        : errorMessage.value
          ? 'error'
          : resultData.value
            ? 'done'
            : 'idle',
      extras: { exported: lamellarExportedOnce.value },
    })
  },
  { immediate: true, deep: true }
)
onUnmounted(() => clearWorkspace('lamellar-analysis'))

// The backend ALWAYS returns q arrays (q / zQ / zExtQ) in nm⁻¹ (Å⁻¹ input is
// converted ×10 internally). The UI displays them in the unit the user
// SELECTED — so charts / window readout / CSV divide by 10 when Å⁻¹ is active;
// the q-limit inputs are in the selected unit too, and everything stays
// consistent (axis values, typed limits, output position all same unit).
// 后端返回的 q 数组（q / zQ / zExtQ）恒为 nm⁻¹（Å⁻¹ 输入内部已 ×10）。界面按
// 用户所选单位显示——Å⁻¹ 时图表 / 窗口读出 / CSV 一律 ÷10；q 上下限输入也是
// 所选单位，轴数值、输入界限、输出位置三者单位始终一致。
const qDisplayFactor = computed(() => (qUnit.value === 'A^-1' ? 0.1 : 1))
const toDisplayQ = (arr: number[]): number[] => arr.map((v) => v * qDisplayFactor.value)
const qAxisLabel = computed(() => (qUnit.value === 'nm^-1' ? 'q (nm⁻¹)' : 'q (Å⁻¹)'))

/** Human-facing copy of the q window the backend actually clipped to. */
/** 后端实际裁剪生效的 q 窗口的可读读出。 */
const appliedWindowLabel = computed(() => {
  const q = detailData.value?.quality
  if (!q || typeof q.q_min_nm !== 'number' || typeof q.q_max_nm !== 'number') return ''
  const trim = (v: number): string => v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
  const f = qDisplayFactor.value
  return t('lamellar.appliedWindow', {
    q0: trim(q.q_min_nm * f),
    q1: trim(q.q_max_nm * f),
    u: qUnit.value === 'nm^-1' ? 'nm⁻¹' : 'Å⁻¹',
    n: typeof q.n_points === 'number' ? q.n_points : 0,
  })
})

/** Auto vs manual window label for the tangent card. */
/** 切线卡片上的 自动/手动 区间标签。 */
const tangentModeLabel = computed(() =>
  detailData.value?.tangent?.window_mode === 'manual' ? t('lamellar.windowManual') : t('lamellar.windowAuto'),
)

function togglePick(): void {
  pickActive.value = !pickActive.value
  pickFirst.value = null
}

/** Two clicks on the γ₁ chart set the manual tangent window, then auto refit. */
/** 在 γ₁ 图上点击两点设定手动切线区间，随即自动重拟合。 */
function onGammaClick(event: unknown): void {
  if (!pickActive.value || isRunning.value) return
  const point = (event as { points?: { x?: unknown }[] })?.points?.[0]
  const x = point?.x
  if (typeof x !== 'number' || !Number.isFinite(x)) return
  if (pickFirst.value === null) {
    pickFirst.value = x
    return
  }
  tangentFitMin.value = Math.min(pickFirst.value, x)
  tangentFitMax.value = Math.max(pickFirst.value, x)
  pickActive.value = false
  pickFirst.value = null
  handleRun()
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const batchItems = computed<Record<string, any>[] | null>(() => {
  const d = resultData.value
  return d?.batch && Array.isArray(d.items) ? d.items : null
})

const failedFiles = computed<Record<string, string>[]>(() => {
  const d = resultData.value
  return d?.batch && Array.isArray(d.failed) ? d.failed as Record<string, string>[] : []
})

/** Detail payload: the single result, or the selected batch row. */
/** 明细数据：单次结果或批量表中选中的行。 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const detailData = computed<Record<string, any> | null>(() => {
  if (batchItems.value) {
    return batchItems.value[selectedResultIndex.value] ?? null
  }
  return resultData.value
})

const detailLabel = computed(() => {
  if (!batchItems.value || !detailData.value) return ''
  return detailData.value.sourceLabel ?? ''
})

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const res = computed<Record<string, any> | null>(() => {
  const d = detailData.value
  const first = Array.isArray(d?.results) ? d.results[0] : null
  return first ?? null
})

/** Offer batch apply after a successful single image run with files waiting. */
/** 图像模式首个文件单跑成功且还有其余文件时，提供批量应用入口。 */
const batchOfferVisible = computed(() =>
  inputMode.value === 'image'
  && files.value.length > 1
  && !!resultData.value
  && !resultData.value.batch
  && !isRunning.value,
)

const porodHint = computed(() => {
  const p = detailData.value?.porod
  if (!p) return t('lamellar.porodNone')
  return t('lamellar.porodInfo', { s: p.slope, q2: p.ext_q_max })
})

/** Mirror the fit window actually applied in the latest result. */
/** 与最近一次结果中实际应用的拟合区间保持同步。 */
watch(detailData, (d) => {
  const tan = d?.tangent
  tangentFitMin.value = typeof tan?.fit_min_nm === 'number' ? tan.fit_min_nm : null
  tangentFitMax.value = typeof tan?.fit_max_nm === 'number' ? tan.fit_max_nm : null
  pickActive.value = false
  pickFirst.value = null
})

// ── File list management / 文件列表管理 ──

function addFilePaths(picked: string[]): void {
  const existing = new Set(files.value)
  const added = picked.filter(p => p && !existing.has(p))
  if (!added.length) return
  files.value = [...files.value, ...added]
  selectedFileIndex.value = files.value.length - added.length
}

async function handleAddFiles(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      filters: dataFileFilters,
      multiSelections: true,
    })
    if (!result) return
    addFilePaths(Array.isArray(result) ? result : [result])
  } catch (err) {
    toast.push({ title: t('lamellar.errorTitle'), message: String(err), tone: 'error' })
  }
}

// Drag & drop onto the file card mirrors the add-files button.
// 拖放到文件卡片等同“添加文件”按钮。
const fileDrop = createImportDropZone({
  transport,
  extensions: () => extensionsFromFilters(dataFileFilters),
  onFiles: (paths) => addFilePaths(paths),
  onFolder: () => {
    toast.push({
      title: t('lamellar.selectFile'),
      message: t('business.fileDialog.dropOnlyFile'),
      tone: 'error',
    })
  },
})

function removeFile(idx: number): void {
  files.value.splice(idx, 1)
  if (selectedFileIndex.value >= files.value.length) {
    selectedFileIndex.value = Math.max(0, files.value.length - 1)
  }
}

function clearFiles(): void {
  files.value = []
  selectedFileIndex.value = 0
  resultData.value = null
}

function fileName(path: string): string {
  const parts = String(path).split(/[\\/]/)
  return parts[parts.length - 1] || path
}

// ── Curves parsing / 曲线解析 ──

function parseCurves(): void {
  const q: number[] = []
  const inten: number[] = []
  for (const line of curvesText.value.trim().split(/\r?\n/)) {
    const parts = line.trim().split(/[\s,;\t]+/).filter(Boolean)
    if (parts.length < 2) continue
    const x = parseFloat(parts[0])
    const y = parseFloat(parts[1])
    if (Number.isFinite(x) && Number.isFinite(y)) {
      q.push(x)
      inten.push(y)
    }
  }
  parsedQ.value = q
  parsedIntensity.value = inten
  if (q.length < 8) {
    toast.push({ title: t('lamellar.errorTitle'), message: t('lamellar.curvesParseFail'), tone: 'error' })
  }
}

async function loadCurvesFile(path: string | null): Promise<void> {
  if (!path) return
  try {
    const desktop = (window as unknown as { desktop?: { readTextFile?: (p: string) => Promise<string> } }).desktop
    if (desktop?.readTextFile) {
      curvesText.value = await desktop.readTextFile(path)
      parseCurves()
    }
  } catch (err) {
    toast.push({ title: t('lamellar.errorTitle'), message: String(err), tone: 'error' })
  }
}

// ── Params / 参数 ──

function buildParams(allFiles: boolean): Record<string, unknown> {
  const p: Record<string, unknown> = {
    inputMode: inputMode.value,
    qUnit: qUnit.value,
    background: {
      mode: bgMode.value,
      ...(bgMode.value === 'constant' && bgConstant.value !== null ? { constant: bgConstant.value } : {}),
    },
    minorityPhase: minorityPhase.value,
    // Manual tangent window (empty sides → backend auto-estimates).
    // 手动切线区间（留空的边由后端自动预估）。
    tangent: {
      fitMinNm: tangentFitMin.value,
      fitMaxNm: tangentFitMax.value,
    },
  }
  if (inputMode.value === 'image') {
    const runFiles = allFiles
      ? [...files.value]
      : (files.value[selectedFileIndex.value] ? [files.value[selectedFileIndex.value]] : [])
    p.files = runFiles
    p.geometry = { ...geometry.value }
    p.mask = { ...maskConfig.value }
    p.radialUnit = qUnit.value === 'nm^-1' ? 'q_nm^-1' : 'q_A^-1'
    p.radialMin = radialMin.value
    p.radialMax = radialMax.value
    p.npt = npt.value
    p.dropEmptyBins = true
  } else {
    p.q = [...parsedQ.value]
    p.intensity = [...parsedIntensity.value]
    // Curves mode reuses the same optional one-sided q window.
    // 曲线模式复用同一组各自可选的 q 上下限。
    p.radialMin = radialMin.value
    p.radialMax = radialMax.value
  }
  return p
}

// ── Chart traces per step / 每步曲线 ──

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildChartTraces(data: Record<string, any>): void {
  // Step 1: I(q) raw + corrected. / 第一步：原始与扣背景。
  // q arrays are converted to the selected unit for display. / q 数组按所选单位显示。
  const q = toDisplayQ(Array.isArray(data.q) ? data.q as number[] : [])
  profileTraces.value = q.length
    ? [
        { x: q, y: data.intensity ?? [], name: t('lamellar.rawCurve'), color: '#94a3b8' },
        { x: q, y: data.correctedIntensity ?? [], name: t('lamellar.correctedCurve'), color: '#2563eb' },
      ]
    : []

  // Step 2: Z(q) = q²·I(q) + Porod extension (continuation trace).
  // 第二步：洛伦兹校正曲线 + Porod 外推（延伸段）。
  const zq = toDisplayQ(Array.isArray(data.zQ) ? data.zQ as number[] : [])
  const extQ = toDisplayQ(Array.isArray(data.zExtQ) ? data.zExtQ as number[] : [])
  zTraces.value = zq.length
    ? [
        { x: zq, y: data.z ?? [], name: 'q²·I(q)', color: '#059669' },
        ...(extQ.length
          ? [{ x: extQ, y: data.zExt ?? [], name: t('lamellar.porodExt'), color: '#d97706' }]
          : []),
      ]
    : []

  // Step 3: γ₁(x) + tangent line + L marker + γ_min level line.
  // 第三步：γ₁ + 切线 + L 标线 + γ_min 水平线。
  const r = Array.isArray(data.gammaR) ? data.gammaR as number[] : []
  const gamma = Array.isArray(data.gamma) ? data.gamma as number[] : []
  const tangent = data.tangent ?? null
  const resEntry = Array.isArray(data.results) ? data.results[0] : null
  const traces: LineTrace[] = []
  if (r.length) {
    traces.push({ x: r, y: gamma, name: 'γ₁(x)', color: '#7c3aed' })
  }
  if (tangent?.line_r?.length) {
    traces.push({ x: tangent.line_r as number[], y: tangent.line_gamma as number[], name: t('lamellar.tangentName'), color: '#dc2626' })
  }
  if (resEntry?.first_min_nm != null && resEntry?.gamma_first_min != null && r.length) {
    traces.push({
      x: [0, resEntry.first_min_nm * 1.2],
      y: [resEntry.gamma_first_min, resEntry.gamma_first_min],
      name: t('lamellar.gammaMinLevel'),
      color: '#64748b',
    })
  }
  if (resEntry?.long_period_nm != null && r.length) {
    const yLo = Math.min(0, ...(gamma.length ? gamma : [0]))
    traces.push({
      x: [resEntry.long_period_nm, resEntry.long_period_nm],
      y: [yLo, 1],
      name: `${t('lamellar.lMarker')} = ${resEntry.long_period_nm.toFixed(2)} nm`,
      color: '#0ea5e9',
    })
  }
  // Active tangent fit window (auto or manual) as dashed vertical guides.
  // 当前切线拟合区间（自动或手动）以虚线竖标线显示。
  if (tangent?.fit_min_nm != null && r.length) {
    const yLo = Math.min(0, ...(gamma.length ? gamma : [0]))
    traces.push({
      x: [tangent.fit_min_nm, tangent.fit_min_nm],
      y: [yLo, 1],
      name: t('lamellar.fitWinMin'),
      color: '#9ca3af',
      dash: 'dash',
    })
    if (tangent?.fit_max_nm != null) {
      traces.push({
        x: [tangent.fit_max_nm, tangent.fit_max_nm],
        y: [yLo, 1],
        name: t('lamellar.fitWinMax'),
        color: '#9ca3af',
        dash: 'dash',
      })
    }
  }
  gammaTraces.value = traces
}

// ── Run flows / 运行流程 ──

async function runTask(params: Record<string, unknown>): Promise<void> {
  isRunning.value = true
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = null
  profileTraces.value = []
  zTraces.value = []
  gammaTraces.value = []

  try {
    const response = await transport.submitTask('lamellar_analysis', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })
    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      resultData.value = payload.data as Record<string, any>
      selectedResultIndex.value = 0
      batchConfirming.value = false
      buildChartTraces(
        resultData.value?.batch ? (resultData.value.items?.[0] ?? {}) : (resultData.value ?? {}),
      )
      isRunning.value = false
      taskId.value = null
      cleanupAll()
    })
    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      errorMessage.value = payload.error
      isRunning.value = false
      taskId.value = null
      cleanupAll()
    })
  } catch (err) {
    errorMessage.value = String(err)
    isRunning.value = false
    taskId.value = null
  }
}

async function handleRun(): Promise<void> {
  if (!canRun.value || isRunning.value) return
  await runTask(buildParams(false))
}

/** Batch run: the FIRST file's tuned conditions applied to every file. */
/** 批量运行：把第一个文件调好的条件应用到所有文件。 */
async function handleBatchRun(): Promise<void> {
  if (isRunning.value) return
  batchConfirming.value = false
  await runTask(buildParams(true))
}

function selectBatchRow(idx: number): void {
  selectedResultIndex.value = idx
  const item = batchItems.value?.[idx]
  if (item) buildChartTraces(item)
}

function handleCancel(): void {
  if (taskId.value) transport.cancelTask(taskId.value)
}

// ── Batch deviation vs the first successful item / 相对首项偏离 ──

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function itemResult(item: Record<string, any>): Record<string, any> | null {
  return Array.isArray(item.results) ? item.results[0] ?? null : null
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function deviationOf(item: Record<string, any>): number | null {
  const ref = batchItems.value?.[0] ? itemResult(batchItems.value[0]) : null
  const cur = itemResult(item)
  const lRef = ref?.long_period_nm
  const lCur = cur?.long_period_nm
  if (typeof lRef !== 'number' || typeof lCur !== 'number' || lRef <= 0) return null
  return (lCur - lRef) / lRef
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isDeviating(item: Record<string, any>): boolean {
  const dev = deviationOf(item)
  return dev !== null && Math.abs(dev) > 0.15
}

// ── Formatting & export / 格式化与导出 ──

function fmt(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return Math.abs(v) >= 100 || Math.abs(v) < 0.001 ? v.toExponential(3) : v.toFixed(3)
}

function pct(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function downloadText(content: string, name: string): void {
  const blob = new Blob([content], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function exportCsv(): void {
  const d = detailData.value
  if (!d) return
  lamellarExportedOnce.value = true
  // CSV q columns follow the selected unit (matches the on-screen charts);
  // r/gamma columns stay nm (real space is always reported in nm).
  // CSV 的 q 列按所选单位（与图表一致）；r/γ 列保持 nm（实空间恒以 nm 报告）。
  const u = qUnit.value === 'nm^-1' ? 'nm' : 'A'
  const lines: string[] = [`q_${u},intensity,corrected_intensity,q2I`]
  const q = toDisplayQ((d.q as number[]) ?? [])
  for (let i = 0; i < q.length; i++) {
    lines.push([
      q[i],
      d.intensity?.[i] ?? '',
      d.correctedIntensity?.[i] ?? '',
      d.z?.[i] ?? '',
    ].join(','))
  }
  const extQ = toDisplayQ((d.zExtQ as number[]) ?? [])
  if (extQ.length) {
    lines.push('', `porod_ext_q_${u},porod_ext_q2I`)
    for (let i = 0; i < extQ.length; i++) {
      lines.push([extQ[i], d.zExt?.[i] ?? ''].join(','))
    }
  }
  const rg = (d.gammaR as number[]) ?? []
  if (rg.length) {
    lines.push('', 'r_nm,gamma')
    for (let i = 0; i < rg.length; i++) {
      lines.push([rg[i], d.gamma?.[i] ?? ''].join(','))
    }
  }
  const tan = d.tangent ?? {}
  if (Array.isArray(tan.line_r) && tan.line_r.length) {
    lines.push('', 'tangent_r_nm,tangent_gamma')
    for (let i = 0; i < tan.line_r.length; i++) {
      lines.push([tan.line_r[i], tan.line_gamma?.[i] ?? ''].join(','))
    }
  }
  const r = res.value ?? {}
  lines.push(
    '',
    `# L=${r.long_period_nm}, L_2min=${r.long_period_2min_nm}, l_c=${r.l_crystalline_nm}, l_a=${r.l_amorphous_nm}, phi_c=${r.crystallinity_stack}`,
    `# tangent: slope=${r.tangent_slope_nm_inv}, r2=${r.tangent_r2}, fit=[${r.tangent_fit_min_nm},${r.tangent_fit_max_nm}], x@gamma_min=${r.x_at_gamma_min}, x@0=${r.x_at_gamma_zero}, O_s=${r.specific_surface_nm_inv}`,
  )
  downloadText(lines.join('\n'), 'lamellar_analysis.csv')
}

function exportBatchCsv(): void {
  const items = batchItems.value
  if (!items) return
  const lines = ['file,L_nm,L_2min_nm,l_c_nm,l_a_nm,phi_c,slope_nm_inv,r2,O_s_nm_inv,deviation_vs_first,warnings']
  for (const item of items) {
    const r = itemResult(item) ?? {}
    const dev = deviationOf(item)
    lines.push([
      `"${item.sourceLabel ?? ''}"`,
      r.long_period_nm ?? '',
      r.long_period_2min_nm ?? '',
      r.l_crystalline_nm ?? '',
      r.l_amorphous_nm ?? '',
      r.crystallinity_stack ?? '',
      r.tangent_slope_nm_inv ?? '',
      r.tangent_r2 ?? '',
      r.specific_surface_nm_inv ?? '',
      dev !== null ? (dev * 100).toFixed(1) + '%' : '',
      (item.warnings?.length ?? 0),
    ].join(','))
  }
  downloadText(lines.join('\n'), 'lamellar_batch_summary.csv')
}

onUnmounted(() => {
  cleanupAll()
})
</script>

<style scoped>
.lm-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.lm-header h1 { margin: 0 0 4px; font-size: 1.5rem; }
.lm-subtitle { margin: 0; color: var(--color-text-muted, #6b7280); font-size: 0.92rem; }
.lm-layout {
  display: grid;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.lm-sidebar { display: flex; flex-direction: column; gap: 16px; }
.lm-main { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.lm-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lm-details > summary { cursor: pointer; font-weight: 600; }
.lm-card-title { margin: 0; font-size: 0.95rem; font-weight: 600; }
.lm-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.lm-field-row { display: flex; gap: 8px; }
.lm-label { font-size: 0.82rem; color: var(--color-text-muted, #6b7280); }
.lm-input, .lm-select, .lm-textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 4px;
  font-size: 0.88rem;
  background: var(--color-surface, #fff);
  box-sizing: border-box;
}
.lm-textarea { font-family: monospace; resize: vertical; }
.lm-radio-row, .lm-btn-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
.lm-radio-label { display: flex; align-items: center; gap: 6px; font-size: 0.88rem; cursor: pointer; }
.lm-hint { margin: 0; font-size: 0.78rem; color: var(--color-text-muted, #6b7280); }
.lm-hint-ok { color: #16a34a; }
.lm-hint-warn { color: #b45309; }
.lm-btn {
  padding: 7px 14px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 4px;
  background: var(--color-surface, #fff);
  cursor: pointer;
  font-size: 0.88rem;
}
.lm-btn:hover { background: var(--color-surface-hover, #f3f4f6); }
.lm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.lm-btn-sm { padding: 4px 10px; font-size: 0.82rem; }
.lm-btn-primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.lm-btn-primary:hover { background: #1d4ed8; }
.lm-btn-icon {
  border: none; background: none; cursor: pointer; color: var(--color-text-muted, #6b7280);
  font-size: 1rem; line-height: 1; padding: 2px 4px;
}
.lm-btn-icon:hover { color: #dc2626; }
.lm-run-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.lm-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 0.88rem;
}
.lm-batch-offer {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  padding: 12px 14px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lm-warnings {
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
}
.lm-warnings ul { margin: 6px 0 0; padding-left: 18px; }
.lm-warnings li { margin-bottom: 3px; }
.lm-chart { background: var(--color-surface, #fff); border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 8px; }
.lm-tangent-bar { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.lm-tangent-fields { min-width: 230px; }
.lm-section-title { margin: 0; font-size: 1.05rem; }
.lm-detail-label {
  font-size: 0.85rem;
  color: var(--color-text-muted, #6b7280);
  word-break: break-all;
}
.lm-table-wrap { overflow-x: auto; }
.lm-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.lm-table th, .lm-table td { padding: 6px 10px; border-bottom: 1px solid var(--color-border, #e5e7eb); text-align: right; white-space: nowrap; }
.lm-table th:first-child, .lm-table td:first-child { text-align: left; }
.lm-row--active { background: #eff6ff; cursor: pointer; }
.lm-table tbody tr { cursor: pointer; }
.lm-batch-meta { font-weight: 400; font-size: 0.8rem; color: var(--color-text-muted, #6b7280); margin-left: 8px; }
.lm-dev { font-variant-numeric: tabular-nums; }
.lm-dev--warn { color: #b45309; font-weight: 600; }
.lm-failed {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 0.82rem;
}
.lm-failed ul { margin: 4px 0 0; padding-left: 18px; }
.lm-failed code { word-break: break-all; }
.lm-slope-card { border-left: 4px solid #dc2626; }
.lm-slope-grid { display: flex; flex-direction: column; gap: 4px; }
.lm-slope-main { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.lm-slope-val { font-variant-numeric: tabular-nums; font-weight: 700; font-size: 1.15rem; color: #dc2626; }
.lm-results { display: flex; flex-direction: column; gap: 10px; }
.lm-result-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.lm-result-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 12px 14px;
}
.lm-result-method { margin: 0 0 8px; font-size: 0.95rem; color: #2563eb; }
.lm-result-row { display: flex; justify-content: space-between; font-size: 0.88rem; padding: 2px 0; gap: 10px; }
.lm-result-key { color: var(--color-text-muted, #6b7280); }
.lm-result-val { font-variant-numeric: tabular-nums; font-weight: 600; text-align: right; }
.lm-card--files.lm-card--drop { border-color: #2563eb; background: #eff6ff; }
.lm-file-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; max-height: 220px; overflow-y: auto; }
.lm-file-item {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 3px 8px; border-radius: 4px; border: 1px solid transparent;
}
.lm-file-item--active { background: #eff6ff; border-color: #bfdbfe; }
.lm-file-name { word-break: break-all; font-size: 0.82rem; }
@media (max-width: 960px) {
  .lm-layout { grid-template-columns: 1fr; }
}
</style>
