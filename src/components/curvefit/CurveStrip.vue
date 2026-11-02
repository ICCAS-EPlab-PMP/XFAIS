<script setup lang="ts">
/**
 * 底部曲线条（2026-10-23 用户要求：多条数据希望有如其他模块缩略图一样的
 * 功能，但缩略图改为信息展示、不要太复杂）。每条曲线一个信息片：名称 ·
 * 点数 · 状态（待拟合 / 拟合中 / R² / 失败）；点击 = 切换为参考曲线（已拟
 * 合的连模型与曲线一起恢复，即「点击某一条来观看效果」）；✕ = 从队列移除。
 * 无图像渲染，纯文字信息。
 */
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { useBatch } from '@/lib/curvefit/stores/batch'
import { fmtSig } from '@/lib/curvefit/utils/format'

const sp = useSpectrum()
const batch = useBatch()

type Status = 'queued' | 'running' | 'done' | 'failed'

interface StripItem {
  id: string
  name: string
  n: number
  status: Status
  r2?: number
  error?: string
}

const items = computed<StripItem[]>(() =>
  batch.entries.value.map((e) => {
    const r = batch.results.value?.find((x) => x.id === e.id)
    return {
      id: e.id,
      name: e.name,
      n: e.n,
      status: (r?.status ?? 'queued') as Status,
      r2: r?.r2,
      error: r?.error,
    }
  }),
)

function statusTag(it: StripItem): string {
  if (it.status === 'running') return '拟合中'
  if (it.status === 'done') return it.r2 !== undefined ? `R² ${fmtSig(it.r2, 5)}` : '完成'
  if (it.status === 'failed') return '失败'
  return '待拟合'
}
</script>

<template>
  <div v-if="items.length > 0" class="curve-strip">
    <span class="cs-title">
      <AppIcon name="data" :size="13" />
      曲线条
      <span class="cs-count">{{ items.length }}</span>
    </span>
    <div class="cs-list">
      <!-- Working (reference) curve: display-only chip pinned first. /
           工作（参考）曲线：置顶的只读信息片。 -->
      <span v-if="sp.ready.value" class="cs-chip cs-chip--work" :title="sp.meta.title">
        <span class="cs-dot" />
        <span class="cs-name">{{ sp.meta.title }}</span>
        <span class="cs-meta">参考曲线</span>
      </span>
      <button
        v-for="it in items"
        :key="it.id"
        type="button"
        class="cs-chip"
        :class="`cs-chip--${it.status}`"
        :title="it.error ?? `${it.name} · ${it.n} 点 · 点击切换为参考曲线`"
        :disabled="batch.running.value"
        @click="batch.loadCurveIntoSession(it.id)"
      >
        <span class="cs-name">{{ it.name }}</span>
        <span class="cs-meta">{{ it.n }} 点</span>
        <span class="cs-status">{{ statusTag(it) }}</span>
        <span
          class="cs-del"
          role="button"
          tabindex="-1"
          title="从队列移除"
          @click.stop="batch.removeEntry(it.id)"
          @keydown.stop
        >✕</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.curve-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 10px;
  border-top: 1px solid var(--border);
  background: var(--bg-1);
  flex: none;
}
.cs-title {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-small);
  font-weight: 600;
  color: var(--text-1);
}
.cs-count {
  padding: 0 6px;
  font-size: 9.5px;
  line-height: 15px;
  font-weight: 600;
  color: var(--text-2);
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.cs-list {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding: 2px 0;
}
.cs-chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 250px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-1);
  font-size: var(--fs-small);
  cursor: pointer;
  text-align: left;
}
.cs-chip--work {
  cursor: default;
  border-color: var(--accent-line);
  background: var(--accent-soft);
}
.cs-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  flex: none;
}
.cs-chip:not(.cs-chip--work):hover:not(:disabled) {
  border-color: var(--accent);
}
.cs-chip:disabled {
  cursor: default;
  opacity: 0.65;
}
.cs-name {
  min-width: 0;
  max-width: 130px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.cs-meta {
  flex: none;
  color: var(--text-2);
  font-size: 10px;
}
.cs-status {
  flex: none;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-2);
}
.cs-chip--done .cs-status {
  color: var(--success);
}
.cs-chip--running .cs-status {
  color: var(--accent);
}
.cs-chip--failed {
  border-color: color-mix(in srgb, #d92d20 45%, var(--border));
}
.cs-chip--failed .cs-status {
  color: #d92d20;
}
.cs-del {
  flex: none;
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--bg-1);
  color: var(--text-2);
  font-size: 9px;
  line-height: 1;
}
.cs-del:hover {
  color: #d92d20;
  border-color: #d92d20;
}
</style>
