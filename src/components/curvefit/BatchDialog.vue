<script setup lang="ts">
/**
 * 批量拟合对话框（v0.3.4，2026-10-22 用户需求）：以当前工作曲线（已放峰并
 * 拟合好）为模板，把其余导入的曲线逐条拟合——峰位为主要初猜、限 ±% 小范围
 * 移动；峰高用各曲线自身数据做初猜且完全自由；背景与数据窗口设置同模板。
 * 输出：对话框内汇总表 + 汇总 CSV / 曲线 CSV 导出。
 */
import { computed, ref } from 'vue'
import Modal from './Modal.vue'
import AppIcon from './AppIcon.vue'
import { BASELINE_FN_MAP } from '@/lib/pwcore/shared/registry'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { useFit } from '@/lib/curvefit/stores/fit'
import { useBatch } from '@/lib/curvefit/stores/batch'
import { pushToast } from '@/lib/curvefit/stores/toast'
import { fmtSig } from '@/lib/curvefit/utils/format'
import {
  buildBatchCurvesCsv,
  buildBatchSummaryCsv,
  saveTextFile,
} from '@/lib/curvefit/utils/exporters'

const emit = defineEmits<{ close: [] }>()

const sp = useSpectrum()
const pk = usePeaks()
const fit = useFit()
const batch = useBatch()

const enabledPeaks = computed(() => pk.list.value.filter((p) => p.enabled))

const baselineLabel = computed(() => {
  const b = pk.baseline
  if (!b.enabled || b.fn === 'none') return '无'
  return BASELINE_FN_MAP.get(b.fn)?.name ?? b.fn
})

/** Template data window: first..last included point of the CURRENT mask —
 * exactly what the batch runner will replicate on every curve. /
 * 模板数据窗口：当前掩膜的首末包含点（批量拟合将复刻到每条曲线）。 */
