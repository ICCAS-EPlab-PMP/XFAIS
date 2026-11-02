<script setup lang="ts">
/**
 * Toolbar dropdown menu. Items render as a flat list; `sep: true` draws a
 * divider. Closes on outside click / Escape / selection.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'

export interface MenuItem {
  id: string
  label: string
  hint?: string
  icon?: string
  danger?: boolean
  disabled?: boolean
  sep?: boolean
}

const props = defineProps<{
  label: string
  items: MenuItem[]
  icon?: string
  variant?: 'default' | 'primary' | 'ghost'
  align?: 'left' | 'right'
  disabled?: boolean
}>()

const emit = defineEmits<{ select: [id: string] }>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
}

function pick(item: MenuItem): void {
  if (item.disabled) return
  open.value = false
  emit('select', item.id)
}

function onDocPointerDown(e: PointerEvent): void {
  if (open.value && rootEl.value && !rootEl.value.contains(e.target as Node)) open.value = false
}

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, true)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, true)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="rootEl" class="dd" :class="{ open }">
    <button
      class="btn"
      :class="{
        primary: props.variant === 'primary',
        ghost: props.variant === 'ghost',
        'icon-only': !props.label,
      }"
      :disabled="props.disabled"
      @click="toggle"
    >
      <AppIcon v-if="props.icon" :name="props.icon" />
      <span v-if="props.label">{{ props.label }}</span>
      <AppIcon name="chevronDown" :size="12" />
    </button>
    <transition name="dd">
      <div v-if="open" class="menu" :class="{ right: props.align === 'right' }" role="menu">
        <template v-for="item in props.items" :key="item.id">
          <div v-if="item.sep" class="sep" />
          <button
            v-else
            class="item"
            :class="{ danger: item.danger, disabled: item.disabled }"
            role="menuitem"
            :disabled="item.disabled"
            @click="pick(item)"
          >
            <AppIcon v-if="item.icon" :name="item.icon" :size="14" />
            <span class="lbl">{{ item.label }}</span>
            <span v-if="item.hint" class="hint2">{{ item.hint }}</span>
          </button>
        </template>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.dd {
  position: relative;
  display: inline-flex;
}
.menu {
  position: absolute;
  top: calc(100% + 5px);
  left: 0;
  min-width: 210px;
  padding: 5px;
  background: var(--bg-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow-2);
  z-index: 90;
}
.menu.right {
  left: auto;
  right: 0;
}
.sep {
  height: 1px;
  margin: 5px 4px;
  background: var(--border);
}
.item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 9px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-1);
  font: inherit;
  font-size: var(--fs-body);
  text-align: left;
  cursor: pointer;
  transition: background-color var(--speed-fast) ease;
}
.item:hover:not(.disabled) {
  background: var(--accent-soft);
}
.item.disabled {
  opacity: 0.4;
  cursor: default;
}
.item .lbl {
  flex: none;
}
.item .hint2 {
  margin-left: auto;
  font-size: var(--fs-small);
  color: var(--text-3);
}
.item.danger {
  color: var(--danger);
}

.dd-enter-active,
.dd-leave-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.dd-enter-from,
.dd-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
