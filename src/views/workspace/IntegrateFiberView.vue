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
        <!-- ── Group 1: Geometry & Corrections / 几何与校正 ── -->
        <div class="fib-collapsible">
          <div class="fib-section-toggle" @click="geomExpanded = !geomExpanded">
            <span class="fib-toggle-icon">{{ geomExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('integrateFiber.geomGroup') }}</span>
          </div>
          <div v-show="geomExpanded" class="fib-collapsible-body fib-group-body">
            <GeometryForm v-model="geometry" />

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
              <!-- Override PONI rotations (PONI mode only) / 覆盖 PONI 旋转（仅 PONI 模式） -->
              <label v-if="geometry.poniPath" class="fib-toggle" style="margin-top:6px">
                <input v-model="overridePoniRot" type="checkbox" />
                <span class="fib-toggle-label">{{ t('integrateFiber.overridePoniRot') }}</span>
              </label>
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
                    <option v-for="o in 8" :key="o" :value="o" :title="orientationHints[o]">{{ o }}</option>
                  </select>
                  <span class="fib-hint">{{ orientationHints[fiberParams.sampleOrientation] }}</span>
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
          </div>
        </div>

        <!-- ── Group 2: Integration Params / 积分参数 ── -->
        <div class="fib-collapsible">
          <div class="fib-section-toggle" @click="integExpanded = !integExpanded">
            <span class="fib-toggle-icon">{{ integExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('integrateFiber.integGroup') }}</span>
          </div>
          <div v-show="integExpanded" class="fib-collapsible-body fib-group-body">
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
                <!-- pyFAI integration algorithm (same set as the 1D page) -->
                <!-- pyFAI 积分算法（与 1D 积分页一致） -->
                <label class="fib-field" style="grid-column: 1 / -1">
                  <span class="fib-label">{{ t('integrateFiber.method') }}</span>
                  <select
                    class="fib-select"
                    :value="fiberParams.method"
                    :data-testid="testIds.fiberAlgorithmMethod"
                    @change="onSelectParam('method', $event)"
                  >
                    <option v-for="m in algorithmOptions" :key="m.value" :value="m.value">
                      {{ m.label }}
                    </option>
                  </select>
                </label>
              </div>
            </fieldset>
          </div>
        </div>

        <!-- ── Group 3: Display settings (always expanded, non-collapsible) / 显示设置（永不折叠） ── -->
        <div class="fib-section-static">
          <div class="fib-section-toggle fib-section-toggle-static">
            <span>{{ t('business.sections.displaySettings') }}</span>
          </div>
          <div class="fib-collapsible-body">
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
            <!-- Contrast controls (moved from main chart area) / 对比度控件（从主区移入） -->
            <label class="fib-field fib-contrast-field" style="margin-top:8px">
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
            <!-- Log floor: clamp sub-threshold values in log mode (collapsed by default) -->
            <!-- 对数阈值：对数模式下 clamp 小于阈值的值（默认折叠关闭） -->
            <label class="fib-toggle" style="margin-top:8px">
              <input v-model="logFloorEnabled" type="checkbox" :disabled="!useLog" />
              <span class="fib-toggle-label">{{ t('integrateFiber.logFloorEnable') }}</span>
            </label>
            <label v-if="logFloorEnabled && useLog" class="fib-field fib-contrast-field">
              <span class="fib-label">{{ t('integrateFiber.logFloor') }}</span>
              <input v-model.number="logFloorValue" type="number" class="fib-input" step="any" min="0" />
              <span class="fib-hint">{{ t('integrateFiber.logFloorHint') }}</span>
            </label>
          </div>
        </div>

        <!-- ── Export result (sidebar, expands after preview) / 导出结果（侧栏，预览后展开） ── -->
        <div v-if="result" class="fib-collapsible">
          <div class="fib-section-toggle" @click="exportExpanded = !exportExpanded">
            <span class="fib-toggle-icon">{{ exportExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('integrateFiber.exportGroup') }}</span>
          </div>
          <div v-show="exportExpanded" class="fib-collapsible-body">
            <ExportDialog
              :formats="exportFormats"
              :data-testid="testIds.fiberExport"
              @export="onExport"
            />
          </div>
        </div>

      </aside>

      <!-- ═══════ Main content area ═══════ -->
      <main class="fiber-main">
        <!-- File selection / 文件选择（支持拖放 / drop target） -->
        <div
          class="fib-file-section"
          :class="{ 'fib-file-section--drop': fileDrop.isDragging.value }"
          @dragenter="fileDrop.onDragEnter"
          @dragover="fileDrop.onDragOver"
          @dragleave="fileDrop.onDragLeave"
          @drop="fileDrop.onDrop"
        >
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
          <div class="fib-file-info-bar fib-file-info-bar--muted fib-drop-hint">
            <span>{{ t('business.fileSelection.dropZoneHint') }}</span>
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

        <!-- Run button / 执行按钮 -->
        <div class="fib-run-section">
          <button
            type="button"
            class="fib-run-btn"
            :disabled="!canRun || isPreviewRunning"
            :data-testid="testIds.fiberRunBtn"
            @click="runPreviewIntegration"
          >
            {{ isPreviewRunning ? t('integrateFiber.running') : t('integrateFiber.preview') }}
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

        <div v-if="previewError" class="fib-error-box">
          <p>{{ previewError }}</p>
        </div>

        <!-- Empty state (before any integration) / 空状态（积分前） -->
        <div v-if="!isPreviewRunning && !result && !previewError" class="fib-empty">
          <p>{{ t('integrateFiber.emptyHint') }}</p>
        </div>

        <!-- ═══════ Result tabs (shown once a result exists) / 结果 Tab（有结果后显示） ═══════ -->
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

          <!-- Shared result thumbnails / 共享结果缩略图 -->
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

          <!-- ═══ Shared 2D heatmap (common to all tabs) + ROI overlay + contrast ═══ -->
          <!-- 共享 2D 热图（各 tab 公用）+ ROI 框选叠加 + 对比度控件 -->
          <div class="fib-chart-container">
            <div class="fib-roi-image-wrapper" ref="roiImageWrapperRef">
              <ImagePreview
                :image-b64="result.previewB64"
                :show-colorbar="true"
                :colorbar-gradient="colorbarGradient"
                :colorbar-min-label="heatmapZMin !== undefined ? formatSci(heatmapZMin) : colorbarMinLabel"
                :colorbar-max-label="heatmapZMax !== undefined ? formatSci(heatmapZMax) : colorbarMaxLabel"
                :title="t('integrateFiber.heatmapTitle')"
                :data-testid="testIds.fiberHeatmap"
              />
              <!-- ROI selection overlay / ROI 框选叠加层 -->
              <canvas
                v-if="roiMode && result?.previewB64"
                ref="roiCanvasRef"
                class="fib-roi-canvas"
                @mousedown="onRoiMouseDown"
                @mousemove="onRoiMouseMove"
                @mouseup="onRoiMouseUp"
                @mouseleave="onRoiMouseUp"
              />
            </div>
          </div>

          <!-- Tab switcher (1D curves / PNG export) / Tab 切换（1D 曲线 / PNG 导出） -->
          <div class="fib-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'roi'"
              :class="['fib-tab', { 'fib-tab-active': activeTab === 'roi' }]"
              @click="activeTab = 'roi'"
            >{{ t('integrateFiber.tabRoi') }}</button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'png'"
              :class="['fib-tab', { 'fib-tab-active': activeTab === 'png' }]"
              @click="activeTab = 'png'"
            >{{ t('integrateFiber.tabPng') }}</button>
          </div>

          <!-- ─── Tab: 1D ROI Integration ─── -->
          <div v-if="activeTab === 'roi'" class="fib-tab-panel">
            <!-- ROI parameters / ROI 参数 -->
            <div class="fib-roi-panel">
              <h3>1D ROI Integration / 区域1D积分</h3>
              <p v-if="!roi1dResult" class="fib-roi-hint">
                Set IP/OOP range + npt, enable selection mode to draw a box on the heatmap above, then run.<br />
                设置面内/面外范围与点数，勾选框选模式后在上方热图上框选区域，再执行。
              </p>

              <label class="fib-toggle" style="margin-bottom:8px">
                <input v-model="roiMode" type="checkbox" />
                <span class="fib-toggle-label">ROI selection mode / 框选模式</span>
              </label>

              <div class="fib-grid fib-roi-grid">
                <!-- ROI qip/qoop units — user-selectable, kept in sync with the
                     sidebar units so the rectangle, numeric ranges and backend
                     integration always share one unit system. -->
                <!-- ROI 的 qip/qoop 单位由用户选择，与侧栏坐标单位双向同步，
                     保证框选矩形、数值范围与后端积分始终同一单位体系。 -->
                <label class="fib-field" style="grid-column: 1 / -1">
                  <span class="fib-label">{{ t('integrateFiber.unitIp') }}</span>
                  <select
                    class="fib-select"
                    :value="fiberParams.unitIp"
                    @change="onSelectParam('unitIp', $event)"
                  >
                    <option v-for="u in unitIpOptions" :key="u.value" :value="u.value">
                      {{ u.label }}
                    </option>
                  </select>
                </label>
                <label class="fib-field" style="grid-column: 1 / -1">
                  <span class="fib-label">{{ t('integrateFiber.unitOop') }}</span>
                  <select
                    class="fib-select"
                    :value="fiberParams.unitOop"
                    @change="onSelectParam('unitOop', $event)"
                  >
                    <option v-for="u in unitOopOptions" :key="u.value" :value="u.value">
                      {{ u.label }}
                    </option>
                  </select>
                </label>
                <label class="fib-field">
                  <span class="fib-label">IP min</span>
                  <input v-model.number="roiIpMin" type="number" class="fib-input" step="any" />
                </label>
                <label class="fib-field">
                  <span class="fib-label">IP max</span>
                  <input v-model.number="roiIpMax" type="number" class="fib-input" step="any" />
                </label>
                <label class="fib-field">
                  <span class="fib-label">OOP min</span>
                  <input v-model.number="roiOopMin" type="number" class="fib-input" step="any" />
                </label>
                <label class="fib-field">
                  <span class="fib-label">OOP max</span>
                  <input v-model.number="roiOopMax" type="number" class="fib-input" step="any" />
                </label>
                <label class="fib-field">
                  <span class="fib-label">npt</span>
                  <input v-model.number="roiNpt" type="number" class="fib-input" min="50" step="50" />
                </label>
              </div>

              <p class="fib-hint" style="grid-column: 1 / -1; margin: 0">
                Units apply to the ROI ranges and 1D profiles; re-run the 2D integration to refresh the map axes after changing them.
                单位同时作用于 ROI 数值范围与 1D 剖面；更改后请重新执行 2D 积分以刷新图坐标。
              </p>

              <label class="fib-toggle" style="margin:8px 0">
                <input v-model="roiAbsQ" type="checkbox" />
                <span class="fib-toggle-label">|q| axis / q轴取绝对值</span>
              </label>

              <div class="fib-roi-actions">
                <button
                  type="button"
                  class="fib-run-btn"
                  :disabled="!canRunRoi || roiRunning"
                  @click="runRoiIntegration"
                >
                  {{ roiRunning ? 'Running...' : 'Run 1D / 执行1D积分' }}
                </button>
                <button
                  v-if="roi1dResult"
                  type="button"
                  class="fib-run-btn"
                  :disabled="roiRunning"
                  @click="exportRoi1d"
                >
                  Export 1D / 导出1D曲线
                </button>
              </div>

              <div v-if="roiError" class="fib-error-box">
                <p>{{ roiError }}</p>
              </div>
            </div>

            <!-- 1D result curves: out-of-plane (qoop) + in-plane (qip) -->
            <!-- 1D 结果曲线：面外 (qoop) + 面内 (qip) 两个方向 -->
            <div v-if="roi1dResult" class="fib-roi-chart-main">
              <h3>1D ROI Result / 1D 区域积分结果</h3>
              <div class="fib-roi-charts">
                <div class="fib-roi-chart-cell">
                  <p class="fib-roi-chart-caption">{{ roiOopCaption }}</p>
                  <LineChart
                    :traces="roi1dTraces"
                    :x-title="roi1dResult?.unit ? `${roi1dResult.unit}` : ''"
                    :y-title="'Intensity'"
                    :legend-visible="false"
                  />
                </div>
                <div v-if="roi1dTracesIp.length > 0" class="fib-roi-chart-cell">
                  <p class="fib-roi-chart-caption">{{ roiIpCaption }}</p>
                  <LineChart
                    :traces="roi1dTracesIp"
                    :x-title="roi1dResult?.unitIp ? `${roi1dResult.unitIp}` : ''"
                    :y-title="'Intensity'"
                    :legend-visible="false"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- ─── Tab: PNG Export ─── -->
          <div v-if="activeTab === 'png'" class="fib-tab-panel">
            <!-- Annotated (matplotlib) preview — WYSIWYG with exported PNG. -->
            <!-- 带坐标轴预览（所见即所得） -->
            <div class="fib-mpl-preview">
              <div class="fib-mpl-preview-header">
                <h3>PNG Preview / PNG 预览</h3>
                <label class="fib-toggle">
                  <input v-model="mplPreviewEnabled" type="checkbox" @change="void refreshMplPreview()" />
                  <span class="fib-toggle-label">Show / 显示</span>
                </label>
              </div>
              <div v-if="resultSummaries.length > 1" class="fib-mpl-hint">
                {{ t('integrateFiber.multiResultHint', { current: currentResultIndex + 1, total: resultSummaries.length }) }}
              </div>
              <div v-if="mplPreviewEnabled" class="fib-mpl-preview-body">
                <div v-if="mplPreviewLoading" class="fib-mpl-loading">Rendering… / 渲染中…</div>
                <img
                  v-else-if="mplPreviewB64"
                  :src="`data:image/png;base64,${mplPreviewB64}`"
                  class="fib-mpl-img"
                  alt="Annotated GIWAXS result preview"
                />
                <div v-else class="fib-mpl-empty">No preview yet. Run integration first. / 暂无预览，请先执行积分。</div>
              </div>
            </div>

            <!-- Export current result as single PNG / 导出当前结果为单张 PNG -->
            <!-- Batch export all results as PNG / 批量导出全部为 PNG -->
            <div class="fib-png-batch-row">
              <button
                type="button"
                class="fib-run-btn fib-batch-png-btn"
                :disabled="!result || pngBatchExporting"
                @click="onExportCurrentPng"
              >
                {{ t('integrateFiber.exportCurrentPng') }}
              </button>
              <button
                type="button"
                class="fib-run-btn fib-batch-png-btn"
                :disabled="!result || pngBatchExporting"
                @click="onBatchExportPng"
              >
                {{ pngBatchExporting
                    ? t('business.taskProgress.processing')
                    : t('integrateFiber.batchPng') }}
              </button>
            </div>

            <!-- PNG Options (below batch button) / PNG 选项（批量按钮下方） -->
            <div class="fib-collapsible">
              <div class="fib-section-toggle" @click="pngOptionsExpanded = !pngOptionsExpanded">
                <span class="fib-toggle-icon">{{ pngOptionsExpanded ? '▾' : '▸' }}</span>
                <span>PNG Options / PNG 选项</span>
              </div>
              <div v-show="pngOptionsExpanded" class="fib-collapsible-body">
                <label class="fib-toggle" style="margin-bottom:8px">
                  <input v-model="pngShowLabels" type="checkbox" />
                  <span class="fib-toggle-label">Show axis labels / 显示坐标轴标注</span>
                </label>
                <div class="fib-grid">
                  <label class="fib-field">
                    <span class="fib-label">Font size / 字号</span>
                    <input v-model.number="pngFontSize" type="number" class="fib-input" min="6" max="36" step="1" />
                  </label>
                  <label class="fib-field">
                    <span class="fib-label">DPI / 分辨率</span>
                    <select v-model.number="pngDpi" class="fib-select">
                      <option :value="72">72 (screen)</option>
                      <option :value="100">100</option>
                      <option :value="150">150 (default)</option>
                      <option :value="300">300 (print)</option>
                      <option :value="600">600 (hi-res)</option>
                    </select>
                  </label>
                </div>
                <label class="fib-field" style="margin-top:8px">
                  <span class="fib-label">No-data fill / 无数据填充</span>
                  <select v-model="pngNoDataBg" class="fib-select">
                    <option value="white">White / 白色</option>
                    <option value="black">Black / 黑色</option>
                    <option value="transparent">Transparent / 透明</option>
                  </select>
                </label>

                <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">
                  <label class="fib-toggle">
                    <input v-model="pngShowColorbar" type="checkbox" />
                    <span class="fib-toggle-label">Colorbar / 色条</span>
                  </label>
                  <label class="fib-toggle">
                    <input v-model="pngShowTitle" type="checkbox" />
                    <span class="fib-toggle-label">Title (filename) / 标题(文件名)</span>
                  </label>
                </div>

                <div class="fib-grid" style="margin-top:8px">
                  <label class="fib-field">
                    <span class="fib-label">Border / 边框粗细</span>
                    <input v-model.number="pngBorderWidth" type="number" class="fib-input" min="0" max="6" step="0.5" />
                  </label>
                  <label class="fib-field">
                    <span class="fib-label">Edge color / 边框颜色</span>
                    <div class="fib-color-row">
                      <input v-model="pngEdgeColor" type="color" class="fib-color-input" />
                      <select v-model="pngEdgeColor" class="fib-select">
                        <option value="black">Black / 黑</option>
                        <option value="white">White / 白</option>
                        <option value="#1f2937">Slate / 深灰</option>
                        <option value="#dc2626">Red / 红</option>
                        <option value="#2563eb">Blue / 蓝</option>
                      </select>
                    </div>
                  </label>
                </div>

                <div class="fib-grid" style="margin-top:8px">
                  <label class="fib-field">
                    <span class="fib-label">X axis title / X 轴标题</span>
                    <input v-model="pngXLabel" type="text" class="fib-input" :placeholder="t('integrateFiber.xAxisPlaceholder')" />
                  </label>
                  <label class="fib-field">
                    <span class="fib-label">Y axis title / Y 轴标题</span>
                    <input v-model="pngYLabel" type="text" class="fib-input" :placeholder="t('integrateFiber.yAxisPlaceholder')" />
                  </label>
                </div>
                <label class="fib-field" style="margin-top:8px">
                  <span class="fib-label">Font / 字体</span>
                  <select v-model="pngFontFamily" class="fib-select">
                    <option v-for="f in FONT_OPTIONS" :key="f" :value="f">{{ f || 'Default / 默认' }}</option>
                  </select>
                </label>
                <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">
                  <label class="fib-toggle">
                    <input v-model="pngShowAxisTitle" type="checkbox" />
                    <span class="fib-toggle-label">Axis titles / 轴标题文字</span>
                  </label>
                  <label class="fib-toggle">
                    <input v-model="pngShowTicks" type="checkbox" />
                    <span class="fib-toggle-label">Tick marks &amp; numbers / 刻度与数值</span>
                  </label>
                </div>
                <div v-if="pngShowTicks" class="fib-grid" style="margin-top:8px">
                  <label class="fib-field">
                    <span class="fib-label">{{ t('integrateFiber.xTickStep') }}</span>
                    <input v-model.number="pngXTickStep" type="number" class="fib-input" step="any" :placeholder="t('integrateFiber.tickStepPlaceholder')" />
                  </label>
                  <label class="fib-field">
                    <span class="fib-label">{{ t('integrateFiber.yTickStep') }}</span>
                    <input v-model.number="pngYTickStep" type="number" class="fib-input" step="any" :placeholder="t('integrateFiber.tickStepPlaceholder')" />
                  </label>
                </div>

                <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">
                  <label class="fib-toggle">
                    <input v-model="pngTitleBold" type="checkbox" />
                    <span class="fib-toggle-label">Bold title / 标题加粗</span>
                  </label>
                  <label class="fib-toggle">
                    <input v-model="pngAxisTitleBold" type="checkbox" />
                    <span class="fib-toggle-label">Bold axis titles / xy小标题加粗</span>
                  </label>
                  <label class="fib-toggle">
                    <input v-model="pngTickBold" type="checkbox" />
                    <span class="fib-toggle-label">Bold tick numbers / 坐标轴数字加粗</span>
                  </label>
                </div>

                <div style="display:flex;flex-direction:column;gap:6px;margin-top:8px">
                  <label class="fib-toggle">
                    <input v-model="pngFlipX" type="checkbox" />
                    <span class="fib-toggle-label">Flip X axis / X轴反转</span>
                  </label>
                  <label class="fib-toggle">
                    <input v-model="pngFlipY" type="checkbox" />
                    <span class="fib-toggle-label">Flip Y axis / Y轴反转</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </section>
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
import { ref, reactive, computed, watch, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { createImportDropZone, extensionsFromFilters } from '@/lib/fileDrop'
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
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'

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

/** Sample orientation hints from pyFAI / pyFAI 样品方向说明 */
const orientationHints: Record<number, string> = {
  1: '1 – No changes / 无变化',
  2: '2 – Mirrored (flip horizontally) / 水平翻转',
  3: '3 – Rotated 180° / 旋转180°',
  4: '4 – Rotated 180° + mirrored / 旋转180°+翻转',
  5: '5 – Mirrored + rotated 90° CCW / 翻转+逆时针90°',
  6: '6 – Rotated 90° CCW / 逆时针旋转90°',
  7: '7 – Mirrored + rotated 90° CW / 翻转+顺时针90°',
  8: '8 – Rotated 90° CW / 顺时针旋转90°',
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
/**
 * pyFAI integration algorithm. 'auto' omits the method argument entirely,
 * reproducing the pre-0.2.4 behavior (pyFAI default: no pixel splitting,
 * histogram). The explicit values change how pixels are split/rebinned and
 * can look "stretched" under the nonlinear GIWAXS χ–q transform.
 * pyFAI 积分算法。'auto' 表示完全不传 method 参数，与旧版行为一致
 * （pyFAI 默认：不分裂像素的直方图法）。显式算法会改变像素分裂/重排方式，
 * 在 GIWAXS 非线性 χ–q 变换下可能出现"拉伸"观感。
 */
type FiberAlgorithmMethod = 'auto' | 'splitpixel' | 'csr' | 'lut' | 'bbox' | 'numpy'

const algorithmOptions: Array<{ value: FiberAlgorithmMethod; label: string }> = [
  { value: 'auto', label: 'Default (pyFAI, no split)' },
  { value: 'splitpixel', label: 'SplitPixel (full split)' },
  { value: 'csr', label: 'CSR (fast)' },
  { value: 'lut', label: 'LUT (fast)' },
  { value: 'bbox', label: 'BBox (approx.)' },
  { value: 'numpy', label: 'NumPy (fallback)' },
]

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
  method: FiberAlgorithmMethod
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
  autoRange: true,
  ipMin: -20,
  ipMax: 20,
  oopMin: -20,
  oopMax: 20,
  nptIp: 400,
  nptOop: 400,
  method: 'auto',
})

