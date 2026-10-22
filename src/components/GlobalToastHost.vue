<template>
  <aside class="toast-viewport" :data-testid="testIds.toastViewport" aria-live="polite">
    <article v-for="item in store.items" :key="item.id" class="toast-card" :class="`tone-${item.tone}`">
      <div>
        <strong>{{ item.title }}</strong>
        <p>{{ item.message }}</p>
      </div>
      <button type="button" class="toast-close" @click="store.remove(item.id)">
        {{ t('toast.close') }}
      </button>
    </article>
  </aside>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { testIds } from '@/lib/testIds'

const { t } = useI18n()
const store = useToast()
</script>

<style scoped>
.toast-viewport {
  position: fixed;
  /* Below the AppShell top bar (visual review 2026-10-21: at 24px the toasts
   * covered the sticky header's 主页/EN/status row and washed it out at
   * ~1.06:1 contrast). The shell header measures ~18–106px tall.
   * 移到顶栏之下（视觉审查 2026-10-21：原 24px 时 toast 盖住 sticky 顶栏的
   * 主页/EN/状态行，对比度被洗到约 1.06:1）。顶栏实测高约 18–106px。 */
  top: 120px;
  right: 24px;
  z-index: var(--z-tooltip);
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast-card {
  width: min(360px, calc(100vw - 48px));
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
}

.toast-card strong {
  display: block;
  margin-bottom: 4px;
}

.toast-card.tone-error {
  border-color: rgba(239, 68, 68, 0.24);
}

.toast-card.tone-success {
  border-color: rgba(16, 185, 129, 0.24);
}

.toast-card.tone-warning {
  border-color: rgba(245, 158, 11, 0.35);
}

.toast-close {
  align-self: flex-start;
  border: none;
  background: transparent;
  color: var(--text-secondary);
}
</style>