const windowLabel = computed(() => {
  const xv = sp.x.value
  const mv = sp.mask.value
  if (!xv || !mv) return '—'
  let lo = Number.POSITIVE_INFINITY
  let hi = Number.NEGATIVE_INFINITY
  for (let i = 0; i < mv.length; i++) {
    if (mv[i] !== 1) continue
    if (xv[i] < lo) lo = xv[i]
    if (xv[i] > hi) hi = xv[i]
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return '—'
  return `[${fmtSig(lo, 6)}, ${fmtSig(hi, 6)}]`
})

const canRun = computed(
  () =>
    sp.ready.value &&
    enabledPeaks.value.length > 0 &&
    batch.entries.value.length > 0 &&
    !batch.running.value &&
    fit.status.value !== 'running',
)

const doneCount = computed(
  () => batch.results.value?.filter((r) => r.status === 'done').length ?? 0,
)
const failCount = computed(
  () => batch.results.value?.filter((r) => r.status === 'failed').length ?? 0,
)
const hasCurves = computed(() => batch.results.value?.some((r) => r.curves) ?? false)

const exporting = ref(false)

function onAddFiles(): void {
  void batch.addBatchFiles()
}

async function onExportSummary(): Promise<void> {
  const csv = buildBatchSummaryCsv()
  if (!csv) {
    pushToast('warn', '尚无批量结果可导出')
    return
  }
  exporting.value = true
  try {
    await saveTextFile('pw_batch_summary.csv', csv)
    pushToast('success', '批量汇总 CSV 已导出')
  } finally {
    exporting.value = false
  }
}

async function onExportCurves(): Promise<void> {
  const csv = buildBatchCurvesCsv()
  if (!csv) {
    pushToast('warn', '没有可导出的曲线（未保留曲线数据或尚无成功结果）')
    return
  }
  exporting.value = true
  try {
    await saveTextFile('pw_batch_curves.csv', csv)
    pushToast('success', '批量曲线 CSV 已导出')
  } finally {
    exporting.value = false
  }
}

function statusText(s: string): string {
  if (s === 'done') return '完成'
  if (s === 'failed') return '失败'
  if (s === 'running') return '拟合中'
  return '待处理'
}
</script>

<template>
  <Modal title="批量拟合 — 以当前曲线为模板" :width="560" @close="emit('close')">
    <div class="form">
      <!-- Template summary / 模板信息 -->
      <div class="tcard">
        <div class="trow"><span class="k">模板数据</span><span class="v">{{ sp.ready.value ? sp.meta.title : '（未载入数据）' }}</span></div>
        <div class="trow"><span class="k">启用峰</span><span class="v">{{ enabledPeaks.length }} 个（{{ enabledPeaks.map(p => p.p.a1 != null ? fmtSig(p.p.a1, 5) : '?').join(' · ') || '—' }}）</span></div>
        <div class="trow"><span class="k">基线</span><span class="v">{{ baselineLabel }}（随每条曲线重新精修）</span></div>
        <div class="trow"><span class="k">数据窗口</span><span class="v">{{ windowLabel }}（同第一条，含数据步排除）</span></div>
        <div class="trow"><span class="k">拟合选项</span><span class="v">maxIter={{ fit.options.maxIter }} · convDigits={{ fit.options.convDigits }} · robust={{ fit.options.robust }} · fitExtent=1/{{ fit.options.fitExtent }}</span></div>
      </div>
      <p v-if="!sp.ready.value || enabledPeaks.length === 0" class="warn-hint">
        请先在第一条曲线上放峰并拟合，再进行批量拟合（峰位/峰形/基线/数据窗口都以当前会话为模板）。
      </p>

      <!-- Options / 选项 -->
      <div class="opts">
        <label class="row">
          <span class="k">峰位小范围移动 ±%</span>
          <input v-model.number="batch.batchOpts.centerPct" class="field num" type="number" min="0" max="100" step="0.5" />
        </label>
        <label class="row check">
          <input v-model="batch.batchOpts.keepCurves" type="checkbox" />
          <span>保留每条曲线的数据+拟合（供导出曲线 CSV）</span>
        </label>
        <p class="hint">
          峰位以模板为主要初猜、限 ±{{ batch.batchOpts.centerPct }}% 软约束小范围移动（0 = 完全锁定）；峰高用各曲线自身数据做初猜、不设约束自由收敛；背景与数据范围设置同第一条。批量曲线不做平滑/扣底等数据步预处理。
        </p>
      </div>

      <!-- Queue / 队列 -->
      <div class="qcard">
        <div class="qhead">
          <span class="k">批量曲线（{{ batch.entries.value.length }} 条）</span>
          <span class="qbtns">
            <button class="btn sm" type="button" :disabled="batch.running.value" @click="onAddFiles">
              <AppIcon name="plus" :size="12" />添加文件…
            </button>
            <button
              class="btn sm"
              type="button"
              :disabled="batch.running.value || batch.entries.value.length === 0"
              @click="batch.clearBatchQueue()"
            >清空</button>
          </span>
        </div>
        <div v-if="batch.entries.value.length" class="qlist">
          <div v-for="e in batch.entries.value" :key="e.id" class="qitem">
            <span class="qname" :title="e.name">{{ e.name }}</span>
            <span class="qn">{{ e.n }} 点</span>
            <button
              class="qdel"
              type="button"
              title="从队列移除"
              :disabled="batch.running.value"
              @click="batch.removeEntry(e.id)"
            >✕</button>
          </div>
        </div>
        <p v-else class="hint">队列为空：点「添加文件…」选择其余曲线（可多选，PRN/CSV/TXT/TSV/DAT/SCN）。</p>
      </div>

      <!-- Progress / 进度 -->
      <div v-if="batch.running.value || batch.progress.done > 0" class="prog">
        <div class="pbar">
          <div class="pfill" :style="{ width: `${batch.progress.total ? (100 * batch.progress.done) / batch.progress.total : 0}%` }" />
        </div>
        <p class="hint num">
          {{ batch.progress.done }} / {{ batch.progress.total }}
          <span v-if="batch.running.value && batch.progress.current"> · 正在拟合 {{ batch.progress.current }}</span>
          <span v-else-if="batch.results.value"> · 成功 {{ doneCount }} · 失败 {{ failCount }}</span>
        </p>
      </div>

      <!-- Results / 结果 -->
      <div v-if="batch.results.value && batch.results.value.length" class="rcard">
        <div v-for="r in batch.results.value" :key="r.id" class="rfile" :class="`rfile--${r.status}`">
          <details>
            <summary>
              <span class="rname" :title="r.name">{{ r.name }}</span>
              <span class="rstat">{{ statusText(r.status) }}</span>
              <span v-if="r.status === 'done' && r.r2 !== undefined" class="rr2">R² = {{ fmtSig(r.r2, 6) }}</span>
              <span v-else-if="r.error" class="rerr" :title="r.error">{{ r.error }}</span>
            </summary>
            <table v-if="r.peaks && r.peaks.length" class="rtable">
              <thead>
                <tr>
                  <th>#</th><th>峰形</th>
                  <th class="r">中心 ± err</th>
                  <th class="r">峰高 ± err</th>
                  <th class="r">FWHM</th>
                  <th class="r">面积</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in r.peaks" :key="p.index">
                  <td>{{ p.index }}</td>
                  <td>{{ p.fnName }}</td>
                  <td class="r num">{{ fmtSig(p.center, 7) }} ± {{ fmtSig(p.centerErr, 3) }}</td>
                  <td class="r num">{{ fmtSig(p.height, 6) }} ± {{ fmtSig(p.heightErr, 3) }}</td>
                  <td class="r num">{{ fmtSig(p.fwhm, 6) }}</td>
                  <td class="r num">{{ fmtSig(p.area, 7) }}</td>
                </tr>
              </tbody>
            </table>
          </details>
        </div>
      </div>
    </div>

    <template #footer>
      <button class="btn" @click="emit('close')">关闭</button>
      <button
        class="btn"
        :disabled="!batch.running.value"
        title="取消：当前曲线拟合结束后停止"
        @click="batch.cancelBatch()"
      >取消</button>
      <button
        class="btn"
        :disabled="exporting || !batch.results.value"
        @click="onExportCurves"
      >导出曲线 CSV</button>
      <button
        class="btn"
        :disabled="exporting || !batch.results.value"
        @click="onExportSummary"
      >导出汇总 CSV</button>
      <button class="btn primary" :disabled="!canRun" @click="batch.runBatch()">
        <span v-if="batch.running.value" class="spinner" />
        <AppIcon v-else name="play" :size="13" />开始批量拟合
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.tcard {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--bg-2);
  font-size: var(--fs-small);
}
.trow {
  display: flex;
  gap: 10px;
  min-width: 0;
}
.trow .k {
  flex: none;
  width: 62px;
  color: var(--text-2);
}
.trow .v {
  min-width: 0;
  color: var(--text-1);
  word-break: break-all;
}
.warn-hint {
  margin: 0;
  padding: 7px 9px;
  font-size: var(--fs-small);
  border: 1px solid var(--warn, #b45309);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, #b45309 12%, transparent);
  color: var(--text-1);
}
.opts .row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.opts .row .k {
  flex: 1;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.opts .field {
  width: 80px;
}
.opts .check {
  font-size: var(--fs-small);
  color: var(--text-1);
  cursor: pointer;
}
.hint {
  margin: 0;
  font-size: var(--fs-small);
  line-height: 1.55;
  color: var(--text-2);
}
.qcard {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.qhead {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qhead .k {
  font-size: var(--fs-small);
  font-weight: 600;
  color: var(--text-1);
}
.qbtns {
  margin-left: auto;
  display: flex;
  gap: 6px;
}
.btn.sm {
  padding: 3px 9px;
  font-size: var(--fs-small);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.qlist {
  max-height: 150px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.qitem {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 4px;
  font-size: var(--fs-small);
}
.qname {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-1);
}
.qn {
  flex: none;
  color: var(--text-3);
  font-size: var(--fs-small);
}
.qdel {
  flex: none;
  border: 1px solid var(--border);
  background: var(--bg-1);
  color: var(--text-2);
  border-radius: 6px;
  width: 18px;
  height: 18px;
  line-height: 1;
  font-size: 10px;
  cursor: pointer;
}
.qdel:hover:not(:disabled) {
  color: #d92d20;
  border-color: #d92d20;
}
.prog {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pbar {
  height: 8px;
  border-radius: 4px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  overflow: hidden;
}
.pfill {
  height: 100%;
  background: var(--accent);
  transition: width 0.2s ease;
}
.rcard {
  max-height: 240px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rfile {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
  font-size: var(--fs-small);
}
.rfile--failed {
  border-color: color-mix(in srgb, #d92d20 55%, var(--border));
}
.rfile summary {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  list-style: none;
  min-width: 0;
}
.rfile summary::-webkit-details-marker {
  display: none;
}
.rname {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-1);
}
.rstat {
  flex: none;
  color: var(--text-2);
}
.rr2 {
  flex: none;
  color: var(--accent);
  font-weight: 600;
}
.rerr {
  flex: none;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #d92d20;
}
.rtable {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
  font-size: var(--fs-small);
}
.rtable th,
.rtable td {
  padding: 2px 6px;
  border-top: 1px solid var(--border);
  text-align: left;
  white-space: nowrap;
}
.rtable th {
  color: var(--text-2);
  font-weight: 600;
}
.rtable .r {
  text-align: right;
}
</style>
