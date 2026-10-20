<script setup lang="ts">
/** 报告页：统计卡 + 基线/峰参数表 + 导出按钮组；
 *  （结晶度 / 取向 / Kβ 已独立为左侧「聚合物」步骤，见 PolymerPanel.vue。） */
import { computed } from 'vue'
import AppIcon from '../AppIcon.vue'
import { PEAK_FN_MAP, BASELINE_FN_MAP } from '@/lib/pwcore/shared/registry'
import { useFit } from '@/lib/curvefit/stores/fit'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { buildDataFitCsv, buildPeakParamsCsv, buildReportTxt, saveTextFile } from '@/lib/curvefit/utils/exporters'
import { fmtMs, fmtSci, fmtSig } from '@/lib/curvefit/utils/format'
import { pushToast } from '@/lib/curvefit/stores/toast'

const fit = useFit()
const pk = usePeaks()
const sp = useSpectrum()

const s = computed(() => fit.lastStats.value)

const statCards = computed(() => {
  const st = s.value
  if (!st) return []
  return [
    { k: 'R²', v: fmtSig(st.r2, 6) },
    { k: '调整 R²', v: fmtSig(st.r2Adj, 6) },
    { k: 'Fit Std Err', v: fmtSig(st.fitStdErr, 6) },
    { k: 'F 值', v: fmtSig(st.fValue, 6) },
    { k: 'SSE', v: fmtSci(st.sse, 4) },
    { k: '自由度', v: String(st.dof) },
    { k: '迭代', v: `${st.iterations}${st.converged ? (st.stopped ? '（停止）' : '') : '（上限）'}` },
    { k: '耗时', v: fmtMs(st.timeMs) },
  ]
})

const totalArea = computed(() => {
  let a = 0
  for (const p of pk.list.value) {
    const r = pk.resultById.value.get(p.id)
    if (r && p.enabled) a += Math.abs(r.area)
  }
  return a
})

const peakRows = computed(() =>
  pk.list.value.map((p, i) => {
    const meta = PEAK_FN_MAP.get(p.fn)
    const res = pk.resultById.value.get(p.id)
    return {
      p,
      index: i + 1,
      fnName: meta?.name ?? p.fn,
      params: (meta?.params ?? []).map((pm) => ({
        key: pm.key,
        label: pm.label,
        value: p.p[pm.key] ?? 0,
        err: res?.pErr[pm.key],
        locked: !!p.locked[pm.key],
      })),
      area: res?.area,
      fwhm: res?.fwhm,
      share: res && totalArea.value > 0 ? Math.abs(res.area) / totalArea.value : undefined,
    }
  }),
)

/** Background (baseline) parameters, fitted alongside the peaks. */
const baselineRow = computed(() => {  const bl = pk.baseline
  const meta = BASELINE_FN_MAP.get(bl.fn)
  if (bl.fn === 'none' || !meta) return null
  const res = fit.lastResult.value
  return {
    fnName: meta.name,
    enabled: bl.enabled,
    params: meta.params.map((pm) => ({
      key: pm.key,
      label: pm.label,
      value: bl.p[pm.key] ?? 0,
      err: res?.baselineErr[pm.key],
      locked: !!bl.locked[pm.key],
    })),
  }
})

async function exportParams(): Promise<void> {
  const ok = await saveTextFile('pw_params.csv', buildPeakParamsCsv())
  if (ok) pushToast('success', '参数 CSV 已导出')
}

async function exportDataFit(): Promise<void> {
  if (!sp.ready.value) return
  const ok = await saveTextFile('pw_data_fit.csv', buildDataFitCsv())
  if (ok) pushToast('success', '数据+拟合 CSV 已导出')
}

async function exportReport(): Promise<void> {
  const ok = await saveTextFile('pw_report.txt', buildReportTxt())
  if (ok) pushToast('success', '报告 TXT 已导出')
}

defineExpose({ exportParams, exportDataFit, exportReport })
</script>

