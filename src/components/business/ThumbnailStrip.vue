<template>
  <div class="thumbnail-strip">
    <!-- Toolbar / 工具栏 -->
    <div class="ts-toolbar">
      <div class="ts-toolbar-left">
        <label class="ts-control">
          <span class="ts-control-label">{{ t('viewer.thumbnailsPerPage') }}</span>
          <select
            :value="pageSize"
            class="ts-select-sm"
            @change="onPageSizeChange"
          >
            <option v-for="s in PAGE_SIZE_OPTIONS" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label class="ts-control">
          <span class="ts-control-label">{{ t('viewer.thumbnailsPerRow') }}</span>
          <input
            type="range"
            class="ts-cols-slider"
            min="3"
            max="12"
            :value="columnsPerRow"
            @input="onColsChange"
          />
          <span class="ts-cols-value">{{ columnsPerRow }}</span>
        </label>
      </div>
      <div class="ts-toolbar-right">
        <label
          class="ts-sync"
          :title="t('viewer.syncThumbnailsHint')"
        >
          <input
            type="checkbox"
            :checked="syncWithMain"
            @change="onSyncToggle"
          />
          <span>{{ t('viewer.syncThumbnails') }}</span>
        </label>
      </div>
    </div>

    <!-- Thumbnail grid / 缩略图网格 -->
    <div
      v-if="items.length"
      class="ts-grid"
      :style="{ gridTemplateColumns: `repeat(${columnsPerRow}, minmax(0, 1fr))` }"
    >
      <div
        v-for="item in items"
        :key="item.index"
        class="ts-thumb"
        :class="{ 'ts-thumb--selected': item.index === selectedIndex }"
        :data-testid="`thumb-${item.index}`"
        @click="emit('select', item.index)"
      >
        <img
          :src="'data:image/png;base64,' + item.b64"
          :alt="`Frame ${item.index + 1}`"
          class="ts-img"
          loading="lazy"
          draggable="false"
        />
        <span class="ts-label">{{ truncatedLabel(item) }}</span>
      </div>
    </div>

    <!-- Loading state / 加载状态 -->
    <div v-if="loading && !items.length" class="ts-loading">
      <span>{{ t('viewer.loadingImage') }}</span>
    </div>

    <!-- Empty state / 空状态 -->
    <div v-if="!items.length && !loading" class="ts-empty">
      <span>{{ t('viewer.noThumbnails') }}</span>
    </div>

    <!-- Pagination controls / 分页控件 -->
    <div v-if="totalPages > 1 || loading" class="ts-pagination">
      <button
        type="button"
        class="ts-page-btn"
        :disabled="currentPage <= 1 || loading"
        @click="emit('prev-page')"
      >
        &#9664; {{ t('viewer.prevPage') }}
      </button>

      <div class="ts-page-center">
        <span class="ts-page-indicator">
          {{ t('viewer.pageOf', { current: currentPage, total: totalPages }) }}
        </span>
        <label class="ts-jump">
          <input
            type="number"
            class="ts-jump-input"
            min="1"
            :max="totalPages"
            :placeholder="t('viewer.jumpToPage')"
            @keydown.enter="onJumpToPage"
          />
        </label>
      </div>

      <button
        type="button"
        class="ts-page-btn"
        :disabled="currentPage >= totalPages || loading"
        @click="emit('next-page')"
      >
        {{ t('viewer.nextPage') }} &#9654;
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ThumbnailStrip.vue — Paginated thumbnail grid for multi-frame X-ray detector images
 * 分页缩略图网格，用于浏览多帧 X 射线探测器图像
 */
import { useI18n } from 'vue-i18n'

// === Types / 类型定义 ===

export interface ThumbnailStats {
  min: number
  max: number
  adjustedMax: number
  std: number
}

export interface ThumbnailItem {
  index: number
  b64: string
  label?: string
  stats?: ThumbnailStats
}

// === Constants / 常量 ===

const PAGE_SIZE_OPTIONS = [10, 20, 30, 50] as const