/** When true (PONI mode only), user rot1/rot2/rot3 override the PONI file values.
 *  PONI 模式下开启时，用户输入的 rot1/rot2/rot3 覆盖 PONI 文件中的旋转值。 */
const overridePoniRot = ref(false)

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

// ── Result state / 结果状态 ──
const result = ref<FiberResult | null>(null)
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
const thumbExpanded = ref(true)
// Sidebar section groups — default expanded (per requirement) / 侧栏分组默认展开
const geomExpanded = ref(true)
const integExpanded = ref(true)
// Display settings is always expanded (non-collapsible, per requirement).
// 显示设置永不折叠。
const displayExpanded = ref(true)
// Export result section in sidebar — collapsed until preview runs / 导出区默认收起，预览积分后展开
const exportExpanded = ref(false)
// Mask import lives inside the Geometry group — keep collapsed by default / 掩膜默认收起
const maskExpanded = ref(false)
// Batch PNG export (in PNG tab) busy state / 批量 PNG 导出忙碌状态
const pngBatchExporting = ref(false)

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

const exportFormats: ExportFormat[] = ['tiff', 'edf', 'npy', 'hdf5', 'csv', 'png']

// ── PNG export options / PNG 导出选项 ──
const pngShowLabels = ref(true)
const pngFontSize = ref(12)
const pngDpi = ref(150)
const pngOptionsExpanded = ref(true)
// Fill for no-data (NaN) pixels + figure background / 无数据(NaN)像素及图背景填充
const pngNoDataBg = ref<'white' | 'black' | 'transparent'>('white')
// Publication-style extras / 出版风格附加项
const pngShowColorbar = ref(true)       // 是否绘制色条
const pngShowTitle = ref(false)         // 是否绘制标题（文件名）
const pngBorderWidth = ref(1.0)         // 边框粗细（磅），0=无边框
const pngEdgeColor = ref('black')       // 边框/刻度/标签颜色
// Custom axis titles + font + granular toggles / 自定义轴标题与字体与粒度开关
const pngXLabel = ref('')               // 自定义 X 轴标题（空=用单位推导）
const pngYLabel = ref('')               // 自定义 Y 轴标题（空=用单位推导）
const pngFontFamily = ref('')           // 字体（空=默认）；如 Arial / Times New Roman
const pngShowAxisTitle = ref(true)      // 是否绘制轴标题文字
const pngShowTicks = ref(true)          // 是否绘制刻度线与数值
// Bold (3 independent) + axis flip (default on, per-axis) / 加粗(3独立) + 轴反转(默认开, 各轴独立)
const pngTitleBold = ref(false)         // 标题加粗
const pngAxisTitleBold = ref(false)     // x/y 轴标题加粗
const pngTickBold = ref(false)          // 刻度数字加粗
const pngFlipX = ref(true)              // X 轴反转（默认开，匹配样品方向约定）
const pngFlipY = ref(true)              // Y 轴反转（默认开）
// Log floor (problem 2): clamp sub-threshold finite values in log mode / 对数阈值
const logFloorEnabled = ref(false)       // 对数阈值开关（默认关）
const logFloorValue = ref(0.01)          // 阈值（小于此值的有限数据以此值显示）
// Tick step (problem 5): custom axis tick spacing / 刻度间隔
const pngXTickStep = ref<number | null>(null)  // X 刻度间隔（null=自动）
const pngYTickStep = ref<number | null>(null)  // Y 刻度间隔（null=自动）

