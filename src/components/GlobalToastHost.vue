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
  top: 24px;
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

.toast-close {
  align-self: flex-start;
  border: none;
  background: transparent;
  color: var(--text-secondary);
}
</style>
