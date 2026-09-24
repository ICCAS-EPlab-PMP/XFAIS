<template>
  <div class="ai-bar" :class="{ 'ai-bar--dragging': dragging }" data-ai-id="ai:assistant-bar">
    <!-- ── Expanded floating panel / 悬浮面板 ─────────────────────── -->
    <section
      v-if="open"
      ref="panelEl"
      class="ai-bar__panel"
      :style="panelStyle"
      role="complementary"
      aria-label="AI assistant"
    >
      <header class="ai-bar__header" @pointerdown="onHeaderPointerDown">
        <span class="ai-bar__title">{{ t('ai.bar.title') }}</span>
        <span class="ai-bar__provider" :title="t('ai.bar.provider')">
          {{ t('ai.bar.provider') }}: {{ providerLabel }}
        </span>
        <button
          type="button"
          class="ai-bar__close"
          :title="t('ai.bar.clear')"
          :aria-label="t('ai.bar.clear')"
          @click="clearConversation"
        >
          ⌫
        </button>
        <button
          type="button"
          class="ai-bar__close"
          :title="t('ai.bar.restore')"
          :aria-label="t('ai.bar.restore')"
          @click="restoreBar"
        >
          ⟲
        </button>
        <button
          type="button"
          class="ai-bar__close"
          :title="t('ai.bar.close')"
          :aria-label="t('ai.bar.close')"
          @click="open = false"
        >
          ✕
        </button>
      </header>

      <!-- ── Guided-tour status / 教学步骤状态 ──────────────────── -->
      <div v-if="state === 'guide'" class="ai-bar__guide">
        <span class="ai-bar__guide-step">{{ guideStepLabel }}</span>
        <span class="ai-bar__guide-title" :title="guideTitle">{{ guideTitle }}</span>
        <span class="ai-bar__guide-actions">
          <button type="button" class="ai-bar__guide-btn" :title="t('ai.guide.skip')" @click="skipGuide">
            ›
          </button>
          <button type="button" class="ai-bar__guide-btn" @click="stopGuide">
            {{ t('ai.guide.exit') }}
          </button>
        </span>
      </div>

      <!-- ── Transcript / 对话记录 ──────────────────────────────── -->
      <div ref="transcriptEl" class="ai-bar__transcript">
        <div
          v-for="(line, index) in history"
          :key="index"
          class="ai-bar__line"
          :class="`ai-bar__line--${line.role}`"
        >
          {{ line.text }}
        </div>

        <p v-if="state === 'thinking'" class="ai-bar__status ai-bar__status--thinking">
          {{ t('ai.bar.thinking') }}<span class="ai-bar__dots"><i /><i /><i /></span>
        </p>

        <!-- ── Suggestions / 候选建议 ───────────────────────────── -->
        <div v-if="state === 'suggest' && topPicks.length > 0" class="ai-bar__picks">
          <p class="ai-bar__status">{{ t('ai.bar.suggestHint') }}</p>
          <div class="ai-bar__pick-row">
            <button
              v-for="entry in topPicks"
              :key="entry.routeName"
              type="button"
              class="ai-bar__pick"
              @click="pick(entry.routeName)"
            >
              {{ pickLabel(entry.routeName) }}
            </button>
          </div>
        </div>

        <p v-else-if="state === 'wait-user'" class="ai-bar__status">{{ t('ai.bar.waitHint') }}</p>
        <p v-else-if="state === 'template-apply'" class="ai-bar__status ai-bar__status--ok">
          {{ t('ai.template.applied') }}
        </p>
        <p v-else-if="state === 'guide'" class="ai-bar__status ai-bar__status--ok">
          {{ t('ai.guide.waitNext') }}
        </p>
      </div>

      <!-- ── PONI picker / PONI 选择 ────────────────────────────── -->
      <div class="ai-bar__poni">
        <button type="button" class="ai-bar__poni-btn" @click="pickPoni">PONI</button>
        <input
          v-if="!isDesktop"
          v-model="poniDraft"
          type="text"
          class="ai-bar__poni-input"
          placeholder=".poni"
          @change="commitPoniText"
          @keyup.enter="commitPoniText"
        />
        <span v-else class="ai-bar__poni-path" :title="poniPath">{{ poniName || '—' }}</span>
      </div>

      <!-- ── Tour entry + toggles / 教学入口与开关 ────────────────── -->
      <div class="ai-bar__tour-row">
        <button
          v-if="state !== 'guide' && routeHasGuide"
          type="button"
          class="ai-bar__tour-btn"
          :title="t('ai.guide.startPrompt')"
          @click="startGuideHere"
        >
          {{ t('ai.guide.start') }}
        </button>
        <label class="ai-bar__toggle">
          <input v-model="teachingOn" type="checkbox" />
          {{ t('ai.guide.toggle') }}
        </label>
        <label class="ai-bar__toggle" :title="t('ai.guide.autoclickHint')">
          <input v-model="autoClickOn" type="checkbox" />
          {{ t('ai.guide.autoclick') }}
        </label>
      </div>

      <!-- ── Input / 输入 ───────────────────────────────────────── -->
      <form class="ai-bar__input-row" @submit.prevent="send">
        <input
          v-model="draft"
          type="text"
          class="ai-bar__input"
          :placeholder="t('ai.bar.placeholder')"
          :disabled="busy"
        />
        <button
          type="submit"
          class="ai-bar__send"
          :disabled="busy || draft.trim().length === 0"
        >
          {{ t('ai.bar.send') }}
        </button>
      </form>

      <!-- ── Resize grip / 缩放手柄 ─────────────────────────────── -->
      <div class="ai-bar__resize" @pointerdown="onResizePointerDown" />
    </section>

    <!-- ── Collapsed FAB / 收起按钮 ──────────────────────────────── -->
    <button
      v-if="!open"
      type="button"
      class="ai-bar__fab"
      :title="t('ai.bar.open')"
      :aria-label="t('ai.bar.open')"
      @click="open = true"
    >
      ✦
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'
import { useAiAgent } from '@/ai/agent'
import { PONI_PATH_KEY, navTitle, rememberVisit } from '@/ai/context'
import { clearHighlight } from '@/ai/highlight'
import {
  autoClickEnabled,
  setAutoClickEnabled,
  setTeachingEnabled,
  teachingEnabled,
} from '@/ai/guide/engine'
import { hasGuide } from '@/ai/guide/registry'