<template>
  <div class="panel">
    <div class="panel-title"><AppIcon name="report" :size="13" />报告</div>
    <div class="content">
      <template v-if="s">
        <div class="cards">
          <div v-for="c in statCards" :key="c.k" class="scard">
            <span class="k">{{ c.k }}</span>
            <b class="num">{{ c.v }}</b>
          </div>
        </div>

        <template v-if="baselineRow">
          <div class="sec-label">背景（基线）参数</div>
          <div class="ptable">
            <div class="pblock">
              <div class="phead">
                <span class="dot base" />
                <b>{{ baselineRow.fnName }}</b>
                <span v-if="!baselineRow.enabled" class="off">未参与拟合</span>
              </div>
              <table class="table">
                <thead>
                  <tr><th>参数</th><th class="r">值</th><th class="r">±σ</th><th class="lockcol"></th></tr>
                </thead>
                <tbody>
                  <tr v-for="pm in baselineRow.params" :key="pm.key">
                    <td class="pcol" :title="pm.key + ' · ' + pm.label">
                      <span class="pname">{{ pm.key }} <span class="pl">{{ pm.label }}</span></span>
                    </td>
                    <td class="r">{{ fmtSig(pm.value, 8) }}</td>
                    <td class="r">{{ pm.err !== undefined ? fmtSig(pm.err, 5) : '—' }}</td>
                    <td class="r lockcol">
                      <span v-if="pm.locked" class="lockmark">锁定</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>

        <div class="sec-label">峰参数</div>
        <div class="ptable">
          <div v-for="r in peakRows" :key="r.p.id" class="pblock">
            <div class="phead">
              <span class="dot" :style="{ background: r.p.color }" />
              <b>#{{ r.index }} {{ r.fnName }}</b>
              <span v-if="!r.p.enabled" class="off">已停用</span>
              <span class="share num">{{ r.share !== undefined ? '占比 ' + (r.share * 100).toFixed(1) + ' %' : '' }}</span>
            </div>
            <table class="table">
              <thead>
                <tr><th>参数</th><th class="r">值</th><th class="r">±σ</th><th class="lockcol"></th></tr>
              </thead>
              <tbody>
                <tr v-for="pm in r.params" :key="pm.key">
                  <td class="pcol" :title="pm.key + ' · ' + pm.label">
                    <span class="pname">{{ pm.key }} <span class="pl">{{ pm.label }}</span></span>
                  </td>
                  <td class="r">{{ fmtSig(pm.value, 8) }}</td>
                  <td class="r">{{ pm.err !== undefined ? fmtSig(pm.err, 5) : '—' }}</td>
                  <td class="r lockcol">
                    <span v-if="pm.locked" class="lockmark">锁定</span>
                  </td>
                </tr>
                <tr v-if="r.area !== undefined">
                  <td colspan="2">area {{ fmtSig(r.area, 8) }} · FWHM {{ fmtSig(r.fwhm ?? 0, 6) }}</td>
                  <td colspan="2" class="r hint"></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="sec-label">导出</div>
        <div class="btns">
          <button class="btn sm" @click="exportParams"><AppIcon name="export" :size="13" />参数 CSV</button>
          <button class="btn sm" @click="exportDataFit"><AppIcon name="export" :size="13" />数据+拟合 CSV</button>
          <button class="btn sm" @click="exportReport"><AppIcon name="file" :size="13" />报告 TXT</button>
        </div>
      </template>
      <div v-else class="placeholder">
        <AppIcon name="report" :size="30" />
        <p class="hint">尚无拟合结果 —— 完成“放峰”后运行拟合，统计报告将显示在此处。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.content {
  padding: 2px 12px 12px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 6px;
}
.scard {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 8px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.scard .k {
  font-size: 10px;
  color: var(--text-3);
  letter-spacing: 0.04em;
  white-space: nowrap;
}
.scard b {
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ptable {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pblock {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.phead {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 9px;
  background: var(--bg-2);
  font-size: 12px;
}
.phead b {
  font-weight: 600;
}
.phead .off {
  font-size: 10px;
  color: var(--warning);
  border: 1px solid var(--warning);
  border-radius: 8px;
  padding: 0 6px;
}
.share {
  margin-left: auto;
  font-size: var(--fs-small);
  color: var(--text-2);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.base {
  background: var(--warning);
}
.pl {
  color: var(--text-3);
  font-size: var(--fs-small);
}
.lockmark {
  font-size: 10px;
  color: var(--warning);
}
.btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 28px 8px;
  color: var(--text-3);
  text-align: center;
}
.table td,
.table th {
  padding: 3px 6px;
}
.ptable .table th:first-child {
  width: 36%;
}
.ptable .table .lockcol {
  width: 30px;
}
.pcol {
  max-width: 0;
}
.pname {
  display: inline-block;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

</style>
