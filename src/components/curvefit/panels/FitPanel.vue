<script setup lang="ts">
/** 拟合页：引擎选项 + Fast/Full 模式 + 迭代遥测面板 + r² 进度条。 */
import { computed } from 'vue'
import AppIcon from '../AppIcon.vue'
import type { RobustMethod } from '@/lib/pwcore/shared/types'
import { startFit, stopFit, useFit } from '@/lib/curvefit/stores/fit'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { fmtMs, fmtSci, fmtSig } from '@/lib/curvefit/utils/format'

const fit = useFit()
const sp = useSpectrum()

const ROBUST: { id: RobustMethod; label: string; hint: string }[] = [
  { id: 'ls', label: 'LS', hint: '最小二乘（默认）' },
  { id: 'lad', label: 'LAD', hint: '最小绝对偏差（抗离群）' },
  { id: 'lorentz', label: 'Lorentz', hint: 'Lorentz 损失（手册推荐抗离群）' },
  { id: 'p7lim', label: 'P7 Lim', hint: 'Pearson VII 限差（最强抗离群，手册 p.6-79）' },
]

/** Peak Fn Constraints rows (original shipped defaults: a0 25% / a1 5% / a2 50% ON). */
type ConstraintKey = 'a0' | 'a1' | 'a2' | 'a3' | 'a4'
const CONSTRAINT_ROWS: { key: ConstraintKey; label: string; hint: string }[] = [
  { key: 'a0', label: 'a0 幅值', hint: '幅值相对初始估计的最大变化（保号）' },
  { key: 'a1', label: 'a1 中心', hint: '中心漂移上限，防小峰游走进相邻峰' },
  { key: 'a2', label: 'a2 宽度', hint: '宽度变化上限，防塌缩到零宽' },
  { key: 'a3', label: 'a3 形状', hint: '第三参数（原版默认关）' },
  { key: 'a4', label: 'a4 形状', hint: '第四参数（原版默认关）' }
]

function onConstraintPct(key: ConstraintKey, e: Event): void {
  const v = parseFloat((e.target as HTMLInputElement).value)
  const c = fit.options.constraints[key]
  c.pct = Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : c.pct
}

const r2Pct = computed(() => {
  const r = fit.telemetry.r2
  if (!Number.isFinite(r)) return 0
  return Math.max(0, Math.min(100, r * 100))
})

const r2Display = computed(() => (Number.isFinite(fit.telemetry.r2) ? fit.telemetry.r2.toFixed(5) : '—'))

function onExtent(e: Event): void {
  const v = parseInt((e.target as HTMLInputElement).value, 10)
  fit.options.fitExtent = Number.isFinite(v) && v >= 1 ? Math.min(v, 100000) : 1
}

function onMaxIter(e: Event): void {
  const v = parseInt((e.target as HTMLInputElement).value, 10)
  fit.options.maxIter = Number.isFinite(v) && v >= 1 ? Math.min(v, 100000) : 500
}
</script>