// ── Tab navigation / Tab 导航 ──
const activeTab = ref<'roi' | 'png'>('roi')

// Common publication fonts offered in the dropdown / 下拉常用出版字体
const FONT_OPTIONS = [
  '',                   // default / 默认
  'Arial',
  'Times New Roman',
  'Calibri',
  'Cambria',
  'DejaVu Sans',
  'DejaVu Serif',
  'Courier New',
  'SimHei',             // 黑体（中文）
  'Microsoft YaHei',    // 微软雅黑（中文）
]

// ── Annotated matplotlib preview (WYSIWYG with exported PNG) / 带坐标轴的所见即所得预览 ──
// A small image rendered server-side via render_png_mpl, shown below the heatmap
// so the user can see axes/labels/no-data fill exactly as they will export.
const mplPreviewB64 = ref<string | null>(null)
const mplPreviewLoading = ref(false)
const mplPreviewEnabled = ref(true)

// ── ROI 1D Integration state / ROI区域1D积分状态 ──
const roiMode = ref(false)
// ROI section collapsed until a 2D result exists and/or 1D runs / ROI 区域默认折叠，有结果/跑完1D后展开
const roiExpanded = ref(false)
const roiIpMin = ref(0)
const roiIpMax = ref(10)
const roiOopMin = ref(0)
const roiOopMax = ref(10)
const roiNpt = ref(100)
const roiAbsQ = ref(true)  // default: take |q| / 默认q轴取绝对值
const roiRunning = ref(false)
const roiError = ref<string | null>(null)
const roi1dResult = ref<{
  curves: Array<{ radial: number[]; intensity: number[]; filename: string }>
  unit: string
  curvesIp: Array<{ radial: number[]; intensity: number[]; filename: string }>
  unitIp: string
} | null>(null)
const roiImageWrapperRef = ref<HTMLElement | null>(null)
const roiCanvasRef = ref<HTMLCanvasElement | null>(null)

