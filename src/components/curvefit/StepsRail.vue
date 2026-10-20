<script setup lang="ts">
/**
 * Vertical workflow rail: 数据 → 基线 → 放峰 → 拟合 → 报告 → 聚合物.
 * Steps before data exists are visually locked.
 */
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { STEPS, stepIndex, useUi, type StepId } from '@/lib/curvefit/stores/ui'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'

const ui = useUi()
const sp = useSpectrum()

const currentIdx = computed(() => stepIndex(ui.step.value))

const stepIcons: Record<StepId, string> = {
  data: 'data',
  baseline: 'baseline',
  peaks: 'peak',
  fit: 'fit',
  report: 'report',
  polymer: 'chart',
}

function locked(id: StepId): boolean {
  if (!sp.ready.value && stepIndex(id) > 0) return true
  return false
}

function go(id: StepId): void {
  if (locked(id)) return
  ui.step.value = id
}
</script>

<template>
  <nav class="rail">
    <button
      v-for="(s, i) in STEPS"
      :key="s.id"
      class="step"
      :class="{
        on: ui.step.value === s.id,
        done: i < currentIdx,
        locked: locked(s.id),
      }"
      :title="s.hint"
      @click="go(s.id)"
    >
      <span class="bar" />
      <AppIcon :name="stepIcons[s.id]" :size="16" />
      <span class="lbl">{{ s.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 108px;
  flex: none;
  padding: 10px 0;
  background: var(--bg-1);
  border-right: 1px solid var(--border);
  transition: background-color var(--speed) ease;
}
.step {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  height: 34px;
  padding: 0 12px 0 14px;
  border: none;
  background: transparent;
  color: var(--text-2);
  font: inherit;
  font-size: var(--fs-body);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--speed-fast) ease, color var(--speed-fast) ease;
}
.step:hover:not(.locked) {
  background: var(--bg-3);
  color: var(--text-1);
}
.step.locked {
  opacity: 0.35;
  cursor: default;
}
.step.on {
  color: var(--text-1);
  background: var(--accent-soft);
}
.step.on .bar {
  opacity: 1;
}
.bar {
  position: absolute;
  left: 0;
  top: 5px;
  bottom: 5px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--accent);
  opacity: 0;
  transition: opacity var(--speed-fast) ease;
}
.step.done {
  color: var(--text-1);
}
.step .lbl {
  font-weight: 500;
}
</style>