const { t } = useI18n()
const transport = useTransport()
const route = useRoute()
const agent = useAiAgent()

const { state, history, topPicks, busy, lastDecision, submit, pick, guide, startGuideHere, clearConversation } = agent

const open = ref(false)
const draft = ref('')
const transcriptEl = ref<HTMLElement | null>(null)
const isDesktop = ref(false)
const poniPath = ref('')
const poniDraft = ref('')

const autoClickOn = ref(autoClickEnabled())
watch(autoClickOn, (value) => setAutoClickEnabled(value))
const teachingOn = ref(teachingEnabled())
watch(teachingOn, (value) => setTeachingEnabled(value))

const routeHasGuide = computed(() => typeof route.name === 'string' && hasGuide(route.name))

const guideStepLabel = computed(() =>
  t('ai.guide.stepOf', {
    current: String(guide.stepIndex.value + 1),
    total: String(guide.totalSteps.value),
  })
)
const guideTitle = computed(() => guide.currentTitle.value)

const skipGuide = (): void => guide.skip()
const stopGuide = (): void => guide.stop()

// ── Floating panel: drag by header / resize by grip / restore ─────────
// 悬浮面板：标题栏拖动、右下角手柄缩放、⟲ 恢复默认位置与大小；位置尺寸
// 持久化到 localStorage，重开应用后保持。

const POS_KEY = 'xfaos.ai.barPos'
const SIZE_KEY = 'xfaos.ai.barSize'
const DEFAULT_W = 360
const MIN_W = 300
const MAX_W = 720
const MIN_H = 320

interface PanelPos { left: number; top: number }
interface PanelSize { w: number; h: number }

const panelEl = ref<HTMLElement | null>(null)
const dragging = ref(false)
const resizing = ref(false)

const clamp = (v: number, min: number, max: number): number =>
  Math.min(Math.max(v, min), Math.max(min, max))

function loadJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function saveJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* best-effort */
  }
}

const panelPos = ref<PanelPos | null>(loadJson<PanelPos>(POS_KEY))
const panelSize = ref<PanelSize | null>(loadJson<PanelSize>(SIZE_KEY))

/** Inline styles only when the user moved/resized; otherwise CSS defaults. */
const panelStyle = computed(() => {
  const style: Record<string, string> = {}
  if (panelPos.value) {
    style.left = `${Math.round(panelPos.value.left)}px`
    style.top = `${Math.round(panelPos.value.top)}px`
    style.right = 'auto'
    style.bottom = 'auto'
  }
  if (panelSize.value) {
    style.width = `${Math.round(panelSize.value.w)}px`
    style.height = `${Math.round(panelSize.value.h)}px`
    style.maxHeight = 'none'
  }
  return style
})

/** Keep the panel inside the viewport (at least a drag-grip visible). */
const clampIntoViewport = (): void => {
  const pos = panelPos.value
  if (!pos || typeof window === 'undefined') return
  pos.left = clamp(pos.left, 8, Math.max(8, window.innerWidth - 120))
  pos.top = clamp(pos.top, 8, Math.max(8, window.innerHeight - 48))
}

const onHeaderPointerDown = (event: PointerEvent): void => {
  if (event.button !== 0) return
  if ((event.target as HTMLElement).closest('button, input, label, a, select')) return
  const panel = panelEl.value
  if (!panel) return
  event.preventDefault()

  const rect = panel.getBoundingClientRect()
  const startLeft = rect.left
  const startTop = rect.top
  const startX = event.clientX
  const startY = event.clientY
  panelPos.value = { left: startLeft, top: startTop }
  dragging.value = true

  const onMove = (e: PointerEvent): void => {
    const pos = panelPos.value
    if (!pos) return
    pos.left = clamp(startLeft + e.clientX - startX, 8, Math.max(8, window.innerWidth - 120))
    pos.top = clamp(startTop + e.clientY - startY, 8, Math.max(8, window.innerHeight - 48))
  }
  const onUp = (): void => {
    dragging.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    if (panelPos.value) saveJson(POS_KEY, panelPos.value)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

const onResizePointerDown = (event: PointerEvent): void => {
  if (event.button !== 0) return
  const panel = panelEl.value
  if (!panel) return
  event.preventDefault()
  event.stopPropagation()

  const rect = panel.getBoundingClientRect()
  // Anchor the top-left corner so resizing feels natural from the grip.
  if (!panelPos.value) panelPos.value = { left: rect.left, top: rect.top }
  const startW = panelSize.value?.w ?? rect.width
  const startH = panelSize.value?.h ?? rect.height
  const startX = event.clientX
  const startY = event.clientY
  resizing.value = true

  const onMove = (e: PointerEvent): void => {
    panelSize.value = {
      w: clamp(startW + e.clientX - startX, MIN_W, Math.min(MAX_W, window.innerWidth - 16)),
      h: clamp(startH + e.clientY - startY, MIN_H, window.innerHeight - 16),
    }
  }
  const onUp = (): void => {
    resizing.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    if (panelSize.value) saveJson(SIZE_KEY, panelSize.value)
    if (panelPos.value) saveJson(POS_KEY, panelPos.value)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

/** Restore the default bottom-right position and auto size. */
const restoreBar = (): void => {
  panelPos.value = null
  panelSize.value = null
  try {
    localStorage.removeItem(POS_KEY)
    localStorage.removeItem(SIZE_KEY)
  } catch {
    /* best-effort */
  }
}

const onWindowResize = (): void => clampIntoViewport()
window.addEventListener('resize', onWindowResize)
onUnmounted(() => window.removeEventListener('resize', onWindowResize))
// Clamp a restored position on open (display layout may have changed).
watch(open, (isOpen) => {
  if (isOpen) clampIntoViewport()
})

const poniName = computed(() => {
  const p = poniPath.value
  if (!p) return ''
  const parts = p.split(/[\\/]/)
  return parts[parts.length - 1] || p
})

const providerLabel = computed(() => {
  switch (lastDecision.value?.provider) {
    case 'jev':
      return t('ai.bar.providerJev')
    default:
      return t('ai.bar.providerRules')
  }
})

const pickLabel = (routeName: string): string => navTitle(routeName)

const send = async (): Promise<void> => {
  const text = draft.value.trim()
  if (!text || busy.value) return
  draft.value = ''
  await submit(text)
}

const readPoni = (): void => {
  try {
    poniPath.value = localStorage.getItem(PONI_PATH_KEY) ?? ''
    poniDraft.value = poniPath.value
  } catch {
    poniPath.value = ''
    poniDraft.value = ''
  }
}

const storePoni = (value: string): void => {
  poniPath.value = value
  poniDraft.value = value
  try {
    if (value) localStorage.setItem(PONI_PATH_KEY, value)
    else localStorage.removeItem(PONI_PATH_KEY)
  } catch {
    // Storage unavailable — best-effort only.
  }
}

const pickPoni = async (): Promise<void> => {
  if (!isDesktop.value) return // web mode: the text input handles it
  const result = await transport.selectFiles({
    filters: [{ name: 'PONI', extensions: ['poni'] }],
  })
  const chosen = Array.isArray(result) ? result[0] : result
  if (chosen) storePoni(chosen)
}

const commitPoniText = (): void => {
  storePoni(poniDraft.value.trim())
}

// Auto-scroll the transcript to the latest line.
watch(
  () => history.value.length,
  async () => {
    await nextTick()
    if (transcriptEl.value) transcriptEl.value.scrollTop = transcriptEl.value.scrollHeight
  }
)

// Track visits for the AppState snapshot; clear spotlights on navigation
// (history-API pushes don't fire popstate, so this complements the overlay's
// own popstate/hashchange listeners).
watch(
  () => route.fullPath,
  (fullPath) => {
    rememberVisit(fullPath)
    clearHighlight()
  }
)

onMounted(() => {
  isDesktop.value = transport.isDesktop()
  readPoni()
})
</script>

<style scoped>
.ai-bar {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9000;
  font-family: var(--font-sans);
}

/* ── Collapsed FAB ─────────────────────────────────────────────── */

.ai-bar__fab {
  position: absolute;
  right: 24px;
  bottom: 24px;
  pointer-events: auto;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  color: #ffffff;
  font-size: 20px;
  line-height: 1;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.45);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.ai-bar__fab:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 12px 30px rgba(99, 102, 241, 0.55);
}

/* ── Panel (floating window) ───────────────────────────────────── */

.ai-bar__panel {
  position: absolute;
  right: 24px;
  bottom: 24px;
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  width: 360px;
  max-height: min(560px, calc(100vh - 64px));
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.ai-bar__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  cursor: grab;
  user-select: none;
  touch-action: none;
}

.ai-bar--dragging .ai-bar__header {
  cursor: grabbing;
}

/* Resize grip (bottom-right corner) / 右下角缩放手柄 */
.ai-bar__resize {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 18px;
  height: 18px;
  cursor: nwse-resize;
  touch-action: none;
  z-index: 2;
}

.ai-bar__resize::after {
  content: '';
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 8px;
  height: 8px;
  border-right: 2px solid rgba(99, 102, 241, 0.55);
  border-bottom: 2px solid rgba(99, 102, 241, 0.55);
  border-bottom-right-radius: 3px;
}

.ai-bar__title {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-primary);
}

.ai-bar__provider {
  flex: 1;
  font-size: 0.6875rem;
  color: var(--text-secondary);
  background: var(--bg-surface-alt);
  border-radius: 999px;
  padding: 3px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ai-bar__close {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast), color var(--transition-fast);
}

/* ── Guided-tour status row / 教学步骤状态行 ────────────────────── */

.ai-bar__guide {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.10), rgba(139, 92, 246, 0.10));
  border-bottom: 1px solid var(--border);
}

