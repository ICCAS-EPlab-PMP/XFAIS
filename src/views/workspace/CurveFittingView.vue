<template>
  <section class="cf-page">
    <!-- X-FAIS page header only — the workbench below is the verbatim
         PeakWorkbench shell (title bar omitted: our app owns the window). /
         仅保留 X-FAIS 页头——下方是原样移植的 PeakWorkbench 工作台外壳
         （无边框标题栏：窗口由本应用外壳管理）。 -->
    <header class="cf-header">
      <h1>{{ t('curveFitting.title') }}</h1>
      <p class="cf-subtitle">{{ t('curveFitting.subtitle') }}</p>
    </header>

    <!-- .cf-wb is the design-token scope for the ported workbench (its
         tokens.css maps PeakWorkbench tokens onto the X-FAIS palette under
         this class). / .cf-wb 是移植工作台的设计令牌作用域（tokens.css 在
         此类下把 PeakWorkbench 令牌映射到 X-FAIS 配色）。 -->
    <div class="cf-wb cf-wb-shell">
      <Toolbar />
      <div class="cfwb-body">
        <StepsRail />
        <PlotArea />
        <aside class="cfwb-side">
          <component :is="activePanel" />
        </aside>
      </div>
      <StatusBar />

      <PeakAdjustPopover />
      <ToastStack />
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * CurveFittingView.vue — 衍射曲线拟合（X-FAIS 工作台壳，2026-10-20 v0.3.3 二轮）
 *
 * The page IS the ported PeakWorkbench (REA/peakfit) workbench now: Toolbar /
 * StepsRail / PlotArea (uPlot + overlay-canvas interactions) / per-step side
 * panel (数据 → 基线 → 放峰 → 拟合 → 报告 → 聚合物) / StatusBar, plus the peak-adjust
 * popover, the workbench toast stack and the Ctrl+Z/Y undo shortcuts — every
 * step's UX follows the reference program; only the COLOR SCHEME is remapped
 * to X-FAIS (components/curvefit/styles/tokens.css). The numeric core runs
 * in-process (src/lib/pwcore, ported verbatim); fits run in the inline Web
 * Worker via src/lib/curvefit/platform → src/lib/fitEngine.
 * 本页即原样移植的 PeakWorkbench（REA/peakfit）工作台：工具栏 / 步骤栏 /
 * 图区（uPlot + 覆盖层画布交互）/ 各步骤侧面板（数据 → 基线 → 放峰 → 拟合 →
 * 报告）/ 状态栏，另含峰调整浮层、工作台内提示栈与 Ctrl+Z/Y 撤销快捷键——
 * 交互全部照搬参考程序；仅配色映射为 X-FAIS（见 tokens.css）。数值核心进程
 * 内运行（逐字节移植的 pwcore）；拟合经 platform → fitEngine 在内联 Web
 * Worker 中运行。
 *
 * Stores are module singletons (the reference's session semantics): leaving
 * the page KEEPS the session — data, peaks and the last fit survive
 * navigation; only the workspace-state bridge is released on unmount.
 * 各 store 为模块级单例（参考程序的会话语义）：离开页面保留会话——数据、
 * 峰与最近拟合跨导航存活；卸载时仅释放工作区状态桥。
 */
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { reportWorkspace } from '@/lib/workspace-state'
import Toolbar from '@/components/curvefit/Toolbar.vue'
import StepsRail from '@/components/curvefit/StepsRail.vue'
import PlotArea from '@/components/curvefit/PlotArea.vue'
import StatusBar from '@/components/curvefit/StatusBar.vue'
import PeakAdjustPopover from '@/components/curvefit/PeakAdjustPopover.vue'
import ToastStack from '@/components/curvefit/ToastStack.vue'
import DataPanel from '@/components/curvefit/panels/DataPanel.vue'
import BaselinePanel from '@/components/curvefit/panels/BaselinePanel.vue'
import PeaksPanel from '@/components/curvefit/panels/PeaksPanel.vue'
import FitPanel from '@/components/curvefit/panels/FitPanel.vue'
import ReportPanel from '@/components/curvefit/panels/ReportPanel.vue'
import PolymerPanel from '@/components/curvefit/panels/PolymerPanel.vue'
import '@/components/curvefit/styles/tokens.css'
import '@/components/curvefit/styles/base.css'
import { useUi } from '@/lib/curvefit/stores/ui'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { useFit } from '@/lib/curvefit/stores/fit'
import { redo, undo } from '@/lib/curvefit/stores/undo'

const { t } = useI18n()

const ui = useUi()
const spectrum = useSpectrum()
const peaksStore = usePeaks()
const fitStore = useFit()

const PANELS = {
  data: DataPanel,
  baseline: BaselinePanel,
  peaks: PeaksPanel,
  fit: FitPanel,
  report: ReportPanel,
  polymer: PolymerPanel,
} as const

const activePanel = computed(() => PANELS[ui.step.value])

// Keyboard shortcuts (reference App.vue): Ctrl/Cmd+Z undo (Shift = redo),
// Ctrl/Cmd+Y redo, Esc closes the peak-adjust popover; never while typing in
// an input. Bound at mount, released at unmount (view-scoped).
// 键盘快捷键（参考 App.vue）：Ctrl/Cmd+Z 撤销（Shift=重做）、Ctrl/Cmd+Y 重做、
// Esc 关闭峰调整浮层；输入框内不拦截。挂载时绑定、卸载时释放（页面作用域）。
function onKey(e: KeyboardEvent): void {
  const target = e.target as HTMLElement | null
  const inEditor = !!target
    && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
  if (e.key === 'Escape' && !inEditor) {
    ui.popover.value = null
    return
  }
  if ((e.ctrlKey || e.metaKey) && !e.altKey) {
    const key = e.key.toLowerCase()
    if (key === 'z' && !inEditor) {
      e.preventDefault()
      if (e.shiftKey) redo()
      else undo()
    } else if (key === 'y' && !inEditor) {
      e.preventDefault()
      redo()
    }
  }
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

// Workspace-state bridge (inert in the main build): report data presence /
// peak count / running phase for the AI layer. Store singletons outlive the
// page, so this only reports WHILE the page is mounted. / 工作区状态桥（主线
// 构建中为惰性）：向 AI 层上报数据/峰数/运行阶段。store 单例寿命长于页面，
// 仅在页面挂载期间上报。
watch(
  [
    () => spectrum.ready.value,
    () => spectrum.meta.n,
    () => peaksStore.list.value.length,
    () => peaksStore.enabledPeaks.value.length,
    () => fitStore.status.value,
  ],
  () => {
    reportWorkspace('curve-fitting', {
      filesCount: spectrum.ready.value ? 1 : 0,
      hasPoni: false,
      canRun: peaksStore.enabledPeaks.value.length > 0,
      phase: fitStore.status.value === 'running'
        ? 'running'
        : fitStore.lastResult.value
          ? 'done'
          : 'idle',
      extras: {
        peaks: peaksStore.list.value.length,
        step: ui.step.value,
      },
    })
  },
  { immediate: true },
)
</script>

<style scoped>
.cf-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 24px 24px;
  max-width: 1720px;
  margin: 0 auto;
}

.cf-header h1 {
  margin: 0 0 4px;
  font-size: 1.5rem;
}

.cf-subtitle {
  margin: 0;
  color: var(--color-text-muted, var(--text-secondary, #64748b));
  font-size: 0.92rem;
}

/* Workbench shell: fills the viewport minus app chrome (the reference runs
   frameless-fullscreen; our shell scrolls, so a calc height + floor is used —
   uPlot resizes through its ResizeObserver). / 工作台外壳：占满视口减去应用
   铬条（参考程序为无边框全屏；本应用外壳可滚动，故用 calc 高度 + 下限——
   uPlot 经 ResizeObserver 自适应）。 */
.cf-wb-shell {
  height: calc(100vh - 215px);
  min-height: 620px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-1);
}

.cfwb-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

/* Side panel column (reference App.vue .side, tokens resolve inside .cf-wb). /
   侧面板列（参考 App.vue 的 .side；令牌在 .cf-wb 内解析）。 */
.cfwb-side {
  width: 330px;
  flex: none;
  overflow: auto;
  padding: 10px;
  border-left: 1px solid var(--border);
  background: var(--bg-1);
  transition: background-color var(--speed) ease;
}
</style>