<template>
  <div class="panel">
    <div class="panel-title"><AppIcon name="fit" :size="13" />拟合</div>
    <div class="content">
      <div class="grid2">
        <label class="inline">
          <span class="k">maxIter</span>
          <input class="field num" :value="fit.options.maxIter" inputmode="numeric" @change="onMaxIter" />
        </label>
        <label class="inline">
          <span class="k">fitExtent</span>
          <input class="field num" :value="fit.options.fitExtent" inputmode="numeric" @change="onExtent" />
        </label>
      </div>

      <div class="slider-row">
        <span class="k">convDigits</span>
        <input
          v-model.number="fit.options.convDigits"
          class="slider"
          type="range"
          min="3"
          max="14"
          step="1"
        />
        <span class="num val">{{ fit.options.convDigits }}</span>
      </div>
      <p class="hint">χ² 连续 5 次迭代稳定到该有效位数即收敛（原版默认 6）。</p>

      <div class="sec-label">稳健方法</div>
      <div class="seg">
        <button
          v-for="r in ROBUST"
          :key="r.id"
          :class="{ on: fit.options.robust === r.id }"
          :title="r.hint"
          @click="fit.setRobust(r.id)"
        >
          {{ r.label }}
        </button>
      </div>

      <div class="sec-label">峰函数约束 <span class="lbl-hint">（相对初始估计的最大变化 %）</span></div>
      <div class="constraints">
        <label v-for="row in CONSTRAINT_ROWS" :key="row.key" class="crow" :title="row.hint">
          <input
            type="checkbox"
            class="ck"
            :checked="fit.options.constraints[row.key].enabled"
            @change="fit.options.constraints[row.key].enabled = ($event.target as HTMLInputElement).checked"
          />
          <span class="ck-label">{{ row.label }}</span>
          <input
            class="field num pct"
            :value="fit.options.constraints[row.key].pct"
            :disabled="!fit.options.constraints[row.key].enabled"
            inputmode="numeric"
            @change="onConstraintPct(row.key, $event)"
          />
        </label>
      </div>
      <p class="hint">软约束：迭代可短暂越界并逐步挣脱；"违约"遥测持续偏高时说明需要放宽（原版建议保持 a0/a1 开启）。</p>

      <div class="sec-label">更新模式</div>
      <div class="seg">
        <button :class="{ on: fit.mode.value === 'full' }" title="每迭代重绘曲线（图形更新模式）" @click="fit.mode.value = 'full'">
          Full 图形更新
        </button>
        <button :class="{ on: fit.mode.value === 'fast' }" title="只滚动数字遥测，不重绘（Fast Numerical Update）" @click="fit.mode.value = 'fast'">
          Fast 数值更新
        </button>
      </div>

      <label class="checkbox" title="Adjust Fit：调整锚点/参数后自动重新拟合，无需再点拟合按钮（原版核心循环）">
        <input type="checkbox" v-model="fit.autoRefit.value" />
        <span class="box"><AppIcon name="check" :size="10" /></span>
        自动重拟合（Adjust Fit，默认关）
      </label>

      <div class="run-row">
        <button class="btn primary grow" :disabled="!sp.ready.value || fit.status.value === 'running'" @click="void startFit({ stepTo: 'report' })">
          <span v-if="fit.status.value === 'running'" class="spinner" />
          <AppIcon v-else name="play" :size="14" />
          {{ fit.status.value === 'running' ? '拟合中…' : '拟合' }}
        </button>
        <button class="btn" :disabled="fit.status.value !== 'running'" title="停止并保留：停在当前最优参数" @click="stopFit">
          <AppIcon name="stop" :size="13" />停止
        </button>
      </div>

      <div class="sec-label">迭代遥测</div>
      <div class="tele">
        <div class="cell"><span class="k">迭代</span><b class="num">{{ fit.telemetry.iter }}</b></div>
        <div class="cell"><span class="k">FnEval</span><b class="num">{{ fit.telemetry.fnEval }}</b></div>
        <div class="cell"><span class="k">χ²</span><b class="num">{{ fmtSci(fit.telemetry.chi2, 4) }}</b></div>
        <div class="cell"><span class="k">违约</span><b class="num" :class="{ warn: fit.telemetry.viol > 0 }">{{ fit.telemetry.viol }}</b></div>
        <div class="cell"><span class="k">r²</span><b class="num">{{ r2Display }}</b></div>
        <div class="cell"><span class="k">用时</span><b class="num">{{ fmtMs(fit.telemetry.timeMs) }}</b></div>
      </div>
      <div class="progress" :title="'r² = ' + r2Display">
        <div class="fill" :style="{ width: r2Pct + '%' }" />
      </div>
      <p v-if="fit.telemetry.viol > 0" class="hint warn">
        存在 {{ fit.telemetry.viol }} 个约束违约 —— 请检查初值或参数边界。
      </p>
    </div>
  </div>
</template>

<style scoped>
.content {
  padding: 2px 12px 12px;
}
.lbl-hint {
  font-weight: 400;
  color: var(--text-3);
  font-size: var(--fs-small);
}
.constraints {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 4px 0 2px;
}
.crow {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  cursor: pointer;
}
.crow .ck {
  accent-color: var(--accent);
  width: 13px;
  height: 13px;
  flex: none;
  cursor: pointer;
}
.crow .ck-label {
  flex: 1;
  min-width: 0;
  font-size: var(--fs-small);
  color: var(--text-2);
  user-select: none;
}
.crow .field.pct {
  width: 64px;
  flex: none;
  text-align: right;
}
.crow .field.pct:disabled {
  opacity: 0.45;
}
.grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 4px 0;
}
.inline {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.inline .k,
.slider-row .k {
  flex: none;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.inline .field {
  width: 100%;
  min-width: 0;
}
.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 8px 0 2px;
}
.slider {
  flex: 1;
}
.val {
  min-width: 22px;
  text-align: right;
  color: var(--accent);
  font-weight: 600;
}
.run-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.grow {
  flex: 1;
  justify-content: center;
}
.tele {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 8px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.cell .k {
  font-size: 10px;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.cell b {
  font-weight: 600;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell b.warn {
  color: var(--warning);
}
.progress {
  height: 5px;
  margin-top: 8px;
  border-radius: 3px;
  background: var(--bg-3);
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--accent), var(--success));
  transition: width 0.15s ease;
}
.warn {
  color: var(--warning);
}
</style>