.ai-bar__guide-step {
  flex-shrink: 0;
  font-size: 0.6875rem;
  font-weight: 700;
  color: #ffffff;
  background: #4f46e5;
  border-radius: 999px;
  padding: 3px 8px;
  white-space: nowrap;
}

.ai-bar__guide-title {
  flex: 1;
  min-width: 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ai-bar__guide-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.ai-bar__guide-btn {
  border: 1px solid var(--border);
  background: #ffffff;
  color: #4f46e5;
  font-size: 0.6875rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-md);
  padding: 3px 8px;
  transition: background var(--transition-fast);
}

.ai-bar__guide-btn:hover {
  background: #eef2ff;
}

/* ── Tour entry + toggles / 教学入口与开关 ─────────────────────── */

.ai-bar__tour-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px;
  border-top: 1px solid var(--border);
}

.ai-bar__tour-btn {
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #ffffff;
  font-size: 0.6875rem;
  font-weight: 700;
  cursor: pointer;
  border-radius: 999px;
  padding: 5px 12px;
  white-space: nowrap;
  transition: opacity var(--transition-fast);
}

.ai-bar__tour-btn:hover {
  opacity: 0.88;
}

.ai-bar__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.6875rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.ai-bar__toggle input {
  accent-color: #4f46e5;
  margin: 0;
  cursor: pointer;
}

