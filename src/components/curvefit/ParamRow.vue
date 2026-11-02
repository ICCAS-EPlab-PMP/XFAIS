<script setup lang="ts">
/**
 * One parameter row: label + numeric editor + lock toggle.
 * Commit-on-change with registry bounds clamping; invalid input highlighted.
 */
import { computed, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { clampBound, fmtSig, parseNum } from '@/lib/curvefit/utils/format'

const props = withDefaults(
  defineProps<{
    label: string
    paramKey: string
    modelValue: number
    locked?: boolean
    min?: number | null
    max?: number | null
    lockable?: boolean
    compact?: boolean
  }>(),
  { locked: false, min: null, max: null, lockable: true, compact: false },
)

const emit = defineEmits<{
  'update:modelValue': [v: number]
  'update:locked': [v: boolean]
}>()

const editing = ref(String(fmtSig(props.modelValue, 8)))
const invalid = ref(false)
const focused = ref(false)

watch(
  () => props.modelValue,
  (v) => {
    if (!focused.value) editing.value = String(fmtSig(v, 8))
    invalid.value = false
  },
)

const display = computed(() => fmtSig(props.modelValue, 6))

function commit(): void {
  focused.value = false
  const v = parseNum(editing.value)
  if (!Number.isFinite(v)) {
    invalid.value = true
    editing.value = String(fmtSig(props.modelValue, 8))
    return
  }
  const clamped = clampBound(v, props.min, props.max)
  editing.value = String(fmtSig(clamped, 8))
  if (clamped !== props.modelValue) emit('update:modelValue', clamped)
}
</script>

<template>
  <div class="prow" :class="{ compact: props.compact }">
    <label class="lbl" :title="props.paramKey">{{ props.label }}</label>
    <input
      v-model="editing"
      class="field num"
      :class="{ invalid }"
      inputmode="decimal"
      spellcheck="false"
      @focus="focused = true"
      @keydown.enter="($event.target as HTMLInputElement).blur()"
      @blur="commit"
    />
    <button
      v-if="props.lockable"
      class="lock"
      :class="{ on: props.locked }"
      :title="props.locked ? '已锁定（拟合中保持不变）' : '未锁定'"
      @click="emit('update:locked', !props.locked)"
    >
      <AppIcon :name="props.locked ? 'lock' : 'unlock'" :size="13" />
    </button>
    <span v-else class="ghost-slot" />
  </div>
</template>

<style scoped>
.prow {
  display: grid;
  grid-template-columns: minmax(72px, 1fr) 110px 26px;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
}
.prow.compact {
  grid-template-columns: minmax(56px, 1fr) 92px 22px;
}
.lbl {
  font-size: var(--fs-small);
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lock {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  transition: background-color var(--speed-fast) ease, color var(--speed-fast) ease;
}
.lock:hover {
  background: var(--bg-3);
  color: var(--text-1);
}
.lock.on {
  color: var(--warning);
}
.ghost-slot {
  width: 22px;
}
</style>
