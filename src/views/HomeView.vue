<template>
  <section class="home-page" :data-testid="testIds.homePage">
    <div class="hero-card">
      <div class="hero-copy">
        <div class="hero-logo-row">
          <img class="hero-logo" src="/icon_256.png" alt="X-FAIS" />
          <div class="hero-logo-text">
            <span class="hero-kicker">{{ t('home.kicker') }}</span>
            <h1>{{ t('home.title') }}</h1>
          </div>
        </div>
        <p class="hero-subtitle">{{ t('home.subtitle') }}</p>
        <p class="hero-notice-inline"><strong>{{ t('home.heroPanel.notice') }}</strong></p>
        <p class="hero-open-source-notice">{{ t('home.heroPanel.openSourceNotice') }}</p>
        <div class="hero-actions">
          <button
            class="hero-action primary"
            type="button"
            @click="checkUpdate"
          >
            {{ t('home.actions.checkUpdate') }}
          </button>
          <button
            class="hero-action secondary"
            type="button"
            @click="openPyFAICitation"
          >
            {{ t('home.actions.citePyFAI') }}
          </button>
          <button
            class="hero-action secondary"
            type="button"
            @click="openFabIOCitation"
          >
            {{ t('home.actions.citeFabIO') }}
          </button>
        </div>
      </div>

      <div class="hero-panel">
        <div class="hero-links">
          <div class="hero-links-group">
            <span class="hero-label">{{ t('home.heroPanel.polymcrystal') }}</span>
            <a href="https://www.polymcrystal.com" target="_blank" rel="noopener">www.polymcrystal.com</a>
          </div>
          <hr class="hero-divider" />
          <div class="hero-links-group">
            <span class="hero-label">{{ t('home.heroPanel.official') }}</span>
            <a href="https://www.silx.org/" target="_blank" rel="noopener">silx.org</a>
            <a href="https://www.silx.org/doc/pyFAI/latest/" target="_blank" rel="noopener">pyFAI Docs</a>
          </div>
          <div class="hero-links-group">
            <span class="hero-label">{{ t('home.heroPanel.study') }}</span>
            <a href="https://www.silx.org/doc/pyFAI/latest/usage/index.html" target="_blank" rel="noopener">pyFAI Usage Guide</a>
          </div>
          <div class="hero-links-group">
            <span class="hero-label">{{ t('home.heroPanel.repositories') }}</span>
            <a href="https://github.com/silx-kit/pyFAI" target="_blank" rel="noopener">silx-kit/pyFAI</a>
            <a href="https://github.com/silx-kit/fabio" target="_blank" rel="noopener">silx-kit/fabio</a>
          </div>
        </div>
      </div>
    </div>

    <!-- Row 1: Common Integration / 常用积分 -->
    <div class="card-section">
      <h2 class="section-header">{{ t('home.sections.commonIntegration') }}</h2>
      <div class="card-row">
        <router-link
          v-for="card in integrationCards"
          :key="card.key"
          :to="card.route"
          class="feature-card"
          :data-testid="`home-card-${card.key}`"
        >
          <span class="feature-icon">{{ card.icon }}</span>
          <h2>{{ t(`home.cards.${card.key}.title`) }}</h2>
          <p>{{ t(`home.cards.${card.key}.description`) }}</p>
        </router-link>
      </div>
    </div>

    <!-- Row 2: GIWAXS / 掠入射衍射 -->
    <div class="card-section">
      <h2 class="section-header">{{ t('home.sections.giwaxs') }}</h2>
      <div class="card-row">
        <router-link
          v-for="card in fiberCards"
          :key="card.key"
          :to="card.route"
          class="feature-card"
          :data-testid="`home-card-${card.key}`"
        >
          <span class="feature-icon">{{ card.icon }}</span>
          <h2>{{ t(`home.cards.${card.key}.title`) }}</h2>
          <p>{{ t(`home.cards.${card.key}.description`) }}</p>
        </router-link>
      </div>
    </div>

    <!-- Row 3: Image Tools / 图像工具 -->
    <div class="card-section">
      <h2 class="section-header">{{ t('home.sections.imageTools') }}</h2>
      <div class="card-row">
        <router-link
          v-for="card in imageCards"
          :key="card.key"
          :to="card.route"
          class="feature-card"
          :data-testid="`home-card-${card.key}`"
        >
          <span class="feature-icon">{{ card.icon }}</span>
          <h2>{{ t(`home.cards.${card.key}.title`) }}</h2>
          <p>{{ t(`home.cards.${card.key}.description`) }}</p>
        </router-link>
      </div>
    </div>

    <!-- Row 4: Background Subtraction (standalone) -->
    <div class="card-section">
      <h2 class="section-header">{{ t('home.sections.backgroundSubtraction') }}</h2>
      <div class="card-row">
        <router-link
          v-for="card in bgSubtractCards"
          :key="card.key"
          :to="card.route"
          class="feature-card"
          :data-testid="`home-card-${card.key}`"
        >
          <span class="feature-icon">{{ card.icon }}</span>
          <h2>{{ t(`home.cards.${card.key}.title`) }}</h2>
          <p>{{ t(`home.cards.${card.key}.description`) }}</p>
        </router-link>
      </div>
    </div>

    <!-- Row 5: PyFAI辅助功能 -->
    <div class="card-section">
      <h2 class="section-header">{{ t('home.sections.pyfaiTools') }}</h2>
      <div class="card-row">
        <router-link
          v-for="card in pyfaiCards"
          :key="card.key"
          :to="card.route"
          class="feature-card"
          :data-testid="`home-card-${card.key}`"
        >
          <span class="feature-icon">{{ card.icon }}</span>
          <h2>{{ t(`home.cards.${card.key}.title`) }}</h2>
          <p>{{ t(`home.cards.${card.key}.description`) }}</p>
        </router-link>
      </div>
    </div>

    <!-- Acknowledgments / 致谢 -->
    <section class="acknowledgments">
      <h2>{{ t('home.acknowledgments.title') }}</h2>
      <p>
        {{ t('home.acknowledgments.thanks') }}
        <a href="https://github.com/anomalyco/opencode" target="_blank" rel="noopener">opencode</a>、
        <a href="https://github.com/code-yeongyu/oh-my-openagent" target="_blank" rel="noopener">oh-my-openagent</a>、
        <a href="https://github.com/esengine/DeepSeek-Reasonix" target="_blank" rel="noopener">Reasonix</a>
      </p>
      <p>
        {{ t('home.acknowledgments.models') }}
        <a href="https://bigmodel.cn/" target="_blank" rel="noopener">GLM-5.1</a> /
        <a href="https://www.deepseek.com/" target="_blank" rel="noopener">DeepSeek V4</a> /
        <a href="https://www.minimaxi.com/" target="_blank" rel="noopener">MiniMax 2.7</a> /
        <a href="https://tongyi.aliyun.com/" target="_blank" rel="noopener">Qwen 3.6 Plus</a> /
        <a href="https://platform.xiaomimimo.com/docs/zh-CN/welcome" target="_blank" rel="noopener">MiMo V2.5</a>
      </p>
      <p>
        {{ t('home.acknowledgments.developer') }}
        <a href="https://github.com/ICCAS-EPlab-PMP" target="_blank" rel="noopener">{{ t('home.acknowledgments.devOrg') }}</a>
        （<a href="https://ic.cas.cn/" target="_blank" rel="noopener">ICCAS</a> /
        <a href="http://eplab.iccas.ac.cn/" target="_blank" rel="noopener">EP</a> /
        <a href="http://pmp.iccas.ac.cn/" target="_blank" rel="noopener">PMP</a>）
      </p>
      <p>
        {{ t('home.heroPanel.contact') }}：
        <a href="https://github.com/ICCAS-EPlab-PMP/XFAIS/issues" target="_blank" rel="noopener">{{ t('home.heroPanel.issueHint') }}</a>
      </p>
    </section>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

