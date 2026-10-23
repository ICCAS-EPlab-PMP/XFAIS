<script setup lang="ts">
/**
 * 基线页（对应原版两种基线路线，二选一）：
 *  A) 自动拟合 Baseline（预处理扣除）：自动检测点集 → 图上点选/段编辑即时
 *     重拟合 → 扣除为新数据（原版 ch.6 p.6-1..6-6）。
 *  B) 参与拟合的参数化基线（8 函数）：“预拟合基线”得到初值并自动打开
 *     扣除预览（原版 As-If 语义：扣除视图只用于放峰，拟合始终用原始数据
 *     + 基线联合建模）。
 */
import { computed, onBeforeUnmount, watch } from 'vue'
import AppIcon from '../AppIcon.vue'
import HelpTip from '../HelpTip.vue'
import ParamRow from '../ParamRow.vue'
import { BASELINE_FN_MAP } from '@/lib/pwcore/shared/registry'
import {
  BASELINE_OPTIONS,
  setBaselineEnabled,
  setBaselineFn,
  setBaselineLocked,
  setBaselineParam,
  usePeaks,
} from '@/lib/curvefit/stores/peaks'
import { useFit, startFit, resetFitState } from '@/lib/curvefit/stores/fit'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { useUi } from '@/lib/curvefit/stores/ui'
import { pushCommand } from '@/lib/curvefit/stores/undo'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { BASELINE_METHODS, BASELINE_MODELS, useBaselineWork } from '@/lib/curvefit/stores/baseline-work'

const bl = useBaselineWork()
const pk = usePeaks()
const fit = useFit()
const sp = useSpectrum()
const ui = useUi()

const meta = () => BASELINE_FN_MAP.get(pk.baseline.fn)

// -- route A: 自动拟合 Baseline ----------------------------------------------

const methodHint = computed(
  () => BASELINE_METHODS.find((m) => m.id === bl.opts.method)?.hint ?? '',
)

const stats = computed(() => {
  // `used` is mutated in place; `version` is the change signal.
  void bl.version.value
  const f = bl.fit.value
  if (!f || !bl.active.value) return null
  const u = bl.used.value
  let used = 0
  if (u) for (let i = 0; i < u.length; i++) used += u[i]
  return {
    model: f.model,
    used,
    n: u ? u.length : sp.meta.n,
    r2: Number.isFinite(f.r2) ? f.r2.toFixed(4) : '—',
  }
})

function onMethodChange(e: Event): void {
  bl.opts.method = (e.target as HTMLSelectElement).value as (typeof BASELINE_METHODS)[number]['id']
}

function onModelChange(e: Event): void {
  bl.opts.model = (e.target as HTMLSelectElement).value as (typeof BASELINE_MODELS)[number]['id']
}

// Changing method/model/tolerance re-runs detection while point-select mode is on.
let rerunTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => [bl.opts.method, bl.opts.model, bl.opts.tol],
  () => {
    if (!bl.active.value) return
    if (rerunTimer !== null) clearTimeout(rerunTimer)
    rerunTimer = setTimeout(() => {
      rerunTimer = null
      if (bl.active.value) bl.detect()
    }, 200)
  },
)

onBeforeUnmount(() => {
  if (rerunTimer !== null) clearTimeout(rerunTimer)
})

function applySubtracted(): void {
  const ny = bl.buildSubtracted()
  if (!ny) {
    pushToast('error', '扣除失败：基线或数据不可用')
    return
  }
  const old = sp.replaceY(ny)
  if (!old) {
    pushToast('error', '扣除失败：数据不可用')
    return
  }
  bl.clear()
  resetFitState()
  pushCommand({
    label: '扣除 自动拟合 基线',
    undo: () => {
      sp.restoreY(old)
      resetFitState()
    },
    redo: () => {
      sp.replaceY(ny)
      resetFitState()
    },
  })
  pushToast('success', '已扣除 自动拟合 基线（生成新数据，Ctrl+Z 可撤销）')
}

// -- route B: parametric baseline joined into the fit -----------------------

function onFnChange(id: string): void {
  const before = pk.exportSnapshot()
  setBaselineFn(id as typeof pk.baseline.fn)
  const after = pk.exportSnapshot()
  pushCommand({
    label: '更换基线函数',
    undo: () => pk.importSnapshot(before),
    redo: () => pk.importSnapshot(after),
  })
}

