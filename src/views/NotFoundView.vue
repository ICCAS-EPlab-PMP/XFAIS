<template>
  <section class="not-found-page" :data-testid="testIds.notFoundPage">
    <span class="not-found-kicker">404</span>
    <h1>{{ t('notFound.title') }}</h1>
    <p>{{ t('notFound.subtitle') }}</p>
    <button class="not-found-action" type="button" @click="goHome">
      {{ t('notFound.action') }}
    </button>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { testIds } from '@/lib/testIds'

const { t } = useI18n()
const router = useRouter()

const goHome = async (): Promise<void> => {
  await router.replace('/')
}
</script>

<style scoped>
.not-found-page {
  display: grid;
  place-items: center;
  text-align: center;
  gap: 14px;
  min-height: 58vh;
  padding: 32px;
  border-radius: 32px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(226, 232, 240, 0.88);
}

.not-found-kicker {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.not-found-action {
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
  color: var(--text-inverse);
}
</style>