interface FeatureCard {
  key: string
  route: string
  icon: string
}

// Row 1: Common Integration (3 cards)
const integrationCards: FeatureCard[] = [
  {
    key: 'integrate1d',
    route: '/workspace/integrate-1d',
    icon: '↗'
  },
  {
    key: 'integrateAzimuth',
    route: '/workspace/integrate-azimuth',
    icon: '⟳'
  },
  {
    key: 'integrateCake',
    route: '/workspace/integrate-cake',
    icon: '扇'
  }
]

// Row 2: GIWAXS (1 card)
const fiberCards: FeatureCard[] = [
  {
    key: 'integrateFiber',
    route: '/workspace/integrate-fiber',
    icon: '◈'
  }
]

// Row 3: Image Tools (viewer + H5 tools + mask maker)
const imageCards: FeatureCard[] = [
  {
    key: 'viewer',
    route: '/workspace/viewer',
    icon: '⊞'
  },
  {
    key: 'maskMaker',
    route: '/workspace/mask-maker',
    icon: 'M'
  },
  {
    key: 'h5convert',
    route: '/workspace/h5convert',
    icon: '⇄'
  },
  {
    key: 'h5extract',
    route: '/workspace/h5-extract',
    icon: '⤓'
  }
]

// Row 4: Background Subtraction (standalone section)
const bgSubtractCards: FeatureCard[] = [
  {
    key: 'bgSubtract',
    route: '/workspace/bg-subtract',
    icon: '⊖'
  }
]

