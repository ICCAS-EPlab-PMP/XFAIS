<template>
  <div :data-testid="testIds.resultSummary" class="result-summary">
    <h3 class="rs-title">{{ t('business.resultSummary.title') }}</h3>

    <div class="rs-stats">
      <div class="rs-stat">
        <span class="rs-stat-value" :data-testid="testIds.resultTotal">{{ summary.total }}</span>
        <span class="rs-stat-label">{{ t('business.resultSummary.total') }}</span>
      </div>
      <div class="rs-stat rs-stat--success">
        <span class="rs-stat-value" :data-testid="testIds.resultSuccess">{{ summary.success }}</span>
        <span class="rs-stat-label">{{ t('business.resultSummary.success') }}</span>
      </div>
      <div class="rs-stat rs-stat--error">
        <span class="rs-stat-value" :data-testid="testIds.resultFailed">{{ summary.failed }}</span>
        <span class="rs-stat-label">{{ t('business.resultSummary.failed') }}</span>
      </div>
      <div class="rs-stat rs-stat--time">
        <span class="rs-stat-value" :data-testid="testIds.resultElapsed">{{ formatElapsed(summary.elapsed) }}</span>
        <span class="rs-stat-label">{{ t('business.resultSummary.elapsed') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ResultSummary.vue — 结果摘要卡片，显示处理统计信息
 * Result summary card showing processing statistics
 */
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'

/** Processing summary shape / 处理摘要结构 */
export interface ResultSummaryData {
  /** Total files processed / 处理文件总数 */
  total: number
  /** Successfully processed / 成功数 */
  success: number
  /** Failed / 失败数 */
  failed: number
  /** Elapsed time in seconds / 耗时（秒） */
  elapsed: number
}

defineProps<{
  /** Summary data / 摘要数据 */
  summary: ResultSummaryData
}>()

const { t } = useI18n()

function formatElapsed(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}
</script>

<style scoped>
.result-summary {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  background: var(--bg-surface);
}

.rs-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 14px 0;
}

.rs-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.rs-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
}

.rs-stat-value {
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.rs-stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.rs-stat--success .rs-stat-value {
  color: var(--secondary);
}

.rs-stat--error .rs-stat-value {
  color: var(--error);
}

.rs-stat--time .rs-stat-value {
  font-size: 1rem;
}
</style>