.ai-bar__close:hover {
  background: var(--bg-surface-alt);
  color: var(--text-primary);
}

/* ── Transcript ────────────────────────────────────────────────── */

.ai-bar__transcript {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 140px;
}

.ai-bar__line {
  max-width: 85%;
  padding: 6px 10px;
  border-radius: 12px;
  font-size: 0.8125rem;
  line-height: 1.45;
  word-break: break-word;
  white-space: pre-wrap;
}

.ai-bar__line--user {
  align-self: flex-end;
  background: #6366f1;
  color: #ffffff;
  border-bottom-right-radius: 4px;
}

.ai-bar__line--agent {
  align-self: flex-start;
  background: var(--bg-surface-alt);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.ai-bar__status {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.ai-bar__status--ok {
  color: var(--secondary);
  font-weight: 600;
}

.ai-bar__status--thinking {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ai-bar__dots {
  display: inline-flex;
  gap: 3px;
}

.ai-bar__dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: ai-bar-bounce 1.2s ease-in-out infinite;
}

.ai-bar__dots i:nth-child(2) { animation-delay: 0.15s; }
.ai-bar__dots i:nth-child(3) { animation-delay: 0.3s; }

@keyframes ai-bar-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-3px); opacity: 1; }
}

/* ── Suggested picks ───────────────────────────────────────────── */

.ai-bar__picks {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-bar__pick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ai-bar__pick {
  border: 1px solid #c7d2fe;
  background: rgba(99, 102, 241, 0.08);
  color: #4338ca;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 5px 10px;
  border-radius: 999px;
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.ai-bar__pick:hover {
  background: rgba(99, 102, 241, 0.18);
  border-color: #6366f1;
}

/* ── PONI row ──────────────────────────────────────────────────── */

.ai-bar__poni {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-top: 1px solid var(--border);
}

.ai-bar__poni-btn {
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 4px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.ai-bar__poni-btn:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.ai-bar__poni-input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 4px 8px;
  font-size: 0.75rem;
  color: var(--text-primary);
  background: var(--bg-surface);
}

.ai-bar__poni-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

.ai-bar__poni-path {
  flex: 1;
  min-width: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Input row ─────────────────────────────────────────────────── */

.ai-bar__input-row {
  display: flex;
  gap: 8px;
  padding: 10px 14px 12px;
  border-top: 1px solid var(--border);
}

.ai-bar__input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  font-size: 0.8125rem;
  color: var(--text-primary);
  background: var(--bg-surface);
  transition: border-color var(--transition-fast);
}

.ai-bar__input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.ai-bar__input:disabled {
  opacity: 0.6;
}

.ai-bar__send {
  border: none;
  border-radius: var(--radius-md);
  background: #6366f1;
  color: #ffffff;
  font-size: 0.8125rem;
  font-weight: 600;
  padding: 8px 14px;
  cursor: pointer;
  transition: background var(--transition-fast), opacity var(--transition-fast);
}

.ai-bar__send:hover:not(:disabled) {
  background: #4f46e5;
}

.ai-bar__send:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