function onParam(key: string, v: number): void {
  const beforeV = pk.baseline.p[key]
  setBaselineParam(key, v)
  pushCommand({
    label: '基线参数',
    undo: () => setBaselineParam(key, beforeV),
    redo: () => setBaselineParam(key, v),
  })
}

function onLock(key: string, v: boolean): void {
  setBaselineLocked(key, v)
}

function fitBaselineOnly(): void {
  if (!sp.ready.value) {
    pushToast('warn', '没有数据：请先导入数据')
    return
  }
  void startFit({
    baselineOnly: true,
    onDone: () => {
      // As-If semantics: the subtracted view exists to make peak placement
      // easy; the actual fit keeps using the original data + joint baseline.
      ui.subtractPreview.value = true
      pushToast('info', '已预拟合基线并打开扣除预览（用于放峰）；拟合仍将联合基线使用原始数据')
    },
  })
}
</script>

<template>
  <div class="panel">
    <div class="panel-title">
      <AppIcon name="baseline" :size="13" />基线
      <!-- 2026-10-23 用户要求：两条路线的说明改为标题行的 ? 图标。 -->
      <span class="pt-help">
        <HelpTip
          :size="17"
          text="两条路线二选一：路线 A 在拟合前把基线从数据中扣除（预处理）；路线 B 让参数化基线作为模型的一部分参与联合拟合。"
        />
      </span>
    </div>
    <div class="content">
      <!-- ============================ route A ============================ -->
      <div class="sec-label route-head">
        <span class="route-letter">A</span>
        <span class="route-title">自动拟合 Baseline</span>
        <span class="route-tag">预处理扣除</span>
      </div>

      <div class="route-card">
        <label class="inline">
          <span class="k">方法</span>
          <select
            class="select"
            :value="bl.opts.method"
            :title="methodHint"
            @change="onMethodChange"
          >
            <option v-for="m in BASELINE_METHODS" :key="m.id" :value="m.id" :title="m.hint">
              {{ m.label }}
            </option>
          </select>
        </label>
        <p class="hint mono-hint">{{ methodHint }}</p>

        <label class="inline">
          <span class="k">模型</span>
          <select class="select" :value="bl.opts.model" @change="onModelChange">
            <option v-for="m in BASELINE_MODELS" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
        </label>

        <label
          class="inline"
          title="点太多（峰翼混入）→ 减小；点太少 → 增大"
        >
          <span class="k">容差</span>
          <input
            v-model.number="bl.opts.tol"
            class="range"
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            title="点太多（峰翼混入）→ 减小；点太少 → 增大"
          />
          <span class="num val">{{ bl.opts.tol.toFixed(1) }}</span>
        </label>

        <div class="row-btns">
          <button class="btn primary" :disabled="!sp.ready.value" @click="bl.detect()">
            <AppIcon name="baseline" :size="13" />自动检测基线
          </button>
        </div>

        <div v-if="stats" class="stats">
          模型 <b>{{ stats.model }}</b> · 基线点 <b class="num">{{ stats.used }}/{{ stats.n }}</b> · R²
          <b class="num">{{ stats.r2 }}</b>
        </div>
      </div>

      <template v-if="bl.active.value">
        <div class="sec-label sec-head">
          手动点选
          <HelpTip
            :size="14"
            text="图上：单击点 = 加入/退出基线；向右拖 = 排除一段；向左拖 = 恢复一段。每次操作立即重新拟合。"
          />
        </div>
        <div class="route-card">
          <div class="row-btns">
            <button class="btn sm" :disabled="!sp.ready.value" @click="bl.detect()">
              <AppIcon name="baseline" :size="13" />重新自动检测
            </button>
            <button class="btn sm" @click="bl.clear()">退出点选模式</button>
          </div>
        </div>

        <div class="sec-label">扣除</div>
        <div class="route-card">
          <label class="checkbox">
            <input v-model="bl.opts.zeroNegative" type="checkbox" />
            <span class="box"><AppIcon name="check" :size="10" /></span>
            Zero Negative（负值置零）
          </label>
          <div class="row-btns">
            <button
              class="btn primary"
              :disabled="!sp.ready.value || !bl.fit.value"
              title="将 y − 基线 作为新数据（可撤销）"
              @click="applySubtracted"
            >
              <AppIcon name="check" :size="13" />扣除为新数据
            </button>
          </div>
          <p class="hint">扣除后点选模式自动退出；正式拟合请在新数据上重新 自动拟合。</p>
        </div>
      </template>

      <!-- ============================ route B ============================ -->
      <div class="sec-label sec-head route-head">
        <span class="route-letter">B</span>
        <span class="route-title">参与拟合的参数化基线</span>
        <!-- 2026-10-23 用户要求：预拟合/As-If 说明改为 ? 图标。 -->
        <span class="pt-help">
          <HelpTip
            :size="14"
            text="预拟合 = 仅拟合基线并打开扣除预览（用于放峰）；正式拟合始终以原始数据 + 基线联合建模（原版 As-If 语义）。"
          />
        </span>
      </div>

      <label class="inline">
        <span class="k">函数</span>
        <select class="select" :value="pk.baseline.fn" @change="onFnChange(($event.target as HTMLSelectElement).value)">
          <option v-for="o in BASELINE_OPTIONS" :key="o.id" :value="o.id">{{ o.name }} — {{ o.label }}</option>
        </select>
      </label>
      <p v-if="meta()" class="hint mono-hint">{{ meta()!.notes }}</p>

      <label class="checkbox" style="margin-top: 8px">
        <input
          type="checkbox"
          :checked="pk.baseline.enabled"
          @change="setBaselineEnabled(($event.target as HTMLInputElement).checked)"
        />
        <span class="box"><AppIcon name="check" :size="10" /></span>
        拟合时同步优化基线参数
      </label>

      <template v-if="meta() && meta()!.params.length > 0">
        <div class="sec-label">参数</div>
        <ParamRow
          v-for="pm in meta()!.params"
          :key="pm.key"
          :label="pm.label"
          :param-key="pm.key"
          :model-value="pk.baseline.p[pm.key] ?? 0"
          :locked="!!pk.baseline.locked[pm.key]"
          :min="pm.min"
          :max="pm.max"
          @update:model-value="(v) => onParam(pm.key, v)"
          @update:locked="(v) => onLock(pm.key, v)"
        />
      </template>
      <p v-else class="hint">该基线无参数。</p>

      <div class="row-btns">
        <button class="btn sm" :disabled="fit.status.value === 'running' || !sp.ready.value" @click="fitBaselineOnly">
          <AppIcon name="fit" :size="13" />预拟合基线（放峰视图）
        </button>
      </div>

      <div class="sec-label">预览</div>
      <label class="checkbox">
        <input v-model="ui.subtractPreview.value" type="checkbox" />
        <span class="box"><AppIcon name="check" :size="10" /></span>
        在图上预览扣除基线后的数据
      </label>
    </div>
  </div>
