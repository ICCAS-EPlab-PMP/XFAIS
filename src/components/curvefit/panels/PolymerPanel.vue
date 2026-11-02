<script setup lang="ts">
/**
 * 聚合物分析步骤（2026-10-20 用户要求）：左侧步骤栏「报告」之下的独立一步。
 * Three INDEPENDENT switches — 结晶度 / 取向分析 / Kβ — each default OFF:
 * only the switched-on analysis is rendered AND computed (the computeds
 * short-circuit on the same flags, so nothing is evaluated while off).
 * 三项独立开关（结晶度 / 取向分析 / Kβ），默认全关：只有开启的项才显示并
 * 计算（各 computed 以同一开关短路，关闭期间不做任何计算）。
 *
 * Areas come from the fit when one exists; before any fit the LIVE model's
 * numeric areas are used so the numbers follow peak placement.
 * 有拟合结果用拟合面积；未拟合时用实时模型的数值面积。
 */
import { computed } from 'vue'
import AppIcon from '../AppIcon.vue'
import HelpTip from '../HelpTip.vue'
import { PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { peakShape } from '@/lib/pwcore/core/statsfn'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { useBatch } from '@/lib/curvefit/stores/batch'
import { fmtSig } from '@/lib/curvefit/utils/format'
import {
  KB_ROLES,
  crystallinityOf,
  kbAssign,
  kbFractionOf,
  orientationOfComponent,
  orientOpts,
  polyOn,
  roleOf,
  toggleRole,
  type CrysResult,
  type CrysRole,
  type KbResult,
  type KbRole,
  type OrientResult,
} from '@/lib/curvefit/utils/analysis'

const pk = usePeaks()
const batch = useBatch()

function liveArea(fn: string, p: Record<string, number>): number {
  const meta = PEAK_FN_MAP.get(fn)
  const packed = (meta?.params ?? []).map((pm) => p[pm.key] ?? 0)
  return Math.abs(peakShape(fn as never, packed).area)
}

function liveHeight(fn: string, p: Record<string, number>): number {
  const meta = PEAK_FN_MAP.get(fn)
  const packed = (meta?.params ?? []).map((pm) => p[pm.key] ?? 0)
  return Math.abs(peakShape(fn as never, packed).height)
}

interface AnalysisRow {
  id: string
  index: number
  fn: string
  color?: string
  center: number
  area: number
  /** Peak height (fit result, else live model) — the Kβ height variant
   * (2026-10-22 user request) needs it alongside the area. /
   * 峰高（拟合结果，否则实时模型）——Kβ 峰高法（2026-10-22 用户要求）。 */
  height: number
  role: CrysRole
}

/** Enabled peaks → analysis rows (fit values, else live-model values). /
 *  启用的峰 → 分析行（优先拟合值，否则实时模型值）。 */
const analysisRows = computed<AnalysisRow[]>(() => {
  let i = 0
  return pk.list.value
    .filter((p) => p.enabled)
    .map((p) => {
      i += 1
      const res = pk.resultById.value.get(p.id)
      const meta = PEAK_FN_MAP.get(p.fn)
      const center = p.p.a1 ?? 0
      return {
        id: p.id,
        index: i,
        fn: meta?.name ?? p.fn,
        color: p.color,
        center,
        area: res ? Math.abs(res.area) : liveArea(p.fn, p.p),
        height: res ? Math.abs(res.height) : liveHeight(p.fn, p.p),
        role: roleOf(p.id),
      }
    })
})

// Each analysis is guarded by its own switch: while off the result is null /
// empty and no numeric work happens. / 每项分析由各自开关守卫：关闭时结果为空，
// 不做任何数值计算。
const crys = computed(() => (polyOn.crystallinity ? crystallinityOf(analysisRows.value) : null))

const orientRows = computed(() => {
  if (!polyOn.orientation) return []
  return analysisRows.value.map((row) => {
    const spec = pk.list.value.find((p) => p.id === row.id)
    const stats = spec
      ? orientationOfComponent(spec.fn, spec.p, {
        chiZero: orientOpts.chiZero,
        refDeg: orientOpts.refDeg,
        equatorialToChain: orientOpts.equatorialToChain,
      })
      : null
    return { row, stats }
  })
})

const peakSelectOptions = computed(() =>
  analysisRows.value.map((r) => ({
    value: r.id,
    label: `#${r.index} · ${fmtSig(r.center, 5)}`,
  })),
)

const kb = computed(() => {
  if (!polyOn.kb) return null
  const byId = new Map(analysisRows.value.map((r) => [r.id, r.area]))
  return kbFractionOf({
    beta300: kbAssign.beta300 ? byId.get(kbAssign.beta300) ?? null : null,
    a110: kbAssign.a110 ? byId.get(kbAssign.a110) ?? null : null,
    a040: kbAssign.a040 ? byId.get(kbAssign.a040) ?? null : null,
    a130: kbAssign.a130 ? byId.get(kbAssign.a130) ?? null : null,
  })
})

/** Kβ from peak HEIGHTS (2026-10-22 user request: 有人提出 Kβ 可能按峰高给
 *  出) — same Turner-Jones ratio, height intensities, reported alongside the
 *  area value and clearly labelled. / 峰高法 Kβ——同一公式的峰高版本，与面积
 *  法并列展示并标注来源。 */
const kbH = computed(() => {
  if (!polyOn.kb) return null
  const byId = new Map(analysisRows.value.map((r) => [r.id, r.height]))
  return kbFractionOf(
    {
      beta300: kbAssign.beta300 ? byId.get(kbAssign.beta300) ?? null : null,
      a110: kbAssign.a110 ? byId.get(kbAssign.a110) ?? null : null,
      a040: kbAssign.a040 ? byId.get(kbAssign.a040) ?? null : null,
      a130: kbAssign.a130 ? byId.get(kbAssign.a130) ?? null : null,
    },
    'height',
  )
})

function onKbSelect(role: KbRole, ev: Event): void {
  kbAssign[role] = (ev.target as HTMLSelectElement).value || null
}

// ---------------------------------------------------------------------------
// Multi-curve analyses over BATCH results (2026-10-23 user request: 多条数据
// 的结晶度/取向/iPP 分析随用户开启而逐曲线开启，数据尽可能折叠). Uses each
// curve's stored fitted model (peak ids = template ids, so the assignment
// state above applies to EVERY curve); each enabled analysis is computed only
// when its switch is on, and every curve renders COLLAPSED by default.
// 基于批量结果的逐曲线分析：峰 id 即模板 id（上方指派对每条曲线都成立）；
// 各分析只在开关开启时计算，每条曲线默认折叠。
// ---------------------------------------------------------------------------

interface BatchOrientRow {
  index: number
  center: number
  stats: OrientResult | null
}

interface BatchCurveAnalysis {
  id: string
  name: string
  /** Peak rows shared by all three analyses (id/index/area/height). */
  rows: Array<{ id: string; area: number; height: number }>
  crys: CrysResult | null
  kb: KbResult | null
  kbH: KbResult | null
  orient: BatchOrientRow[]
}

const batchAnalyses = computed<BatchCurveAnalysis[]>(() => {
  const rs = batch.results.value
  if (!rs || rs.length === 0) return []
  const out: BatchCurveAnalysis[] = []
  for (const r of rs) {
    if (r.status !== 'done' || !r.model) continue
    const specs = r.model.peaks
    const rows = specs.map((spec, i) => {
      const fitted = r.outcome?.peaks.find((q) => q.id === spec.id)
      const meta = PEAK_FN_MAP.get(spec.fn)
      const packed = (meta?.params ?? []).map((pm) => spec.p[pm.key] ?? 0)
      return {
        id: spec.id,
        area: fitted ? Math.abs(fitted.area) : Math.abs(peakShape(spec.fn, packed).area),
        height: fitted ? Math.abs(fitted.height) : Math.abs(peakShape(spec.fn, packed).height),
        index: i + 1,
        center: spec.p.a1 ?? 0,
      }
    })
    const byArea = new Map(rows.map((x) => [x.id, x.area]))
    const byHeight = new Map(rows.map((x) => [x.id, x.height]))
    out.push({
      id: r.id,
      name: r.name,
      rows,
      crys: polyOn.crystallinity ? crystallinityOf(rows) : null,
      kb: polyOn.kb
        ? kbFractionOf({
            beta300: kbAssign.beta300 ? byArea.get(kbAssign.beta300) ?? null : null,
            a110: kbAssign.a110 ? byArea.get(kbAssign.a110) ?? null : null,
            a040: kbAssign.a040 ? byArea.get(kbAssign.a040) ?? null : null,
            a130: kbAssign.a130 ? byArea.get(kbAssign.a130) ?? null : null,
          })
        : null,
      kbH: polyOn.kb
        ? kbFractionOf(
            {
              beta300: kbAssign.beta300 ? byHeight.get(kbAssign.beta300) ?? null : null,
              a110: kbAssign.a110 ? byHeight.get(kbAssign.a110) ?? null : null,
              a040: kbAssign.a040 ? byHeight.get(kbAssign.a040) ?? null : null,
              a130: kbAssign.a130 ? byHeight.get(kbAssign.a130) ?? null : null,
            },
            'height',
          )
        : null,
      orient: polyOn.orientation
        ? specs.map((spec, i) => ({
            index: i + 1,
            center: spec.p.a1 ?? 0,
            stats: orientationOfComponent(spec.fn, spec.p, {
              chiZero: orientOpts.chiZero,
              refDeg: orientOpts.refDeg,
              equatorialToChain: orientOpts.equatorialToChain,
            }),
          }))
        : [],
    })
  }
  return out
})

/** Any batch-fitted curve available for the multi-curve section? */
const hasBatchCurves = computed(
  () => batch.results.value?.some((r) => r.status === 'done' && r.model) ?? false,
)
</script>

<template>
  <div class="panel">
    <div class="panel-title">
      <AppIcon name="chart" :size="13" />聚合物分析
      <HelpTip
        :size="17"
        text="基于当前峰模型（拟合后为拟合分量，未拟合时用实时模型）。按需开启，未开启的项目不计算；结晶度把非晶晕峰标为「非晶」，Kβ 按四晶面下拉指派，取向按逐峰方位分布。多条批量曲线时下方「批量曲线分析」用同一套指派逐曲线计算。"
      />
    </div>
    <div class="content">

      <!-- ① 结晶度（峰分类法） -->
      <div class="xcard" :class="{ on: polyOn.crystallinity }">
        <label class="xhead">
          <input v-model="polyOn.crystallinity" type="checkbox" class="xcheck" />
          <span class="xtitle">结晶度（峰分类法）</span>
          <span class="xstate">{{ polyOn.crystallinity ? '已开启' : '未开启' }}</span>
        </label>
        <p class="xhint">
          把非晶晕对应的峰标为「非晶」，其余计为结晶峰：Xc = ΣA结晶 / (ΣA结晶 + ΣA非晶) × 100 %
        </p>
        <div v-if="polyOn.crystallinity" class="xbody">
          <div v-if="analysisRows.length" class="chips">
            <button
              v-for="r in analysisRows"
              :key="r.id"
              type="button"
              class="chip"
              :class="{ 'chip--amorph': r.role === 'amorphous' }"
              :title="r.role === 'amorphous' ? '点击改回结晶峰' : '点击标为非晶峰'"
              @click="toggleRole(r.id)"
            >
              <span class="dot" :style="{ background: r.color }" />#{{ r.index }}
              <em>{{ r.role === 'amorphous' ? '非晶' : '结晶' }}</em>
            </button>
          </div>
          <template v-if="crys">
            <p class="xline"><b class="xval">Xc = {{ crys.xcPct.toFixed(1) }}%</b></p>
            <p class="xhint num">
              A结晶 {{ fmtSig(crys.crystalArea, 6) }} · A非晶 {{ fmtSig(crys.amorphousArea, 6) }}
            </p>
          </template>
          <p v-else class="xhint">尚无峰面积：请先在“放峰”步骤添加并启用的峰。</p>
        </div>
      </div>

      <!-- ② 取向分析（I(χ) 逐峰） -->
      <div class="xcard" :class="{ on: polyOn.orientation }">
        <label class="xhead">
          <input v-model="polyOn.orientation" type="checkbox" class="xcheck" />
          <span class="xtitle">取向分析（方位角 I(χ) 逐峰）</span>
          <span class="xstate">{{ polyOn.orientation ? '已开启' : '未开启' }}</span>
        </label>
        <p class="xhint">
          与取向模块同口径：Hermans 半区间 sinφ 权重，赤道反射
          &lt;cos²φ&gt; = 1 − &lt;cos²χ&gt;，f = (3&lt;cos²φ&gt; − 1)/2；
          f_FWHM = (180° − H)/180。
        </p>
        <div v-if="polyOn.orientation" class="xbody">
          <div class="orow-opts">
            <label class="olabel">
              参考轴
              <select v-model="orientOpts.chiZero" class="sel">
                <option value="meridian">子午线 0°</option>
                <option value="equator">赤道 90°</option>
                <option value="custom">自定义</option>
              </select>
            </label>
            <label v-if="orientOpts.chiZero === 'custom'" class="olabel">
              χ₀ (°)
              <input v-model.number="orientOpts.refDeg" type="number" step="any" class="sel" />
            </label>
            <label class="olabel check" title="赤道反射：实测法向 <cos²χ> 换算为链轴 <cos²φc> = 1 − <cos²χ>">
              <input v-model="orientOpts.equatorialToChain" type="checkbox" />
              法向→链轴
            </label>
          </div>
          <!-- Headers drop the ° / ⟨⟩ decorations so every label fits the fixed
             * columns; the full meaning stays in title + the legend under the table.
             * 表头去掉 ° / ⟨⟩ 装饰以适配固定列宽——完整含义保留在 title 与表下注释行。 -->
          <table v-if="orientRows.length" class="table otable">
            <colgroup>
              <col class="c-id" />
              <col class="c-chi" />
              <col class="c-h" />
              <col class="c-fw" />
              <col class="c-c2" />
              <col class="c-cp" />
              <col class="c-f" />
            </colgroup>
            <thead>
              <tr>
                <th>峰</th>
                <th class="r" title="χc：峰中心方位角（°）">χc</th>
                <th class="r" title="H：方位角分布半高宽 FWHM（°）">H</th>
                <th class="r" title="f_FWHM：经验取向指数 (180° − H)/180">f_FWHM</th>
                <th class="r" title="cos²χ：实测法向取向因子 ⟨cos²χ⟩">cos²χ</th>
                <th class="r" title="cos²φ：链轴取向因子 ⟨cos²φc⟩ = 1 − ⟨cos²χ⟩（赤道反射）">cos²φ</th>
                <th class="r" title="f：Hermans 取向因子 f = (3cos²φ − 1)/2">f</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="{ row, stats } in orientRows" :key="row.id">
                <td><span class="dot" :style="{ background: row.color }" />#{{ row.index }}</td>
                <td class="r">{{ fmtSig(row.center, 5) }}</td>
                <template v-if="stats">
                  <td class="r">{{ fmtSig(stats.fwhmDeg, 4) }}</td>
                  <td class="r">{{ fmtSig(stats.fwhmIndex, 4) }}</td>
                  <td class="r">{{ fmtSig(stats.cos2Normal, 4) }}</td>
                  <td class="r">{{ fmtSig(stats.cos2Phi, 4) }}</td>
                  <td class="r num"><b>{{ fmtSig(stats.f, 4) }}</b></td>
                </template>
                <td v-else colspan="5" class="r hint">—</td>
              </tr>
            </tbody>
          </table>
          <p v-if="orientRows.length" class="xhint ocap">
            χc 峰位(°) · H 半高宽(°) · f_FWHM 经验指数 · cos²χ 法向 · cos²φ 链轴 · f Hermans
          </p>
          <p v-else class="xhint">尚无启用的峰：请先在“放峰”步骤添加峰。</p>
        </div>
      </div>

      <!-- ③ iPP Kβ（Turner-Jones） -->
      <div class="xcard" :class="{ on: polyOn.kb }">
        <label class="xhead">
          <input v-model="polyOn.kb" type="checkbox" class="xcheck" />
          <span class="xtitle">iPP β 晶相分数 Kβ</span>
          <span class="xstate">{{ polyOn.kb ? '已开启' : '未开启' }}</span>
        </label>
        <p class="xhint">
          Kβ = Iβ(300) / [Iα(110) + Iα(040) + Iα(130) + Iβ(300)]（Turner-Jones）；
          面积法用拟合面积（原式），峰高法用拟合峰高——两者并列给出。
        </p>
        <div v-if="polyOn.kb" class="xbody">
          <div class="kgrid">
            <label v-for="role in KB_ROLES" :key="role.key" class="olabel" :title="role.hint">
              {{ role.label }}
              <select :value="kbAssign[role.key] ?? ''" class="sel" @change="onKbSelect(role.key, $event)">
                <option value="">—</option>
                <option v-for="opt in peakSelectOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>
          </div>
          <template v-if="kb">
            <p class="xline">
              <span class="kbsrc">面积法</span>
              <b class="xval">Kβ = {{ (kb.kb * 100).toFixed(1) }}%</b>
            </p>
            <p class="xhint num">强度来源：拟合面积 A（Turner-Jones 原式）</p>
            <p v-if="kbH" class="xline">
              <span class="kbsrc">峰高法</span>
              <b class="xval">Kβ = {{ (kbH.kb * 100).toFixed(1) }}%</b>
            </p>
            <p v-if="kbH" class="xhint num">峰高来源：拟合峰高 h（同一公式，代入峰高）</p>
          </template>
          <p v-else class="xline hint"><span class="xval hint">未指派完整</span></p>
        </div>
      </div>

      <!-- ④ 批量曲线分析（2026-10-23 用户要求）：同一套指派/开关逐曲线计算，
           每条曲线默认折叠，点开看明细。 / Multi-curve analyses over the
           batch results — same assignments & switches, collapsed per curve. -->
      <div v-if="hasBatchCurves" class="xcard on">
        <label class="xhead">
          <span class="xtitle">批量曲线分析（{{ batchAnalyses.length }} 条已拟合）</span>
          <span class="xstate">同一套指派</span>
        </label>
        <p class="xhint">
          逐曲线使用上方开关与指派（峰 id 即模板 id）；点击曲线行展开明细。
        </p>
        <div class="bc-list">
          <details v-for="c in batchAnalyses" :key="c.id" class="bc-item">
            <summary>
              <span class="bc-name" :title="c.name">{{ c.name }}</span>
              <span v-if="c.crys" class="bc-val">Xc {{ c.crys.xcPct.toFixed(1) }}%</span>
              <span v-if="c.kb" class="bc-val">Kβ<sub>A</sub> {{ (c.kb.kb * 100).toFixed(1) }}%</span>
              <span v-if="c.kbH" class="bc-val">Kβ<sub>h</sub> {{ (c.kbH.kb * 100).toFixed(1) }}%</span>
              <span v-if="c.orient.length" class="bc-val">f {{ fmtSig(c.orient[0]?.stats?.f ?? Number.NaN, 3) }}</span>
            </summary>
            <div class="bc-body">
              <p v-if="c.crys" class="xhint num">
                Xc = {{ c.crys.xcPct.toFixed(2) }}% · A结晶 {{ fmtSig(c.crys.crystalArea, 6) }} · A非晶 {{ fmtSig(c.crys.amorphousArea, 6) }}
              </p>
              <p v-if="c.kb" class="xhint num">
                Kβ 面积法 = {{ (c.kb.kb * 100).toFixed(2) }}%（强度来源：拟合面积 A）
              </p>
              <p v-if="c.kbH" class="xhint num">
                Kβ 峰高法 = {{ (c.kbH.kb * 100).toFixed(2) }}%（峰高来源：拟合峰高 h）
              </p>
              <table v-if="c.orient.length" class="bc-table">
                <thead>
                  <tr><th>峰</th><th class="r">χc</th><th class="r">H</th><th class="r">f</th></tr>
                </thead>
                <tbody>
                  <tr v-for="row in c.orient" :key="row.index">
                    <td>#{{ row.index }}</td>
                    <td class="r num">{{ fmtSig(row.center, 5) }}</td>
                    <td class="r num">{{ row.stats ? fmtSig(row.stats.fwhmDeg, 4) : '—' }}</td>
                    <td class="r num">{{ row.stats ? fmtSig(row.stats.f, 4) : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.content {
  padding: 2px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── 分析卡 / analysis card (one per switch) ─────────────────────────── */
.xcard {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 9px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--bg-1);
  transition: border-color var(--speed-fast) ease;
}
.xcard.on {
  border-color: var(--accent-line);
}
/* Title row: checkbox + name + state; the whole row toggles. /
 *  标题行：勾选框 + 名称 + 状态；整行可点。 */
.xhead {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}
.xcheck {
  margin: 0;
  flex: none;
  accent-color: var(--accent);
}
/* The title may wrap inside its own flex item; the state badge stays whole. /
 *  标题可在自身 flex 项内换行，状态徽标保持整宽。 */
.xtitle {
  min-width: 0;
  font-weight: 600;
  color: var(--text-1);
  line-height: 1.35;
}
.xstate {
  margin-left: auto;
  flex: none;
  white-space: nowrap;
  padding: 0 6px;
  font-size: 9.5px;
  font-weight: 600;
  line-height: 15px;
  /* text-2, not text-3: the disabled badge sits on bg-2 and needs ≥ 4.5:1. /
     用 text-2 而非 text-3：未开启徽章坐在 bg-2 上，需满足 4.5:1 对比度。 */
  color: var(--text-2);
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.xcard.on .xstate {
  /* 2026-10-22 visual review: accent-on-accent-soft was 3.68:1 — below AA.
     Use the deeper blue for the ON badge text. / 用更深的蓝保证 ≥4.5:1。 */
  color: #1d4ed8;
  background: var(--accent-soft);
  border-color: var(--accent-line);
}
.xbody {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.xhint {
  margin: 0;
  font-size: 10.5px;
  line-height: 1.5;
  color: var(--text-2);
}
.ocap {
  margin-top: -2px;
  font-size: 9.5px;
}

/* ── 批量曲线分析 / batch multi-curve analyses (collapsed per curve) ───── */
.bc-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bc-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 3px 8px;
  font-size: 11.5px;
  background: var(--bg-2);
}
.bc-item summary {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  list-style: none;
  min-width: 0;
}
.bc-item summary::-webkit-details-marker {
  display: none;
}
.bc-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: var(--text-1);
}
.bc-val {
  flex: none;
  white-space: nowrap;
  /* blue-700 for AA on the row background (2026-10-23 visual review). */
  color: #1d4ed8;
  font-weight: 600;
  font-size: 11px;
}
.bc-val sub {
  font-size: 8px;
}
.bc-body {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed var(--border);
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.bc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
.bc-table th,
.bc-table td {
  padding: 1.5px 6px;
  text-align: left;
  white-space: nowrap;
}
.bc-table th {
  color: var(--text-2);
  font-weight: 600;
}
.bc-table .r {
  text-align: right;
}
/* X-FAIS: the value never splits inside the 330 px side panel
 * (`Kβ = 14.6` + `%`, `Xc = 56.8 %`, `未指派完整`). / 数值不拆行。 */
.xline {
  margin: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
}
.xval {
  margin-left: auto;
  flex: none;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  /* 2026-10-23 visual review: accent-on-white was 3.68:1 — use blue-700. /
     数值用更深的蓝保证对比度。 */
  color: #1d4ed8;
}
/* Source badge in front of a Kβ value line (面积法 / 峰高法). /
 * Kβ 数值行前的来源徽章。 */
.kbsrc {
  flex: none;
  font-size: 10px;
  line-height: 16px;
  padding: 0 7px;
  color: var(--text-2);
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.xline .xval.hint {
  margin-left: 0;
  color: var(--text-3);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}

/* ── 结晶度 chip / crystallinity role chips ──────────────────────────── */
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--bg-2);
  color: var(--text-1);
  font-family: inherit;
  cursor: pointer;
}
.chip em {
  font-style: normal;
  color: var(--text-3);
}
.chip--amorph {
  border-color: var(--warning);
  background: var(--warning-soft);
}
.chip--amorph em {
  color: var(--warning);
  font-weight: 600;
}

/* ── 取向 / Kβ 选项行 ────────────────────────────────────────────────── */
.orow-opts,
.kgrid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
}
.olabel {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--text-2);
}
.olabel.check {
  cursor: pointer;
}
/* X-FAIS: the native checkbox picked up the browser's default blue, which
 * clashed with the X-FAIS accent. / X-FAIS：勾选框改用主题色。 */
.olabel input[type='checkbox'] {
  accent-color: var(--accent);
}
.sel {
  max-width: 118px;
  padding: 2px 5px;
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-1);
}

