<template>
  <div class="settings-view">
    <section class="settings-card" data-ai-id="settings:card">
      <header class="settings-card-header">
        <h1>{{ t('settings.title') }}</h1>
        <p>{{ t('settings.subtitle') }}</p>
      </header>

      <!-- Language / 语言 -->
      <div class="settings-section">
        <h2>{{ t('settings.language.title') }}</h2>
        <p class="settings-hint">{{ t('settings.language.hint') }}</p>
        <div class="settings-row">
          <select v-model="localeProxy" class="settings-select" data-testid="settings-locale">
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>

      <!-- Performance / 性能 -->
      <div class="settings-section">
        <h2>{{ t('settings.performance.title') }}</h2>
        <p class="settings-hint">{{ t('settings.performance.hint') }}</p>

        <label class="settings-field">
          <span class="settings-label">{{ t('settings.performance.defaultMethod') }}</span>
          <select v-model="settings.performance.defaultMethod" class="settings-select" data-testid="settings-default-method">
            <option value="splitpixel">splitpixel</option>
            <option value="csr">csr</option>
          </select>
          <small class="settings-hint">{{ t('settings.performance.defaultMethodHint') }}</small>
        </label>

        <label class="settings-field settings-toggle">
          <input
            v-model="settings.performance.batchParallel"
            type="checkbox"
            data-testid="settings-batch-parallel"
          />
          <span class="settings-label">{{ t('settings.performance.batchParallel') }}</span>
          <small class="settings-hint">{{ t('settings.performance.batchParallelHint') }}</small>
        </label>

        <label v-if="settings.performance.batchParallel" class="settings-field">
          <span class="settings-label">{{ t('settings.performance.batchWorkers') }}</span>
          <input
            v-model.number="settings.performance.batchWorkers"
            type="number"
            min="1"
            max="16"
            class="settings-input"
            data-testid="settings-batch-workers"
          />
          <small class="settings-hint">{{ t('settings.performance.batchWorkersHint') }}</small>
        </label>

        <label class="settings-field">
          <span class="settings-label">{{ t('settings.performance.ompThreads') }}</span>
          <select v-model="ompProxy" class="settings-select" data-testid="settings-omp-threads">
            <option value="auto">{{ t('settings.performance.ompThreadsAuto') }}</option>
            <option v-for="n in ompChoices" :key="n" :value="String(n)">{{ n }}</option>
          </select>
          <small class="settings-hint">{{ t('settings.performance.ompThreadsHint') }}</small>
        </label>
        <p class="settings-note">{{ t('settings.performance.restartNote') }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * SettingsView.vue — 应用设置页
 * Language / performance (default method, batch parallelism, OpenMP).
 * All changes persist immediately via useSettings().
 * 语言 / 性能（默认算法、批处理并行、OpenMP）。所有修改经 useSettings() 即时持久化。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettings } from '@/lib/settings'
import { useToast } from '@/lib/toast'

const { t, locale } = useI18n()
const toast = useToast()
const settings = useSettings()

const ompChoices = [2, 4, 8, 12, 16, 24, 32]

const localeProxy = computed<'zh' | 'en'>({
  get: () => (locale.value === 'en' ? 'en' : 'zh'),
  set: (value) => {
    locale.value = value
    settings.locale = value
    toast.push({ title: t('settings.title'), message: t('settings.performance.saved'), tone: 'success' })
  }
})

const ompProxy = computed<string>({
  get: () => (settings.performance.ompThreads === 'auto' ? 'auto' : String(settings.performance.ompThreads)),
  set: (value) => {
    settings.performance.ompThreads = value === 'auto' ? 'auto' : Number(value)
  }
})
</script>

<style scoped>
.settings-view {
  display: flex;
  justify-content: center;
  padding: 8px 0 32px;
}

.settings-card {
  width: min(720px, 100%);
  padding: 28px 32px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  display: grid;
  gap: 28px;
}

.settings-card-header h1 {
  margin: 0 0 6px;
  font-size: 1.5rem;
}

.settings-card-header p {
  margin: 0;
  color: var(--text-secondary);
}

.settings-section {
  display: grid;
  gap: 12px;
  padding-top: 18px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.settings-section h2 {
  margin: 0;
  font-size: 1.1rem;
}

.settings-hint {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.settings-note {
  color: var(--text-secondary);
  font-size: 0.82rem;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 12px;
  padding: 8px 12px;
}

.settings-field {
  display: grid;
  gap: 6px;
}

.settings-label {
  font-weight: 600;
  font-size: 0.92rem;
}

.settings-select,
.settings-input {
  width: 100%;
  max-width: 360px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.92);
  font-size: 0.92rem;
}

.settings-toggle {
  grid-template-columns: auto 1fr;
  align-items: baseline;
}

.settings-toggle input {
  width: 16px;
  height: 16px;
  grid-row: span 2;
}
</style>
