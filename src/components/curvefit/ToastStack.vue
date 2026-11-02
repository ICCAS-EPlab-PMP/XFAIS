<script setup lang="ts">
/** Bottom-right toast stack. */
import AppIcon from './AppIcon.vue'
import { dismissToast, useToasts, type ToastKind } from '@/lib/curvefit/stores/toast'

const { items } = useToasts()

const ICON: Record<ToastKind, string> = {
  info: 'info',
  success: 'check',
  warn: 'alert',
  error: 'alert',
}
</script>

<template>
  <div class="stack">
    <transition-group name="toast">
      <div v-for="t in items" :key="t.id" class="toast" :class="t.kind" @click="dismissToast(t.id)">
        <AppIcon :name="ICON[t.kind]" :size="15" />
        <span class="msg">{{ t.msg }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.stack {
  position: fixed;
  /* 2026-10-23 visual review: bottom-right covered the report panel's peak
     cards (side column 330 px + ~49 px page margin) — anchor fully LEFT of
     the side panel. / 原右下角遮挡报告面板逐峰卡；完全移到侧栏(330px+
     ~49px 页边距)左侧。 */
  right: 392px;
  bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 300;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 420px;
  padding: 9px 13px;
  border-radius: var(--radius);
  background: var(--bg-2);
  border: 1px solid var(--border-strong);
  box-shadow: var(--shadow-2);
  font-size: var(--fs-body);
  cursor: default;
}
.toast.info {
  border-left: 3px solid var(--accent);
  color: var(--text-1);
}
.toast.info .icon {
  color: var(--accent);
  margin-top: 1px;
}
.toast.success {
  border-left: 3px solid var(--success);
}
.toast.success .icon {
  color: var(--success);
  margin-top: 1px;
}
.toast.warn {
  border-left: 3px solid var(--warning);
}
.toast.warn .icon {
  color: var(--warning);
  margin-top: 1px;
}
.toast.error {
  border-left: 3px solid var(--danger);
}
.toast.error .icon {
  color: var(--danger);
  margin-top: 1px;
}
.msg {
  line-height: 1.45;
}

.toast-enter-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.toast-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(24px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
