<template>
  <fieldset v-if="datasets.length" :data-testid="testIds.h5Selector" class="h5-selector">
    <legend class="h5-legend">{{ t('business.h5.title') }}</legend>

    <div class="h5-field">
      <label class="h5-label">{{ t('business.h5.dataset') }}</label>
      <select
        class="h5-select"
        :value="modelValue.dataset"
        :data-testid="testIds.h5DatasetSelect"
        @change="onDatasetChange"
      >
        <option v-for="ds in datasets" :key="ds.path" :value="ds.path">
          {{ ds.path }} ({{ ds.ndim }}D)
        </option>
      </select>
    </div>

    <div v-if="channelCount > 1" class="h5-field">
      <label class="h5-label">{{ t('business.h5.channel') }}</label>
      <select
        class="h5-select"
        :value="modelValue.channel"
        :data-testid="testIds.h5ChannelSelect"
        @change="onChannelChange"
      >
        <option v-for="i in channelCount" :key="i - 1" :value="i - 1">Ch{{ i - 1 }}</option>
      </select>
    </div>

    <div v-if="totalFrames > 1" class="h5-field">
      <label class="h5-label">{{ t('business.h5.frame') }}</label>
      <select
        class="h5-select"
        :value="modelValue.frame"
        :data-testid="testIds.h5FrameSelect"
        @change="onFrameChange"
      >
        <option v-for="i in totalFrames" :key="i - 1" :value="i - 1">{{ i - 1 }}</option>
      </select>
    </div>

    <p class="h5-hint">{{ t('business.h5.hint') }}</p>
  </fieldset>
</template>

<script setup lang="ts">
/**
 * H5Selector.vue — HDF5 数据集 / 通道 / 帧选择器（积分页共享组件）
 * Shared HDF5 dataset / channel / frame selector for the integration pages.
 *
 * 数据集下拉只在 .h5 有多个可选数据集时出现；通道选择只在 4D 多通道时出现；
 * 帧选择只在多帧（N>1）时出现。默认第一帧、通道 0。
 * Dataset selector shows only when the .h5 has image datasets; channel selector
 * shows only for multi-channel 4-D data; frame selector only for multi-frame
 * data. Defaults: first frame, channel 0.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'

export interface H5DatasetInfo {
  path: string
  ndim: number
  shape: number[]
  nFrames?: number
  nChannels?: number
}

export interface H5Selection {
  dataset: string
  channel: number
  frame: number
}

const props = defineProps<{
  /** Current selection (v-model) / 当前选择（v-model） */
  modelValue: H5Selection
  /** Image datasets discovered in the file / 文件中探测到的图像数据集 */
  datasets: H5DatasetInfo[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: H5Selection]
  /** Fired after any selection change so the parent can refresh preview */
  'change': []
}>()

const { t } = useI18n()

const selectedInfo = computed<H5DatasetInfo | undefined>(() =>
  props.datasets.find((d) => d.path === props.modelValue.dataset) ?? props.datasets[0],
)
const totalFrames = computed(() => Math.max(1, selectedInfo.value?.nFrames ?? 1))
const channelCount = computed(() => Math.max(0, selectedInfo.value?.nChannels ?? 0))

function clampIndex(value: number, count: number): number {
  // count is the number of slots (frames or channels); valid range [0, count-1]
  return count <= 1 ? 0 : Math.max(0, Math.min(value, count - 1))
}

function onDatasetChange(event: Event): void {
  const path = (event.target as HTMLSelectElement).value
  const info = props.datasets.find((d) => d.path === path)
  const nFrames = Math.max(1, info?.nFrames ?? 1)
  const nChannels = Math.max(0, info?.nChannels ?? 0)
  emit('update:modelValue', {
    dataset: path,
    frame: clampIndex(props.modelValue.frame, nFrames),
    channel: nChannels > 1 ? clampIndex(props.modelValue.channel, nChannels) : 0,
  })
  emit('change')
}

function onChannelChange(event: Event): void {
  const v = parseInt((event.target as HTMLSelectElement).value, 10)
  emit('update:modelValue', { ...props.modelValue, channel: Number.isNaN(v) ? 0 : v })
  emit('change')
}

function onFrameChange(event: Event): void {
  const v = parseInt((event.target as HTMLSelectElement).value, 10)
  emit('update:modelValue', { ...props.modelValue, frame: Number.isNaN(v) ? 0 : v })
  emit('change')
}
</script>

<style scoped>
.h5-selector {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.h5-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.h5-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.h5-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.h5-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.h5-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.h5-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
}
</style>
