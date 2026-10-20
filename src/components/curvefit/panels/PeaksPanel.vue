<script setup lang="ts">
/**
 * 放峰页（自动拟合 工作台）：一键"放峰+拟合"（原版 auto placement 主流程），
 * 之后调整锚点/参数会自动重拟合（Adjust Fit 循环）；下方保留手动放置与
 * 数值编辑。
 */
import { computed, ref } from 'vue'
import AppIcon from '../AppIcon.vue'
import ParamRow from '../ParamRow.vue'
import type { PeakFnId } from '@/lib/pwcore/shared/registry'
import { PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { FN_GROUPS, createPeak, removePeak, selectPeak, setParam, setParamLocked, setPeakEnabled, usePeaks } from '@/lib/curvefit/stores/peaks'
import { useUi } from '@/lib/curvefit/stores/ui'
import { pushCommand } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { detectPeaks, evalPeakAt, estimateFwhm } from '@/lib/curvefit/core-bridge/engine'
import { estimateLocalWidth } from '@/lib/fitEngine'
import { startFit } from '@/lib/curvefit/stores/fit'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { fmtSig } from '@/lib/curvefit/utils/format'
import { guardContextFrom, repairPeakParams, widthKeysOfSpec } from '@/lib/curvefit/utils/paramGuard'

const pk = usePeaks()
const ui = useUi()
const sp = useSpectrum()

// -- 自动拟合 one-click (place + fit, the reference application auto placement flow) ------------
const afMethod = ref<'residual' | 'deriv2'>('residual')
const afSens = ref(0.6)
const afMax = ref(12)
const afRunning = ref(false)

function run自动拟合(): void {
  const xv = sp.x.value
  const yv = sp.y.value
  if (!xv || !yv) {
    pushToast('warn', '没有数据：请先导入数据或加载示例')
    return
  }
  afRunning.value = true
  try {
    let found
    try {
      found = detectPeaks(xv, yv, {
        method: afMethod.value,
        sensitivity: afSens.value,
        maxPeaks: afMax.value,
        fn: pk.defaultFn.value,
        smoothWindow: 0,
      })
    } catch (err) {
      pushToast('error', `寻峰失败：${err instanceof Error ? err.message : String(err)}`)
      return
    }
    if (found.length === 0) {
      pushToast('warn', '未检出峰：试着提高灵敏度或更换方法')
      return
    }
    // Replacing placements mirrors the original: changing scan settings
    // discards custom placements and rebuilds the autoscan.
    const snap = pk.exportSnapshot()
    while (pk.list.value.length > 0) removePeak(pk.list.value[pk.list.value.length - 1].id)
    for (const d of found) {
      createPeak(pk.defaultFn.value, d.x0, d.y0, Math.max(d.width, 1e-12))
    }
    const after = pk.exportSnapshot()
    pushCommand({
      label: `自动拟合 放峰 (+${found.length})`,
      undo: () => pk.importSnapshot(snap),
      redo: () => pk.importSnapshot(after),
    })
    pushToast('success', `自动拟合：已放置 ${found.length} 个峰，开始拟合…`)
    void startFit({})
  } finally {
    afRunning.value = false
  }
}

const rows = computed(() =>
  pk.list.value.map((p, i) => {
    const meta = PEAK_FN_MAP.get(p.fn)
    const res = pk.resultById.value.get(p.id)
    const h = evalPeakAt(p.fn, p.p, p.p.a1)
    const fwhm = res ? res.fwhm : estimateFwhm(p.fn, p.p, h)
    return {
      p,
      index: i + 1,
      fnLabel: meta?.name ?? p.fn,
      center: res ? res.center : p.p.a1,
      height: res ? res.height : h,
      fwhm,
    }
  }),
)

function onDefaultFn(id: string): void {
  pk.defaultFn.value = id as PeakFnId
}

function onDelete(id: string): void {
  const snap = pk.exportSnapshot()
  removePeak(id)
  const after = pk.exportSnapshot()
  pushCommand({
    label: '删峰',
    undo: () => pk.importSnapshot(snap),
    redo: () => pk.importSnapshot(after),
  })
}

function onToggleEnabled(id: string): void {
  const peak = pk.list.value.find((p) => p.id === id)
  if (!peak) return
  const before = peak.enabled
  setPeakEnabled(id, !before)
  pushCommand({
    label: '峰 开/关',
    undo: () => setPeakEnabled(id, before),
    redo: () => setPeakEnabled(id, !before),
  })
}

function onLock(peakId: string, key: string, locked: boolean): void {
  const peak = pk.list.value.find((p) => p.id === peakId)
  setParamLocked(peak ?? null, key, locked)
}

/** Selected peak + registry metadata for the inline numeric editor. */
const selectedPeak = computed(() => {
  const id = pk.selectedId.value
  return id ? pk.list.value.find((p) => p.id === id) : undefined
})
const selectedMeta = computed(() => (selectedPeak.value ? PEAK_FN_MAP.get(selectedPeak.value.fn) : undefined))
const selectedIndex = computed(() => {
  const id = pk.selectedId.value
  const i = pk.list.value.findIndex((p) => p.id === id)
  return i >= 0 ? i + 1 : 0
})

function onParam(key: string, v: number): void {
  const p = selectedPeak.value
  if (!p) return
  if (!Number.isFinite(v)) return
  // Same data-resolvable width floor as the chart anchors (paramGuard.ts):
  // typing 0 / 1e-12 used to create a peak the fit can never recover because
  // its model is zero at every sample (zero width Jacobian) and the ±50 %
  // soft box keeps it collapsed on every later run.
  // 与图上锚点相同的数据可分辨宽度下限（paramGuard.ts）：输入 0 / 1e-12 曾会
  // 造出拟合永远无法恢复的峰——所有采样点模型为零（宽度雅可比为零），且 ±50%
  // 软约束每次又把它按回塌缩值。
  let next = v
  const xs = sp.x.value
  const ys = sp.y.value
  const ctx = xs && ys ? guardContextFrom(xs, ys) : null
  if (ctx && widthKeysOfSpec(p).includes(key)) {
    // Repair with the SAME data-driven policy the fit request uses, so the
    // value shown here is the value that will be fitted (a floor-only clamp
    // would still leave a barely-visible peak that cannot recover).
    // 用与拟合请求完全相同的数据驱动策略修正，保证这里显示的值就能被拟合
    // （只做下限钳制仍会留下几乎不可见、无法恢复的峰）。
    const seed = xs && ys ? estimateLocalWidth(xs, ys, p.p['a1'] ?? ctx.xMid) : null
    const probe = { ...p, p: { ...p.p, [key]: next } }
    repairPeakParams(probe, ctx, Number.isFinite(seed as number) ? (seed as number) : null)
    next = probe.p[key]
    // Tell the user when their typed width was replaced: silently changing an
    // input is worse than refusing it (the reported symptom started exactly
    // with a width the data cannot resolve). / 输入被替换时明确告知：静默改值
    // 比拒绝更糟（本缺陷正是从“数据无法分辨的宽度”开始的）。
    if (next !== v) {
      pushToast('warn', `宽度 ${fmtSig(v, 4)} 超出数据可分辨范围，已修正为 ${fmtSig(next, 4)}`)
    }
  }
  const before = p.p[key]
  setParam(p, key, next)
  pushCommand({
    label: '峰参数',
    undo: () => setParam(p, key, before),
    redo: () => setParam(p, key, next),
  })
}
</script>

<template>
  <div class="panel">
    <div class="panel-title"><AppIcon name="peak" :size="13" />放峰 · 自动拟合</div>
    <div class="content">
      <div class="autofit-card">
        <div class="sec-label">一键 自动拟合（放峰 + 拟合）</div>
        <label class="inline">
          <span class="k">峰函数</span>
          <select class="select" :value="pk.defaultFn.value" @change="onDefaultFn(($event.target as HTMLSelectElement).value)">
            <optgroup v-for="g in FN_GROUPS" :key="g.family" :label="g.label">
              <option v-for="f in g.fns" :key="f.id" :value="f.id">{{ f.name }} — {{ f.label }}</option>
            </optgroup>
          </select>
        </label>
        <div class="af-row">
          <label class="inline grow">
            <span class="k">方法</span>
            <select class="select" v-model="afMethod">
              <option value="residual">残差法 (I)</option>
              <option value="deriv2">二阶导数法 (II)</option>
            </select>
          </label>
          <label class="inline num-field">
            <span class="k">上限</span>
            <input class="field num" v-model.number="afMax" inputmode="numeric" />
          </label>
        </div>
        <label class="inline">
          <span class="k">灵敏度</span>
          <input type="range" class="range grow" min="0.05" max="0.95" step="0.05" v-model.number="afSens" />
          <span class="num val">{{ afSens.toFixed(2) }}</span>
        </label>
        <button class="btn primary grow autofit-btn" :disabled="!sp.ready.value || afRunning" @click="run自动拟合">
          <AppIcon name="play" :size="14" />自动拟合 拟合
        </button>
        <p class="hint">放置后立即可在图上拖锚点微调 —— 拟合会自动跟随每次调整（Adjust Fit）。</p>
      </div>

      <p class="hint body">
        手动：图上<b>左键单击任意位置</b>放峰（数据峰正上方也可以）。每个峰 3–4 个锚点：
        <b>主锚</b>（峰位/幅值）、<b>左右半高锚</b>（宽度；不对称峰左右独立）、
        <b>25% 形状锚</b>（4 参数峰）。单击主锚开/关；右键主锚 峰调整；
        <b>Alt+左键</b>点数据点 = 排除该点。
      </p>

      <div class="sec-label">峰列表（{{ pk.list.value.length }}）</div>
      <div v-if="rows.length === 0" class="hint none">尚未放峰 —— 切到图上点击即可创建第一个峰。</div>
      <div class="cards">
        <div
          v-for="r in rows"
          :key="r.p.id"
          class="card"
          :class="{ sel: pk.selectedId.value === r.p.id, off: !r.p.enabled }"
          @click="selectPeak(r.p.id)"
        >
          <span class="dot" :style="{ background: r.p.color }" />
          <div class="meta">
            <div class="line1">
              <span class="fn">{{ r.fnLabel }}</span>
              <span class="idx">#{{ r.index }}</span>
            </div>
            <div class="nums num">
              c {{ fmtSig(r.center, 5) }} · h {{ fmtSig(r.height, 4) }} · FWHM {{ fmtSig(r.fwhm, 4) }}
            </div>
          </div>
          <button
            class="tool"
            :title="r.p.enabled ? '停用（不参与拟合）' : '启用'"
            @click.stop="onToggleEnabled(r.p.id)"
          >
            <AppIcon :name="r.p.enabled ? 'eye' : 'eyeoff'" :size="14" />
          </button>
          <button class="tool danger" title="删除" @click.stop="onDelete(r.p.id)">
            <AppIcon name="trash" :size="14" />
          </button>
        </div>
      </div>
      <p v-if="rows.length > 0" class="hint tip">
        单击峰卡片选中后，可直接在下方编辑参数；锁定项不进入拟合参数向量。
      </p>

      <div v-if="selectedPeak && selectedMeta" class="sec-label">
        参数 · #{{ selectedIndex }} {{ selectedMeta.name }}
      </div>
      <div v-if="selectedPeak && selectedMeta" class="param-editor">
        <ParamRow
          v-for="pm in selectedMeta.params"
          :key="pm.key"
          :label="pm.label"
          :param-key="pm.key"
          :model-value="selectedPeak.p[pm.key] ?? 0"
          :locked="!!selectedPeak.locked[pm.key]"
          :min="pm.min"
          :max="pm.max"
          compact
          @update:model-value="(v) => onParam(pm.key, v)"
          @update:locked="(v) => onLock(selectedPeak!.id, pm.key, v)"
        />
      </div>

      <div v-if="pk.list.value.some((p) => Object.keys(p.locked).length > 0)" class="locks">
        <div v-for="p in pk.list.value.filter((q) => Object.keys(q.locked).length > 0)" :key="p.id" class="lockrow">
          <span class="dot sm" :style="{ background: p.color }" />
          <span class="mono">
            {{ Object.keys(p.locked).join(', ') }}
          </span>
          <button
            v-for="k in Object.keys(p.locked)"
            :key="k"
            class="chip"
            :title="'解锁 ' + k"
            @click="onLock(p.id, k, false)"
          >
            <AppIcon name="unlock" :size="11" />{{ k }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>

.autofit-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  margin: 2px 0 10px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.af-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.af-row .grow, .inline.grow {
  flex: 1;
  min-width: 0;
}
.num-field .field {
  width: 56px;
  text-align: right;
}
.range {
  flex: 1;
  min-width: 0;
  accent-color: var(--accent);
}
.val {
  min-width: 34px;
  text-align: right;
}
.autofit-btn {
  justify-content: center;
}
.content {
  padding: 2px 12px 12px;
}
.inline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 8px;
}
.inline .k {
  flex: none;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.param-editor {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 8px;
  margin: 2px 0 4px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.inline .select {
  flex: 1;
  min-width: 0;
}
.hint b {
  color: var(--text-1);
}
/* Body-level explanation (placement / Alt+click exclusion): --text-3 is only
   ~2.6:1 on the white panel, so the main how-to paragraph uses --text-2. */
.hint.body {
  color: var(--text-2);
}
.none {
  padding: 6px 0;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color var(--speed-fast) ease, background-color var(--speed-fast) ease;
}
.card:hover {
  background: var(--bg-3);
}
.card.sel {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.card.off {
  opacity: 0.55;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex: none;
  box-shadow: 0 0 0 2px var(--bg-1);
}
.dot.sm {
  width: 7px;
  height: 7px;
}
.meta {
  flex: 1;
  min-width: 0;
}
.line1 {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.fn {
  font-weight: 600;
  font-size: 12px;
}
.idx {
  font-size: var(--fs-small);
  color: var(--text-3);
}
.nums {
  font-size: var(--fs-small);
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  transition: background-color var(--speed-fast) ease, color var(--speed-fast) ease;
}
.tool:hover {
  background: var(--bg-1);
  color: var(--text-1);
}
.tool.danger:hover {
  color: var(--danger);
}
.tip {
  margin-top: 8px;
}
.locks {
  margin-top: 8px;
  border-top: 1px dashed var(--border);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.lockrow {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.mono {
  font-family: var(--mono);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 18px;
  padding: 0 6px;
  border: 1px solid var(--warning);
  border-radius: 9px;
  background: var(--warning-soft);
  color: var(--warning);
  font-size: 10px;
  cursor: pointer;
}
</style>