// ROI rectangle drawing state / ROI 矩形框选状态
const roiDrawing = ref(false)
const roiStartX = ref(0)
const roiStartY = ref(0)
const roiEndX = ref(0)
const roiEndY = ref(0)

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
      log_floor: logFloorEnabled.value && useLog.value ? logFloorValue.value : null,
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
  // Reveal ROI section now that a 2D result exists / 有2D结果后展开ROI区域使其可设置
  roiExpanded.value = true
  // Refresh the annotated (matplotlib) preview for the newly loaded result / 刷新带坐标轴预览
  void refreshMplPreview()

}

/**
 * Fetch a matplotlib-rendered PNG (with axes/colorbar/no-data fill) that matches
 * exactly what Export→PNG will produce. Shown below the heatmap for WYSIWYG.
 * 获取与「导出 PNG」完全一致的带坐标轴出版质量预览图，显示在热图下方（所见即所得）。
 */
async function refreshMplPreview(): Promise<void> {
  if (!batchCachePath.value || !mplPreviewEnabled.value) {
    mplPreviewB64.value = null
    return
  }
  mplPreviewLoading.value = true
  try {
    const raw = await submitAndWait('viewer_config', {
      action: 'fiber_result_mpl_preview',
      batchCachePath: batchCachePath.value,
      resultIndex: currentResultIndex.value,
      unitIp: fiberParams.unitIp,
      unitOop: fiberParams.unitOop,
      pngOptions: {
        showLabels: pngShowLabels.value,
        fontSize: pngFontSize.value,
        dpi: 100, // preview DPI kept low for speed; export uses pngDpi / 预览用低DPI提速
        cmap: colormap.value,
        useLog: useLog.value,
        noDataBg: pngNoDataBg.value,
        showColorbar: pngShowColorbar.value,
        showTitle: pngShowTitle.value,
        borderWidth: pngBorderWidth.value,
        edgeColor: pngEdgeColor.value,
        title: pngShowTitle.value ? (result.value?.filename ?? fileName.value ?? undefined) : undefined,
        xLabel: pngXLabel.value || null,
        yLabel: pngYLabel.value || null,
        fontFamily: pngFontFamily.value || null,
        showAxisTitle: pngShowAxisTitle.value,
        showTicks: pngShowTicks.value,
        titleBold: pngTitleBold.value,
        axisTitleBold: pngAxisTitleBold.value,
        tickBold: pngTickBold.value,
        flipX: pngFlipX.value,
        flipY: pngFlipY.value,
        logFloor: logFloorEnabled.value && useLog.value ? logFloorValue.value : null,
        xTickStep: pngXTickStep.value,
        yTickStep: pngYTickStep.value,
        // In auto mode, forward the on-screen contrast (resultContrast) so the
        // preview matches the heatmap exactly instead of Python recomputing it.
        // 自动模式下透传屏幕对比度，使预览与热图一致而非后端重算。
        clim: resultClimMode.value === 'manual'
          ? [resultClimMin.value, resultClimMax.value]
          : (resultContrast.value
              ? [useLog.value ? resultContrast.value.logMin : resultContrast.value.autoMin,
                 useLog.value ? resultContrast.value.logMax : resultContrast.value.autoMax]
              : null),
      },
    })
    const data = raw as { mplPreviewB64?: string }
    mplPreviewB64.value = data.mplPreviewB64 ?? null
  } catch {
    // Non-fatal: the heatmap above still works; just hide the annotated preview.
    mplPreviewB64.value = null
  } finally {
    mplPreviewLoading.value = false
  }
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
    log_floor: logFloorEnabled.value && useLog.value ? logFloorValue.value : null,
  }
}

