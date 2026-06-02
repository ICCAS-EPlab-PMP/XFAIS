<template>
  <div class="app-shell" :data-testid="testIds.appShell">
    <div class="shell-backdrop shell-backdrop-one"></div>
    <div class="shell-backdrop shell-backdrop-two"></div>

    <header class="shell-header">
      <button class="brand-block" type="button" :data-testid="testIds.shellLogo" @click="goHome">
        <img class="brand-mark" src="/icon_48.png" alt="" />
        <span class="brand-copy">
          <strong>{{ appMeta?.appName ?? t('app.name') }}</strong>
          <small>{{ t('app.version') }}</small>
        </span>
      </button>

      <div class="shell-center">
        <span class="section-pill">{{ currentSection }}</span>
        <div class="section-copy">
          <strong>{{ currentTitle }}</strong>
          <span>{{ currentDescription }}</span>
        </div>
      </div>

      <div class="shell-actions">
        <span class="shell-status" :data-testid="testIds.shellStatus">{{ shellStatusLabel }}</span>

        <button
          v-if="route.name !== 'home'"
          class="home-button"
          type="button"
          :data-testid="testIds.shellHomeButton"
          @click="goHome"
        >
          {{ t('shell.actions.home') }}
        </button>

        <button
          class="locale-toggle"
          type="button"
          :data-testid="testIds.shellLocaleSwitch"
          @click="toggleLocale"
          :title="t('shell.actions.language')"
        >
          {{ currentLocale === 'zh' ? 'EN' : '中' }}
        </button>
      </div>
    </header>

    <main class="shell-main">
      <section
        v-if="pythonStatus && pythonStatus.state !== 'healthy'"
        class="python-status-banner"
        :data-testid="testIds.pythonStatusBanner"
        :class="`state-${pythonStatus.state}`"
      >
        <div class="python-status-copy">
          <span class="python-status-pill">Python runtime</span>
          <strong>{{ pythonStateLabel }}</strong>
          <p>{{ t('python.subtitle') }}</p>
          <small>{{ t('python.detailLabel') }}: {{ pythonStatus.detail }}</small>
        </div>
        <button
          v-if="pythonStatus.canRetry && transport.isDesktop()"
          class="python-restart-button"
          type="button"
          :data-testid="testIds.pythonRestartButton"
          @click="restartPython"
        >
          {{ t('python.restart') }}
        </button>
      </section>

      <router-view />
    </main>

    <GlobalToastHost />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import GlobalToastHost from '@/components/GlobalToastHost.vue'

import { localeStorageKey } from '@/i18n/messages'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'
import type { AppMeta, PythonStatus } from '@/lib/transport'

const { t, locale } = useI18n()

const currentLocale = computed(() => locale.value)

function toggleLocale(): void {
  const next = locale.value === 'zh' ? 'en' : 'zh'
  locale.value = next
  localStorage.setItem(localeStorageKey, next)
}
const route = useRoute()
const router = useRouter()
const transport = useTransport()
const appMeta = ref<AppMeta | null>(null)
const pythonStatus = ref<PythonStatus | null>(null)
let removePythonListener: (() => void) | null = null

const currentSection = computed(() => t(String(route.meta.sectionKey ?? 'shell.sections.home')))
const currentTitle = computed(() => t(String(route.meta.titleKey ?? 'home.title')))
const currentDescription = computed(() => t(String(route.meta.descriptionKey ?? 'home.subtitle')))
const shellStatusLabel = computed(() => {
  if (!pythonStatus.value) {
    return t('shell.status.ready')
  }

  if (pythonStatus.value.state === 'error') {
    return t('shell.status.pythonError')
  }

  if (pythonStatus.value.state === 'restarting') {
    return t('shell.status.pythonRestarting')
  }

  if (pythonStatus.value.state === 'starting') {
    return t('shell.status.pythonStarting')
  }

  return t('shell.status.ready')
})
const pythonStateLabel = computed(() => {
  const state = pythonStatus.value?.state ?? 'starting'
  return t(`python.states.${state}`)
})

const goHome = async (): Promise<void> => {
  await router.push('/')
}

const restartPython = async (): Promise<void> => {
  const status = await transport.restartPython()
  if (status) pythonStatus.value = status
}

onMounted(async () => {
  appMeta.value = await transport.getAppMeta()
  const status = await transport.getPythonStatus()
  if (status) pythonStatus.value = status
  removePythonListener = transport.onPythonStatusChange((status) => {
    pythonStatus.value = status
  })
})

onBeforeUnmount(() => {
  removePythonListener?.()
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.86), rgba(241, 245, 249, 0.96));
}

.shell-backdrop {
  display: none;
}

.shell-backdrop-one {
  inset: 60px auto auto 6%;
  width: 260px;
  height: 260px;
  background: rgba(59, 130, 246, 0.14);
}

.shell-backdrop-two {
  inset: auto 8% 10% auto;
  width: 320px;
  height: 320px;
  background: rgba(16, 185, 129, 0.12);
}

.shell-header {
  position: sticky;
  top: 0;
  z-index: var(--z-dropdown);
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
  padding: 18px 28px;
  margin: 18px 18px 0;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(18px);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
  border: none;
  background: transparent;
  text-align: left;
}

.brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  object-fit: cover;
  box-shadow: var(--shadow-md);
  background: rgba(255,255,255,0.15);
}

.brand-copy {
  display: flex;
  flex-direction: column;
}

.brand-copy strong {
  font-size: 1.1rem;
}

.brand-copy small {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.shell-center {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16px;
}

.section-pill,
.shell-status {
  display: inline-flex;
  align-items: center;
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
}

.section-pill {
  background: var(--primary-bg);
  color: var(--primary);
}

.section-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.section-copy strong,
.section-copy span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-copy strong {
  font-size: 0.95rem;
}

.section-copy span {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.shell-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.shell-status {
  background: rgba(16, 185, 129, 0.14);
  color: var(--secondary);
}

.python-status-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
  padding: 22px 24px;
  border-radius: 24px;
  border: 1px solid rgba(251, 191, 36, 0.4);
  background: rgba(255, 251, 235, 0.96);
  box-shadow: var(--shadow-card);
}

.python-status-banner.state-error {
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(254, 242, 242, 0.98);
}

.python-status-copy {
  display: grid;
  gap: 8px;
}

.python-status-pill {
  display: inline-flex;
  width: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.python-status-copy p,
.python-status-copy small {
  color: var(--text-secondary);
}

.python-restart-button {
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
  color: var(--text-inverse);
  font-weight: 700;
  box-shadow: var(--shadow-sm);
}

.home-button {
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  background: transparent;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.home-button {
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-primary);
  box-shadow: var(--shadow-sm);
}

.locale-toggle {
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  min-width: 44px;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 700;
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: opacity var(--transition-fast);
  box-shadow: var(--shadow-sm);
}

.locale-toggle:hover {
  opacity: 0.85;
}

.shell-main {
  width: min(var(--content-max-width), calc(100vw - 48px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

@media (max-width: 1120px) {
  .shell-header {
    grid-template-columns: 1fr;
  }

  .shell-actions {
    flex-wrap: wrap;
  }

  .python-status-banner {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
