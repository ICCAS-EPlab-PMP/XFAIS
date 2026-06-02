<template>
  <slot v-if="!error" />

  <section v-else class="boundary-state" :data-testid="testIds.boundaryPage">
    <span class="boundary-badge">Renderer fallback</span>
    <h2>{{ t('boundary.title') }}</h2>
    <p>{{ t('boundary.subtitle') }}</p>
    <details class="boundary-details">
      <summary>Error details</summary>
      <pre class="boundary-error-text">{{ error?.message ?? 'Unknown' }}</pre>
      <pre v-if="error?.stack" class="boundary-stack-text">{{ error.stack }}</pre>
    </details>
    <button class="boundary-action" type="button" @click="recover">
      {{ t('boundary.action') }}
    </button>
  </section>
</template>

<script setup lang="ts">
import { onErrorCaptured, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { testIds } from '@/lib/testIds'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const error = ref<Error | null>(null)

onErrorCaptured((captured) => {
  const err = captured instanceof Error ? captured : new Error('Unknown renderer error')
  console.error('[ErrorBoundary] Caught renderer error:', err)
  error.value = err
  return false
})

watch(
  () => route.fullPath,
  () => {
    error.value = null
  }
)

const recover = async (): Promise<void> => {
  error.value = null
  await router.replace('/')
}
</script>

<style scoped>
.boundary-state {
  min-height: 100vh;
  display: grid;
  place-items: center;
  text-align: center;
  gap: 14px;
  padding: 48px;
}

.boundary-badge {
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--primary-bg);
  color: var(--primary);
  font-size: 0.8rem;
  font-weight: 700;
}

.boundary-action {
  border: none;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
  color: var(--text-inverse);
  padding: 12px 18px;
  box-shadow: var(--shadow-md);
}

.boundary-details {
  text-align: left;
  max-width: 640px;
  width: 100%;
  margin: 0 auto;
}

.boundary-details summary {
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.boundary-error-text {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #ef4444;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

.boundary-stack-text {
  background: rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 8px;
  padding: 12px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
}
</style>