</template>

<style scoped>
/* 2026-10-23 用户要求：路线 A/B 标签加粗加大，一眼可辨。 */
.route-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 14px;
}
.route-letter {
  flex: none;
  font-size: 1.15rem;
  font-weight: 800;
  line-height: 1;
  color: var(--accent);
}
.route-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--text-1);
}
.route-tag {
  font-size: var(--fs-small);
  font-weight: 400;
  color: var(--text-2);
}
/* 2026-10-23 用户要求：区块标题行右侧放 ? 图标。 */
.sec-head {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}
.pt-help {
  display: inline-flex;
  align-items: center;
}
.panel-title .pt-help,
.sec-head .pt-help {
  margin-left: auto;
}
/* 侧栏仅 330px 且 overflow:auto，默认居中/向上的气泡会被裁剪——
   标题行气泡贴右向下展开，区块气泡贴右向上展开。 */
.panel-title :deep(.help-pop) {
  left: auto;
  right: 0;
  top: calc(100% + 6px);
  bottom: auto;
  width: 252px;
  max-width: 252px;
  transform: translateY(2px) !important;
  text-transform: none;
  letter-spacing: normal;
}
.sec-head :deep(.help-pop) {
  left: auto;
  right: 0;
  width: 240px;
  max-width: 240px;
  transform: translateY(2px) !important;
}
.route-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  margin: 2px 0 8px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.stats {
  padding: 6px 8px;
  font-size: var(--fs-small);
  color: var(--text-2);
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.stats b {
  color: var(--text-1);
  font-weight: 600;
}
.content {
  padding: 2px 12px 12px;
}
.inline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
}
.inline .k {
  flex: none;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.inline .select {
  flex: 1;
  min-width: 0;
}
.mono-hint {
  margin: 2px 0 4px;
  font-family: var(--mono);
  font-size: 10.5px;
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
.row-btns {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-top: 2px;
}
</style>
