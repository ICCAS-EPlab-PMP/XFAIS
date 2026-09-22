<template>
  <aside v-if="uploadStore.items.length > 0" class="upload-viewport" aria-live="polite">
    <article v-for="item in uploadStore.items" :key="item.id" class="upload-card" :class="`status-${item.status}`">
      <div class="upload-head">
        <span class="upload-name" :title="item.name">{{ item.name }}</span>
        <span class="upload-pct">{{ pctOf(item) }}%</span>
      </div>
      <div class="upload-bar">
        <div
          class="upload-bar-fill"
          :class="{ 'upload-bar-fill--done': item.status === 'done' }"
          :style="{ width: `${Math.min(100, Math.max(2, pctOf(item)))}%` }"
        ></div>
      </div>
      <div class="upload-meta">
        <span v-if="item.status === 'uploading'">
          {{ formatBytes(item.loaded) }} / {{ formatBytes(item.total) }}
          <template v-if="item.speedBps > 0">· {{ formatBytes(item.speedBps) }}/s</template>
          <template v-if="etaSeconds(item) !== null">· ~{{ formatEta(etaSeconds(item)!) }}</template>
        </span>
        <span v-else-if="item.status === 'done'" class="upload-done">
          {{ t('upload.complete') }} · {{ formatBytes(item.total) }}
        </span>
        <span v-else class="upload-error" :title="item.error">{{ item.error }}</span>
      </div>
    </article>
  </aside>
</template>

<script setup lang="ts">
/**
 * UploadProgressHost.vue — 右下角全局上传进度面板（Web 模式）。
 * Bottom-right global upload progress panel (web mode).
 * The store is fed by transport.web.ts automatically; desktop mode shows nothing.
 */
import { useI18n } from 'vue-i18n'
import { formatBytes, uploadStore } from '@/lib/upload'

const { t } = useI18n()

function pctOf(item: { loaded: number; total: number; status: string }): number {
  if (item.status === 'done') return 100
  if (item.total <= 0) return 0
  return Math.floor((item.loaded / item.total) * 100)
}

function etaSeconds(item: { loaded: number; total: number; speedBps: number }): number | null {
  if (item.speedBps <= 0 || item.loaded >= item.total) return null
  const seconds = Math.round((item.total - item.loaded) / item.speedBps)
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null
}

function formatEta(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (minutes < 60) return rest > 0 ? `${minutes}m${rest}s` : `${minutes}m`
  const hours = Math.floor(minutes / 60)
  return `${hours}h${minutes % 60}m`
}
</script>

<style scoped>
.upload-viewport {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: var(--z-tooltip);
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.upload-card {
  width: min(340px, calc(100vw - 48px));
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--shadow-lg);
}

.upload-card.status-error {
  border-color: rgba(239, 68, 68, 0.4);
}

.upload-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}

.upload-name {
  flex: 1;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-pct {
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
}

.upload-bar {
  height: 6px;
  border-radius: 3px;
  background: rgba(15, 23, 42, 0.1);
  overflow: hidden;
}

.upload-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--primary);
  transition: width 0.2s ease;
}

.upload-bar-fill--done {
  background: #10b981;
}

.upload-card.status-error .upload-bar-fill {
  background: var(--error);
}

.upload-meta {
  margin-top: 6px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.upload-done {
  color: #059669;
}

.upload-error {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--error);
}
</style>
