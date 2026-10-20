<script setup lang="ts">
/** Centered modal dialog with backdrop; closes on Escape / backdrop click. */
import { onBeforeUnmount, onMounted } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ title: string; width?: number }>()
const emit = defineEmits<{ close: [] }>()

function onKey(e: KeyboardEvent): void {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
void props
</script>

<template>
  <teleport to="body">
    <div class="backdrop" @pointerdown.self="emit('close')">
      <div class="modal panel" :style="{ width: (props.width ?? 420) + 'px' }" role="dialog" aria-modal="true">
        <header class="head">
          <span class="title">{{ props.title }}</span>
          <button class="btn ghost icon-only sm" title="关闭" @click="emit('close')">
            <AppIcon name="close" :size="14" />
          </button>
        </header>
        <div class="body">
          <slot />
        </div>
        <footer class="foot">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  background: var(--backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-3);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px 14px;
  border-bottom: 1px solid var(--border);
}
.title {
  font-weight: 600;
  font-size: 14px;
}
.body {
  padding: 14px;
  overflow: auto;
}
.foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}
.foot:empty {
  display: none;
}
</style>
