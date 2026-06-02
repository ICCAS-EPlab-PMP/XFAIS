<template>
  <div :data-testid="testIds.taskProgressBar" class="task-progress-bar">
    <div class="tpb-header">
      <span class="tpb-message">{{ message ?? t('business.taskProgress.processing') }}</span>
      <span class="tpb-percent" :data-testid="testIds.taskProgressPercent">
        {{ percentText }}
      </span>
    </div>

    <div class="tpb-track" :data-testid="testIds.taskProgressTrack">
      <div
        class="tpb-fill"
        :style="{ width: percentText }"
      />
    </div>

    <div class="tpb-footer">
      <button
        v-if="taskId"
        type="button"
        class="tpb-cancel"
        :data-testid="testIds.taskProgressCancel"
        @click="handleCancel"
      >
        {{ t('business.taskProgress.cancel') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * TaskProgressBar.vue — 任务进度条组件，支持进度显示和取消操作
 * Task progress bar with percentage display and cancel action
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'

const props = withDefaults(defineProps<{
  /** Task ID for cancellation / 任务 ID（用于取消） */
  taskId?: string | null
  /** Progress value 0–1 / 进度值 0–1 */
  progress?: number
  /** Status message / 状态消息 */
  message?: string | null
}>(), {
  taskId: null,
  progress: 0,
  message: null,
})

const emit = defineEmits<{
  cancel: []
}>()

const { t } = useI18n()
const transport = useTransport()

const percentText = computed(() => {
  const clamped = Math.max(0, Math.min(1, props.progress))
  return `${Math.round(clamped * 100)}%`
})

async function handleCancel(): Promise<void> {
  if (props.taskId) {
    try {
      await transport.cancelTask(props.taskId)
    } catch {
      // Task may already be completed / 任务可能已完成
    }
  }
  emit('cancel')
}
</script>

<style scoped>
.task-progress-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tpb-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.tpb-message {
  font-size: 0.875rem;
  color: var(--text-primary);
  font-weight: 500;
}

.tpb-percent {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.tpb-track {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: var(--bg-surface-alt);
  overflow: hidden;
}

.tpb-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--primary-light);
  transition: width 200ms ease-out;
}

.tpb-footer {
  display: flex;
  justify-content: flex-end;
}

.tpb-cancel {
  padding: 5px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}

.tpb-cancel:hover {
  color: var(--error);
  border-color: var(--error);
}
</style>
