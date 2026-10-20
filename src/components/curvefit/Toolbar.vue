<script setup lang="ts">
/**
 * Top toolbar: import / demo / smooth / auto-detect / fit / stop / abort /
 * undo / redo / export. Dialogs are mounted from here.
 */
import { computed, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import Dropdown, { type MenuItem } from './Dropdown.vue'
import SmoothDialog from './SmoothDialog.vue'
import DetectDialog from './DetectDialog.vue'
import type { SmoothMethod } from '@/lib/pwcore/shared/types'
import { platform } from '@/lib/curvefit/platform/platform'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { useFit, startFit, stopFit, abortFit } from '@/lib/curvefit/stores/fit'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { canRedo, canUndo, redo, undo } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { useUi } from '@/lib/curvefit/stores/ui'
import { DEMO_LABELS, importFromPlatform, loadDemoSet } from '@/lib/curvefit/stores/session'
import { buildDataFitCsv, buildPeakParamsCsv, buildReportTxt, saveTextFile } from '@/lib/curvefit/utils/exporters'

const sp = useSpectrum()
const fit = useFit()
const pk = usePeaks()
const ui = useUi()

const fitRunning = computed(() => fit.status.value === 'running')

const smoothMethod = ref<SmoothMethod | null>(null)
const detectMethod = ref<'residual' | 'deriv2' | null>(null)

const demoItems: MenuItem[] = DEMO_LABELS.map((d) => ({ id: d.id, label: d.label }))

const smoothItems: MenuItem[] = [
  { id: 'sg', label: 'Savitzky-Golay…', hint: '窗口+阶数' },
  { id: 'movavg', label: '移动平均…', hint: '窗口' },
  { id: 'fftLowpass', label: 'FFT 低通…', hint: '截止频率' },
]

const detectItems: MenuItem[] = [
  { id: 'residual', label: '残差法 (残差法)…' },
  { id: 'deriv2', label: '二阶导数法 (残差法I)…' },
]

const exportItems: MenuItem[] = [
  { id: 'params', label: '参数 CSV', icon: 'export' },
  { id: 'datafit', label: '数据+拟合 CSV', icon: 'export' },
  { id: 'png', label: '图表 PNG', icon: 'chart' },
  { id: 'report', label: '报告 TXT', icon: 'file' },
]

function onSmooth(id: string): void {
  if (!sp.ready.value) {
    pushToast('warn', '没有数据：请先导入数据')
    return
  }
  smoothMethod.value = id as SmoothMethod
}

function onDetect(id: string): void {
  if (!sp.ready.value) {
    pushToast('warn', '没有数据：请先导入数据')
    return
  }
  detectMethod.value = id === 'deriv2' ? 'deriv2' : 'residual'
}

async function onExport(id: string): Promise<void> {
  if (id === 'params') {
    if (pk.list.value.length === 0) {
      pushToast('warn', '尚无峰参数可导出')
      return
    }
    await saveTextFile('pw_params.csv', buildPeakParamsCsv())
    pushToast('success', '参数 CSV 已导出')
  } else if (id === 'datafit') {
    if (!sp.ready.value) {
      pushToast('warn', '没有数据')
      return
    }
    await saveTextFile('pw_data_fit.csv', buildDataFitCsv())
    pushToast('success', '数据+拟合 CSV 已导出')
  } else if (id === 'report') {
    await saveTextFile('pw_report.txt', buildReportTxt())
    pushToast('success', '报告 TXT 已导出')
  } else if (id === 'png') {
    const chart = ui.chart.value
    if (!chart) {
      pushToast('warn', '图表尚未就绪')
      return
    }
    const png = await chart.exportPng()
    if (!png) {
      pushToast('error', 'PNG 导出失败')
      return
    }
    await platform.saveDataFile('pw_chart.png', png)
    pushToast('success', '图表 PNG 已导出')
  }
}

function onUndo(): void {
  const cmd = undo()
  if (cmd) pushToast('info', `撤销：${cmd.label}`)
}

function onRedo(): void {
  const cmd = redo()
  if (cmd) pushToast('info', `重做：${cmd.label}`)
}
</script>

<template>
  <div class="toolbar">
    <button class="btn" title="导入 PRN / CSV / TXT 数据" @click="importFromPlatform">
      <AppIcon name="import" :size="15" />导入数据
    </button>
    <Dropdown label="示例数据" :items="demoItems" @select="loadDemoSet" />

    <span class="vsep" />

    <Dropdown label="平滑" :items="smoothItems" :disabled="!sp.ready.value" @select="onSmooth" />
    <Dropdown label="自动寻峰" :items="detectItems" :disabled="!sp.ready.value" @select="onDetect" />

    <span class="vsep" />

    <button class="btn primary" :disabled="!sp.ready.value" title="运行拟合引擎" @click="startFit({ stepTo: 'report' })">
      <span v-if="fitRunning" class="spinner" />
      <AppIcon v-else name="play" :size="14" />拟合
    </button>
    <button class="btn" :disabled="!fitRunning" title="停止并保留：停在当前最优参数" @click="stopFit">
      <AppIcon name="stop" :size="14" />停止
    </button>
    <button class="btn" :disabled="!fitRunning" title="中止并回滚：中止并回滚到拟合前" @click="abortFit">
      <AppIcon name="abort" :size="14" />中止
    </button>

    <span class="vsep" />

    <button class="btn icon-only" :disabled="!canUndo" title="撤销 (Ctrl+Z)" @click="onUndo">
      <AppIcon name="undo" :size="15" />
    </button>
    <button class="btn icon-only" :disabled="!canRedo" title="重做 (Ctrl+Shift+Z)" @click="onRedo">
      <AppIcon name="redo" :size="15" />
    </button>

    <span class="spring" />

    <Dropdown label="导出" :items="exportItems" align="right" @select="onExport" />

    <SmoothDialog v-if="smoothMethod" :method="smoothMethod" @close="smoothMethod = null" />
    <DetectDialog v-if="detectMethod" :method="detectMethod" @close="detectMethod = null" />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 7px;
  /* Wrap instead of scrolling: with many buttons a horizontal scrollbar
     pushed the right-side dropdowns (示例数据 / 导出) off-screen and clipped
     their absolutely-positioned menus. Wrapping keeps every control visible
     and lets menus escape the bar. / 换行而非横向滚动：按钮多时滚动条会把
     右侧下拉（示例数据/导出）挤到不可见处，且横向 overflow 会裁掉绝对定位
     的菜单。换行保证全部控件可见、菜单不被裁切。 */
  flex-wrap: wrap;
  height: auto;
  min-height: 44px;
  padding: 6px 10px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  flex: none;
  transition: background-color var(--speed) ease;
}
.vsep {
  width: 1px;
  height: 18px;
  background: var(--border);
  margin: 0 3px;
}
/* Never let the flexbox squeeze buttons/dropdowns below their natural width:
   overflow-x on the bar handles narrow windows instead. */
.toolbar > * {
  flex: none;
}
.spring {
  flex: 1;
}
</style>