// === Props & Emits / 属性与事件 ===

const props = withDefaults(defineProps<{
  items: ThumbnailItem[]
  selectedIndex?: number
  columnsPerRow?: number
  maxLabelLength?: number
  currentPage: number
  totalPages: number
  pageSize: number
  loading?: boolean
  syncWithMain?: boolean
}>(), {
  selectedIndex: -1,
  columnsPerRow: 5,
  maxLabelLength: 24,
  loading: false,
  syncWithMain: false,
})

const emit = defineEmits<{
  'select': [index: number]
  'prev-page': []
  'next-page': []
  'jump-to-page': [page: number]
  'page-size-change': [size: number]
  'update:syncWithMain': [value: boolean]
  'update:columnsPerRow': [value: number]
}>()

// === Composables / 组合函数 ===

const { t } = useI18n()

// === Methods / 方法 ===

function truncatedLabel(item: ThumbnailItem): string {
  const raw = item.label ?? `Frame ${item.index + 1}`
  if (raw.length <= props.maxLabelLength) return raw
  return raw.slice(0, props.maxLabelLength) + '\u2026'
}

function onPageSizeChange(event: Event): void {
  const val = Number((event.target as HTMLSelectElement).value)
  emit('page-size-change', val)
}

function onColsChange(event: Event): void {
  const val = Number((event.target as HTMLInputElement).value)
  emit('update:columnsPerRow', val)
}

function onSyncToggle(event: Event): void {
  emit('update:syncWithMain', (event.target as HTMLInputElement).checked)
}

function onJumpToPage(event: Event): void {
  const input = event.target as HTMLInputElement
  const page = Math.max(1, Math.min(props.totalPages, Number(input.value)))
  if (Number.isFinite(page) && page !== props.currentPage) {
    emit('jump-to-page', page)
  }
  input.value = ''
}
</script>

<style scoped>
.thumbnail-strip {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

/* Toolbar / 工具栏 */
.ts-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-bottom: 4px;
  flex-wrap: wrap;
}

.ts-toolbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ts-toolbar-right {
  display: flex;
  align-items: center;
}

.ts-control {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.ts-control-label {
  white-space: nowrap;
}

.ts-select-sm {
  padding: 3px 6px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.ts-cols-slider {
  width: 80px;
  accent-color: var(--primary);
}

.ts-cols-value {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  min-width: 18px;
  text-align: center;
}

.ts-sync {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.ts-sync input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Grid / 网格 */
.ts-grid {
  display: grid;
  gap: 8px;
  padding: 2px;
}

/* Thumbnail card / 缩略图卡片 */
.ts-thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border: 2px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    transform var(--transition-fast);
  user-select: none;
}

.ts-thumb:hover {
  transform: scale(1.03);
  border-color: var(--border-hover);
}

.ts-thumb--selected {
  border-color: var(--primary);
  border-width: 3px;
}

.ts-thumb--selected:hover {
  border-color: var(--primary);
}

/* Image / 图像 */
.ts-img {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 2px;
  image-rendering: pixelated;
}

/* Label / 标签 */
.ts-label {
  font-size: 0.6875rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

/* Loading / 加载中 */
.ts-loading {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
  font-size: 0.8125rem;
}

/* Empty state / 空状态 */
.ts-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 24px;
  font-size: 0.875rem;
}

/* Pagination / 分页 */
.ts-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 0;
  border-top: 1px solid var(--border);
}

.ts-page-btn {
  padding: 4px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.75rem;
  cursor: pointer;
  transition: border-color var(--transition-fast);
  white-space: nowrap;
}

.ts-page-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
}

.ts-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.ts-page-center {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ts-page-indicator {
  font-size: 0.8125rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  white-space: nowrap;
}

.ts-jump-input {
  width: 56px;
  padding: 3px 6px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.75rem;
  font-family: var(--font-mono);
  text-align: center;
}

.ts-jump-input::-webkit-inner-spin-button,
.ts-jump-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.ts-jump-input[type='number'] {
  -moz-appearance: textfield;
}
</style>