/* X-FAIS: the 330 px side panel clipped `f_FWHM`/`cos²φ` in the orientation
 * table — fixed layout pairs explicit column shares with 9 px short headers,
 * so all 7 columns stay inside the panel without ellipsis.
 * X-FAIS：330px 侧栏会把取向表的 `f_FWHM`/`cos²φ` 表头截断——固定布局改为
 * 显式列宽 + 9px 短表头，7 列全部落在栏内，表头不做省略号截断。 */
.otable {
  table-layout: fixed;
  width: 100%;
}
.otable col.c-id {
  width: 14%;
}
.otable col.c-chi,
.otable col.c-h {
  width: 13%;
}
.otable col.c-fw {
  width: 18%;
}
.otable col.c-c2,
.otable col.c-cp,
.otable col.c-f {
  width: 14%;
}
/* X-FAIS: base.css `.table th/td` is emitted after this scoped block at equal
 * specificity, which silently restored its 11 px / #94a3b8 padding and text
 * style; the `.xcard` prefix raises specificity so the compact 9 px table wins.
 * X-FAIS：base.css 的 `.table th/td` 在同等特异性下于本 scoped 块之后生效，
 * 会把表头还原成 11px / #94a3b8 的内边距与字色；加 `.xcard` 前缀提高特异性，
 * 紧凑表头才会生效。 */
.xcard .otable th,
.xcard .otable td {
  padding: 2px 2px;
}
.xcard .otable th {
  font-size: 9px;
  line-height: 1.3;
  color: var(--text-2);
  white-space: nowrap;
}
.xcard .otable td {
  font-size: 9.5px;
}
</style>
