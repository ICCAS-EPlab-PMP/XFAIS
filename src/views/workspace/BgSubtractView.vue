<template>
  <section class="bg-subtract-page">
    <!-- Header / 页头 -->
    <header class="bgs-header">
      <h1>{{ t('bgSubtract.title') }}</h1>
      <p class="bgs-subtitle">{{ t('bgSubtract.subtitle') }}</p>
      <div class="bgs-notice">
        <span class="bgs-notice-icon">ℹ</span>
        <span>{{ t('bgSubtract.simpleNotice') }}</span>
      </div>
    </header>

    <div class="bgs-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="bgs-sidebar">
        <!-- Mode toggle / 模式切换 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.mode') }}</h3>
          <div class="bgs-radio-row">
            <label class="bgs-radio-label">
              <input v-model="mode" type="radio" value="single" />
              <span>{{ t('bgSubtract.modeSingle') }}</span>
            </label>
            <label class="bgs-radio-label">
              <input v-model="mode" type="radio" value="batch" />
              <span>{{ t('bgSubtract.modeBatch') }}</span>
            </label>
          </div>
        </div>

        <!-- File selection / 文件选择 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.fileSelection') }}</h3>

          <!-- Single mode: multi-file selection / 单文件模式：多文件选择（支持拖放 / drop target） -->
          <template v-if="mode === 'single'">
            <div
              class="bgs-file-actions"
              :class="{ 'bgs-file-actions--drop': fileDrop.isDragging.value }"
              @dragenter="fileDrop.onDragEnter"
              @dragover="fileDrop.onDragOver"
              @dragleave="fileDrop.onDragLeave"
              @drop="fileDrop.onDrop"
            >
              <button type="button" class="bgs-btn" data-ai-id="bg:files" @click="handleChooseSampleFiles">
                {{ t('bgSubtract.selectFiles') }}
              </button>
              <div class="bgs-import-mode">
                <span class="bgs-import-mode-label">{{ t('bgSubtract.importMode') }}</span>
                <label class="bgs-radio-label">
                  <input v-model="importMode" type="radio" value="replace" />
                  <span>{{ t('bgSubtract.importReplace') }}</span>
                </label>
                <label class="bgs-radio-label">
                  <input v-model="importMode" type="radio" value="append" />
                  <span>{{ t('bgSubtract.importAppend') }}</span>
                </label>
              </div>
              <span v-if="samplePaths.length" class="bgs-file-summary">
                {{ t('bgSubtract.fileCount', { count: samplePaths.length }) }}
              </span>
              <span v-else class="bgs-file-summary bgs-file-summary--muted">
                {{ t('bgSubtract.noFilesSelected') }}
              </span>
              <span class="bgs-file-summary bgs-file-summary--muted bgs-drop-hint">
                {{ t('business.fileSelection.dropZoneHint') }}
              </span>
            </div>

            <!-- File list / 文件列表 -->
            <div v-if="samplePaths.length > 0" class="bgs-file-list-wrap">
              <div class="bgs-file-list-header">
                <span class="bgs-file-list-title">{{ t('bgSubtract.fileList') }}</span>
              </div>
              <div class="bgs-file-list">
                <div
                  v-for="(fp, idx) in samplePaths"
                  :key="fp"
                  class="bgs-file-list-item"
                  :class="{ 'bgs-file-list-item--active': idx === currentSampleIndex }"
                  @click="currentSampleIndex = idx"
                >
                  <span class="bgs-file-list-name" :title="fp">{{ extractFileName(fp) }}</span>
                  <NumberField
                    v-if="transmissionSource === 'per-file'"
                    :model-value="perFileTransmissions[fp]"
                    class="bgs-input bgs-input-tiny"
                    min="0"
                    max="100"
                    step="0.1"
                    placeholder="%"
                    @click.stop
                    @update:model-value="(v) => { if (v != null) perFileTransmissions[fp] = v }"
                  />
                  <button
                    type="button"
                    class="bgs-file-list-remove"
                    :title="t('bgSubtract.removeFile')"
                    @click.stop="removeSampleFile(idx)"
                  >✕</button>
                </div>
              </div>
            </div>

            <FileDialogButton
              v-model="bgPath"
              mode="openFile"
              :label="t('bgSubtract.bgFile')"
              :filters="dataFileFilters"
              data-ai-id="bg:background"
            />
          </template>

          <!-- Batch mode: folder selection + scan / 批量模式：文件夹选择 + 扫描 -->
          <template v-else>
            <!-- Web mode: browsers cannot pick a server-side folder, so the
                 batch source is a multi-file selection (the backend then
                 writes each "_subtracted" file next to its source).
                 / web 模式：浏览器无法选择服务器端文件夹，批量改为多选文件
                 （后端把每个 "_subtracted" 结果写到源文件旁）。 -->
            <button
              v-if="!transport.isDesktop()"
              type="button"
              class="bgs-btn"
              data-ai-id="bg:batch-files"
              @click="handleChooseBatchFiles"
            >
              {{ t('bgSubtract.selectFiles') }}
            </button>
            <FileDialogButton
              v-else
              v-model="sampleFolder"
              mode="openFolder"
              :label="t('bgSubtract.sampleFolder')"
            />
            <div v-if="batchFolderFiles.length > 0" class="bgs-folder-info">
              {{ t('bgSubtract.folderFileCount', { count: batchFolderFiles.length }) }}
            </div>
            <div v-if="batchFolderFiles.length > 0" class="bgs-file-list-wrap">
              <div class="bgs-file-list">
                <div
                  v-for="(fp, idx) in batchFolderFiles"
                  :key="fp"
                  class="bgs-file-list-item"
                  :class="{ 'bgs-file-list-item--active': idx === currentSampleIndex }"
                  @click="currentSampleIndex = idx"
                >
                  <span class="bgs-file-list-name" :title="fp">{{ extractFileName(fp) }}</span>
                </div>
              </div>
            </div>
            <FileDialogButton
              v-model="bgPath"
              mode="openFile"
              :label="t('bgSubtract.bgFile')"
              :filters="dataFileFilters"
              data-ai-id="bg:background"
            />
          </template>
        </div>

        <!-- Ionchamber section / 电离室部分 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.ionchamber') }}</h3>

          <div class="bgs-radio-row">
            <label class="bgs-radio-label">
              <input v-model="transmissionSource" type="radio" value="manual" />
              <span>{{ t('bgSubtract.transManual') }}</span>
            </label>
            <label class="bgs-radio-label" :class="{ 'bgs-radio-label--disabled': tooManyFilesForPerFile }">
              <input v-model="transmissionSource" type="radio" value="per-file" :disabled="tooManyFilesForPerFile" />
              <span>{{ t('bgSubtract.transPerFile') }}</span>
            </label>
            <label class="bgs-radio-label">
              <input v-model="transmissionSource" type="radio" value="ionchamber" />
              <span>{{ t('bgSubtract.transIonchamber') }}</span>
            </label>
            <label class="bgs-radio-label">
              <input v-model="transmissionSource" type="radio" value="file" data-testid="bg-trans-file-radio" />
              <span>{{ t('bgSubtract.transFile') }}</span>
            </label>
            <label class="bgs-radio-label">
              <input v-model="transmissionSource" type="radio" value="log" data-testid="bg-trans-log-radio" />
              <span>{{ t('bgSubtract.transLog') }}</span>
            </label>
          </div>

          <!-- Over-limit notice: shown whenever the per-file option is out of
               reach (any source mode), so the user is always told WHY it is
               disabled. / 超限提示：只要超出逐文件上限就显示（与当前来源模式
               无关），用户始终能知道选项为何不可用。 -->
          <div v-if="tooManyFilesForPerFile" class="bgs-match-warning">
            ⚠ {{ t('bgSubtract.tooManyFilesWarning', { limit: PER_FILE_TRANSMISSION_LIMIT }) }}
          </div>

          <!-- Manual transmission / 手动透射率 -->
          <div v-if="transmissionSource === 'manual'" class="bgs-field">
            <label class="bgs-label">{{ t('bgSubtract.transmissionValue') }} (%)</label>
            <NumberField
              :model-value="manualTransmission"
              class="bgs-input"
              min="0"
              max="100"
              step="0.1"
              @update:model-value="(v) => { if (v != null) manualTransmission = v }"
            />
          </div>

          <!-- Ionchamber folder + match + filters / 电离室文件夹 + 匹配 + 过滤 -->
          <!-- Keep visible after a successful match even though the source
               auto-switches to per-file (the matched values take effect as
               per-file transmissions) — otherwise the table the user just
               earned would vanish with the card. / 匹配成功后来源自动切到
               “分别设置”（匹配值作为逐文件透射率生效），卡片必须保留——否则
               刚得到的匹配表会跟着卡片一起消失。 -->
          <template v-if="transmissionSource === 'ionchamber' || ionchamberMatches.length > 0">
            <FileDialogButton
              v-model="ionchamberFolder"
              mode="openFolder"
              :label="t('bgSubtract.ionchamberFolder')"
            />

            <!-- Background ionchamber file / 背景电离室文件 -->
            <FileDialogButton
              v-model="bgIonchamberPath"
              mode="openFile"
              :label="t('bgSubtract.bgIonchamberFile')"
              :filters="[{ name: 'All Files', extensions: ['*'] }]"
            />
            <div v-if="!bgIonchamberPath" class="bgs-match-warning">
              ⚠ {{ t('bgSubtract.noBgIonchamberWarning') }}
            </div>

            <!-- Ionchamber mode / 计算模式（单通道 or 前后通道） -->
            <div class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.ionMode') }}</label>
              <select v-model="ionchamberMode" class="bgs-select" data-testid="bg-ion-mode">
                <option value="single">{{ t('bgSubtract.ionModeSingle') }}</option>
                <option value="dual">{{ t('bgSubtract.ionModeDual') }}</option>
              </select>
            </div>

            <!-- Ionchamber channel selector / 电离室通道选择（单通道） -->
            <div v-if="ionchamberMode === 'single'" class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.ionchamberChannel') }}</label>
              <select v-model="ionchamberChannel" class="bgs-select">
                <option value="Ionchamber0">Ionchamber0 (I₀)</option>
                <option value="Ionchamber1">Ionchamber1 (I₁)</option>
                <option value="Ionchamber2">Ionchamber2 (I₂)</option>
              </select>
            </div>

            <!-- Dual mode: before/after channel pairs / 前后通道模式 -->
            <template v-else>
              <p class="bgs-ion-formula">{{ t('bgSubtract.ionDualFormula') }}</p>
              <div class="bgs-dual-grid">
                <div class="bgs-field">
                  <label class="bgs-label">{{ t('bgSubtract.ionSampleBefore') }}</label>
                  <select v-model="ionSampleBefore" class="bgs-select">
                    <option value="Ionchamber0">Ionchamber0 (I₀)</option>
                    <option value="Ionchamber1">Ionchamber1 (I₁)</option>
                    <option value="Ionchamber2">Ionchamber2 (I₂)</option>
                  </select>
                </div>
                <div class="bgs-field">
                  <label class="bgs-label">{{ t('bgSubtract.ionSampleAfter') }}</label>
                  <select v-model="ionSampleAfter" class="bgs-select">
                    <option value="Ionchamber0">Ionchamber0 (I₀)</option>
                    <option value="Ionchamber1">Ionchamber1 (I₁)</option>
                    <option value="Ionchamber2">Ionchamber2 (I₂)</option>
                  </select>
                </div>
                <div class="bgs-field">
                  <label class="bgs-label">{{ t('bgSubtract.ionBgBefore') }}</label>
                  <select v-model="ionBgBefore" class="bgs-select">
                    <option value="Ionchamber0">Ionchamber0 (I₀)</option>
                    <option value="Ionchamber1">Ionchamber1 (I₁)</option>
                    <option value="Ionchamber2">Ionchamber2 (I₂)</option>
                  </select>
                </div>
                <div class="bgs-field">
                  <label class="bgs-label">{{ t('bgSubtract.ionBgAfter') }}</label>
                  <select v-model="ionBgAfter" class="bgs-select">
                    <option value="Ionchamber0">Ionchamber0 (I₀)</option>
                    <option value="Ionchamber1">Ionchamber1 (I₁)</option>
                    <option value="Ionchamber2">Ionchamber2 (I₂)</option>
                  </select>
                </div>
              </div>
              <div v-if="ionchamberDualInvalid" class="bgs-match-warning">
                ⚠ {{ t('bgSubtract.ionDualInvalid') }}
              </div>
              <p class="bgs-ion-hint">{{ t('bgSubtract.ionFormulaHint') }}</p>
            </template>

            <!-- Ionchamber method selector / 电离室计算方法 -->
            <div class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.ionchamberMethod') }}</label>
              <select v-model="ionchamberMethod" class="bgs-select">
                <option value="median">{{ t('bgSubtract.methodMedian') }}</option>
                <option value="mean">{{ t('bgSubtract.methodMean') }}</option>
                <option value="trimmed_mean">{{ t('bgSubtract.methodTrimmedMean') }}</option>
              </select>
            </div>

            <!-- Match threshold slider / 匹配阈值滑块 -->
            <div class="bgs-field">
              <label class="bgs-label">
                {{ t('bgSubtract.matchThreshold') }}: {{ minScore.toFixed(2) }}
              </label>
              <input
                v-model.number="minScore"
                type="range"
                class="bgs-slider"
                min="0"
                max="1"
                step="0.05"
              />
            </div>

            <!-- Regex pattern / 正则表达式 -->
            <div class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.matchRegex') }}</label>
              <input
                v-model="regexPattern"
                type="text"
                class="bgs-input"
                :placeholder="t('bgSubtract.matchRegexHint')"
              />
            </div>

            <button
              type="button"
              class="bgs-btn"
              :disabled="!canMatchIonchamber"
              @click="handleMatchIonchamber"
            >
              {{ matchingIonchamber ? t('bgSubtract.matching') : t('bgSubtract.matchBtn') }}
            </button>

            <!-- Match results table / 匹配结果表 -->
            <div v-if="ionchamberMatches.length > 0" class="bgs-match-table-wrap">
              <!-- Warning if no background ionchamber provided / 如果没有提供背景电离室文件 -->
              <div v-if="!bgIonchamberPath" class="bgs-match-warning">
                ⚠ {{ t('bgSubtract.noBgIonchamberWarning') }}
              </div>
              <!-- Matched values were applied as per-file transmissions. /
                   匹配值已作为逐文件透射率生效。 -->
              <div
                v-if="transmissionSource !== 'ionchamber' && matchedTransmissionCount > 0"
                class="bgs-file-summary bgs-file-summary--muted"
              >
                {{ t('bgSubtract.ionchamberAppliedHint') }}
              </div>
              <table class="bgs-match-table">
                <thead>
                  <tr>
                    <th>{{ t('bgSubtract.matchColFile') }}</th>
                    <th>{{ t('bgSubtract.matchColIon') }}</th>
                    <th>{{ t('bgSubtract.matchColScore') }}</th>
                    <th>{{ t('bgSubtract.matchColTrans') }}</th>
                    <th>{{ t('bgSubtract.matchColNote') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in ionchamberMatches" :key="m.data_file">
                    <td :title="m.data_file">{{ extractFileName(m.data_file) }}</td>
                    <td>{{ m.matched_ion ?? '—' }}</td>
                    <td
                      :class="{ 'bgs-warn-cell': typeof m.score === 'number' && m.score < 0.8 }"
                      :title="m.method"
                    >{{ typeof m.score === 'number' ? m.score.toFixed(3) : '—' }}</td>
                    <td>{{ typeof m.transmission === 'number' ? (m.transmission * 100).toFixed(2) + '%' : '—' }}</td>
                    <td :class="{ 'bgs-error-cell': m.error, 'bgs-warn-cell': !m.error && ionMatchWarn(m) }">{{ ionMatchNote(m) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>

        <!-- Transmission file import / 透过率文件导入 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.transFile') }}</h3>
          <!-- Stay visible after a successful match even though the source
               auto-switched to per-file — otherwise the match table the user
               just earned vanishes with the card. / 匹配成功后来源会自动切到
               “分别设置”，卡片内容必须随之保留——否则刚得到的匹配表跟着卡片
               一起消失。 -->
          <p
            v-if="transmissionSource !== 'file' && transmissionMatches.length === 0"
            class="bgs-file-summary bgs-file-summary--muted"
          >
            {{ t('bgSubtract.transFileHint') }}
          </p>
          <template v-else>
            <FileDialogButton
              v-model="transmissionFile"
              mode="openFile"
              :label="t('bgSubtract.transFilePick')"
              :filters="transmissionFileFilters"
              data-ai-id="bg:trans-file-pick"
            />
            <button
              type="button"
              class="bgs-btn"
              :disabled="!canMatchTransmissionFile"
              data-ai-id="bg:trans-file-match"
              data-testid="bg-trans-file-match"
              @click="handleMatchTransmissionFile"
            >
              {{ matchingTransmissionFile ? t('bgSubtract.transFileMatching') : t('bgSubtract.transFileMatch') }}
            </button>

            <!-- Match results table / 匹配结果表 -->
            <div v-if="transmissionMatches.length > 0" class="bgs-match-table-wrap" data-testid="bg-trans-match-table">
              <div v-if="allTransmissionUnmatched" class="bgs-match-warning">
                ⚠ {{ t('bgSubtract.transFileNoMatch') }}
              </div>
              <table class="bgs-match-table">
                <thead>
                  <tr>
                    <th>{{ t('bgSubtract.transMatchColFile') }}</th>
                    <th class="bgs-col-num">{{ t('bgSubtract.transMatchColTrans') }}</th>
                    <th>{{ t('bgSubtract.transMatchColNote') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in transmissionMatches" :key="m.data_file">
                    <td :title="m.data_file">{{ extractFileName(m.data_file) }}</td>
                    <td class="bgs-col-num">{{ typeof m.transmission === 'number' ? (m.transmission * 100).toFixed(2) + '%' : '—' }}</td>
                    <td
                      :class="{ 'bgs-error-cell': typeof m.transmission !== 'number' }"
                      :title="m.note || (m.matched_file ? extractFileName(m.matched_file) : '')"
                    >
                      {{ m.note || (m.matched_file ? extractFileName(m.matched_file) : '') }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>

        <!-- Acquisition log ("计算文件") import / 采集日志（计算文件）导入 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.transLog') }}</h3>
          <p
            v-if="transmissionSource !== 'log' && logCt0Entries.length === 0"
            class="bgs-file-summary bgs-file-summary--muted"
          >
            {{ t('bgSubtract.transLogHint') }}
          </p>
          <template v-else>
            <FileDialogButton
              v-model="logCt0File"
              mode="openFile"
              :label="t('bgSubtract.transLogPick')"
              :filters="logCt0Filters"
              data-testid="bg-log-pick"
            />
            <p class="bgs-ion-formula">{{ t('bgSubtract.logFormula') }}</p>
            <p class="bgs-ion-hint">{{ t('bgSubtract.logFormulaHint') }}</p>

            <button
              type="button"
              class="bgs-btn"
              :disabled="!canMatchLogCt0"
              data-testid="bg-log-parse"
              @click="handleParseLogCt0"
            >
              {{ matchingLogCt0 ? t('bgSubtract.matching') : t('bgSubtract.logParseBtn') }}
            </button>

            <template v-if="logCt0Entries.length > 0">
              <!-- Blank (open-beam) reference / blank（开放光路）参考读数 -->
              <div class="bgs-field">
                <label class="bgs-label">{{ t('bgSubtract.logBlankRef') }}</label>
                <select
                  v-model.number="logCt0BlankIndex"
                  class="bgs-select"
                  data-testid="bg-log-blank"
                >
                  <option :value="null">—</option>
                  <option v-for="(e, i) in logCt0Entries" :key="i" :value="i">
                    {{ logEntryLabel(e) }}
                  </option>
                </select>
                <p v-if="logCt0BlankIndex == null" class="bgs-match-warning">
                  ⚠ {{ t('bgSubtract.logBlankRequired') }}
                </p>
              </div>

              <!-- Editable pairing table / 可编辑配对表 -->
              <div v-if="logCt0Matches.length > 0" class="bgs-match-table-wrap" data-testid="bg-log-match-table">
                <table class="bgs-match-table">
                  <thead>
                    <tr>
                      <th>{{ t('bgSubtract.matchColFile') }}</th>
                      <th>{{ t('bgSubtract.logColEntry') }}</th>
                      <th>{{ t('bgSubtract.logColCt0') }}</th>
                      <th>{{ t('bgSubtract.transMatchColNote') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in logCt0Matches" :key="row.data_file">
                      <td :title="row.data_file">{{ extractFileName(row.data_file) }}</td>
                      <td>
                        <select
                          class="bgs-select bgs-select--compact"
                          :value="logCt0Assignment[row.data_file] ?? -1"
                          data-testid="bg-log-assign"
                          @change="onLogAssignment(row.data_file, $event)"
                        >
                          <option :value="-1">—</option>
                          <option v-for="(e, i) in logCt0Entries" :key="i" :value="i">
                            {{ logEntryLabel(e) }}
                          </option>
                        </select>
                      </td>
                      <td>{{ logRowCt0(row) }}</td>
                      <td :title="logRowNote(row)">{{ logRowNote(row) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <button
                type="button"
                class="bgs-btn"
                :disabled="!canApplyLogCt0"
                data-testid="bg-log-apply"
                @click="handleApplyLogCt0"
              >
                {{ applyingLogCt0 ? t('bgSubtract.matching') : t('bgSubtract.logApplyBtn') }}
              </button>
            </template>
          </template>
        </div>

        <!-- Export settings / 导出设置 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.export') }}</h3>
          <!-- Web mode cannot pick a server-side folder; results download
               automatically instead — say so, or the dead dir picker reads
               as broken. / web 模式无法选择服务器目录，结果改为自动下载
               ——必须说明，否则点不动的目录按钮像坏了。 -->
          <div v-if="!transport.isDesktop()" class="bgs-match-warning">
            {{ t('bgSubtract.webExportNote') }}
          </div>
          <FileDialogButton
            v-if="transport.isDesktop()"
            v-model="outputDir"
            mode="openFolder"
            :label="t('bgSubtract.outputDir')"
          />
          <div class="bgs-field">
            <label class="bgs-label">{{ t('bgSubtract.outputFormat') }}</label>
            <select v-model="outputFormat" class="bgs-select">
              <option value="h5">HDF5</option>
              <option value="edf">EDF</option>
              <option value="tif">TIFF</option>
            </select>
          </div>
        </div>

        <!-- Execute / 执行 -->
        <div class="bgs-card">
          <!-- Say WHY the run button is disabled — a greyed-out button with no
               explanation reads as "stuck at step 1" (user report 2026-10-29:
               ionchamber matching done but the subtraction step unreachable).
               / 明确告知执行按钮为何不可用——只变灰不解释会让用户以为卡在
               第一步（2026-10-29 用户反馈：电离室匹配完成却进不了扣除）。 -->
          <div v-if="missingPrerequisites.length > 0" class="bgs-match-warning">
            ⚠ {{ t('bgSubtract.executeBlocked', { items: missingPrerequisites.join(' / ') }) }}
          </div>
          <button
            type="button"
            class="bgs-btn bgs-btn-primary"
            :disabled="!canSubtract"
            data-ai-id="bg:run"
            @click="handleSubtract"
          >
            {{ mode === 'batch' ? t('bgSubtract.startBatch') : t('bgSubtract.execute') }}
          </button>
        </div>
      </aside>

      <!-- ===== Main area / 主区域 ===== -->
      <main class="bgs-main">
        <!-- Row 1: Sample + Background side by side / 样品与背景并列 -->
        <div class="bgs-two-row">
          <!-- Sample panel / 样品面板 -->
          <div class="bgs-panel">
            <div class="bgs-panel-header">
              <span class="bgs-panel-title">{{ t('bgSubtract.tabSample') }}</span>
            </div>
            <div v-if="samplePreviewLoading" class="bgs-preview-loading">
              {{ t('bgSubtract.loading') }}
            </div>
            <div v-else-if="samplePreviewUrl" class="bgs-panel-image">
              <ImagePreview
                :image-b64="samplePreviewUrl"
                :show-colorbar="false"
                :placeholder="t('bgSubtract.noImage')"
                :render-min="climMode === 'manual' ? climMin : undefined"
                :render-max="climMode === 'manual' ? climMax : undefined"
                :use-log-scale="useLog"
              />
            </div>
            <div v-else class="bgs-preview-empty">
              {{ t('bgSubtract.noPreview') }}
            </div>
            <div v-if="samplePreviewStats" class="bgs-panel-stats">
              <span>Min: {{ formatSci(samplePreviewStats.min) }}</span>
              <span>Max: {{ formatSci(samplePreviewStats.max) }}</span>
              <span>Mean: {{ formatSci(samplePreviewStats.mean) }}</span>
            </div>
          </div>

          <!-- Background panel / 背景面板 -->
          <div class="bgs-panel">
            <div class="bgs-panel-header">
              <span class="bgs-panel-title">{{ t('bgSubtract.tabBackground') }}</span>
              <span v-if="bgPath" class="bgs-panel-file-hint">{{ extractFileName(bgPath) }}</span>
            </div>
            <div v-if="bgPreviewLoading" class="bgs-preview-loading">
              {{ t('bgSubtract.loading') }}
            </div>
            <div v-else-if="bgPreviewUrl" class="bgs-panel-image">
              <ImagePreview
                :image-b64="bgPreviewUrl"
                :show-colorbar="false"
                :placeholder="t('bgSubtract.noImage')"
                :render-min="climMode === 'manual' ? climMin : undefined"
                :render-max="climMode === 'manual' ? climMax : undefined"
                :use-log-scale="useLog"
              />
            </div>
            <div v-else class="bgs-preview-empty">
              {{ t('bgSubtract.noPreview') }}
            </div>
            <div v-if="bgPreviewStats" class="bgs-panel-stats">
              <span>Min: {{ formatSci(bgPreviewStats.min) }}</span>
              <span>Max: {{ formatSci(bgPreviewStats.max) }}</span>
              <span>Mean: {{ formatSci(bgPreviewStats.mean) }}</span>
            </div>
          </div>
        </div>

        <!-- Display settings / 显示设置 -->
        <div class="bgs-card bgs-display-bar">
          <div class="bgs-display-row">
            <div class="bgs-field" style="min-width:140px">
              <label class="bgs-label">{{ t('bgSubtract.colormap') }}</label>
              <select v-model="colormap" class="bgs-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
              </select>
            </div>
            <label class="bgs-toggle-label" style="white-space:nowrap">
              <input v-model="useLog" type="checkbox" />
              <span>{{ t('bgSubtract.logScale') }}</span>
            </label>
            <div class="bgs-radio-row">
              <label class="bgs-radio-label">
                <input v-model="climMode" type="radio" value="auto" />
                <span>{{ t('bgSubtract.contrastAuto') }}</span>
              </label>
              <label class="bgs-radio-label">
                <input v-model="climMode" type="radio" value="manual" />
                <span>{{ t('bgSubtract.contrastManual') }}</span>
              </label>
            </div>
            <template v-if="climMode === 'manual'">
              <div class="bgs-field">
                <label class="bgs-label">Min</label>
                <NumberField
                  :model-value="climMin"
                  class="bgs-input bgs-input-sm"
                  step="any"
                  @update:model-value="climMin = $event ?? 0"
                />
              </div>
              <div class="bgs-field">
                <label class="bgs-label">Max</label>
                <NumberField
                  :model-value="climMax"
                  class="bgs-input bgs-input-sm"
                  step="any"
                  @update:model-value="climMax = $event ?? 0"
                />
              </div>
            </template>
          </div>
        </div>

        <!-- Result panel / 结果面板 -->
        <div v-if="resultPreviewUrl || resultPreviewLoading" class="bgs-panel bgs-result-panel-single">
          <div class="bgs-panel-header">
            <span class="bgs-panel-title">{{ t('bgSubtract.tabResult') }}</span>
          </div>
          <div v-if="resultPreviewLoading" class="bgs-preview-loading">
            {{ t('bgSubtract.loading') }}
          </div>
          <div v-else-if="resultPreviewUrl" class="bgs-panel-image">
            <ImagePreview
              :image-b64="resultPreviewUrl"
              :show-colorbar="false"
              :placeholder="t('bgSubtract.noImage')"
              :render-min="climMode === 'manual' ? climMin : undefined"
              :render-max="climMode === 'manual' ? climMax : undefined"
              :use-log-scale="useLog"
            />
          </div>
          <div v-if="resultPreviewStats" class="bgs-panel-stats">
            <span>Min: {{ formatSci(resultPreviewStats.min) }}</span>
            <span>Max: {{ formatSci(resultPreviewStats.max) }}</span>
            <span>Mean: {{ formatSci(resultPreviewStats.mean) }}</span>
          </div>
        </div>

        <!-- Thumbnail strip below result / 缩略图在结果下方 -->
        <div
          v-if="currentSamplePaths.length > 1 && (thumbnailItems.length || thumbnailsLoading)"
          class="bgs-thumb-strip"
        >
          <ThumbnailStrip
            :items="thumbnailItems"
            :selected-index="currentSampleIndex"
            :current-page="1"
            :total-pages="1"
            :page-size="100"
            :loading="thumbnailsLoading"
            :sync-with-main="false"
            :columns-per-row="6"
            @select="onThumbnailSelect"
          />
        </div>

        <!-- Progress bar / 进度条 -->
        <TaskProgressBar
          v-if="state === 'running'"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />

        <!-- Error state / 错误状态 -->
        <div v-if="state === 'error'" class="bgs-error">
          <p>{{ t('bgSubtract.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <!-- Batch result summary / 批量结果摘要 -->
        <ResultSummary
          v-if="batchResultSummary"
          :summary="batchResultSummary"
        />

        <!-- Empty state / 空状态 -->
        <div v-if="state === 'idle' && !samplePreviewUrl && !batchResultSummary" class="bgs-empty">
          <p>{{ t('bgSubtract.emptyState') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * BgSubtractView.vue — 背景减除页面
 * Background subtraction page: single/batch processing with ionchamber matching,
 * multi-file selection, folder scanning, and image display controls.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { clearWorkspace, reportWorkspace } from '@/lib/workspace-state'
import type { TaskBinaryPayload } from '@/lib/transport'
import { createImportDropZone, extensionsFromFilters } from '@/lib/fileDrop'
import { COLORMAP_PRESETS } from '@/lib/chart-utils'

import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import NumberField from '@/components/common/NumberField.vue'
import ResultSummary from '@/components/business/ResultSummary.vue'
import type { ResultSummaryData } from '@/components/business/ResultSummary.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'

// === Type definitions / 类型定义 ===

interface IonchamberMatch {
  data_file: string
  matched_ion: string | null
  score?: number
  method?: string
  transmission?: number
  note?: string
  error?: string
  transmission_computed?: boolean
}

/** One row of the transmission-file match table (basename match, case-insensitive).
 *  透过率文件匹配表的一行（按文件名匹配，大小写不敏感）。 */
interface TransmissionFileMatch {
  data_file: string
  matched_file: string | null
  transmission: number | null
  note?: string
}

/** One "Pil Ct0" counter reading parsed from the beamline acquisition log
 *  ("计算文件", fixed format, 2026-11-06). / 从线站固定格式采集日志（计算文
 *  件）解析出的一条 Pil Ct0 计数读数。 */
interface LogCt0Entry {
  position: string
  timestamp: string
  ct0: number | null
  source_file: string
}

/** One row of the log pairing table: a data file with its suggested Ct0
 *  reading (filename match first, log order flagged as a suggestion).
 *  日志配对表的一行：数据文件 + 建议配对的 Ct0 读数（文件名优先，日志顺序
 *  兜底并标注为建议）。 */
interface LogCt0MatchRow {
  data_file: string
  position: string
  ct0: number | null
  timestamp: string
  source_file: string
  entry_index?: number | null
  matched_by: 'filename' | 'order' | null
  note?: string
}

interface BatchResult {
  success_count: number
  failed_count: number
  failed_files: string[]
  /** Absolute paths of exported files (web mode downloads these). */
  output_files?: string[]
  output_dir: string
  elapsed: number
}

interface PreviewStats {
  min: number
  max: number
  mean: number
  shape?: [number, number]
}

type PageState = 'idle' | 'running' | 'done' | 'error'
type Mode = 'single' | 'batch'
type TransmissionSource = 'manual' | 'per-file' | 'ionchamber' | 'file' | 'log'
type ImportMode = 'replace' | 'append'

// === Composables / 组合函数 ===

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// === Colormap options / 色图选项 ===

const colormapOptions = [
  'smooth_WAXS_foxtrot',
  'smooth_WAXS_fit2D',
  ...Object.keys(COLORMAP_PRESETS).filter(k => k !== 'foxtrot' && k !== 'fit2d'),
] as string[]

// === Mode & state / 模式与状态 ===

const mode = ref<Mode>('single')
const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

// === File selection / 文件选择 ===

const samplePaths = ref<string[]>([])
const bgPath = ref<string | null>(null)
const sampleFolder = ref<string | null>(null)
const importMode = ref<ImportMode>('replace')
const currentSampleIndex = ref(0)
const batchFolderFiles = ref<string[]>([])

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// === Ionchamber / 电离室 ===

const ionchamberFolder = ref<string | null>(null)
const bgIonchamberPath = ref<string | null>(null)
const ionchamberMatches = ref<IonchamberMatch[]>([])
/** True once match results were backfilled into perFileTransmissions, so the
 *  run can refuse files that are not covered. / 匹配结果是否已回填逐文件
 *  透射率——用于拒绝未被覆盖的文件，避免静默按 100% 扣除。 */
const ionchamberBackfilled = ref(false)
const manualTransmission = ref(100)
const perFileTransmissions = ref<Record<string, number>>({})
const transmissionSource = ref<TransmissionSource>('manual')
const matchingIonchamber = ref(false)
const minScore = ref(0.4)
const regexPattern = ref('')
const ionchamberChannel = ref('Ionchamber0')
const ionchamberMethod = ref<'median' | 'mean' | 'trimmed_mean'>('median')
/** Transmission calculation mode: single channel ratio or the before/after
 *  pair formula T = (sample_after/sample_before)·(bg_before/bg_after)
 *  (corrected 2026-11-06 — the 2026-11-04 first version was its reciprocal).
 *  / 透射率计算模式：单通道比值，或前后通道公式 T = 样品后/样品前 × 背景前/
 *  背景后（2026-11-06 用户指正后修正——2026-11-04 首版恰为其倒数）。 */
const ionchamberMode = ref<'single' | 'dual'>('single')
const ionSampleBefore = ref('Ionchamber0')
const ionSampleAfter = ref('Ionchamber1')
const ionBgBefore = ref('Ionchamber0')
const ionBgAfter = ref('Ionchamber1')
/** Before/after channels must differ or the formula degenerates to 100%.
 *  前后通道必须不同，否则公式恒为 100%。 */
const ionchamberDualInvalid = computed(() =>
  ionchamberMode.value === 'dual'
  && (ionSampleBefore.value === ionSampleAfter.value
    || ionBgBefore.value === ionBgAfter.value))

// === Transmission file (CSV/JSON from the transmission page) / 透过率文件 ===

const transmissionFile = ref<string | null>(null)
const transmissionMatches = ref<TransmissionFileMatch[]>([])
const matchingTransmissionFile = ref(false)
const transmissionFileFilters = [
  { name: 'Transmission Files', extensions: ['csv', 'json'] },
  { name: 'All Files', extensions: ['*'] },
]

// === Acquisition log ("计算文件", Pil Ct0) / 采集日志（计算文件，Pil Ct0）===

const logCt0File = ref<string | null>(null)
const logCt0Entries = ref<LogCt0Entry[]>([])
const logCt0Matches = ref<LogCt0MatchRow[]>([])
const matchingLogCt0 = ref(false)
const applyingLogCt0 = ref(false)
/** Chosen blank (open-beam) reference: index into logCt0Entries. / 选定的
 *  blank（开放光路）参考读数：logCt0Entries 的下标。 */
const logCt0BlankIndex = ref<number | null>(null)
/** User-adjusted pairing: data file → index into logCt0Entries. / 用户调整后
 *  的配对：数据文件 → logCt0Entries 下标（-1 = 不配对）。 */
const logCt0Assignment = ref<Record<string, number>>({})
const logCt0Filters = [
  { name: 'Log Files', extensions: ['txt', 'log', 'text'] },
  { name: 'All Files', extensions: ['*'] },
]

// === Display settings / 显示设置 ===

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(false)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
const climMax = ref(1)

// Debounce timer for contrast changes / 对比度变化防抖定时器
let contrastDebounceTimer: ReturnType<typeof setTimeout> | null = null

// === Preview / 预览 ===

// Per-panel preview data / 每栏独立预览数据
const samplePreviewUrl = ref<string | null>(null)
const samplePreviewStats = ref<PreviewStats | null>(null)
const samplePreviewLoading = ref(false)
const bgPreviewUrl = ref<string | null>(null)
const bgPreviewStats = ref<PreviewStats | null>(null)
const bgPreviewLoading = ref(false)
const resultPreviewUrl = ref<string | null>(null)
const resultPreviewStats = ref<PreviewStats | null>(null)
const resultPreviewLoading = ref(false)

// Thumbnail strip / 缩略图
const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbnailsLoading = ref(false)

// === Batch result / 批量结果 ===

const batchResult = ref<BatchResult | null>(null)

// === Export / 导出 ===

const outputDir = ref<string | null>(null)
const outputFormat = ref<'h5' | 'edf' | 'tif'>('tif')

// === Cleanup functions / 清理函数 ===

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupBinaryData: (() => void) | null = null

// === Computed / 计算属性 ===

const currentSamplePaths = computed(() => {
  if (mode.value === 'single') return samplePaths.value
  return batchFolderFiles.value
})

/** Number of match rows with a usable transmission. / 有可用透射率的匹配行数。 */
const matchedTransmissionCount = computed(() =>
  ionchamberMatches.value.filter(
    m => typeof m.transmission === 'number' && m.transmission > 0
  ).length
)

/** Files in the current selection with no ionchamber transmission after a
 *  backfill. They must not silently run at T=1.0. / 回填后仍无电离室透射率
 *  的文件——不得静默按 T=1.0 扣除。 */
const ionchamberUncoveredCount = computed(() => {
  if (!ionchamberBackfilled.value) return 0
  // Only the per-file/ionchamber paths consume the matched values; if the
  // user deliberately switched to a manual global value that is an explicit
  // choice, not a silent fallback. / 仅逐文件/电离室来源消费匹配值；用户
  // 主动改为手动全局值属于明确选择，不算静默回退。
  if (
    transmissionSource.value !== 'ionchamber'
    && transmissionSource.value !== 'per-file'
  ) {
    return 0
  }
  // Count against the actual per-file map so a value the user typed in the
  // file list also clears the blocker. / 以逐文件映射为准，用户在文件列表
  // 手填的值同样能解除阻塞。
  return currentSamplePaths.value.filter(fp => {
    const value = perFileTransmissions.value[fp]
    return !(typeof value === 'number' && value > 0)
  }).length
})

const canSubtract = computed(() => {
  if (state.value === 'running') return false
  // Desktop requires an explicit output dir in BOTH modes: single-file runs
  // must also land on disk (the legacy single path computed a preview but
  // never saved — user report 2026-10-23 "subtracted but nothing exported").
  // Web mode has NO folder picker (browsers cannot browse the server), so
  // NEITHER mode requires one there: results are saved next to the uploaded
  // samples and auto-downloaded via /api/download (2026-11-04: batch used to
  // stay blocked on the missing output dir in web mode).
  // 桌面模式两种方式都要求显式输出目录：单文件执行同样要落盘（旧单文件
  // 路径只算不存，2026-10-23 用户报告"发生了扣除但不导出"的根因）。
  // web 模式没有目录选择器（浏览器无法浏览服务器目录），两种模式都不要求
  // 输出目录：结果保存到样品上传目录旁并经 /api/download 自动下载
  // （2026-11-04：批量此前在 web 下被缺失的输出目录卡死）。
  const requireOutDir = transport.isDesktop()
  const ionchamberReady = transmissionSource.value !== 'ionchamber'
    || matchedTransmissionCount.value > 0
  return currentSamplePaths.value.length > 0 && !!bgPath.value
    && (!requireOutDir || !!outputDir.value) && ionchamberReady
    && ionchamberUncoveredCount.value === 0
})

// Publish progress to the workspace-state bridge for the AI guided tour
// (Jev build); inert in the main build — no AI module is imported.
// 向状态桥上报进度供教学模式使用；主线构建中为惰性。
watch(
  [samplePaths, batchFolderFiles, bgPath, outputDir, state, canSubtract],
  () => {
    reportWorkspace('bg-subtract', {
      filesCount: currentSamplePaths.value.length,
      hasPoni: false,
      canRun: canSubtract.value,
      phase: state.value,
      extras: {
        hasBackground: Boolean(bgPath.value),
        hasOutputDir: Boolean(outputDir.value),
      },
    })
  },
  { immediate: true, deep: true }
)
onUnmounted(() => clearWorkspace('bg-subtract'))

const canMatchIonchamber = computed(() => {
  const hasFiles = mode.value === 'batch'
    ? batchFolderFiles.value.length > 0
    : samplePaths.value.length > 0
  // The background ionchamber file is required — without it the backend
  // cannot compute any transmission and now rejects the match explicitly.
  // 背景电离室文件为必需项——没有它后端算不出任何透射率（现在会明确拒绝）。
  return hasFiles && !!ionchamberFolder.value && !!bgIonchamberPath.value
    && !matchingIonchamber.value
    && !ionchamberDualInvalid.value
})

/** Human-readable list of what still blocks the run button. The button is
 *  disabled without these; showing the list keeps users from being stuck at
 *  an unexplained grey button. / 仍阻塞执行的条件清单，避免用户面对一个
 *  没有任何解释的灰色按钮。 */
const missingPrerequisites = computed<string[]>(() => {
  const items: string[] = []
  if (currentSamplePaths.value.length === 0) items.push(t('bgSubtract.reqSamples'))
  if (!bgPath.value) items.push(t('bgSubtract.reqBackground'))
  if (transport.isDesktop() && !outputDir.value) {
    items.push(t('bgSubtract.reqOutput'))
  }
  if (transmissionSource.value === 'ionchamber' && matchedTransmissionCount.value === 0) {
    items.push(t('bgSubtract.reqIonchamberMatch'))
  }
  if (ionchamberUncoveredCount.value > 0) {
    items.push(t('bgSubtract.reqIonchamberCoverage', {
      count: ionchamberUncoveredCount.value,
    }))
  }
  return items
})

/** Transmission-file matching: files present + a transmission file chosen.
 *  In batch mode a selected folder is enough — the backend scans it itself. */
const canMatchTransmissionFile = computed(() => {
  const hasFiles = mode.value === 'batch'
    ? !!sampleFolder.value || batchFolderFiles.value.length > 0
    : samplePaths.value.length > 0
  return hasFiles && !!transmissionFile.value && !matchingTransmissionFile.value
})

/** True when a match attempt produced no usable transmission at all. */
const allTransmissionUnmatched = computed(() =>
  transmissionMatches.value.length > 0
  && transmissionMatches.value.every(m => typeof m.transmission !== 'number')
)

// === Log ("计算文件") matching computeds / 日志匹配计算属性 ===

/** Files present + a log file chosen. / 有数据文件且已选日志文件。 */
const canMatchLogCt0 = computed(() => {
  const hasFiles = mode.value === 'batch'
    ? !!sampleFolder.value || batchFolderFiles.value.length > 0
    : samplePaths.value.length > 0
  return hasFiles && !!logCt0File.value && !matchingLogCt0.value
})

/** The blank reference must be picked and carry a positive reading; at least
 *  one pairing row must have a usable Ct0. / blank 参考必须已选且读数为正；
 *  至少一行配对有可用 Ct0。 */
const canApplyLogCt0 = computed(() => {
  if (logCt0Matches.value.length === 0 || applyingLogCt0.value) return false
  const blank = logCt0BlankIndex.value != null
    ? logCt0Entries.value[logCt0BlankIndex.value]
    : null
  if (!blank || typeof blank.ct0 !== 'number' || blank.ct0 <= 0) return false
  return Object.entries(logCt0Assignment.value).some(([, idx]) =>
    idx != null && idx >= 0
    && typeof logCt0Entries.value[idx]?.ct0 === 'number')
})

/** Select-option label for one Ct0 entry. / 一条 Ct0 读数的下拉选项文案。 */
function logEntryLabel(entry: LogCt0Entry): string {
  const value = typeof entry.ct0 === 'number' ? formatSci(entry.ct0) : '—'
  return `Position ${entry.position || '?'} · ${value}`
}

/** Ct0 value of the row's CURRENTLY ASSIGNED entry (live with the dropdown).
 *  该行当前所选读数的 Ct0 值（随下拉即时变化）。 */
function logRowCt0(row: LogCt0MatchRow): string {
  const idx = logCt0Assignment.value[row.data_file]
  const entry = idx != null && idx >= 0 ? logCt0Entries.value[idx] : null
  if (!entry || typeof entry.ct0 !== 'number') return '—'
  return formatSci(entry.ct0)
}

/** Note text for a pairing row. / 配对行的备注文案。 */
function logRowNote(row: LogCt0MatchRow): string {
  if (row.note) return row.note
  if (row.matched_by === 'filename') return t('bgSubtract.logMatchByFilename')
  if (row.matched_by === 'order') return t('bgSubtract.logMatchByOrder')
  return t('bgSubtract.logNoMatch')
}

/** Dropdown change on a pairing row. / 配对行下拉变化。 */
function onLogAssignment(dataFile: string, event: Event): void {
  const value = Number((event.target as HTMLSelectElement).value)
  logCt0Assignment.value = {
    ...logCt0Assignment.value,
    [dataFile]: Number.isFinite(value) ? value : -1,
  }
}

// Per-file transmission cap (user request 2026-10-13: raised 10 → 100). The
// UI keeps the per-file inputs for up to 100 sample images; beyond that the
// radio is disabled AND the user is explicitly told (visible warning + toast
// on the forced switch) instead of the option silently greying out — the
// previous behaviour read as "the feature disappeared" after importing many
// images. / 逐文件透过率上限（2026-10-13 用户要求：10 → 100）。≤100 张仍可
// 逐文件设置；超出时禁用单选并明确告知（警示条 + 强切时的 toast），而非像
// 从前那样选项悄悄变灰——用户导入多图后误以为功能丢失。
const PER_FILE_TRANSMISSION_LIMIT = 100
const tooManyFilesForPerFile = computed(() => currentSamplePaths.value.length > PER_FILE_TRANSMISSION_LIMIT)

const batchResultSummary = computed<ResultSummaryData | null>(() => {
  if (!batchResult.value) return null
  return {
    total: batchResult.value.success_count + batchResult.value.failed_count,
    success: batchResult.value.success_count,
    failed: batchResult.value.failed_count,
    elapsed: batchResult.value.elapsed,
  }
})

// === Watchers / 监听器 ===

// Reload preview when contrast settings change (debounced to prevent bounce)
// 对比度设置变化时重新加载预览（防抖以避免值弹回）
let suppressContrastReload = false

watch([climMode, climMin, climMax, useLog], () => {
  if (suppressContrastReload) return
  // Skip if values are invalid (e.g. user is mid-typing) / 跳过无效值
  if (climMode.value === 'manual') {
    if (!Number.isFinite(climMin.value) || !Number.isFinite(climMax.value)) return
  }
  // Debounce: wait for user to finish typing / 防抖：等待用户输入完毕
  if (contrastDebounceTimer) clearTimeout(contrastDebounceTimer)
  contrastDebounceTimer = setTimeout(() => {
    contrastDebounceTimer = null
    if (state.value === 'idle') {
      reloadAllPreviews()
    }
  }, 400)
})

watch(sampleFolder, (folder) => {
  batchFolderFiles.value = []
  currentSampleIndex.value = 0
  if (folder) {
    void scanFolder(folder)
  }
})

// Reload panels when current sample index changes / 样品索引变化时重新加载面板
watch(currentSampleIndex, () => {
  if (currentSamplePaths.value.length > 0) {
    loadSamplePanel()
    if (resultPreviewUrl.value || state.value === 'done') {
      loadResultPanel()
    }
  }
})

// Auto-load background panel when bgPath changes / 背景文件变化时自动加载
watch(bgPath, (newPath) => {
  if (newPath) {
    loadBgPanel()
  } else {
    if (bgPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(bgPreviewUrl.value)
    bgPreviewUrl.value = null
    bgPreviewStats.value = null
  }
})

// Force switch away from per-file when over the limit — WITH a toast, so the
// forced fallback is never silent (user request 2026-10-13: 超出数量请告知用户).
// 超出逐文件上限时强制切回统一模式——附 toast 提示，绝不静默切换。
watch(tooManyFilesForPerFile, (tooMany) => {
  if (tooMany && transmissionSource.value === 'per-file') {
    transmissionSource.value = 'manual'
    toast.push({
      title: t('bgSubtract.title'),
      message: t('bgSubtract.tooManyFilesWarning', { limit: PER_FILE_TRANSMISSION_LIMIT }),
      tone: 'warning',
    })
  }
})

// === Helpers / 辅助函数 ===

/** Note cell for an ionchamber match row: error, backend note, method badge
 *  for continuous-scan fallbacks, and a >100% transmission hint.
 *  电离室匹配行的备注列：错误 / 后端备注 / 就近与时间窗方法标记 / 超 100% 提示。 */
function ionMatchNote(m: IonchamberMatch): string {
  const parts: string[] = []
  if (m.error) parts.push(m.error)
  else if (m.note) parts.push(m.note)
  else if (m.method === 'time_window') parts.push(t('bgSubtract.ionMethodTimeWindow'))
  else if (m.method === 'base_num_nearest') parts.push(t('bgSubtract.ionMethodNearest'))
  if (typeof m.transmission === 'number' && m.transmission > 1) {
    parts.push(t('bgSubtract.ionTransOverHint'))
  }
  return parts.join(' · ')
}

/** True when the row needs attention: weak name match or T over 100%.
 *  需要注意的行：弱命名匹配或透射率超 100%。 */
function ionMatchWarn(m: IonchamberMatch): boolean {
  return (typeof m.score === 'number' && m.score < 0.8)
    || (typeof m.transmission === 'number' && m.transmission > 1)
}

function extractFileName(filePath: string): string {
  const sep = filePath.includes('/') ? '/' : '\\'
  const parts = filePath.split(sep)
  return parts[parts.length - 1] || filePath
}

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

/** Scalar fallback: the first USABLE matched transmission (rows without a
 *  computed value must not shadow one that has it). / 标量回退：第一个真正
 *  算出的匹配透射率（无值行不得遮挡有值行）。 */
function getMatchedTransmission(): number {
  const computedMatch = ionchamberMatches.value.find(
    m => typeof m.transmission === 'number' && m.transmission > 0
  )
  if (computedMatch?.transmission) return computedMatch.transmission
  return manualTransmission.value / 100
}

/** Per-file map (ratios) built from matched ionchamber transmissions — sent
 *  with the run so the matched values take effect for every file, mirroring
 *  the transmission-file import flow. / 由电离室匹配结果构建的逐文件映射
 *  （小数比率），随执行一起发送，让匹配值对每个文件生效，与透过率文件导入
 *  流程一致。 */
function getMatchedTransmissions(): Record<string, number> {
  const result: Record<string, number> = {}
  for (const m of ionchamberMatches.value) {
    if (typeof m.transmission === 'number' && m.transmission > 0) {
      result[m.data_file] = m.transmission
    }
  }
  return result
}

function getPerFileTransmissions(): Record<string, number> {
  const result: Record<string, number> = {}
  for (const fp of currentSamplePaths.value) {
    const pct = perFileTransmissions.value[fp] ?? manualTransmission.value
    result[fp] = pct / 100  // convert % to ratio
  }
  return result
}

function getRenderSettingsParams(): Record<string, unknown> {
  const params: Record<string, unknown> = {
    cmap: colormap.value,
    use_log: useLog.value,
  }
  if (climMode.value === 'manual') {
    params.clim_min = climMin.value
    params.clim_max = climMax.value
  }
  return params
}

function removeSampleFile(index: number): void {
  const fp = samplePaths.value[index]
  samplePaths.value.splice(index, 1)
  if (fp) delete perFileTransmissions.value[fp]
  if (currentSampleIndex.value >= samplePaths.value.length) {
    currentSampleIndex.value = Math.max(0, samplePaths.value.length - 1)
  }
}

// === Multi-file selection / 多文件选择 ===

/** Apply a batch of sample file paths honoring the replace/append import mode. */
function applySampleFilePaths(paths: string[]): void {
  if (importMode.value === 'append') {
    const existingSet = new Set(samplePaths.value)
    const newFiles = paths.filter(p => !existingSet.has(p))
    samplePaths.value = [...samplePaths.value, ...newFiles]
  } else {
    samplePaths.value = paths
    currentSampleIndex.value = 0
  }
  // Initialize per-file transmission defaults / 初始化逐文件透射率默认值
  for (const p of paths) {
    if (perFileTransmissions.value[p] === undefined) {
      perFileTransmissions.value[p] = manualTransmission.value  // copy current manual value as default
    }
  }
  // Load sample panel after file selection / 选择文件后加载样品面板
  if (samplePaths.value.length > 0) {
    loadSamplePanel()
    generateThumbnails()
  }
}

async function handleChooseSampleFiles(): Promise<void> {
  const result = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!result) return
  applySampleFilePaths(Array.isArray(result) ? result : [result])
}

/**
 * Web-mode batch source picker (2026-11-04): with no server-side folder
 * picker available, the batch list is filled by a multi-file selection. The
 * run then sends ``data_files`` and the backend writes each result next to
 * its source file.
 * web 模式的批量来源选择（2026-11-04）：没有服务器端目录选择器，批量列表
 * 改由多选文件填充；执行时发送 data_files，后端把结果写到各源文件旁。
 */
async function handleChooseBatchFiles(): Promise<void> {
  const result = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!result) return
  batchFolderFiles.value = Array.isArray(result) ? result : [result]
  currentSampleIndex.value = 0
  if (batchFolderFiles.value.length > 0) {
    loadSamplePanel()
    generateThumbnails()
  }
}

// Drag & drop onto the sample file area mirrors the select-files button.
// (Dropping a folder routes through the batch-mode folder scan only in
// desktop mode; in web mode a toast explains folders are unsupported.)
const fileDrop = createImportDropZone({
  transport,
  extensions: () => extensionsFromFilters(dataFileFilters),
  onFiles: (paths) => applySampleFilePaths(paths),
  onFolder: (folder) => {
    // Single mode has no folder list UI — switch into it like the batch picker.
    mode.value = 'batch'
    sampleFolder.value = folder
  },
})

// === Folder scanning / 文件夹扫描 ===

async function scanFolder(folder: string): Promise<void> {
  try {
    const response = await transport.submitTask('bg_subtract', {
      action: 'scan_folder',
      folder,
    })
    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { files: string[]; count: number }
      batchFolderFiles.value = data.files ?? []
      currentSampleIndex.value = 0
      if (batchFolderFiles.value.length > 0) {
        loadSamplePanel()
        generateThumbnails()
      }
      unsubResult()
      unsubError()
    })
    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Ionchamber matching / 电离室匹配 ===

async function handleMatchIonchamber(): Promise<void> {
  const files = currentSamplePaths.value
  if (files.length === 0 || !ionchamberFolder.value) return
  if (!bgIonchamberPath.value) {
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: t('bgSubtract.errorNoBgIonchamber'),
      tone: 'error',
    })
    return
  }
  if (ionchamberDualInvalid.value) {
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: t('bgSubtract.ionDualInvalid'),
      tone: 'error',
    })
    return
  }

  matchingIonchamber.value = true
  // Drop values from the previous match so a re-match cannot leave stale
  // transmissions behind for files the new match does not cover.
  // 清除上一次匹配回填的值，避免重新匹配后遗留过期透射率。
  for (const m of ionchamberMatches.value) {
    delete perFileTransmissions.value[m.data_file]
  }
  ionchamberBackfilled.value = false
  ionchamberMatches.value = []

  try {
    // Web batch mode has no folder path — send the selected files instead.
    // web 批量模式没有文件夹路径——改发选中的文件列表。
    const batchOnWeb = mode.value === 'batch' && !transport.isDesktop()
    const response = await transport.submitTask('bg_subtract', {
      action: 'ionchamber_match',
      sample_folder: mode.value === 'batch' && !batchOnWeb ? sampleFolder.value : undefined,
      data_files: mode.value === 'single'
        ? [...files]
        : (batchOnWeb ? [...batchFolderFiles.value] : undefined),
      ionchamber_folder: ionchamberFolder.value,
      bg_ionchamber_path: bgIonchamberPath.value || undefined,
      ionchamber_channel: ionchamberChannel.value,
      ionchamber_method: ionchamberMethod.value,
      ionchamber_mode: ionchamberMode.value,
      ionchamber_sample_before: ionSampleBefore.value,
      ionchamber_sample_after: ionSampleAfter.value,
      ionchamber_bg_before: ionBgBefore.value,
      ionchamber_bg_after: ionBgAfter.value,
      min_score: minScore.value,
      regex_pattern: regexPattern.value || undefined,
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { matches?: IonchamberMatch[] }
      const matches = Array.isArray(data.matches) ? data.matches : []
      ionchamberMatches.value = matches
      matchingIonchamber.value = false

      // Backfill the per-file transmission map exactly like the
      // transmission-file import does: the matched values are what the run
      // consumes, and switching to per-file makes them visible/editable.
      // Rows without a value must not inherit a stale value from an earlier
      // match. / 与透过率文件导入一致：把匹配值回填到逐文件映射并切源，
      // 执行时按这些值扣除；未算出值的行清掉旧值，避免张冠李戴。
      let matched = 0
      let missing = 0
      for (const m of matches) {
        if (typeof m.transmission === 'number' && m.transmission > 0) {
          // Round to 4 decimals of a percent (same rationale as the
          // transmission-file flow: full-float ratios overflow the input).
          // 百分比保留 4 位小数（与透过率文件流程一致）。
          perFileTransmissions.value[m.data_file] =
            Math.round(m.transmission * 100 * 1e4) / 1e4
          matched += 1
        } else {
          delete perFileTransmissions.value[m.data_file]
          missing += 1
        }
      }

      if (matched > 0) {
        ionchamberBackfilled.value = true
        if (!tooManyFilesForPerFile.value) {
          transmissionSource.value = 'per-file'
        }
        toast.push({
          title: t('bgSubtract.ionchamber'),
          message: t('bgSubtract.ionchamberMatchApplied', { matched, missing }),
          tone: missing > 0 ? 'warning' : 'success',
        })
        if (resultPreviewUrl.value || state.value === 'done') {
          loadResultPanel()
        }
      } else {
        toast.push({
          title: t('bgSubtract.errorTitle'),
          message: matches.length > 0
            ? t('bgSubtract.ionchamberNoTransmission')
            : t('bgSubtract.ionchamberNoMatch'),
          tone: 'error',
        })
      }

      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      matchingIonchamber.value = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    matchingIonchamber.value = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Transmission file matching / 透过率文件匹配 ===

/**
 * Match the imported transmission CSV/JSON against the current data files by
 * basename (backend does the normalization), fill the per-file map, and switch
 * the source to per-file so the matched values take effect.
 * 按文件名把导入的透过率表与当前数据文件匹配（归一化在后端），填充逐文件
 * 透过率映射并切到“分别设置”来源，使匹配值生效。
 */
async function handleMatchTransmissionFile(): Promise<void> {
  if (!canMatchTransmissionFile.value) return

  matchingTransmissionFile.value = true
  transmissionMatches.value = []

  try {
    // Web batch mode has no folder path — send the selected files instead.
    // web 批量模式没有文件夹路径——改发选中的文件列表。
    const batchOnWeb = mode.value === 'batch' && !transport.isDesktop()
    const response = await transport.submitTask('bg_subtract', {
      action: 'transmission_file_match',
      data_files: mode.value === 'single'
        ? [...samplePaths.value]
        : (batchOnWeb ? [...batchFolderFiles.value] : undefined),
      sample_folder: mode.value === 'batch' && !batchOnWeb ? sampleFolder.value ?? undefined : undefined,
      transmission_file: transmissionFile.value ?? undefined,
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { matches?: TransmissionFileMatch[] }
      const matches = Array.isArray(data.matches) ? data.matches : []
      transmissionMatches.value = matches
      matchingTransmissionFile.value = false

      const matched = matches.filter(
        (m): m is TransmissionFileMatch & { transmission: number } =>
          typeof m.transmission === 'number'
      )
      const missing = matches.length - matched.length
      if (matched.length > 0) {
        for (const m of matched) {
          // Round to 4 decimals of a percent — the raw ratio is a full float
          // (e.g. 60.00000008788259) that overflows the narrow per-file input
          // ("60.0E") and adds false precision the measurement never had.
          // 百分比保留 4 位小数——原始比值是全长浮点（如 60.00000008788259），
          // 会撑爆窄输入框（显示 "60.0E"）并带出测量根本没有的假精度。
          perFileTransmissions.value[m.data_file] =
            Math.round(m.transmission * 100 * 1e4) / 1e4
        }
        // Switch to per-file so the filled values are visible/editable — except
        // over the per-file limit (the radio is disabled there); 'file' already
        // resolves to the same per-file numbers downstream.
        // 切到“分别设置”以显示/编辑已填值——超过逐文件上限时该单选被禁用，
        // 保持 'file' 来源即可（下游同样按逐文件数值处理）。
        if (!tooManyFilesForPerFile.value) {
          transmissionSource.value = 'per-file'
        }
        toast.push({
          title: t('bgSubtract.transFile'),
          message: t('bgSubtract.transFileApplied', { matched: matched.length, missing }),
          tone: missing > 0 ? 'warning' : 'success',
        })
        // The result preview depends on the transmission — refresh it so the
        // screen never shows a result computed with the previous values.
        // 结果预览依赖透射率——立即刷新，避免屏幕停留在旧值算出的结果上。
        if (resultPreviewUrl.value || state.value === 'done') {
          loadResultPanel()
        }
      } else {
        toast.push({
          title: t('bgSubtract.transFile'),
          message: t('bgSubtract.transFileNoMatch'),
          tone: 'error',
        })
      }

      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      matchingTransmissionFile.value = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    matchingTransmissionFile.value = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Acquisition log ("计算文件") flow / 采集日志（计算文件）流程 ===

/**
 * Parse the fixed-format beamline log for the ordered "Pil Ct0" readings
 * (plus the blank open-beam reference) and get auto-matched suggestions —
 * filename first, log order as a flagged fallback. The pairing table stays
 * fully editable: the user can re-assign any row's reading and pick the
 * blank before applying (T = Ct0(file) / Ct0(blank), generally < 100%).
 * 解析线站固定格式日志中的有序 "Pil Ct0" 读数（含 blank 开放光路参考）并取
 * 回自动匹配建议——文件名优先，日志顺序兜底并标注。配对表完全可编辑：用户
 * 可改配任意行的读数、指定 blank 后再应用（T = Ct0(文件) / Ct0(blank)，一般
 * 小于 100%）。
 */
async function handleParseLogCt0(): Promise<void> {
  if (!canMatchLogCt0.value) return

  matchingLogCt0.value = true
  logCt0Entries.value = []
  logCt0Matches.value = []
  logCt0Assignment.value = {}
  logCt0BlankIndex.value = null

  try {
    // Web batch mode has no folder path — send the selected files instead.
    // web 批量模式没有文件夹路径——改发选中的文件列表。
    const batchOnWeb = mode.value === 'batch' && !transport.isDesktop()
    const response = await transport.submitTask('bg_subtract', {
      action: 'log_ct0_parse',
      log_file: logCt0File.value ?? undefined,
      data_files: mode.value === 'single'
        ? [...samplePaths.value]
        : (batchOnWeb ? [...batchFolderFiles.value] : undefined),
      sample_folder: mode.value === 'batch' && !batchOnWeb ? sampleFolder.value ?? undefined : undefined,
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as {
        entries?: LogCt0Entry[]
        blank?: LogCt0Entry | null
        matches?: LogCt0MatchRow[]
      }
      const entries = Array.isArray(data.entries) ? data.entries : []
      const matches = Array.isArray(data.matches) ? data.matches : []
      logCt0Entries.value = entries
      logCt0Matches.value = matches
      matchingLogCt0.value = false

      // Default blank: the entry the parser flagged as the open-beam reading.
      // 默认 blank：解析器标记的开放光路条目。
      const blankIdx = entries.findIndex(
        e => typeof e.position === 'string' && /blank/i.test(e.position)
      )
      logCt0BlankIndex.value = blankIdx >= 0 ? blankIdx : null

      // Seed the editable pairing from the suggestions (entry_index points
      // back into entries). / 以建议初始化可编辑配对（entry_index 指回
      // entries 数组）。
      const assign: Record<string, number> = {}
      for (const m of matches) {
        if (typeof m.entry_index === 'number' && m.entry_index >= 0) {
          assign[m.data_file] = m.entry_index
        }
      }
      logCt0Assignment.value = assign

      if (entries.length === 0) {
        toast.push({
          title: t('bgSubtract.transLog'),
          message: t('bgSubtract.transFileNoMatch'),
          tone: 'error',
        })
      } else {
        toast.push({
          title: t('bgSubtract.transLog'),
          message: t('bgSubtract.logParsed', {
            count: entries.length,
            matched: matches.filter(m => m.matched_by != null).length,
          }),
          tone: 'success',
        })
        if (blankIdx < 0) {
          toast.push({
            title: t('bgSubtract.transLog'),
            message: t('bgSubtract.logBlankMissing'),
            tone: 'warning',
          })
        }
      }

      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      matchingLogCt0.value = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    matchingLogCt0.value = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

/**
 * Apply the confirmed pairing: the backend computes T = ct0 / blank_ct0 per
 * row (validating positivity, flagging >100% in the note) and the values
 * land in the per-file map exactly like the transmission-file import.
 * 应用确认后的配对：后端逐行计算 T = ct0 / blank_ct0（校验正数、>100% 时在
 * note 中提示），数值与透过率文件导入一样落入逐文件映射。
 */
async function handleApplyLogCt0(): Promise<void> {
  if (!canApplyLogCt0.value) return
  const blankIdx = logCt0BlankIndex.value
  const blankEntry = blankIdx != null ? logCt0Entries.value[blankIdx] : null
  if (!blankEntry || typeof blankEntry.ct0 !== 'number') return

  const assignments = logCt0Matches.value
    .map(row => {
      const idx = logCt0Assignment.value[row.data_file]
      const entry = idx != null && idx >= 0 ? logCt0Entries.value[idx] : null
      if (!entry || typeof entry.ct0 !== 'number') return null
      return { data_file: row.data_file, ct0: entry.ct0, position: entry.position }
    })
    .filter((a): a is { data_file: string; ct0: number; position: string } => a != null)
  if (assignments.length === 0) return

  applyingLogCt0.value = true
  try {
    const response = await transport.submitTask('bg_subtract', {
      action: 'log_ct0_transmission',
      assignments,
      blank_ct0: blankEntry.ct0,
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as {
        matches?: { data_file: string; transmission: number | null; note?: string }[]
      }
      const matches = Array.isArray(data.matches) ? data.matches : []
      const matched = matches.filter(
        m => typeof m.transmission === 'number' && m.transmission > 0
      )
      applyingLogCt0.value = false

      if (matched.length > 0) {
        for (const m of matched) {
          // Same 4-decimal percent rounding as the transmission-file flow —
          // no false precision, no overflowing the narrow per-file input.
          // 与透过率文件流程相同的 4 位小数百分比取整——不带假精度，也不
          // 撑爆逐文件输入框。
          perFileTransmissions.value[m.data_file] =
            Math.round((m.transmission as number) * 100 * 1e4) / 1e4
        }
        if (!tooManyFilesForPerFile.value) {
          transmissionSource.value = 'per-file'
        }
        const over = matches.filter(m =>
          typeof m.transmission === 'number' && (m.transmission as number) > 1
        ).length
        toast.push({
          title: t('bgSubtract.transLog'),
          message: over > 0
            ? t('bgSubtract.logAppliedOver', { matched: matched.length, over })
            : t('bgSubtract.logApplied', { matched: matched.length }),
          tone: 'success',
        })
        // Refresh the result preview — it depends on the transmission.
        // 刷新结果预览——它依赖透射率。
        if (resultPreviewUrl.value || state.value === 'done') {
          loadResultPanel()
        }
      } else {
        toast.push({
          title: t('bgSubtract.transLog'),
          message: t('bgSubtract.transFileNoMatch'),
          tone: 'error',
        })
      }

      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      applyingLogCt0.value = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    applyingLogCt0.value = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Preview / 预览 ===

function cleanupPreviewListeners(): void {
  cleanupBinaryData?.()
  cleanupBinaryData = null
}

// Load preview into a specific panel's refs / 加载预览到指定面板的 ref
function loadPanelPreview(
  tab: 'sample' | 'background' | 'result',
  urlRef: { value: string | null },
  statsRef: { value: PreviewStats | null },
  loadingRef: { value: boolean }
): void {
  loadingRef.value = true
  suppressContrastReload = true
  if (urlRef.value?.startsWith('blob:')) {
    URL.revokeObjectURL(urlRef.value)
  }
  urlRef.value = null
  statsRef.value = null
  cleanupPreviewListeners()

  let filePath: string | null = null
  let previewAction: string

  const files = currentSamplePaths.value

  switch (tab) {
    case 'sample':
      filePath = files.length > 0 ? files[currentSampleIndex.value] ?? files[0] ?? null : null
      previewAction = 'preview_sample'
      break
    case 'background':
      filePath = bgPath.value
      previewAction = 'preview_background'
      break
    case 'result':
      filePath = files.length > 0 ? files[currentSampleIndex.value] ?? files[0] ?? null : null
      previewAction = 'preview_result'
      break
    default:
      loadingRef.value = false
      return
  }

  if (!filePath) {
    loadingRef.value = false
    return
  }

  const params: Record<string, unknown> = {
    action: previewAction,
    sample_path: filePath,
    bg_path: bgPath.value,
    ...getRenderSettingsParams(),
  }

  if (tab === 'result') {
    // 'file' (imported transmission file) behaves exactly like 'per-file':
    // the match step has already populated the per-file map.
    // 'file'（导入的透过率文件）与“分别设置”同义：匹配步骤已填好逐文件映射。
    if (transmissionSource.value === 'per-file' || transmissionSource.value === 'file') {
      const currentFile = files[currentSampleIndex.value]
      params.transmission = (perFileTransmissions.value[currentFile] ?? manualTransmission.value) / 100
    } else if (transmissionSource.value === 'manual') {
      params.transmission = manualTransmission.value / 100
    } else {
      params.transmission = getMatchedTransmission()
    }
  }

  transport.submitTask('bg_subtract', params).then((response) => {
    cleanupBinaryData = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
      if (payload.data) {
        const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
        if (urlRef.value?.startsWith('blob:')) {
          URL.revokeObjectURL(urlRef.value)
        }
        urlRef.value = URL.createObjectURL(blob)
      }
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { stats?: PreviewStats }
      if (data.stats) {
        statsRef.value = data.stats
        if (climMode.value === 'auto' && tab === 'sample') {
          climMin.value = data.stats.min
          climMax.value = data.stats.max
        }
      }
      loadingRef.value = false
      suppressContrastReload = false
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      loadingRef.value = false
      suppressContrastReload = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  }).catch((err: unknown) => {
    loadingRef.value = false
    suppressContrastReload = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  })
}

// Reload all visible panels / 重新加载所有可见面板
function reloadAllPreviews(): void {
  loadPanelPreview('sample', samplePreviewUrl, samplePreviewStats, samplePreviewLoading)
  if (bgPath.value) {
    loadPanelPreview('background', bgPreviewUrl, bgPreviewStats, bgPreviewLoading)
  }
  if (resultPreviewUrl.value || state.value === 'done') {
    loadPanelPreview('result', resultPreviewUrl, resultPreviewStats, resultPreviewLoading)
  }
}

// Load sample panel (called when files are selected) / 加载样品面板
function loadSamplePanel(): void {
  loadPanelPreview('sample', samplePreviewUrl, samplePreviewStats, samplePreviewLoading)
}

// Load background panel / 加载背景面板
function loadBgPanel(): void {
  if (bgPath.value) {
    loadPanelPreview('background', bgPreviewUrl, bgPreviewStats, bgPreviewLoading)
  }
}

// Load result panel / 加载结果面板
function loadResultPanel(): void {
  loadPanelPreview('result', resultPreviewUrl, resultPreviewStats, resultPreviewLoading)
}

// Generate thumbnails for sample files / 为样品文件生成缩略图
async function generateThumbnails(): Promise<void> {
  const paths = currentSamplePaths.value
  if (paths.length <= 1) {
    thumbnailItems.value = []
    return
  }

  thumbnailsLoading.value = true
  const items: ThumbnailItem[] = []

  for (let i = 0; i < paths.length; i++) {
    const path = paths[i]
    const label = extractFileName(path)
    try {
      const result = await new Promise<any>((resolve, reject) => {
        transport.submitTask('bg_subtract', {
          action: 'preview_sample',
          sample_path: path,
          bg_path: bgPath.value,
          ...getRenderSettingsParams(),
        }).then((response) => {
          let b64Data = ''
          const unsubBinary = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
            if (payload.data) {
              const bytes = new Uint8Array(payload.data)
              let binary = ''
              for (let j = 0; j < bytes.byteLength; j++) {
                binary += String.fromCharCode(bytes[j])
              }
              b64Data = btoa(binary)
            }
          })
          const unsubResult = transport.onTaskResult(response.taskId, () => {
            unsubBinary()
            unsubResult()
            unsubError()
            resolve({ b64: b64Data })
          })
          const unsubError = transport.onTaskError(response.taskId, (p) => {
            unsubBinary()
            unsubResult()
            unsubError()
            reject(new Error(p.error))
          })
        }).catch(reject)
      })
      items.push({ index: i, b64: result.b64 || '', label })
    } catch {
      items.push({ index: i, b64: '', label })
    }
  }

  thumbnailItems.value = items
  thumbnailsLoading.value = false
}

// Handle thumbnail click / 缩略图点击处理
function onThumbnailSelect(index: number): void {
  currentSampleIndex.value = index
  // Watcher on currentSampleIndex handles panel reloading
}

// === Subtraction execution / 执行减除 ===

async function handleSubtract(): Promise<void> {
  if (state.value === 'running') return

  // Programmatic callers can bypass the disabled button — refuse with the
  // same explicit reason instead of silently running with a fallback T.
  // 程序化调用可能绕过禁用状态——同样给出明确原因，绝不静默按回退透射率执行。
  if (missingPrerequisites.value.length > 0) {
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: t('bgSubtract.executeBlocked', {
        items: missingPrerequisites.value.join(' / '),
      }),
      tone: 'error',
    })
    return
  }

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  batchResult.value = null

  const params: Record<string, unknown> = mode.value === 'single'
    ? {
        // All single-mode runs (1 file or many) go through the batch action:
        // it is the only path that saves "_subtracted" files to disk. The
        // legacy 'subtract' action computed a preview and never exported —
        // fixed after the 2026-10-23 user report "subtracted but not
        // exported". / 单文件模式（无论选几张）统一走 batch 动作：只有
        // 它会把 "_subtracted" 结果落盘。旧 'subtract' 动作只算预览从不
        // 导出——2026-10-23 用户报告"发生了扣除但不导出"后修复。
        action: 'batch',
        // IMPORTANT: spread into a plain array — passing the reactive Proxy
        // directly makes Electron's structured-clone IPC throw
        // "An object could not be cloned." Matches Integrate1dView convention.
        // 重要：展开为普通数组——直接传响应式 Proxy 会导致 Electron 结构化克隆
        // IPC 抛出 "An object could not be cloned."，与 Integrate1dView 保持一致。
        data_files: [...samplePaths.value],
        bg_path: bgPath.value,
        output_dir: outputDir.value,
        output_format: outputFormat.value,
        ionchamber_folder: transmissionSource.value === 'ionchamber'
          ? ionchamberFolder.value ?? undefined
          : undefined,
        bg_ionchamber_path: transmissionSource.value === 'ionchamber'
          ? bgIonchamberPath.value || undefined
          : undefined,
        ionchamber_channel: transmissionSource.value === 'ionchamber'
          ? ionchamberChannel.value
          : undefined,
        ionchamber_method: transmissionSource.value === 'ionchamber'
          ? ionchamberMethod.value
          : undefined,
        ionchamber_mode: transmissionSource.value === 'ionchamber'
          ? ionchamberMode.value
          : undefined,
        ionchamber_sample_before: transmissionSource.value === 'ionchamber'
          ? ionSampleBefore.value
          : undefined,
        ionchamber_sample_after: transmissionSource.value === 'ionchamber'
          ? ionSampleAfter.value
          : undefined,
        ionchamber_bg_before: transmissionSource.value === 'ionchamber'
          ? ionBgBefore.value
          : undefined,
        ionchamber_bg_after: transmissionSource.value === 'ionchamber'
          ? ionBgAfter.value
          : undefined,
      }
    : {
        action: 'batch',
        // Web mode has no folder picker: send the explicitly selected files
        // (the backend then defaults the output dir to their own folder).
        // web 模式没有目录选择器：发送显式选中的文件列表（后端默认写到
        // 这些文件所在目录）。
        ...(transport.isDesktop()
          ? { folder_path: sampleFolder.value }
          : { data_files: [...batchFolderFiles.value] }),
        bg_path: bgPath.value,
        ionchamber_folder: transmissionSource.value === 'ionchamber'
          ? ionchamberFolder.value ?? undefined
          : undefined,
        bg_ionchamber_path: transmissionSource.value === 'ionchamber'
          ? bgIonchamberPath.value || undefined
          : undefined,
        ionchamber_channel: transmissionSource.value === 'ionchamber'
          ? ionchamberChannel.value
          : undefined,
        ionchamber_method: transmissionSource.value === 'ionchamber'
          ? ionchamberMethod.value
          : undefined,
        ionchamber_mode: transmissionSource.value === 'ionchamber'
          ? ionchamberMode.value
          : undefined,
        ionchamber_sample_before: transmissionSource.value === 'ionchamber'
          ? ionSampleBefore.value
          : undefined,
        ionchamber_sample_after: transmissionSource.value === 'ionchamber'
          ? ionSampleAfter.value
          : undefined,
        ionchamber_bg_before: transmissionSource.value === 'ionchamber'
          ? ionBgBefore.value
          : undefined,
        ionchamber_bg_after: transmissionSource.value === 'ionchamber'
          ? ionBgAfter.value
          : undefined,
        output_dir: transport.isDesktop() ? outputDir.value : undefined,
        output_format: outputFormat.value,
      }

  // Set transmission params / 设置透射率参数
  // NOTE: The Python batch handler only reads the scalar `transmission` (plus
  // per-file values it computes itself from an ionchamber folder). The legacy
  // code only set transmission in single mode, silently forcing T=1.0 in batch
  // mode. Apply it in both modes now so the user's choice is respected.
  // 注意：Python 批量端只读取标量 `transmission`（以及它自己根据电离室文件夹
  // 计算出的逐文件值）。旧代码仅在 single 模式下设置透射率，导致 batch 模式
  // 下被静默忽略（T=1.0）。现在两种模式都设置，以尊重用户选择。
  // 'file' (imported transmission file) and 'log' (acquisition-log Ct0) are
  // equivalent to 'per-file' — the match/apply step has already filled
  // perFileTransmissions.
  // 'file'（导入的透过率文件）与 'log'（采集日志 Ct0）都和“分别设置”等价
  // ——匹配/应用步骤已填好逐文件映射。
  if (
    transmissionSource.value === 'per-file'
    || transmissionSource.value === 'file'
    || transmissionSource.value === 'log'
  ) {
    if (mode.value === 'single' && samplePaths.value.length === 1) {
      params.transmission = (perFileTransmissions.value[samplePaths.value[0]] ?? manualTransmission.value) / 100
    } else if (mode.value === 'single' && samplePaths.value.length > 1) {
      // Multi-file single mode: keep per-file map for forward compat, and also
      // set a scalar fallback (first file's value) since the backend reads scalar.
      // 多文件单选模式：保留逐文件映射以向前兼容，并设置标量回退（首文件值），
      // 因为后端只读取标量。
      params.transmissions = getPerFileTransmissions()
      const firstPath = samplePaths.value[0]
      params.transmission = (perFileTransmissions.value[firstPath] ?? manualTransmission.value) / 100
    } else {
      // Batch (folder) mode: the backend consumes the per-file `transmissions`
      // map (exact path first, basename fallback); keep the first file's value
      // as the scalar fallback. / 批量（文件夹）模式：后端逐文件消费
      // `transmissions` 映射（精确路径优先，文件名回退）；首文件值作标量回退。
      params.transmissions = getPerFileTransmissions()
      const firstPath = currentSamplePaths.value[0]
      params.transmission = firstPath
        ? (perFileTransmissions.value[firstPath] ?? manualTransmission.value) / 100
        : manualTransmission.value / 100
    }
  } else if (transmissionSource.value === 'manual') {
    params.transmission = manualTransmission.value / 100
  } else {
    // ionchamber: send the matched per-file values so they take effect for
    // every file even if the backend cannot rescan the folder; the scalar is
    // only a fallback. The backend still recomputes from the folder when it
    // can and rejects the run when transmission is missing.
    // 电离室：把匹配到的逐文件值随请求发送，即使后端无法重新扫描文件夹也能
    // 生效；标量仅作回退。后端能重算时仍会重算，缺值时明确报错。
    params.transmissions = getMatchedTransmissions()
    params.transmission = getMatchedTransmission()
  }

  try {
    const response = await transport.submitTask('bg_subtract', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      // Every run goes through the batch action now, so the result is always
      // a BatchResult. 现在所有执行都走 batch 动作，结果恒为 BatchResult。
      const data = payload.data as BatchResult
      batchResult.value = data
      // Refresh the result panel after every run — preview_result now
      // renders the actual subtracted image instead of the raw sample.
      // 每次执行后刷新结果面板——preview_result 现在渲染真实扣除结果，
      // 而非原始样品图。
      loadResultPanel()
      generateThumbnails()
      const summaryText = mode.value === 'single' && samplePaths.value.length === 1
        ? t('bgSubtract.subtractComplete')
        : t('bgSubtract.batchComplete', {
            success: data.success_count,
            failed: data.failed_count,
          })
      toast.push({
        title: t('bgSubtract.successTitle'),
        // Always tell the user WHERE files went — a bare "done" toast with
        // no files in the expected place reads as a silent failure
        // (2026-10-23 report). / 始终告知导出去向——只说"完成"而目录里
        // 没文件，用户会当成静默失败。
        message: !transport.isDesktop() && (data.output_files?.length ?? 0) > 0
          ? t('bgSubtract.exportedDownload', { count: data.output_files!.length })
          : `${summaryText} → ${data.output_dir ?? ''}`,
        tone: 'success',
      })
      // Web mode: fetch the exported files back through /api/download —
      // the browser cannot browse the server-side output location.
      // web 模式：经 /api/download 取回导出文件——浏览器无法浏览服务器
      // 侧的输出位置（桌面模式用户直接去输出目录拿）。
      if (!transport.isDesktop() && data.output_files?.length) {
        for (const serverPath of data.output_files) {
          transport.downloadFile(serverPath, extractFileName(serverPath)).catch(() => {
            toast.push({
              title: t('bgSubtract.errorTitle'),
              message: `${extractFileName(serverPath)}: download failed`,
              tone: 'error',
            })
          })
        }
      }
      taskId.value = null
      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

// === Cancel / 取消 ===

async function handleCancel(): Promise<void> {
  const tid = taskId.value
  taskId.value = null
  state.value = 'idle'
  progress.value = 0
  cleanupListeners()
  if (tid) {
    try { await transport.cancelTask(tid) } catch { /* already finished */ }
  }
}

// === Cleanup / 清理 ===

function cleanupListeners(): void {
  cleanupProgress?.()
  cleanupProgress = null
  cleanupResult?.()
  cleanupResult = null
  cleanupError?.()
  cleanupError = null
  cleanupPreviewListeners()
}

onUnmounted(() => {
  if (samplePreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(samplePreviewUrl.value)
  if (bgPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(bgPreviewUrl.value)
  if (resultPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(resultPreviewUrl.value)
  cleanupListeners()
  if (contrastDebounceTimer) clearTimeout(contrastDebounceTimer)
})
</script>

<style scoped>
.bg-subtract-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.bgs-header {
  padding-bottom: 8px;
}

.bgs-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.bgs-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.bgs-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.bgs-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Card / 卡片 */
.bgs-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-surface);
}

.bgs-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Main area / 主区域 */
.bgs-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Radio row / 单选行 */
.bgs-radio-row {
  display: flex;
  align-items: center;
  gap: 16px;
  /* The transmission-source row grew to FOUR options (manual / per-file /
   * ionchamber / file) and the 4th radio clipped against the card edge at
   * 1440px (visual review 2026-10-25) — wrap instead of clip.
   * 透射率来源一行增至四项（手动/逐文件/电离室/文件）后，1440px 下第 4 个
   * 单选被卡片边缘裁掉（视觉审查 2026-10-25）——换行而非裁切。 */
  flex-wrap: wrap;
  row-gap: 6px;
}

.bgs-radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
}

.bgs-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Field / 字段 */
.bgs-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bgs-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.bgs-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.bgs-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.bgs-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.bgs-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

/* Compact select for the log pairing table cells. / 日志配对表单元格内的紧凑下拉。 */
.bgs-select--compact {
  padding: 2px 4px;
  font-size: 0.6875rem;
  max-width: 200px;
}

/* Ionchamber dual formula line / 前后通道公式行 */
.bgs-ion-formula {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-md);
  padding: 6px 10px;
}

/* <100% sanity hint under the formula. / 公式下方的 <100% 提示。 */
.bgs-ion-hint {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.bgs-slider {
  width: 100%;
  accent-color: var(--primary);
}

/* Toggle / 切换 */
.bgs-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.bgs-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* File actions / 文件操作 */
.bgs-file-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: var(--radius-md);
  padding: 2px;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

/* Drop-target highlight & hint / 拖放高亮与提示 */
.bgs-file-actions--drop {
  background: var(--primary-bg);
  box-shadow: 0 0 0 2px var(--primary-light);
}

.bgs-drop-hint {
  font-size: 0.75rem;
  /* --text-muted measured ~2.56:1 on white (visual review 2026-10-25);
   * slate-500 clears 4.5:1. Same fix as TransmissionView.
   * 继承的 --text-muted 白底实测约 2.56:1（视觉审查 2026-10-25）；
   * slate-500 达标。与透过率页同步修。 */
  color: #64748b;
}

.bgs-import-mode {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bgs-import-mode-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.bgs-file-summary {
  font-size: 0.8125rem;
  color: var(--text-primary);
  font-weight: 500;
}

.bgs-file-summary--muted {
  color: var(--text-muted);
  font-style: italic;
}

.bgs-folder-info {
  font-size: 0.8125rem;
  color: var(--accent-secondary, var(--primary));
  font-weight: 500;
}

/* File list / 文件列表 */
.bgs-file-list-wrap {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.bgs-file-list-header {
  padding: 6px 10px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.bgs-file-list-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bgs-file-list {
  max-height: 180px;
  overflow-y: auto;
}

.bgs-file-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px;
  cursor: pointer;
  transition: background var(--transition-fast);
  border-bottom: 1px solid var(--border);
}

.bgs-file-list-item:last-child {
  border-bottom: none;
}

.bgs-file-list-item:hover {
  background: var(--bg-hover);
}

.bgs-file-list-item--active {
  background: rgba(59, 130, 246, 0.1);
}

.bgs-file-list-name {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.bgs-file-list-remove {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 2px 4px;
  line-height: 1;
  flex-shrink: 0;
}

.bgs-file-list-remove:hover {
  color: var(--error);
}

/* Buttons / 按钮 */
.bgs-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.bgs-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.bgs-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.bgs-btn-primary {
  padding: 12px 32px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
}

.bgs-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

/* Match table / 匹配表 */
.bgs-match-table-wrap {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.bgs-match-warning {
  padding: 8px 12px;
  background: rgba(245, 158, 11, 0.1);
  border-bottom: 1px solid rgba(245, 158, 11, 0.3);
  /* amber-700: amber-600 measured ~2.9:1 on the pale strip (visual review
   * 2026-10-25). / amber-700：amber-600 在浅琥珀条上实测约 2.9:1。 */
  color: #b45309;
  font-size: 0.75rem;
  font-weight: 500;
}

.bgs-match-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.bgs-match-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface);
  font-weight: 600;
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  z-index: 1;
  color: var(--text-secondary);
  white-space: nowrap;
}

.bgs-match-table td {
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

/* Numeric column: header and cells share ONE alignment (visual review
 * 2026-10-25 caught header-left / value-right mismatch).
 * 数值列：表头与单元格统一右对齐（视觉审查 2026-10-25 发现表头左对齐、
 * 数值右对齐不一致）。 */
.bgs-match-table .bgs-col-num {
  text-align: right;
}

.bgs-error-cell {
  color: var(--error);
  font-weight: 500;
}

/* Attention rows: weak name match (<0.8) or transmission over 100%.
 * amber-700: 4.5:1 on white, distinct from the error red.
 * 需要注意的行：弱命名匹配（<0.8）或透射率超 100%。amber-700 白底对比
 * 4.5:1，与错误红区分。 */
.bgs-warn-cell {
  color: #b45309;
  font-weight: 500;
}

/* Dual-mode before/after channel grid: 2×2 on narrow cards.
 * 前后通道模式的 2×2 通道选择网格。 */
.bgs-dual-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  width: 100%;
}

.bgs-match-table tr:hover td {
  background: var(--bg-hover);
}

/* Preview section / 预览区域 */
.bgs-preview-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* Notice banner / 提示横幅 */
.bgs-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-top: 12px;
  border-radius: var(--radius-md);
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: var(--primary, #3b82f6);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.bgs-notice-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

/* Two-row layout: sample + background side by side / 样品与背景并列 */
.bgs-two-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* Thumbnail strip below result / 缩略图在结果下方 */
.bgs-thumb-strip {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: auto;
  background: var(--bg-surface);
  max-height: 320px;
}

.bgs-result-panel-single {
  min-height: 280px;
}

.bgs-panel-file-hint {
  font-weight: 400;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: 8px;
}

/* Individual panel / 单个面板 */
.bgs-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}

.bgs-panel-header {
  padding: 8px 12px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.bgs-panel-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bgs-panel-image {
  flex: 1;
  min-height: 0;
}

.bgs-panel-stats {
  display: flex;
  gap: 12px;
  padding: 6px 10px;
  border-top: 1px solid var(--border);
  font-size: 0.6875rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: var(--bg-surface);
  flex-wrap: wrap;
}

/* Preview loading & empty / 预览加载与空状态 */
.bgs-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.bgs-preview-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

/* Error / 错误 */
.bgs-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.bgs-error p {
  margin: 0;
}

/* Empty state / 空状态 */
.bgs-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.bgs-empty p {
  margin: 0;
}

/* Display bar below image / 图像下方显示栏 */
.bgs-display-bar {
  padding: 10px 14px;
}

.bgs-display-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.bgs-input-sm {
  width: 100px;
  padding: 4px 8px;
  font-size: 0.8125rem;
}

.bgs-input-tiny {
  width: 60px;
  padding: 2px 6px;
  font-size: 0.6875rem;
  text-align: right;
  flex-shrink: 0;
}

.bgs-radio-label--disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bgs-radio-label--disabled input[type="radio"] {
  cursor: not-allowed;
}

/* Responsive / 响应式 */
@media (max-width: 1200px) {
  .bgs-two-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .bgs-layout {
    grid-template-columns: 1fr;
  }

  .bgs-two-row {
    grid-template-columns: 1fr;
  }
}
</style>