// Row 5: PyFAI辅助功能
const pyfaiCards: FeatureCard[] = [
  {
    key: 'cellCalibrantGenerator',
    route: '/workspace/cell-calibrant-generator',
    icon: '▣'
  },
  {
    key: 'pyfaiCalib',
    route: '/workspace/pyfai-calib',
    icon: '⚙'
  },
  {
    key: 'poniImporter',
    route: '/workspace/poni-importer',
    icon: 'P'
  }
]

// Disabled / Coming Soon cards
const disabledCards: FeatureCard[] = [
]

const showLogDirectory = async (): Promise<void> => {
  const meta = await transport.getAppMeta()
  toast.push({
    title: t('home.actions.showLogs'),
    message: t('home.logsToast', { path: meta.logDirectory }),
    tone: 'success'
  })
}

const REPO_OWNER = 'ICCAS-EPlab-PMP'
const REPO_NAME = 'XFAIS'
const RELEASES_API = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`

async function checkUpdate(): Promise<void> {
  toast.push({
    title: t('home.actions.checkUpdate'),
    message: t('home.update.checking'),
    tone: 'info',
  })

  try {
    const meta = await transport.getAppMeta()
    const currentVersion = meta.appVersion

    const resp = await fetch(RELEASES_API, {
      headers: { Accept: 'application/vnd.github+json' },
    })
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`)
    }
    const data = await resp.json() as { tag_name?: string; html_url?: string }
    const latestTag = data.tag_name ?? ''
    const latestVersion = latestTag.replace(/^v/, '')

    if (latestVersion && latestVersion !== currentVersion) {
      const downloadUrl = data.html_url ?? `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/latest`
      toast.push({
        title: t('home.update.newVersionTitle'),
        message: `${t('home.update.newVersion', { current: currentVersion, latest: latestVersion })}\n${downloadUrl}`,
        tone: 'success',
      })
    } else if (latestVersion) {
      toast.push({
        title: t('home.actions.checkUpdate'),
        message: t('home.update.upToDate', { version: currentVersion }),
        tone: 'info',
      })
    } else {
      // No releases yet
      toast.push({
        title: t('home.actions.checkUpdate'),
        message: t('home.update.noRelease'),
        tone: 'info',
      })
    }
  } catch (err) {
    toast.push({
      title: t('home.actions.checkUpdate'),
      message: t('home.update.failed', { error: err instanceof Error ? err.message : String(err) }),
      tone: 'error',
    })
  }
}

function openPyFAICitation(): void {
  window.open('https://doi.org/10.1107/S1600576715004306', '_blank', 'noopener')
}

function openFabIOCitation(): void {
  window.open('https://doi.org/10.1107/S0021889813000150', '_blank', 'noopener')
}
</script>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.8fr);
  gap: 20px;
  padding: 24px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(226, 232, 240, 0.88);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.06);
}

.hero-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  padding: 8px 16px;
  border-radius: 999px;
  color: var(--primary);
  background: var(--primary-bg);
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.hero-copy h1 {
  font-size: 2.6rem;
  margin-bottom: 6px;
}