function buildGeometryPayload(): Record<string, unknown> {
  const geo = geometry.value
  if (geo.poniPath) {
    return { poniPath: geo.poniPath }
  }
  // Return raw fields (original units) so resolve_geometry_center can read
  // pixel1/distance/wavelength/centerX/centerY directly, and task-adapter's
  // buildFiberGeometry can normalize (unit conversion + rot) for fiber_1d_roi.
  // Previously this returned a {manual:{dist,poni1,...}} dict with wrong units
  // (mm/Å instead of m) and swapped poni1/poni2, causing ROI geometry mismatch.
  // 返回原始字段（原始单位），使 resolve_geometry_center 可直接读取
  // pixel1/distance/wavelength/centerX/centerY，task-adapter 的 buildFiberGeometry
  // 可为 fiber_1d_roi 做归一化（单位转换 + rot）。
  return {
    pixel1: geo.pixel1,
    pixel2: geo.pixel2,
    distance: geo.distance,
    wavelength: geo.wavelength,
    centerX: geo.centerX,
    centerY: geo.centerY,
    rot1: fiberParams.rot1Deg,
    rot2: fiberParams.rot2Deg,
    rot3: fiberParams.rot3Deg,
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

/** Apply a batch of selected file paths honoring the replace/append import mode. */
async function applySelectedFilePaths(paths: string[]): Promise<void> {
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

async function handleChooseFiles(): Promise<void> {
  const res = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!res) return
  await applySelectedFilePaths(Array.isArray(res) ? res : [res])
}

async function handleImportFolder(): Promise<void> {
  const folder = await transport.selectFolder()
  if (!folder) return
  importFolderPath.value = folder
  await rescanFolder()
}

// Drag & drop onto the file section mirrors the two buttons above.
const fileDrop = createImportDropZone({
  transport,
  extensions: () => extensionsFromFilters(dataFileFilters),
  onFiles: (paths) => applySelectedFilePaths(paths),
  onFolder: (folder) => {
    importFolderPath.value = folder
    void rescanFolder()
  },
})

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
          rot1: fiberParams.rot1Deg,
          rot2: fiberParams.rot2Deg,
          rot3: fiberParams.rot3Deg,
        },
    rot1Deg: fiberParams.rot1Deg,
    rot2Deg: fiberParams.rot2Deg,
    rot3Deg: fiberParams.rot3Deg,
    overridePoniRot: overridePoniRot.value,
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
    // 'auto' → omit the key so the backend passes no method to pyFAI,
    // matching the pre-feature behavior exactly.
    // 'auto' → 不发送该键，后端不向 pyFAI 传 method，与旧版行为完全一致。
    method: fiberParams.method === 'auto' ? undefined : fiberParams.method,
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

  // Integrate ALL imported files so batch export can produce every result.
  // Previously previewOnly=true only integrated the first file, so the batch
  // cache contained a single result and batch PNG export only produced 1 file.
  // 积分所有导入文件，使批量导出能生成全部结果。
  // 此前 previewOnly=true 只积分第一个文件，batch cache 只有一个结果，
  // 导致批量 PNG 导出只能导出一张。
  const params = buildParams(false)

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
        // Load the first page of result thumbnails — previously this was never
        // called on completion, so the shared result strip stayed empty until
        // the user happened to change the colormap (which re-triggers it).
        // 加载第一页结果缩略图——此前完成后从不调用，缩略图条一直为空，
        // 直到用户碰巧改色图才经 watcher 触发。
        resultThumbCurrentPage.value = 1
        void loadFiberResultThumbnails(1)
        // Auto-collapse layout: expand export section, collapse sidebar geometry/
        // integration groups and the main-area image preview + thumbnails
        // (now redundant with the shared result heatmap). Display settings stays
        // open (non-collapsible).
        // 自动折叠：展开导出结果，收起几何/积分分组 + 图象预览 + 缩略图（已被共享结果热图取代）。
        // 显示设置保持展开（永不折叠）。
        exportExpanded.value = true
        geomExpanded.value = false
        integExpanded.value = false
        previewExpanded.value = false
        thumbExpanded.value = false
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
    resultIndex: currentResultIndex.value,
    sourceFile: fileName.value,
    pngOptions: {
      showLabels: pngShowLabels.value,
      fontSize: pngFontSize.value,
      dpi: pngDpi.value,
      cmap: colormap.value,
      useLog: useLog.value,
      noDataBg: pngNoDataBg.value,
      showColorbar: pngShowColorbar.value,
      showTitle: pngShowTitle.value,
      borderWidth: pngBorderWidth.value,
      edgeColor: pngEdgeColor.value,
      title: pngShowTitle.value ? (result.value?.filename ?? fileName.value ?? undefined) : undefined,
      xLabel: pngXLabel.value || null,
      yLabel: pngYLabel.value || null,
      fontFamily: pngFontFamily.value || null,
      showAxisTitle: pngShowAxisTitle.value,
      showTicks: pngShowTicks.value,
      titleBold: pngTitleBold.value,
      axisTitleBold: pngAxisTitleBold.value,
      tickBold: pngTickBold.value,
      flipX: pngFlipX.value,
      flipY: pngFlipY.value,
      logFloor: logFloorEnabled.value && useLog.value ? logFloorValue.value : null,
      xTickStep: pngXTickStep.value,
      yTickStep: pngYTickStep.value,
      // Forward on-screen contrast (auto or manual) so exported PNG matches heatmap.
      // 透传屏幕对比度（自动或手动），使导出 PNG 与热图一致。
      clim: resultClimMode.value === 'manual'
        ? [resultClimMin.value, resultClimMax.value]
        : (resultContrast.value
            ? [useLog.value ? resultContrast.value.logMin : resultContrast.value.autoMin,
               useLog.value ? resultContrast.value.logMax : resultContrast.value.autoMax]
            : null),
    },
  }))

  try {
    const response = await transport.submitTask('export_integration', params)

    const removeOk = transport.onTaskResult(response.taskId, (r) => {
      const d = r.data as { success?: boolean; error?: string; path?: string; files?: string[]; errors?: string[] }
      if (d?.success) {
        const count = d.files?.length ?? 1
        const errInfo = d.errors?.length ? ` (${d.errors.length} failed)` : ''
        toast.push({
          title: t('integrateFiber.title'),
          message: count > 1
            ? `${payload.format.toUpperCase()} → ${count} files${errInfo}`
            : `${payload.format.toUpperCase()} → ${d.path ?? payload.path}`,
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

/**
 * Export only the current result as a single annotated PNG (save-file dialog).
 * Reuses the `single` path of onExport.
 * 仅导出当前结果为单张带标注 PNG（保存文件对话框），复用 onExport 的 single 路径。
 */
async function onExportCurrentPng(): Promise<void> {
  if (!result.value) return
  let savePath = ''
  if (transport.isDesktop()) {
    savePath = await transport.selectSavePath({
      filters: [{ name: 'PNG', extensions: ['png'] }],
    }) ?? ''
    if (!savePath) return
    if (!savePath.toLowerCase().endsWith('.png')) savePath += '.png'
  }
  pngBatchExporting.value = true
  try {
    await onExport({ format: 'png', path: savePath, mode: 'single' })
  } finally {
    pngBatchExporting.value = false
  }
}

/**
 * One-click batch PNG export: pick a folder, then export ALL cached results as
 * annotated PNGs using the user's current PNG Options. Reuses the `separate`
 * path of onExport.
 * 一键批量导出：选文件夹后，用当前 PNG 选项把全部缓存结果导出为带标注 PNG。
 */
async function onBatchExportPng(): Promise<void> {
  if (!result.value) return
  const folder = await transport.selectFolder()
  if (!folder) return
  pngBatchExporting.value = true
  try {
    await onExport({ format: 'png', path: folder, mode: 'separate' })
  } finally {
    pngBatchExporting.value = false
  }
}

// ── ROI 1D Integration / ROI区域1D积分 ──────────────────────────────────

/** Get the img element's offset relative to the wrapper (accounting for layout).
 *  获取 img 相对于 wrapper 的偏移（考虑布局）。*/
function getImgOffsetInWrapper(): { left: number; top: number; displayW: number; displayH: number } | null {
  const wrapper = roiImageWrapperRef.value
  if (!wrapper) return null
  const img = wrapper.querySelector('img') as HTMLImageElement | null
  if (!img) return null
  const wr = wrapper.getBoundingClientRect()
  const ir = img.getBoundingClientRect()
  return {
    left: ir.left - wr.left,
    top: ir.top - wr.top,
    displayW: ir.width,
    displayH: ir.height,
  }
}

/** Convert canvas-relative pixel to data (qip / qoop). Canvas covers entire wrapper.
 *  将 canvas 相对像素转换为数据坐标 (qip / qoop)。Canvas 覆盖整个 wrapper。*/
function canvasToRoiData(cx: number, cy: number): { ip: number; oop: number } | null {
  if (!result.value) return null
  const axisIp = result.value.axisIp
  const axisOop = result.value.axisOop
  if (axisIp.length < 2 || axisOop.length < 2) return null

  const offset = getImgOffsetInWrapper()
  if (!offset) return null

  // Relative position inside the displayed image / 相对于显示图像的位置
  const relX = (cx - offset.left) / offset.displayW
  // Flip Y: image origin is lower (imshow origin="lower") / 翻转 Y：图像原点在下方
  const relY = 1 - (cy - offset.top) / offset.displayH

  if (relX < 0 || relX > 1 || relY < 0 || relY > 1) return null

  const idx = relX * (axisIp.length - 1)
  const idy = relY * (axisOop.length - 1)
  const iLo = Math.max(0, Math.min(axisIp.length - 2, Math.floor(idx)))
  const jLo = Math.max(0, Math.min(axisOop.length - 2, Math.floor(idy)))
  const iFrac = idx - iLo
  const jFrac = idy - jLo
  return {
    ip: axisIp[iLo] + (axisIp[iLo + 1] - axisIp[iLo]) * iFrac,
    oop: axisOop[jLo] + (axisOop[jLo + 1] - axisOop[jLo]) * jFrac,
  }
}

// Use canvas-relative coordinates stored as fractions [0,1] / 使用归一化坐标 [0,1]
const roiRectNorm = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
// Track whether we are dragging a corner vs drawing new / 跟踪是否在拖拽角 vs 新建
const roiDragCorner = ref<'tl' | 'tr' | 'bl' | 'br' | 'move' | null>(null)
const roiDragStartNorm = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
const roiDragStartPos = ref<{ cx: number; cy: number }>({ cx: 0, cy: 0 })
const CORNER_HANDLE_R = 8 // px radius for corner hit-test / 角点命中半径

function canvasNorm(cx: number, cy: number): { nx: number; ny: number } | null {
  const offset = getImgOffsetInWrapper()
  if (!offset) return null
  return {
    nx: (cx - offset.left) / offset.displayW,
    ny: (cy - offset.top) / offset.displayH,
  }
}

function normToCanvas(nx: number, ny: number): { cx: number; cy: number } {
  const offset = getImgOffsetInWrapper()
  if (!offset) return { cx: 0, cy: 0 }
  return { cx: offset.left + nx * offset.displayW, cy: offset.top + ny * offset.displayH }
}

/** Hit-test which corner (or "move") the canvas point is near. / 命中测试哪个角或移动。*/
function hitCorner(nx: number, ny: number, rect: { x1: number; y1: number; x2: number; y2: number }): 'tl' | 'tr' | 'bl' | 'br' | 'move' | null {
  const offset = getImgOffsetInWrapper()
  if (!offset) return null
  const rPx = CORNER_HANDLE_R / Math.max(offset.displayW, 1)
  const rPy = CORNER_HANDLE_R / Math.max(offset.displayH, 1)
  const corners: Array<{ tag: 'tl' | 'tr' | 'bl' | 'br'; x: number; y: number }> = [
    { tag: 'tl', x: Math.min(rect.x1, rect.x2), y: Math.min(rect.y1, rect.y2) },
    { tag: 'tr', x: Math.max(rect.x1, rect.x2), y: Math.min(rect.y1, rect.y2) },
    { tag: 'bl', x: Math.min(rect.x1, rect.x2), y: Math.max(rect.y1, rect.y2) },
    { tag: 'br', x: Math.max(rect.x1, rect.x2), y: Math.max(rect.y1, rect.y2) },
  ]
  for (const c of corners) {
    if (Math.abs(nx - c.x) <= rPx && Math.abs(ny - c.y) <= rPy) return c.tag
  }
  const minX = Math.min(rect.x1, rect.x2), maxX = Math.max(rect.x1, rect.x2)
  const minY = Math.min(rect.y1, rect.y2), maxY = Math.max(rect.y1, rect.y2)
  if (nx >= minX && nx <= maxX && ny >= minY && ny <= maxY) return 'move'
  return null
}

/** Synchronise ROI input fields from normalised rect. / 从归一化矩形同步 ROI 输入框。*/
function syncRoiFieldsFromNorm(): void {
  if (!roiRectNorm.value || !result.value) return
  const r = roiRectNorm.value
  const axisIp = result.value.axisIp
  const axisOop = result.value.axisOop
  if (axisIp.length < 2 || axisOop.length < 2) return
  const ip0 = axisIp[0] + (axisIp[axisIp.length - 1] - axisIp[0]) * Math.min(r.x1, r.x2)
  const ip1 = axisIp[0] + (axisIp[axisIp.length - 1] - axisIp[0]) * Math.max(r.x1, r.x2)
  const oop0 = axisOop[0] + (axisOop[axisOop.length - 1] - axisOop[0]) * Math.min(r.y1, r.y2)
  const oop1 = axisOop[0] + (axisOop[axisOop.length - 1] - axisOop[0]) * Math.max(r.y1, r.y2)
  roiIpMin.value = ip0
  roiIpMax.value = ip1
  roiOopMin.value = oop0
  roiOopMax.value = oop1
}

function onRoiMouseDown(e: MouseEvent): void {
  if (!roiMode.value) return
  const canvas = roiCanvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top

  // If there's an existing rect, check if we hit a corner / 如果有已有矩形，检测是否点击了角点
  if (roiRectNorm.value && !e.shiftKey) {
    const norm = canvasNorm(cx, cy)
    if (norm) {
      const corner = hitCorner(norm.nx, norm.ny, roiRectNorm.value)
      if (corner) {
        roiDragCorner.value = corner
        roiDragStartNorm.value = { ...roiRectNorm.value }
        roiDragStartPos.value = { cx, cy }
        return
      }
    }
  }

  // Start new rectangle / 开始新矩形
  roiDrawing.value = true
  roiDragCorner.value = null
  roiDragStartPos.value = { cx, cy }
  roiStartX.value = cx
  roiStartY.value = cy
  roiEndX.value = cx
  roiEndY.value = cy
  roiRectNorm.value = null
  drawRoiRect()
}

function onRoiMouseMove(e: MouseEvent): void {
  const canvas = roiCanvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top

  if (roiDragCorner.value && roiDragStartNorm.value) {
    // Dragging a corner / 拖拽角点
    const norm = canvasNorm(cx, cy)
    if (!norm) return
    const orig = roiDragStartNorm.value
    const n = { ...orig }
    const tag = roiDragCorner.value
    if (tag === 'tl') { n.x1 = norm.nx; n.y1 = norm.ny }
    else if (tag === 'tr') { n.x2 = norm.nx; n.y1 = norm.ny }
    else if (tag === 'bl') { n.x1 = norm.nx; n.y2 = norm.ny }
    else if (tag === 'br') { n.x2 = norm.nx; n.y2 = norm.ny }
    else if (tag === 'move') {
      const dx = norm.nx - canvasNorm(roiDragStartPos.value.cx, roiDragStartPos.value.cy)!.nx
      const dy = norm.ny - canvasNorm(roiDragStartPos.value.cx, roiDragStartPos.value.cy)!.ny
      n.x1 = orig.x1 + dx; n.x2 = orig.x2 + dx
      n.y1 = orig.y1 + dy; n.y2 = orig.y2 + dy
      roiDragStartPos.value = { cx, cy }
    }
    roiRectNorm.value = n
    syncRoiFieldsFromNorm()
    drawRoiRect()
    return
  }

  if (!roiDrawing.value) {
    // Hover: change cursor based on corner proximity / 悬停：根据角点改变光标
    if (roiRectNorm.value && !e.shiftKey) {
      const norm = canvasNorm(cx, cy)
      if (norm && hitCorner(norm.nx, norm.ny, roiRectNorm.value)) {
        canvas.style.cursor = 'grab'
      } else {
        canvas.style.cursor = 'crosshair'
      }
    }
    return
  }
  roiEndX.value = cx
  roiEndY.value = cy
  drawRoiRect()
}

function onRoiMouseUp(e: MouseEvent): void {
  if (roiDragCorner.value) {
    // Finish corner drag / 完成角点拖拽
    roiDragCorner.value = null
    roiDragStartNorm.value = null
    if (roiRectNorm.value) syncRoiFieldsFromNorm()
    drawRoiRect()
    return
  }
  if (!roiDrawing.value) return
  roiDrawing.value = false

  const canvas = roiCanvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const cx1 = roiStartX.value, cy1 = roiStartY.value
  const cx2 = roiEndX.value, cy2 = roiEndY.value

  const n1 = canvasNorm(cx1, cy1)
  const n2 = canvasNorm(cx2, cy2)
  if (!n1 || !n2) return

  // Clamp to [0,1] / 钳制到 [0,1]
  n1.nx = Math.max(0, Math.min(1, n1.nx)); n1.ny = Math.max(0, Math.min(1, n1.ny))
  n2.nx = Math.max(0, Math.min(1, n2.nx)); n2.ny = Math.max(0, Math.min(1, n2.ny))

  const minW = 5 / Math.max((getImgOffsetInWrapper()?.displayW ?? 500), 1)
  const minH = 5 / Math.max((getImgOffsetInWrapper()?.displayH ?? 500), 1)
  if (Math.abs(n2.nx - n1.nx) < minW || Math.abs(n2.ny - n1.ny) < minH) {
    // Too small → discard / 矩形太小，放弃
    clearRoiRect()
    return
  }

  roiRectNorm.value = { x1: n1.nx, y1: n1.ny, x2: n2.nx, y2: n2.ny }
  syncRoiFieldsFromNorm()
  drawRoiRect()
}

function drawRoiRect(): void {
  const canvas = roiCanvasRef.value
  const wrapper = roiImageWrapperRef.value
  if (!canvas || !wrapper) return

  canvas.width = wrapper.offsetWidth
  canvas.height = wrapper.offsetHeight
  canvas.style.width = wrapper.offsetWidth + 'px'
  canvas.style.height = wrapper.offsetHeight + 'px'

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  let nx1: number, ny1: number, nx2: number, ny2: number
  if (roiRectNorm.value) {
    const r = roiRectNorm.value
    nx1 = r.x1; ny1 = r.y1; nx2 = r.x2; ny2 = r.y2
  } else if (roiDrawing.value) {
    const n1 = canvasNorm(roiStartX.value, roiStartY.value)
    const n2 = canvasNorm(roiEndX.value, roiEndY.value)
    if (!n1 || !n2) return
    nx1 = n1.nx; ny1 = n1.ny; nx2 = n2.nx; ny2 = n2.ny
  } else {
    return
  }

  const p1 = normToCanvas(nx1, ny1)
  const p2 = normToCanvas(nx2, ny2)
  const x = Math.min(p1.cx, p2.cx), y = Math.min(p1.cy, p2.cy)
  const w = Math.abs(p2.cx - p1.cx), h = Math.abs(p2.cy - p1.cy)

  // Fill / 填充
  ctx.fillStyle = 'rgba(255, 200, 0, 0.15)'
  ctx.fillRect(x, y, w, h)
  // Stroke / 描边
  ctx.strokeStyle = 'rgba(255, 200, 0, 0.9)'
  ctx.lineWidth = 2
  ctx.setLineDash([6, 3])
  ctx.strokeRect(x, y, w, h)
  ctx.setLineDash([]) // reset

  // Corner handles (only when rect is committed) / 角点手柄（仅已确认的矩形）
  if (roiRectNorm.value && !roiDrawing.value) {
    const corners = [
      { cx: p1.cx, cy: p1.cy }, { cx: p2.cx, cy: p2.cy },
      { cx: p1.cx, cy: p2.cy }, { cx: p2.cx, cy: p1.cy },
    ]
    for (const c of corners) {
      ctx.fillStyle = 'rgba(255, 200, 0, 0.9)'
      ctx.beginPath()
      ctx.arc(c.cx, c.cy, CORNER_HANDLE_R, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#000'
      ctx.lineWidth = 1
      ctx.stroke()
    }
  }
}

function clearRoiRect(): void {
  roiRectNorm.value = null
  const canvas = roiCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
}

/** Initialize ROI ranges from current result axis data. */
function initRoiRanges(): void {
  if (!result.value) return
  const ip = result.value.axisIp
  const oop = result.value.axisOop
  if (ip.length >= 2) {
    roiIpMin.value = ip[0]
    roiIpMax.value = ip[ip.length - 1]
  }
  if (oop.length >= 2) {
    roiOopMin.value = oop[0]
    roiOopMax.value = oop[oop.length - 1]
  }
}

const canRunRoi = computed(() => {
  return !!(result.value && roiIpMin.value < roiIpMax.value && roiOopMin.value < roiOopMax.value && roiNpt.value >= 50)
})

const roi1dTraces = computed<LineTrace[]>(() => {
  if (!roi1dResult.value) return []
  return roi1dResult.value.curves.map((c, i) => ({
    x: c.radial,
    y: c.intensity,
    name: c.filename || `Curve ${i + 1}`,
    mode: 'lines' as const,
  }))
})

/** In-plane (X = qip) traces — second integration direction / 面内剖面曲线 */
const roi1dTracesIp = computed<LineTrace[]>(() => {
  if (!roi1dResult.value) return []
  return roi1dResult.value.curvesIp.map((c, i) => ({
    x: c.radial,
    y: c.intensity,
    name: c.filename || `Curve ${i + 1}`,
    mode: 'lines' as const,
  }))
})

/** Chart captions follow the user-selected units (no hardcoded qz/qy) /
 * 曲线标题跟随用户所选单位（不再写死 qz/qy） */
const roiOopCaption = computed(() => {
  const u = roi1dResult.value?.unit
  const label = u ? (UNIT_LABELS[u] ?? u) : ''
  return label ? `${label}（面外 OOP）` : '面外 OOP'
})
const roiIpCaption = computed(() => {
  const u = roi1dResult.value?.unitIp
  const label = u ? (UNIT_LABELS[u] ?? u) : ''
  return label ? `${label}（面内 IP）` : '面内 IP'
})

// A drawn ROI rectangle lives in the 2D map's units; when the user changes
// units, it is stale until the map is re-integrated — drop it so it cannot
// silently mismatch the numeric ranges.
// 框选矩形基于 2D 图当前单位；单位变更后直到重新积分为止都是过期的，
// 直接清除以免与数值范围不一致。
watch([() => fiberParams.unitIp, () => fiberParams.unitOop], () => {
  clearRoiRect()
})

async function runRoiIntegration(): Promise<void> {
  if (!canRunRoi.value || !result.value) return

  // Client-side validation / 客户端验证
  if (!isFinite(roiIpMin.value) || !isFinite(roiIpMax.value) ||
      !isFinite(roiOopMin.value) || !isFinite(roiOopMax.value)) {
    roiError.value = 'Invalid ROI range values (NaN/Infinity). Please re-select.'
    return
  }
  if (roiIpMin.value >= roiIpMax.value) {
    roiError.value = `Invalid IP range: [${roiIpMin.value}, ${roiIpMax.value}]`
    return
  }
  if (roiOopMin.value >= roiOopMax.value) {
    roiError.value = `Invalid OOP range: [${roiOopMin.value}, ${roiOopMax.value}]`
    return
  }

  roiRunning.value = true
  roiError.value = null
  roi1dResult.value = null

  try {
    const raw = await submitAndWait('viewer_config', {
      action: 'fiber_1d_roi',
      filePath: activeFilePath.value ?? files.value[0] ?? '',
      files: [...files.value],
      geometry: buildGeometryPayload(),
      // Top-level rot fields are read by task-adapter's buildFiberGeometry
      // (same as the 2D integrate_fiber path) so ROI 1D uses identical geometry.
      // 顶层 rot 字段由 task-adapter 的 buildFiberGeometry 读取（与 2D 积分路径一致）。
      rot1Deg: fiberParams.rot1Deg,
      rot2Deg: fiberParams.rot2Deg,
      rot3Deg: fiberParams.rot3Deg,
      overridePoniRot: overridePoniRot.value,
      fiberParams: {
        rot1Deg: fiberParams.rot1Deg,
        rot2Deg: fiberParams.rot2Deg,
        rot3Deg: fiberParams.rot3Deg,
        sampleOrientation: fiberParams.sampleOrientation,
        incidentAngleDeg: fiberParams.incidentAngleDeg,
        tiltAngleDeg: fiberParams.tiltAngleDeg,
        unitIp: fiberParams.unitIp,
        unitOop: fiberParams.unitOop,
      },
      ipRange: [roiIpMin.value, roiIpMax.value],
      oopRange: [roiOopMin.value, roiOopMax.value],
      npt1d: roiNpt.value,
      positiveQOnly: roiAbsQ.value,
      correctSolidAngle: correctSolidAngle.value,
      maskConfig: {
        valueRangeMin: maskConfig.value.valueRangeMin,
        valueRangeMax: maskConfig.value.valueRangeMax,
        deadPixelThreshold: maskConfig.value.deadPixelThreshold,
        customMaskPath: maskConfig.value.customMaskPath,
      },
    })

    const data = raw as {
      results: Array<{
        filename: string
        radial: number[]
        intensity: number[]
        radial_ip?: number[]
        intensity_ip?: number[]
        error?: string
      }>
      unit: string
      unit_ip?: string
    }
    const ok = data.results?.filter(r => !r.error && r.radial?.length > 0) ?? []
    if (ok.length === 0) {
      roiError.value = 'No valid 1D results produced.'
      return
    }
    roi1dResult.value = {
      curves: ok.map(r => ({ radial: r.radial, intensity: r.intensity, filename: r.filename })),
      unit: data.unit,
      curvesIp: ok
        .filter(r => (r.radial_ip?.length ?? 0) > 0)
        .map(r => ({ radial: r.radial_ip as number[], intensity: r.intensity_ip as number[], filename: r.filename })),
      unitIp: data.unit_ip ?? '',
    }
    // Auto-expand the ROI section to reveal the 1D curve / 自动展开显示1D曲线
    roiExpanded.value = true
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    roiError.value = msg
    toast.push({ title: '1D ROI Integration', message: msg, tone: 'error' })
  } finally {
    roiRunning.value = false
  }
}

async function exportRoi1d(): Promise<void> {
  if (!roi1dResult.value || roi1dResult.value.curves.length === 0) return
  const format: ExportFormat = 'csv'
  let outputPath = ''

  if (transport.isDesktop()) {
    outputPath = await transport.selectSavePath({
      filters: [{ name: 'CSV', extensions: ['csv'] }],
    }) ?? ''
    if (!outputPath) return
    if (!outputPath.toLowerCase().endsWith('.csv')) outputPath += '.csv'
  }

  // Deep-clone to strip Vue reactive proxies before IPC serialization.
  // Without this, Electron throws "An object could not be cloned." because
  // the radial/intensity arrays inside roi1dResult are reactive Proxies.
  // 深拷贝以去除 Vue reactive proxy，否则 Electron IPC 报
  // "An object could not be cloned."（roi1dResult 内的数组是 reactive Proxy）。
  const params: Record<string, unknown> = JSON.parse(JSON.stringify({
    format,
    outputPath,
    dataType: '1d',
    mode: 'single',
    // Both directions are exported: qoop curves keep the original labels,
    // qip curves are suffixed so the two sets stay distinguishable in CSV.
    // 两个方向都导出：qoop 曲线保留原标签，qip 曲线加后缀以便区分。
    results: [
      ...roi1dResult.value.curves.map(c => ({
        radial: c.radial,
        intensity: c.intensity,
        label: c.filename,
        unit: roi1dResult.value?.unit ?? 'q_nm^-1',
      })),
      ...roi1dResult.value.curvesIp.map(c => ({
        radial: c.radial,
        intensity: c.intensity,
        label: `${c.filename} (qip)`,
        unit: roi1dResult.value?.unitIp || roi1dResult.value?.unit || 'q_nm^-1',
      })),
    ],
  }))

  try {
    const response = await transport.submitTask('export_integration', params)
    transport.onTaskResult(response.taskId, (r) => {
      const d = r.data as { success?: boolean; error?: string; path?: string }
      if (d?.success) {
        toast.push({
          title: '1D ROI Export',
          message: `CSV → ${d.path ?? outputPath}`,
          tone: 'success',
        })
      } else {
        toast.push({ title: '1D ROI Export', message: d?.error ?? 'Export failed', tone: 'error' })
      }
    })
    transport.onTaskError(response.taskId, (e) => {
      toast.push({ title: '1D ROI Export', message: e.error ?? 'Export failed', tone: 'error' })
    })
  } catch (err) {
    toast.push({ title: '1D ROI Export', message: String(err), tone: 'error' })
  }
}

// Initialize ROI ranges when result loads / 结果加载时初始化ROI范围
watch(() => result.value, (newVal) => {
  if (newVal) {
    initRoiRanges()
    // Also reset any existing ROI rect / 重置已有 ROI 矩形
    clearRoiRect()
  }
})

// Toggle ROI mode and update canvas size / 切换ROI模式并更新画布尺寸
watch(roiMode, (enabled) => {
  if (!enabled) {
    clearRoiRect()
  } else {
    if (result.value) initRoiRanges()
    // Size canvas to match image / 调整画布大小匹配图像
    nextTick(() => {
      const canvas = roiCanvasRef.value
      const wrapper = roiImageWrapperRef.value
      if (canvas && wrapper) {
        canvas.width = wrapper.offsetWidth
        canvas.height = wrapper.offsetHeight
        canvas.style.width = wrapper.offsetWidth + 'px'
        canvas.style.height = wrapper.offsetHeight + 'px'
      }
    })
  }
})

// === Watchers / 监听器 ===

/** Re-render preview when display settings change / 显示设置变更时重新渲染预览 */
watch([colormap, useLog, logFloorEnabled, logFloorValue], () => {
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

// Refresh the annotated (matplotlib) preview when PNG options change.
// Debounced because matplotlib rendering is slower than the canvas heatmap.
// 当 PNG 选项变化时刷新带坐标轴预览；matplotlib 渲染较慢，故做防抖。
let mplRefreshTimer: ReturnType<typeof setTimeout> | null = null
watch(
  [pngShowLabels, pngNoDataBg, pngFontSize, pngShowColorbar, pngShowTitle, pngBorderWidth, pngEdgeColor, pngXLabel, pngYLabel, pngFontFamily, pngShowAxisTitle, pngShowTicks, pngTitleBold, pngAxisTitleBold, pngTickBold, pngFlipX, pngFlipY, colormap, useLog, logFloorEnabled, logFloorValue, resultClimMode, resultClimMin, resultClimMax, pngXTickStep, pngYTickStep],
  () => {
    if (mplRefreshTimer) clearTimeout(mplRefreshTimer)
    mplRefreshTimer = setTimeout(() => { void refreshMplPreview() }, 300)
  },
)

watch(
  () => [
    geometry.value.poniPath,
    geometry.value.pixel1,
    geometry.value.pixel2,
    geometry.value.distance,
    geometry.value.wavelength,
    geometry.value.centerX,
    geometry.value.centerY,
    fiberParams.rot1Deg,
    fiberParams.rot2Deg,
    fiberParams.rot3Deg,
    overridePoniRot.value,
  ],
  () => {
    if (activeFilePath.value && previewExpanded.value) {
      void loadPreviewIfExpanded()
    }
    // Invalidate stale 2D results so users know to re-integrate after
    // changing geometry or rotation parameters. Without this the old
    // cached heatmap stays visible, making it look like params had no effect.
    // 几何或旋转参数变化后使旧的 2D 结果失效，提示用户重新积分。
    // 否则旧缓存热图残留，造成"参数不影响积分"的错觉。
    if (result.value) {
      result.value = null
      batchCachePath.value = null
      resultSummaries.value = []
      currentResultIndex.value = 0
      resultThumbnailItems.value = []
      resultContrast.value = null
      roi1dResult.value = null
      toast.push({ title: t('integrateFiber.title'), message: t('integrateFiber.geomChangedHint'), tone: 'info' })
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

/* Drop-target highlight & hint / 拖放高亮与提示 */
.fib-file-section--drop {
  border-color: var(--primary-light);
  background: var(--primary-bg);
}

.fib-drop-hint span {
  font-size: 0.75rem;
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

/* Non-collapsible static section (e.g. Display settings) / 不可折叠静态区（如显示设置） */
.fib-section-static {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.fib-section-toggle-static {
  cursor: default;
  background: var(--bg-surface);
}

.fib-section-toggle-static:hover {
  background: var(--bg-surface);
}

.fib-section-toggle {
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

/* Grouped sections inside a collapsible body need vertical spacing / 分组内各块需纵向间距 */
.fib-group-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

/* ── Tabs / Tab 切换栏 ── */

.fib-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  margin-top: 12px;
}

.fib-tab {
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

.fib-tab:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.fib-tab-active {
  color: var(--text-primary);
  background: var(--bg-surface);
  border-color: var(--border);
  border-bottom-color: var(--bg-surface);
  font-weight: 600;
}

.fib-tab-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 16px;
}

/* ROI parameter panel (in 1D tab) / 1D tab 内 ROI 参数面板 */
.fib-roi-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
}

.fib-roi-panel h3 {
  margin: 0 0 10px;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
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

/* ── Export + PNG options side-by-side / 导出与 PNG 选项左右分栏 ── */

.fib-export-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: start;
}

.fib-export-left,
.fib-export-right {
  min-width: 0;
}

.fib-export-right > .fib-collapsible {
  margin-top: 0;
}

/* Color picker + preset row / 颜色选择器与预设行 */
.fib-color-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.fib-color-input {
  width: 32px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: none;
  cursor: pointer;
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .fib-export-split {
    grid-template-columns: 1fr;
  }
}

/* ── Annotated matplotlib preview / 带坐标轴预览 ── */

.fib-mpl-preview {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fib-mpl-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.fib-mpl-preview-header h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

.fib-mpl-preview-body {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 120px;
  background: var(--bg-surface-alt);
  border-radius: var(--radius-md);
  padding: 12px;
}

/* Checkerboard so transparent no-data areas are visible / 透明背景棋盘格便于观察 */
.fib-mpl-preview-body:has(.fib-mpl-img) {
  background-image:
    linear-gradient(45deg, var(--border) 25%, transparent 25%),
    linear-gradient(-45deg, var(--border) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, var(--border) 75%),
    linear-gradient(-45deg, transparent 75%, var(--border) 75%);
  background-size: 16px 16px;
  background-position: 0 0, 0 8px, 8px -8px, -8px 0;
}

.fib-mpl-img {
  max-width: 100%;
  height: auto;
  display: block;
}

.fib-mpl-loading,
.fib-mpl-empty {
  color: var(--text-muted);
  font-size: 0.875rem;
  padding: 24px;
}

/* Multi-result hint banner / 多图提示横幅 */
.fib-mpl-hint {
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--text-primary);
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
}

/* ── ROI 1D Integration / ROI区域1D积分 ── */

.fib-roi-image-wrapper {
  position: relative;
  width: 100%;
}

.fib-roi-canvas {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
  cursor: crosshair;
  pointer-events: auto;
}

.fib-roi-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-top: 16px;
}

.fib-roi-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.fib-roi-header h3 {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.fib-roi-grid {
  /* Two fields per row, wrapping to multiple lines / 每行两项，自动换行 */
  grid-template-columns: repeat(2, 1fr);
}

.fib-roi-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.fib-roi-chart {
  margin-top: 16px;
  min-height: 300px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
}

/* 1D ROI result in the main area (under the annotated preview) / 主区1D结果（带坐标轴预览下方） */
.fib-roi-chart-main {
  margin-top: 16px;
  min-height: 320px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
}

.fib-roi-chart-main h3 {
  margin: 0 0 10px;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Two-chart layout: qoop + qip side by side, stacking on narrow widths */
/* 双图布局：qoop 与 qip 并排，窄屏自动堆叠 */
.fib-roi-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}

.fib-roi-chart-caption {
  margin: 0 0 6px;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
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

/* Batch PNG export button row in PNG tab / PNG tab 批量导出按钮行 */
.fib-png-batch-row {
  display: flex;
  gap: 12px;
}

.fib-batch-png-btn {
  flex: 1;
  white-space: nowrap;
}

/* ── Disabled (greyed-out) section state / 灰置状态 ── */

.fib-disabled {
  opacity: 0.5;
  pointer-events: none;
}

.fib-disabled > .fib-section-toggle {
  pointer-events: auto; /* keep toggle hover but click blocked via @click guard */
  cursor: not-allowed;
}

.fib-roi-hint {
  margin: 0 0 8px;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--text-muted);
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
