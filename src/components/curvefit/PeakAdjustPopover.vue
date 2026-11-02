<script setup lang="ts">
/**
 * 峰调整 popover（右键主锚打开）：换函数（保 a0/a1/a2）、数值调参 +
 * 锁定、重置（还原开窗时状态）、删除。常驻期间图上锚点仍可点选。
 */
import { computed, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import ParamRow from './ParamRow.vue'
import type { ParamLocks, ParamValues } from '@/lib/pwcore/shared/types'
import type { PeakFnId } from '@/lib/pwcore/shared/registry'
import { PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { bumpEdit, changePeakFn, removePeak, setParam, setParamLocked, usePeaks } from '@/lib/curvefit/stores/peaks'
import { useUi } from '@/lib/curvefit/stores/ui'
import { pushCommand } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { FN_GROUPS } from '@/lib/curvefit/stores/peaks'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { estimateLocalWidth } from '@/lib/fitEngine'
import { guardContextFrom, repairPeakParams, widthKeysOfSpec } from '@/lib/curvefit/utils/paramGuard'

const ui = useUi()
const pk = usePeaks()
const sp = useSpectrum()

interface OpenState {
  peakId: string
  p: ParamValues
  locked: ParamLocks
  fn: PeakFnId
  left: number
  top: number
}

const state = ref<OpenState | null>(null)

watch(
  () => ui.popover.value,
  (pop) => {
    if (!pop) {
      state.value = null
      return
    }
    const peak = pk.list.value.find((p) => p.id === pop.peakId)
    if (!peak) {
      ui.popover.value = null
      return
    }
    const W = 252
    const H = 380
    const left = Math.min(Math.max(8, pop.cx + 14), window.innerWidth - W - 8)
    const top = Math.min(Math.max(8, pop.cy - H / 3), window.innerHeight - Math.min(H, 320) - 8)
    state.value = {
      peakId: pop.peakId,
      p: { ...peak.p },
      locked: { ...peak.locked },
      fn: peak.fn,
      left,
      top,
    }
  },
)

const peak = computed(() => (state.value ? pk.list.value.find((p) => p.id === state.value!.peakId) : undefined))
const meta = computed(() => (peak.value ? PEAK_FN_MAP.get(peak.value.fn) : undefined))

function close(): void {
  ui.popover.value = null
}

function onFnChange(id: string): void {
  const p = peak.value
  if (!p) return
  const snap = pk.exportSnapshot()
  changePeakFn(p, id as PeakFnId)
  const after = pk.exportSnapshot()
  pushCommand({
    label: '更换峰函数',
    undo: () => pk.importSnapshot(snap),
    redo: () => pk.importSnapshot(after),
  })
}

function onParam(key: string, v: number): void {
  const p = peak.value
  if (!p) return
  if (!Number.isFinite(v)) return
  // Same data-resolvable width floor as the chart anchors / PeaksPanel
  // (see utils/paramGuard.ts): a degenerate width can never be fitted again.
  // 与图上锚点 / 放峰面板相同的数据可分辨宽度下限（见 utils/paramGuard.ts）：
  // 退化宽度会让该峰此后再也无法拟合。
  let next = v
  const xs = sp.x.value
  const ys = sp.y.value
  const ctx = xs && ys ? guardContextFrom(xs, ys) : null
  if (ctx && widthKeysOfSpec(p).includes(key)) {
    const seed = xs && ys ? estimateLocalWidth(xs, ys, p.p['a1'] ?? ctx.xMid) : null
    const probe = { ...p, p: { ...p.p, [key]: next } }
    repairPeakParams(probe, ctx, Number.isFinite(seed as number) ? (seed as number) : null)
    next = probe.p[key]
    // Same feedback as the peaks panel: never change a typed value silently.
    // 与放峰面板一致：绝不静默改变用户输入。
    if (next !== v) {
      pushToast('warn', `宽度 ${String(Number(v.toPrecision(4)))} 超出数据可分辨范围，已修正为 ${String(Number(next.toPrecision(4)))}`)
    }
  }
  const beforeV = p.p[key]
  setParam(p, key, next)
  pushCommand({
    label: '峰参数',
    undo: () => setParam(p, key, beforeV),
    redo: () => setParam(p, key, next),
  })
}

function onLock(key: string, v: boolean): void {
  const p = peak.value
  if (!p) return
  setParamLocked(p, key, v)
}

function onReset(): void {
  const p = peak.value
  const st = state.value
  if (!p || !st) return
  p.p = { ...st.p }
  p.locked = { ...st.locked }
  pk.curvesVersion.value++
  bumpEdit()
}

function onDelete(): void {
  const p = peak.value
  if (!p) return
  const snap = pk.exportSnapshot()
  removePeak(p.id)
  const after = pk.exportSnapshot()
  pushCommand({
    label: '删峰',
    undo: () => pk.importSnapshot(snap),
    redo: () => pk.importSnapshot(after),
  })
  pushToast('info', '峰已删除（Ctrl+Z 可撤销）')
  close()
}
</script>

<template>
  <teleport to="body">
    <div
      v-if="state && peak"
      class="pop panel"
      :style="{ left: state.left + 'px', top: state.top + 'px' }"
      @pointerdown.stop
    >
      <header class="head">
        <span class="dot" :style="{ background: peak.color }" />
        <span class="t">峰调整</span>
        <button class="btn ghost icon-only sm" title="关闭" @click="close">
          <AppIcon name="close" :size="13" />
        </button>
      </header>

      <label class="inline">
        <span class="k">函数</span>
        <select class="select" :value="peak.fn" @change="onFnChange(($event.target as HTMLSelectElement).value)">
          <optgroup v-for="g in FN_GROUPS" :key="g.family" :label="g.label">
            <option v-for="f in g.fns" :key="f.id" :value="f.id">{{ f.name }} — {{ f.label }}</option>
          </optgroup>
        </select>
      </label>
      <p v-if="meta" class="hint mono-hint">{{ meta.notes }}</p>

      <div class="params">
        <ParamRow
          v-for="pm in meta?.params"
          :key="pm.key"
          :label="pm.label"
          :param-key="pm.key"
          :model-value="peak.p[pm.key] ?? 0"
          :locked="!!peak.locked[pm.key]"
          :min="pm.min"
          :max="pm.max"
          compact
          @update:model-value="(v) => onParam(pm.key, v)"
          @update:locked="(v) => onLock(pm.key, v)"
        />
      </div>

      <footer class="foot">
        <button class="btn sm" title="还原开窗时的参数" @click="onReset">
          <AppIcon name="reset" :size="12" />重置
        </button>
        <button class="btn sm danger" @click="onDelete"><AppIcon name="trash" :size="12" />删除</button>
      </footer>
    </div>
  </teleport>
</template>

<style scoped>
.pop {
  position: fixed;
  width: 252px;
  z-index: 250;
  padding: 0;
  box-shadow: var(--shadow-3);
  animation: pop-in 0.14s ease;
}
@keyframes pop-in {
  from {
    opacity: 0;
    transform: translateY(4px) scale(0.98);
  }
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px 6px 12px;
  border-bottom: 1px solid var(--border);
}
.head .t {
  font-weight: 600;
  font-size: 12px;
  flex: 1;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--bg-3);
}
.inline {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 0;
}
.inline .k {
  flex: none;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.inline .select {
  flex: 1;
  min-width: 0;
  height: 24px;
}
.mono-hint {
  margin: 4px 12px 0;
  font-family: var(--mono);
  font-size: 10px;
  max-height: 42px;
  overflow: hidden;
}
.params {
  padding: 6px 12px 2px;
  max-height: 200px;
  overflow: auto;
}
.foot {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px 10px;
  border-top: 1px solid var(--border);
}
</style>