.hero-subtitle {
  color: #000;
  font-size: 1.05rem;
  line-height: 1.6;
  margin: 4px 0 0;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.hero-action {
  border: none;
  border-radius: 999px;
  padding: 12px 20px;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.hero-action.secondary {
  background: rgba(15, 23, 42, 0.85);
  color: var(--text-inverse);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.hero-action.secondary:hover {
  background: rgba(15, 23, 42, 1);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.3);
}

.hero-action.secondary:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.2);
}

.hero-action.primary {
  background: var(--primary);
  color: var(--text-inverse);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.hero-action.primary:hover {
  background: var(--primary);
  filter: brightness(1.1);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(var(--primary-rgb, 37, 99, 235), 0.4);
}

.hero-action.primary:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(var(--primary-rgb, 37, 99, 235), 0.3);
}

.hero-panel {
  position: relative;
  padding: 20px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(30, 64, 175, 0.94), rgba(30, 58, 138, 0.94));
  color: var(--text-inverse);
  overflow: hidden;
}

.hero-panel::after {
  content: '';
  position: absolute;
  inset: auto -40px -40px auto;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
}

.hero-panel-title {
  display: inline-flex;
  margin-bottom: 14px;
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.hero-logo-row {
  display: flex;
  align-items: center;
  gap: 18px;
}

.hero-logo {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  object-fit: cover;
  flex-shrink: 0;
}

.hero-logo-text {
  display: flex;
  flex-direction: column;
}

.hero-links {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hero-links-group {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.hero-divider {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  margin: 4px 0;
}

.hero-label {
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.7;
  min-width: 0;
}

.hero-links-group a {
  color: rgba(255, 255, 255, 0.92);
  text-decoration: none;
  font-size: 1.15rem;
  transition: color 0.15s ease, text-decoration-color 0.15s ease;
  border-bottom: 1px solid transparent;
}

.hero-links-group a:hover {
  color: #fff;
  border-bottom-color: rgba(255, 255, 255, 0.5);
}

.hero-xfais-link {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.hero-sep {
  opacity: 0.4;
  padding: 0 2px;
}

/* pyFAI/fabIO notice — inline below subtitle */
.hero-notice-inline {
  font-size: 1rem;
  color: #000;
  margin: 0 0 8px;
  line-height: 1.6;
}

/* Open source notice */
.hero-open-source-notice {
  font-size: 0.9rem;
  color: #555;
  margin: 0 0 12px;
  line-height: 1.6;
  font-style: italic;
}

/* Acknowledgments footer — left aligned */
.acknowledgments {
  padding: 28px 24px;
  border-top: 1px solid var(--border);
  text-align: left;
}

.acknowledgments h2 {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.acknowledgments p {
  font-size: 0.95rem;
  color: var(--text-secondary);
  margin: 0 0 6px;
  line-height: 1.7;
}

.acknowledgments p:last-child {
  margin-bottom: 0;
}

.acknowledgments a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s ease;
}

.acknowledgments a:hover {
  text-decoration: underline;
}

/* Section headers */
.card-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-header {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  padding-bottom: 4px;
  border-bottom: 2px solid rgba(226, 232, 240, 0.6);
}

/* Card rows — uniform grid, all cards same size */
.card-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: var(--shadow-card);
  text-decoration: none;
  color: inherit;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast),
    border-color var(--transition-fast);
  position: relative;
}

.feature-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  border-color: var(--border-hover);
}

/* Disabled card state */
.feature-card--disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.feature-card--disabled:hover {
  transform: none;
  box-shadow: var(--shadow-card);
  border-color: rgba(226, 232, 240, 0.9);
}

.badge-coming-soon {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(156, 163, 175, 0.2);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.feature-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--primary-bg);
  color: var(--primary);
  font-size: 1.2rem;
  font-weight: 700;
}

.feature-card h2 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.feature-card p {
  font-size: 0.95rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.6;
}

@media (max-width: 1100px) {
  .hero-card {
    grid-template-columns: 1fr;
  }

  .card-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .card-row {
    grid-template-columns: 1fr;
  }
}
</style>
