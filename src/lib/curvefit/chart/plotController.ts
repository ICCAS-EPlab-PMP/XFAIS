/**
 * PlotController — uPlot rendering + a hand-drawn overlay canvas that owns
 * every interaction (crosshair, box zoom, peak placement, anchor dragging,
 * point exclusion).
 *
 * Fluency red lines honored here:
 *  - Drag frames never call the backend: param mutation → TS eval → canvas.
 *  - pointermove work is rAF-coalesced (drag apply + overlay draw).
 *  - Large data (> maxSamples visible) uses min-max bucket LOD that keeps
 *    both extremes per pixel bucket, so narrow peaks stay sharp.
 *  - uPlot series bodies are plain TypedArrays outside Vue reactivity.
 */
import uPlot from 'uplot'
import type { PeakSpec } from '@/lib/pwcore/shared/types'
import { BASELINE_FN_MAP, PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'
import { indexAtX, useSpectrum } from '../stores/spectrum'
import {
  bumpEdit,
  createPeak,
  reinsertPeak,
  removePeak,
  selectPeak,
  setPeakEnabled,
  usePeaks,
} from '../stores/peaks'
import { useFit, stopFit } from '../stores/fit'
import { useUi } from '../stores/ui'
import { useBaselineWork } from '../stores/baseline-work'
import { pushCommand } from '../stores/undo'
import { pushToast } from '../stores/toast'
import {
  evalPeak,
  evalBaseline,
  measurePeakGeometry,
  solveAnchorDrag,
  type PeakGeometry,
} from '../core-bridge/engine'
import { readChartPalette, type ChartPalette } from '../utils/palette'
import { guardContextFrom, minMeaningfulWidth, widthKeysOfSpec } from '../utils/paramGuard'
import {
  buildViewTable,
  sampleCurve,
  type ViewTable,
} from '../utils/lod'
import { fmtTick } from '../utils/format'

const MAX_SAMPLES = 3200
// Grab radius in CSS px. Generous on purpose: the visible marks are small, and
// missing one used to fall through to box-zoom, which feels like "drag failed".
const ANCHOR_R = 14
const ANCHOR_R_SMALL = 12
const POINT_R = 5
/** Baseline point-selection hit radius (generous, original manual allows ±7 px). */
const BASELINE_POINT_R = 7
const DRAG_EPS = 3

type AnchorKind = 'main' | 'leftHalf' | 'rightHalf' | 'quarter'

interface AnchorHit {
  kind: AnchorKind
  peakId: string
  dist: number
}

type DownTarget =
  | { t: 'anchor'; hit: AnchorHit }
  | { t: 'point'; idx: number; dist: number }
  | { t: 'baseline-point'; idx: number; dist: number }
  | { t: 'blank' }

interface BandState {
  /** drag-right = exclude, drag-left = restore */
  dir: 'exclude' | 'include'
  /** inclusive raw-index range (lo/hi already normalized) */
  lo: number
  hi: number
}

interface PendingState {
  sx: number
  sy: number
  lx: number
  ly: number
  moved: boolean
  target: DownTarget
}

interface DragState {
  peakId: string
  kind: AnchorKind
  startP: Record<string, number>
  startGeom: PeakGeometry
  sx: number
  sy: number
  /** Smallest data-resolvable width at drag start (see paramGuard.ts). */
  minWidth: number
}

function withAlpha(hex: string, a: number): string {
  const m = hex.replace('#', '')
  const full = m.length === 3 ? m.split('').map((c) => c + c).join('') : m
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  if ([r, g, b].some(Number.isNaN)) return hex
  return `rgba(${r},${g},${b},${a})`
}

export class PlotController {
  private mainEl: HTMLElement
  private residEl: HTMLElement
  /** Optional external container that hosts the uPlot legend row. */
  private legendEl: HTMLElement | null
  private pal: ChartPalette = readChartPalette()

  private u1: uPlot | null = null
  private u2: uPlot | null = null
  private overlay: HTMLCanvasElement | null = null
  private octx: CanvasRenderingContext2D | null = null
  private ro: ResizeObserver | null = null
  /** uPlot `.over` element carrying the x-only wheel-zoom listener. */
  private wheelEl: HTMLElement | null = null
  /**
   * Y range captured by a wheel zoom and re-applied after the rAF data refresh:
   * uPlot auto-ranges y against the freshly rebuilt (zoomed) view table, which
   * would silently change the vertical scale. Wheel zoom is x-only by contract.
   * 滚轮缩放期间锁定的 y 范围：视图重建后 uPlot 会按新数据重算 y 量程，
   * 这里在刷新之后原样回写，保证滚轮只动横轴。
   */
  private wheelYLock: { min: number; max: number } | null = null

  private view: ViewTable | null = null
  /** Length of the last pushed view table (uPlot i0/i1 invalidation guard). */
  private lastViewLen = 0
  private dataYV: Float64Array | null = null
  private baseV: Float64Array | null = null
  private fitV: Float64Array | null = null
  private residV: Float64Array | null = null
  private compCurves = new Map<string, Float64Array>()
  /** aligned slot indices per peak id (series index in uPlot data) */
  private compSlots = new Map<string, number>()

  // interaction state
  private hoverPx: { x: number; y: number } | null = null
  private hoverAnchor: AnchorHit | null = null
  private pending: PendingState | null = null
  private mode: 'idle' | 'zoom' | 'drag' | 'band' = 'idle'
  private drag: DragState | null = null
  private zoomRect: { x0: number; y0: number; x1: number; y1: number } | null = null
  /** Present while a baseline/data point-band drag is in progress. */
  private band: BandState | null = null
  private rafId = 0
  private viewRafId = 0

  constructor(mainEl: HTMLElement, residEl: HTMLElement, legendEl: HTMLElement | null = null) {
    this.mainEl = mainEl
    this.residEl = residEl
    this.legendEl = legendEl
  }

  // ------------------------------------------------------------------
  // lifecycle
  // ------------------------------------------------------------------

  attach(): void {
    this.pal = readChartPalette()
    this.rebuild()
    this.ro = new ResizeObserver(() => this.onResize())
    this.ro.observe(this.mainEl)
    this.ro.observe(this.residEl)
  }

  destroy(): void {
    this.ro?.disconnect()
    this.ro = null
    this.destroyPlots()
    if (this.rafId) cancelAnimationFrame(this.rafId)
    if (this.viewRafId) cancelAnimationFrame(this.viewRafId)
  }

  retheme(): void {
    this.pal = readChartPalette()
    this.rebuild()
  }

  private destroyPlots(): void {
    this.unbindWheelZoom()
    this.u1?.destroy()
    this.u1 = null
    this.u2?.destroy()
    this.u2 = null
    this.overlay = null
    this.octx = null
    this.mainEl.innerHTML = ''
    this.residEl.innerHTML = ''
  }

  /** Full recreation: data / peak structure / theme changed. */
  rebuild(): void {
    this.destroyPlots()
    // Re-read the palette so series/axis colors follow the active theme
    // (the theme watcher routes here on `theme.mode` changes).
    this.pal = readChartPalette()
    const sp = useSpectrum()
    const xv = sp.x.value
    const yv = sp.y.value
    if (!xv || !yv || xv.length === 0) return

    this.compCurves.clear()
    this.createMain()
    this.createResid()
    this.refreshChart(true)
  }

  private onResize(): void {
    // Lazily (re)create either plot once its host has real layout — guards
    // against zero-size-at-mount timing (v-if branch insertion). A freshly
    // created plot has no data yet, so feed it immediately.
    if (this.ensurePlots()) {
      this.refreshChart(true)
      return
    }
    const w = this.mainEl.clientWidth
    const h = this.mainEl.clientHeight
    const w2 = this.residEl.clientWidth
    const h2 = this.residEl.clientHeight
    if (this.u1 && w > 40 && h > 40) this.u1.setSize({ width: w, height: h })
    if (this.u2 && w2 > 40 && h2 > 20) this.u2.setSize({ width: w2, height: h2 })
  }

  /** Create either plot if its host has real layout; true when one was created. */
  private ensurePlots(): boolean {
    let created = false
    if (!this.u1 && this.mainEl.clientWidth > 40 && this.mainEl.clientHeight > 40) {
      this.createMain()
      created = this.u1 !== null
    }
    if (!this.u2 && this.residEl.clientWidth > 40 && this.residEl.clientHeight > 20) {
      this.createResid()
      created = created || this.u2 !== null
    }
    return created
  }

  // ------------------------------------------------------------------
  // plot construction
  // ------------------------------------------------------------------

  private cursorOff(): uPlot.Cursor {
    const none = (): null => null
    return {
      show: false,
      x: false,
      y: false,
      points: { show: false },
      focus: { prox: -1 },
      left: -10,
      top: -10,
      idx: null,
      drag: { x: false, y: false },
      bind: {
        mousedown: none,
        mouseup: none,
        click: none,
        dblclick: none,
        mousemove: none,
        mouseleave: none,
        mouseenter: none,
      },
    }
  }

  private baseAxes(): uPlot.Axis[] {
    const fmt = (_u: uPlot, splits: number[]): string[] => splits.map(fmtTick)
    return [
      {
        stroke: this.pal.axis,
        grid: { show: true, stroke: this.pal.grid, width: 1 },
        ticks: { show: true, stroke: this.pal.grid, width: 1, size: 4 },
        values: fmt,
      },
      {
        stroke: this.pal.axis,
        grid: { show: true, stroke: this.pal.grid, width: 1 },
        ticks: { show: true, stroke: this.pal.grid, width: 1, size: 4 },
        values: fmt,
      },
    ]
  }

  private yRange = (_u: uPlot, dMin: number, dMax: number): uPlot.Range.MinMax => {
    if (!Number.isFinite(dMin) || !Number.isFinite(dMax)) return [0, 1]
    if (dMin === dMax) {
      const pad = Math.abs(dMax) * 0.1 || 1
      return [dMin - pad, dMax + pad]
    }
    const pad = (dMax - dMin) * 0.07
    return [dMin - pad, dMax + pad]
  }

  private createMain(): void {
    const sp = useSpectrum()
    const ui = useUi()
    const pk = usePeaks()
    const w = this.mainEl.clientWidth
    const h = this.mainEl.clientHeight
    if (w < 40 || h < 40) return

    // slot order: 0=x  1=data  2=baseline  3..=comps  last=fit.
    // The fit/composite series is LAST so uPlot draws it on top of every
    // peak component (issue: fit must stay readable over the comps).
    this.compSlots.clear()
    const peaks = pk.list.value
    peaks.forEach((p, i) => this.compSlots.set(p.id, 3 + i))

    const compSeries = (p: PeakSpec, i: number): uPlot.Series => {
      const color = p.color ?? this.pal.accent
      const fname = PEAK_FN_MAP.get(p.fn)?.name ?? p.fn
      return {
        label: `P${i + 1}·${fname}`,
        stroke: () => (p.enabled ? color : withAlpha(color, 0.32)),
        width: 1.3,
        dash: p.enabled ? undefined : [4, 3],
        spanGaps: false,
      }
    }

    const showPoints = ui.showPoints.value && sp.meta.n <= 2000

    // uPlot's own legend is re-parented into the external header row so it
    // never steals plot height; theme styling lives in PlotArea's :deep CSS.
    const legend: uPlot.Legend = this.legendEl
      ? {
          show: true,
          live: false,
          mount: (_u: uPlot, el: HTMLElement): void => {
            this.legendEl?.appendChild(el)
          },
        }
      : { show: false }

    const opts: uPlot.Options = {
      width: w,
      height: h,
      legend,
      cursor: this.cursorOff(),
      scales: {
        x: { time: false },
        y: { range: this.yRange },
      },
      axes: this.baseAxes(),
      series: [
        {},
        {
          label: '数据',
          stroke: this.pal.data,
          width: 1,
          // Excluded raw points are pushed as nulls (see pushData) — the curve
          // must BREAK there instead of drawing a straight chord over the gap.
          // spanGaps: false 让排除点处的 null 真正断开曲线，而不是画一条跨越空洞的直线。
          spanGaps: false,
          points: { show: showPoints, size: 3, stroke: this.pal.data, fill: this.pal.data },
        },
        {
          label: '基线',
          stroke: this.pal.base,
          width: 1.2,
          dash: [6, 4],
        },
        ...peaks.map((p, i) => compSeries(p, i)),
        {
          label: '拟合',
          stroke: this.pal.fit,
          width: 2.2,
        },
      ],
      hooks: {
        setScale: [(u, key) => {
          if (u === this.u1 && key === 'x') this.scheduleViewRefresh()
        }],
        draw: [(u) => {
          if (u === this.u1) this.syncOverlaySize()
        }],
      },
    }

    this.u1 = new uPlot(opts, undefined, this.mainEl)
    // X-only wheel zoom owned here (capture phase, before anything uPlot hosts).
    this.bindWheelZoom()

    // interaction overlay lives inside uPlot's .over layer (plot-area aligned)
    const overlay = document.createElement('canvas')
    overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;touch-action:none;'
    this.u1.over.appendChild(overlay)
    this.overlay = overlay
    this.octx = overlay.getContext('2d')
    this.bindOverlayEvents(overlay)
    this.syncOverlaySize()
  }

  private createResid(): void {
    const w = this.residEl.clientWidth
    const h = this.residEl.clientHeight
    if (w < 40 || h < 20) return
    const axes = this.baseAxes()
    const opts: uPlot.Options = {
      width: w,
      height: h,
      legend: { show: false },
      cursor: this.cursorOff(),
      padding: [2, null, null, null],
      scales: { x: { time: false }, y: { range: this.yRange } },
      axes,
      series: [
        {},
        { label: '残差', stroke: this.pal.resid, width: 1, spanGaps: false },
      ],
      hooks: {
        draw: [(u) => {
          // central zero reference line (weak dashed) for the residuals
          const ctx = u.ctx
          const top = u.bbox.top
          const hgt = u.bbox.height
          const y0 = u.valToPos(0, 'y', true)
          if (y0 >= top && y0 <= top + hgt) {
            ctx.save()
            ctx.strokeStyle = withAlpha(this.pal.axis, 0.7)
            ctx.lineWidth = 1
            ctx.setLineDash([4, 4])
            ctx.beginPath()
            ctx.moveTo(u.bbox.left, y0)
            ctx.lineTo(u.bbox.left + u.bbox.width, y0)
            ctx.stroke()
            ctx.restore()
          }
        }],
      },
    }
    this.u2 = new uPlot(opts, undefined, this.residEl)
  }

  private syncOverlaySize(): void {
    const ov = this.overlay
    const u = this.u1
    if (!ov || !u) return
    const dpr = uPlot.pxRatio
    const w = u.over.clientWidth
    const h = u.over.clientHeight
    if (w < 1 || h < 1) return
    const bw = Math.round(w * dpr)
    const bh = Math.round(h * dpr)
    if (ov.width !== bw || ov.height !== bh) {
      ov.width = bw
      ov.height = bh
    }
  }

  // ------------------------------------------------------------------
  // data / curve refresh
  // ------------------------------------------------------------------

  private currentXRange(): { min: number | null; max: number | null } {
    const u = this.u1
    const sp = useSpectrum()
    if (!u) return { min: null, max: null }
    const sx = u.scales.x
    const mn = typeof sx.min === 'number' ? sx.min : null
    const mx = typeof sx.max === 'number' ? sx.max : null
    if (mn === null || mx === null || !Number.isFinite(mn) || !Number.isFinite(mx)) {
      return { min: null, max: null }
    }
    // clamp to data span so LOD stays within the dataset
    const lo = Math.max(mn, Math.min(sp.meta.xMin, sp.meta.xMax) - (sp.meta.xMax - sp.meta.xMin) * 0.1)
    const hi = Math.min(mx, Math.max(sp.meta.xMin, sp.meta.xMax) + (sp.meta.xMax - sp.meta.xMin) * 0.1)
    return { min: lo, max: hi }
  }

  /**
   * Recompute view table + all curves and push into uPlot.
   * @param fullRange true → ignore current zoom (view reset)
   * @param onlyPeakId drag fast-path: re-evaluate a single component
   */
  refreshChart(fullRange = false, onlyPeakId?: string): void {
    this.ensurePlots()
    const u1 = this.u1
    const sp = useSpectrum()
    const pk = usePeaks()
    const ui = useUi()
    const xv = sp.x.value
    const yv = sp.y.value
    if (!u1) return
    if (!xv || !yv) return

    const range = fullRange ? { min: null, max: null } : this.currentXRange()
    this.view = buildViewTable(xv, yv, range.min, range.max, MAX_SAMPLES)
    const view = this.view
    const n = view.xs.length

    // baseline (live params → always current, incl. preview edits)
    const bl = pk.baseline
    const scan = pk.scanBase.value
    if (scan && scan.length === yv.length) {
      // 自动扫描 preview: sample the full-range vector into the current view
      this.baseV = sampleCurve(scan, view)
    } else {
      const hasBase = bl.enabled && bl.fn !== 'none' && BASELINE_FN_MAP.has(bl.fn)
      this.baseV = hasBase ? evalBaseline(bl.fn, bl.p, view.xs) : null
    }

    // data series (optionally baseline-subtracted preview)
    const dataY = Float64Array.from(view.ys)
    if (ui.subtractPreview.value && this.baseV) {
      for (let i = 0; i < n; i++) dataY[i] = view.ys[i] - this.baseV[i]
    }
    this.dataYV = dataY

    // component curves (view-space evaluation, buffer-reused)
    for (const p of pk.list.value) {
      if (onlyPeakId && p.id !== onlyPeakId) continue
      const prev = this.compCurves.get(p.id)
      const buf = prev && prev.length === n ? prev : new Float64Array(n)
      evalPeak(p.fn, p.p, view.xs, buf)
      this.compCurves.set(p.id, buf)
    }

    // Model envelope (the "拟合" line): ALWAYS the live composite of the
    // CURRENT parameters — enabled component curves + baseline. It follows
    // anchor drags and streamed iterations in real time (the reference application Y2 behavior);
    // the engine's own yFit/residual arrays remain authoritative for the
    // report and exports.
    const bv = this.baseV
    let any = bv !== null
    const sum = bv ? Float64Array.from(bv) : new Float64Array(n)
    for (const p of pk.list.value) {
      if (!p.enabled) continue
      const c = this.compCurves.get(p.id)
      if (!c) continue
      any = true
      for (let i = 0; i < n; i++) sum[i] += c[i]
    }
    this.fitV = any ? sum : null

    // Residual: live y − model envelope over the current view.
    if (this.fitV) {
      const r = new Float64Array(n)
      for (let i = 0; i < n; i++) r[i] = view.ys[i] - sum[i]
      this.residV = r
    } else {
      this.residV = null
    }

    this.pushData(fullRange)
  }

  private pushData(resetScales: boolean): void {
    const u1 = this.u1
    const u2 = this.u2
    const view = this.view
    if (!u1 || !view || !this.dataYV) return
    const pk = usePeaks()
    const sp = useSpectrum()

    const empty = new Float64Array(0)
    // Column order mirrors series order: x, data, baseline, comps..., fit.
    // The DATA column is nullable: excluded raw points become `null`, so the
    // curve shows real gaps on every step (the values stay in view.ys /
    // dataYV for residuals, fit input and exports).
    // 数据列可为 null：被排除的原始点在曲线上一律断开（数值本身仍保留在
    // view.ys / dataYV 中，供残差、拟合输入与导出使用）。
    const dataCol: (number | null)[] = new Array(view.xs.length)
    const mask = sp.mask.value
    for (let k = 0; k < dataCol.length; k++) {
      const ri = view.rawIdx[k]
      dataCol[k] = mask && ri >= 0 && ri < mask.length && mask[ri] === 0 ? null : this.dataYV[k]
    }
    const aligned: Array<Float64Array | (number | null)[]> = [
      view.xs,
      dataCol,
      this.baseV ?? empty,
    ]
    for (const p of pk.list.value) aligned.push(this.compCurves.get(p.id) ?? empty)
    aligned.push(this.fitV ?? empty)
    // guard against any series/columns desync (peak added between rebuilds):
    // pad missing columns so existing series keep their data slots.
    while (aligned.length < u1.series.length) aligned.push(empty)
    const viewLen = view.xs.length
    // uPlot's AlignedData is a tuple of (x, ...y) columns; our array is built
    // dynamically, so the cast is the only way to feed the mixed typed/nullable
    // columns it accepts at runtime.
    u1.setData(aligned as unknown as uPlot.AlignedData, resetScales);
    if (!resetScales) {
      // uPlot's setData(data, false) does NOT repaint and does NOT recompute
      // its visible index window (i0/i1) — that only happens when a scale is
      // committed. After an x-zoom the new view table is shorter than the old
      // window; drawSeries clamps the stale window to the new array end, so
      // the curve truncates (wheel) or disappears entirely (a narrow 放大镜
      // band). Re-assert the UNCHANGED x range: an identical range fires no
      // setScale hook (no refresh loop), but setScales() recomputes i0/i1
      // against the new table before drawing. Only needed when the table
      // length changed — anchor drags keep the same table and stay on the
      // direct repaint path (avoids an unnecessary y auto-range).
      // setData(false) 不重绘、也不重算可见索引窗口（i0/i1）——后者只在提
      // 交 scale 时计算。x 轴放大后新视图更短，旧窗口被夹到数组末尾，曲线
      // 会被截断（滚轮）或整段消失（很窄的框选缩放）。这里用“原样”的 x 量程
      // 再提交一次：量程未变化不会触发 setScale 钩子（不会自激），但
      // setScales() 会按新表重算 i0/i1。仅在表长变化时执行——锚点拖动表长
      // 不变，仍走直接重绘，避免不必要的 y 自动量程。
      const sx = u1.scales.x
      if (viewLen !== this.lastViewLen && typeof sx.min === 'number' && typeof sx.max === 'number') {
        u1.setScale('x', { min: sx.min, max: sx.max })
      } else {
        // redraw(false) calls commit() directly: the forced repaint we need
        // for live drag / streamed fit updates.
        u1.redraw(false)
      }
    }
    this.lastViewLen = viewLen

    if (u2) {
      const d2: uPlot.AlignedData = this.residV ? [view.xs, this.residV] : [view.xs, []]
      u2.setData(d2, false)
      // setData(resetScales=false) keeps the previous (possibly empty-data)
      // y-range — the residual must always be re-ranged to its own data or it
      // collapses onto the axis and looks "empty" after a fit.
      this.syncResidScales()
    }
    this.drawOverlay()
  }

  /** Fit the residual plot's y-range to its data; keep x locked to the main chart. */
  private syncResidScales(): void {
    const u1 = this.u1
    const u2 = this.u2
    if (!u1 || !u2) return
    const sx = u1.scales.x
    if (typeof sx.min === 'number' && typeof sx.max === 'number') {
      u2.setScale('x', { min: sx.min, max: sx.max })
    }
    const resid = this.residV
    if (!resid) return
    let lo = Number.POSITIVE_INFINITY
    let hi = Number.NEGATIVE_INFINITY
    for (let i = 0; i < resid.length; i++) {
      const v = resid[i]
      if (v !== null && Number.isFinite(v)) {
        if (v < lo) lo = v
        if (v > hi) hi = v
      }
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return
    if (lo === hi) {
      lo -= 0.5
      hi += 0.5
    }
    const pad = (hi - lo) * 0.14
    u2.setScale('y', { min: lo - pad, max: hi + pad })
  }

  private scheduleViewRefresh(): void {
    if (this.viewRafId) return
    this.viewRafId = requestAnimationFrame(() => {
      this.viewRafId = 0
      this.refreshChart(false)
      // Re-pin a wheel zoom's y range (see wheelYLock).
      const y = this.wheelYLock
      if (y) {
        this.wheelYLock = null
        const u = this.u1
        if (u) u.setScale('y', { min: y.min, max: y.max })
      }
    })
  }

  // ------------------------------------------------------------------
  // coordinate helpers
  // ------------------------------------------------------------------

  /**
   * The overlay canvas is mounted inside uPlot's `.u-over`, so its own
   * origin IS the plot-area origin. uPlot's valToPos also returns plot-area
   * coordinates — no bbox offset may be added here, or every overlay element
   * is displaced by the axis margins.
   */
  private eventToPlot(e: PointerEvent | MouseEvent): { x: number; y: number } {
    const ov = this.overlay
    if (!ov) return { x: 0, y: 0 }
    const rect = ov.getBoundingClientRect()
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }
  }

  private insidePlot(p: { x: number; y: number }): boolean {
    const u = this.u1
    if (!u) return false
    return (
      p.x >= 0 && p.x <= u.bbox.width / uPlot.pxRatio &&
      p.y >= 0 && p.y <= u.bbox.height / uPlot.pxRatio
    )
  }

  /** Cached geometry per (fn, params) — measurement is ~400 evals per peak. */
  private geomCache = new Map<string, PeakGeometry>()

  private geomOf(p: PeakSpec): PeakGeometry {
    const meta = PEAK_FN_MAP.get(p.fn)
    const keys = meta ? meta.params.map((pm) => pm.key) : Object.keys(p.p)
    const key = p.fn + '|' + keys.map((k) => (p.p[k] ?? 0).toPrecision(12)).join(',')
    let g = this.geomCache.get(key)
    if (!g) {
      g = measurePeakGeometry(p.fn, p.p)
      if (this.geomCache.size > 400) this.geomCache.clear()
      this.geomCache.set(key, g)
    }
    return g
  }

  /**
   * the reference application anchor set: primary (center+amplitude), left/right half-maxima
   * (width, and asymmetry on asymmetric functions), quarter-maxima FW25
   * (shape parameters). Up to 4 draggable points per peak.
   */
  private anchorsOf(p: PeakSpec): {
    main: [number, number]
    leftHalf: [number, number] | null
    rightHalf: [number, number] | null
    quarter: [number, number] | null
    geom: PeakGeometry
  } {
    const g = this.geomOf(p)
    const meta = PEAK_FN_MAP.get(p.fn)
    // FW25 (quarter) anchor exists only when the function carries a shape /
    // asymmetry parameter beyond a0/a1/a2 — 3-param peaks have 3 anchors.
    const hasShapeParam = (meta?.params.length ?? 0) >= 4
    return {
      main: [g.centerX, g.height],
      leftHalf: g.leftHalfX === null ? null : [g.leftHalfX, g.height / 2],
      rightHalf: g.rightHalfX === null ? null : [g.rightHalfX, g.height / 2],
      quarter: hasShapeParam && g.quarterX !== null ? [g.quarterX, g.height / 4] : null,
      geom: g,
    }
  }

  private hitTestAnchors(px: number, py: number): AnchorHit | null {
    const u = this.u1
    if (!u) return null
    const pk = usePeaks()
    let best: AnchorHit | null = null
    const sel = pk.selectedId.value
    for (const p of pk.list.value) {
      const a = this.anchorsOf(p)
      const boost = p.id === sel ? -2 : 0
      const consider = (kind: AnchorKind, pt: [number, number] | null, r: number): void => {
        if (!pt) return
        const dx = px - u.valToPos(pt[0], 'x')
        const dy = py - u.valToPos(pt[1], 'y')
        const d = Math.hypot(dx, dy)
        if (d <= r && (!best || d + boost < best.dist)) best = { kind, peakId: p.id, dist: d }
      }
      consider('main', a.main, ANCHOR_R)
      consider('leftHalf', a.leftHalf, ANCHOR_R_SMALL)
      consider('rightHalf', a.rightHalf, ANCHOR_R_SMALL)
      consider('quarter', a.quarter, ANCHOR_R_SMALL)
    }
    return best
  }

  /** Nearest raw data point within `r` px (both axes). */
  private hitTestPoint(px: number, py: number, r = POINT_R): { idx: number; dist: number } | null {
    const u = this.u1
    const sp = useSpectrum()
    const xv = sp.x.value
    const yv = sp.y.value
    if (!u || !xv || !yv) return null
    const xVal = u.posToVal(px, 'x')
    const i0 = indexAtX(xVal)
    if (i0 < 0) return null
    let best: { idx: number; dist: number } | null = null
    for (let i = Math.max(0, i0 - 3); i <= Math.min(xv.length - 1, i0 + 3); i++) {
      const dx = Math.abs(u.valToPos(xv[i], 'x') - px)
      const dy = Math.abs(u.valToPos(yv[i], 'y') - py)
      if (dx > r || dy > r) continue
      const d = Math.hypot(dx, dy)
      if (!best || d < best.dist) best = { idx: i, dist: d }
    }
    return best
  }

  /**
   * Anchors belong to the peak/fit/report steps. The baseline and data steps
   * reserve the left drag for section editing, so anchor grabbing is off.
   * 锚点属于放峰/拟合/报告步骤；基线/数据步骤把左键拖动留给区段编辑。
   */
  private anchorsEnabled(): boolean {
    const step = useUi().step.value
    return step !== 'baseline' && step !== 'data'
  }

  // ------------------------------------------------------------------
  // interaction
  // ------------------------------------------------------------------

  private bindOverlayEvents(ov: HTMLCanvasElement): void {
    ov.addEventListener('pointerdown', this.onPointerDown)
    ov.addEventListener('pointermove', this.onPointerMove)
    ov.addEventListener('pointerup', this.onPointerUp)
    ov.addEventListener('pointerleave', this.onPointerLeave)
    ov.addEventListener('contextmenu', this.onContextMenu)
    ov.addEventListener('dblclick', this.onDblClick)
  }

  private onPointerDown = (e: PointerEvent): void => {
    if (e.button !== 0) return
    const u = this.u1
    const ov = this.overlay
    if (!u || !ov) return
    const ui = useUi()
    ui.popover.value = null

    const p = this.eventToPlot(e)
    if (!this.insidePlot(p)) return
    // synthetic/automation events may carry a pointerId with no real pointer;
    // a failed capture must not abort the whole gesture.
    try {
      ov.setPointerCapture(e.pointerId)
    } catch {
      /* pointer not capturable — continue without capture */
    }

    const step = ui.step.value
    const bl = useBaselineWork()
    const baselineActive = step === 'baseline' && bl.active.value
    const anchor = this.anchorsEnabled() ? this.hitTestAnchors(p.x, p.y) : null
    let target: DownTarget
    if (anchor) {
      // 拟合进行中拖锚点 → 自动 停止并保留(红线 #9)
      const fit = useFit()
      if (fit.status.value === 'running') {
        stopFit()
        pushToast('info', '检测到锚点拖动：已自动发送“停止当前拟合”')
      }
      target = { t: 'anchor', hit: anchor }
    } else {
      // Baseline step: only point selection (baseline point set); the peak
      // placement click and the data mask live on other steps. When detection
      // has not run yet, clicks do nothing.
      // the reference application places peaks with a plain left click — on the placement step
      // the click must NEVER be eaten by point-exclusion, no matter how close
      // to the data it lands (the data line covers the whole spectrum).
      // Point exclusion: Alt+click anywhere, plain click on other steps.
      let pt: { idx: number; dist: number } | null = null
      if (baselineActive) {
        pt = this.hitTestPoint(p.x, p.y, BASELINE_POINT_R)
      } else if (step !== 'baseline' && (e.altKey || step !== 'peaks')) {
        pt = this.hitTestPoint(p.x, p.y)
      }
      if (!pt) target = { t: 'blank' }
      else if (baselineActive) target = { t: 'baseline-point', idx: pt.idx, dist: pt.dist }
      else target = { t: 'point', idx: pt.idx, dist: pt.dist }
    }
    this.pending = { sx: p.x, sy: p.y, lx: p.x, ly: p.y, moved: false, target }
  }

  private onPointerMove = (e: PointerEvent): void => {
    const p = this.eventToPlot(e)
    this.hoverPx = this.insidePlot(p) ? p : null

    if (this.pending) {
      const pd = this.pending
      pd.lx = p.x
      pd.ly = p.y
      if (!pd.moved && Math.hypot(p.x - pd.sx, p.y - pd.sy) > DRAG_EPS) {
        pd.moved = true
        if (pd.target.t === 'anchor') {
          this.beginDrag(pd.target.hit, pd.sx, pd.sy)
          // Apply this very move too: fast drags (or coalesced pointermove
          // streams) may deliver only one move before pointerup, and starting
          // the drag without applying it made the whole gesture a no-op.
          this.scheduleDragApply(p.x, p.y)
        } else {
          const ui = useUi()
          const step = ui.step.value
          const bl = useBaselineWork()
          const xMoved = Math.abs(p.x - pd.sx) > DRAG_EPS
          if (step === 'data' || (step === 'baseline' && bl.active.value)) {
            // Section editing: drag-right excludes a band, drag-left restores.
            // A purely vertical start stays idle until the x movement is real.
            if (xMoved) {
              this.mode = 'band'
              this.zoomRect = { x0: pd.sx, y0: pd.sy, x1: p.x, y1: p.y }
              this.updateBand(pd.sx, p.x)
            } else {
              this.mode = 'idle'
            }
          } else if (step === 'baseline') {
            // Baseline mode not armed yet: dragging does nothing (no zoom).
            this.mode = 'idle'
          } else {
            this.mode = 'zoom'
            this.zoomRect = { x0: pd.sx, y0: pd.sy, x1: p.x, y1: p.y }
          }
        }
      } else if (pd.moved) {
        if (this.mode === 'zoom' && this.zoomRect) {
          this.zoomRect.x1 = p.x
          this.zoomRect.y1 = p.y
        } else if (this.mode === 'band' && this.zoomRect) {
          this.zoomRect.x1 = p.x
          this.zoomRect.y1 = p.y
          this.updateBand(pd.sx, p.x)
        } else if (this.mode === 'idle') {
          // Upgrade a vertical-first drag into the current mode once x moves.
          const ui = useUi()
          const step = ui.step.value
          const bl = useBaselineWork()
          const xMoved = Math.abs(p.x - pd.sx) > DRAG_EPS
          if (xMoved && (step === 'data' || (step === 'baseline' && bl.active.value))) {
            this.mode = 'band'
            this.zoomRect = { x0: pd.sx, y0: pd.sy, x1: p.x, y1: p.y }
            this.updateBand(pd.sx, p.x)
          }
        } else if (this.mode === 'drag') {
          this.scheduleDragApply(p.x, p.y)
        }
      }
      this.scheduleOverlayDraw()
      return
    }

    // idle: hover feedback + crosshair + readout
    const anchor = this.hoverPx && this.anchorsEnabled() ? this.hitTestAnchors(this.hoverPx.x, this.hoverPx.y) : null
    this.hoverAnchor = anchor
    const ov = this.overlay
    if (ov) {
      const ui = useUi()
      const bl = useBaselineWork()
      ov.style.cursor = anchor
        ? anchor.kind === 'main'
          ? 'grab'
          : 'ew-resize'
        : this.insidePlot(p)
          ? ui.step.value === 'peaks'
            ? 'crosshair'
            : ui.step.value === 'baseline' && bl.active.value
              ? 'crosshair'
              : ui.step.value === 'data'
                ? 'crosshair'
                : 'default'
          : 'default'
    }
    this.updateHoverReadout()
    this.scheduleOverlayDraw()
  }

  private onPointerUp = (e: PointerEvent): void => {
    const ov = this.overlay
    if (!ov) return
    if (ov.hasPointerCapture(e.pointerId)) ov.releasePointerCapture(e.pointerId)
    const pd = this.pending
    this.pending = null

    if (this.mode === 'drag') {
      // Final position: pointermove is rAF-coalesced, so the last move may not
      // have been applied yet when the button is released.
      if (pd) this.applyDrag(pd.lx, pd.ly)
      this.commitDrag()
      this.mode = 'idle'
      this.drag = null
      this.drawOverlay()
      return
    }
    if (this.mode === 'band') {
      if (pd) {
        // Include the release position even when no move event carried it.
        const p = this.eventToPlot(e)
        pd.lx = p.x
        pd.ly = p.y
        this.updateBand(pd.sx, p.x)
      }
      this.applyBand()
      this.mode = 'idle'
      this.band = null
      this.zoomRect = null
      this.drawOverlay()
      return
    }
    if (this.mode === 'zoom') {
      this.applyZoomRect()
      this.mode = 'idle'
      this.zoomRect = null
      this.drawOverlay()
      return
    }
    if (!pd) return
    // Baseline step before detection: a drag is a no-op, never a click.
    if (pd.moved) {
      this.drawOverlay()
      return
    }

    // click (no drag)
    if (pd.target.t === 'anchor') {
      const hit = pd.target.hit
      const pk = usePeaks()
      const peak = pk.list.value.find((q) => q.id === hit.peakId)
      if (!peak) return
      if (hit.kind === 'main') {
        // 单击主锚 = 开关该峰
        const before = peak.enabled
        setPeakEnabled(peak.id, !before)
        pushCommand({
          label: '峰 开/关',
          undo: () => setPeakEnabled(peak.id, before),
          redo: () => setPeakEnabled(peak.id, !before),
        })
      } else {
        selectPeak(peak.id)
      }
    } else if (pd.target.t === 'baseline-point') {
      const bl = useBaselineWork()
      if (bl.active.value) {
        const u = bl.used.value
        const before = u ? u.slice() : null
        bl.togglePoint(pd.target.idx)
        this.pushBaselineUndo(before, '基线点 加入/退出')
      }
    } else if (pd.target.t === 'point') {
      this.togglePointExcluded(pd.target.idx)
    } else {
      const u = this.u1
      const ui = useUi()
      if (!u || !this.insidePlot({ x: pd.lx, y: pd.ly })) return
      if (ui.step.value === 'peaks') {
        this.placePeakAt(u.posToVal(pd.lx, 'x'), u.posToVal(pd.ly, 'y'))
      } else if (ui.step.value !== 'baseline') {
        selectPeak(null)
      }
    }
    this.drawOverlay()
  }

  private onPointerLeave = (): void => {
    this.hoverPx = null
    this.hoverAnchor = null
    const ui = useUi()
    ui.hover.value = null
    this.drawOverlay()
  }

  private onContextMenu = (e: MouseEvent): void => {
    e.preventDefault()
    const u = this.u1
    if (!u) return
    const p = this.eventToPlot(e)
    const anchor = this.insidePlot(p) && this.anchorsEnabled() ? this.hitTestAnchors(p.x, p.y) : null
    const ui = useUi()
    const pk = usePeaks()
    if (anchor && anchor.kind === 'main') {
      // 右键主锚 = 峰调整
      selectPeak(anchor.peakId)
      const peak = pk.list.value.find((q) => q.id === anchor.peakId)
      const rect = this.overlay?.getBoundingClientRect()
      if (peak && rect) {
        const a = this.anchorsOf(peak)
        const mx = u.valToPos(a.main[0], 'x')
        const my = u.valToPos(a.main[1], 'y')
        ui.popover.value = {
          peakId: anchor.peakId,
          cx: rect.left + mx,
          cy: rect.top + my,
        }
      }
    } else {
      ui.popover.value = null
      this.resetView()
    }
  }

  private onDblClick = (e: MouseEvent): void => {
    e.preventDefault()
    this.resetView()
  }

  /** Public: shared with status bar double-click / toolbar. */
  resetView(): void {
    this.refreshChart(true)
  }

  // ------------------------------------------------------------------
  // peak placement / point exclusion
  // ------------------------------------------------------------------

  private estimateLocalWidth(idx: number): number {
    const sp = useSpectrum()
    const xv = sp.x.value
    const yv = sp.y.value
    const span = Math.max(sp.meta.xMax - sp.meta.xMin, 1e-12)
    const fallback = span * 0.03
    if (!xv || !yv || idx < 0 || idx >= xv.length) return fallback
    const n = xv.length
    const win = Math.max(4, Math.round(n * 0.01))
    let best = idx
    const lo = Math.max(0, idx - win)
    const hi = Math.min(n - 1, idx + win)
    for (let i = lo; i <= hi; i++) if (yv[i] > yv[best]) best = i
    const half = yv[best] / 2
    const rightLim = Math.min(n - 1, best + win * 8)
    const leftLim = Math.max(0, best - win * 8)
    let xr = best
    while (xr < rightLim && Math.abs(yv[xr]) > Math.abs(half)) xr++
    let xl = best
    while (xl > leftLim && Math.abs(yv[xl]) > Math.abs(half)) xl--
    let w = xv[xr] - xv[xl]
    if (!Number.isFinite(w) || w <= 0 || w > span * 0.5) w = fallback
    return Math.min(Math.max(w, span * 1e-4), span * 0.5)
  }

  private placePeakAt(xVal: number, yVal: number): void {
    const pk = usePeaks()
    const idx = indexAtX(xVal)
    const width = this.estimateLocalWidth(idx)
    const spec = createPeak(pk.defaultFn.value, xVal, yVal, width)
    selectPeak(spec.id)
    pushCommand({
      label: '放峰',
      undo: () => removePeak(spec.id),
      redo: () => reinsertPeak(spec),
    })
  }

  private togglePointExcluded(idx: number): void {
    const sp = useSpectrum()
    const m = sp.mask.value
    if (!m || idx < 0 || idx >= m.length) return
    const before = m[idx]
    sp.togglePoint(idx)
    pushCommand({
      label: '排除点',
      undo: () => {
        const cur = sp.mask.value
        if (cur && cur[idx] !== before) sp.togglePoint(idx)
      },
      redo: () => {
        const cur = sp.mask.value
        if (cur && cur[idx] !== before) sp.togglePoint(idx)
      },
    })
  }

  // ------------------------------------------------------------------
  // section editing (baseline point-set / data mask bands)
  // ------------------------------------------------------------------

  /** Recompute the inclusive raw-index range from the two drag endpoints. */
  private updateBand(sx: number, x1: number): void {
    const u = this.u1
    if (!u) {
      this.band = null
      return
    }
    const iA = indexAtX(u.posToVal(sx, 'x'))
    const iB = indexAtX(u.posToVal(x1, 'x'))
    if (iA < 0 || iB < 0) {
      this.band = null
      return
    }
    this.band = {
      // Screen direction decides the semantics (right = exclude, left = restore)
      dir: x1 >= sx ? 'exclude' : 'include',
      lo: Math.min(iA, iB),
      hi: Math.max(iA, iB),
    }
  }

  /** Commit the band on pointer-up: the data/baseline step's immediate
   * exclude/restore edit. / 提交区段：数据/基线步骤的即时排除/恢复。 */
  private applyBand(): void {
    const b = this.band
    if (!b) return
    const ui = useUi()
    if (ui.step.value === 'baseline') {
      const bl = useBaselineWork()
      if (!bl.active.value) return
      const u = bl.used.value
      const before = u ? u.slice() : null
      if (b.dir === 'exclude') bl.excludeBand(b.lo, b.hi)
      else bl.includeBand(b.lo, b.hi)
      this.pushBaselineUndo(before, b.dir === 'exclude' ? '排除基线段' : '恢复基线段')
      return
    }
    if (ui.step.value === 'data') this.applyMaskBand(b)
  }

  /** Data-mask band edit (right drag = exclude, left drag = restore) + undo. */
  private applyMaskBand(b: BandState): void {
    const sp = useSpectrum()
    const m = sp.mask.value
    if (!m) return
    const before = m.slice(b.lo, b.hi + 1)
    const value: 0 | 1 = b.dir === 'exclude' ? 0 : 1
    let changed = false
    for (let i = 0; i < before.length; i++) {
      if (before[i] !== value) {
        changed = true
        break
      }
    }
    if (!changed) return
    sp.setMaskRange(b.lo, b.hi, value)
    this.pushMaskBandUndo(b.lo, b.hi, before, value)
  }

  /** Undo/redo for baseline point-set edits (mutate the exposed used array + refit). */
  private pushBaselineUndo(before: Uint8Array | null, label: string): void {
    const bl = useBaselineWork()
    const after = bl.used.value ? bl.used.value.slice() : null
    if (!before || !after || before.length !== after.length) return
    let changed = false
    for (let i = 0; i < before.length; i++) {
      if (before[i] !== after[i]) {
        changed = true
        break
      }
    }
    if (!changed) return
    const apply = (snap: Uint8Array): void => {
      const cur = bl.used.value
      if (!cur || cur.length !== snap.length) return
      cur.set(snap)
      bl.refit()
    }
    pushCommand({
      label,
      undo: () => apply(before),
      redo: () => apply(after),
    })
  }

  /** Undo/redo for a data-mask band (exact slice restore, keeps meta.excluded right). */
  private pushMaskBandUndo(lo: number, hi: number, before: Uint8Array, after: 0 | 1): void {
    const sp = useSpectrum()
    const apply = (vals: Uint8Array | 0 | 1): void => {
      const m = sp.mask.value
      if (!m) return
      let delta = 0
      for (let i = lo; i <= hi; i++) {
        const nv = typeof vals === 'number' ? vals : vals[i - lo]
        if (m[i] === nv) continue
        delta += nv === 0 ? 1 : -1
        m[i] = nv
      }
      if (delta === 0) return
      sp.meta.excluded += delta
      sp.maskVersion.value++
      bumpEdit()
    }
    pushCommand({
      label: after === 0 ? '排除数据段' : '恢复数据段',
      undo: () => apply(before),
      redo: () => apply(after),
    })
  }

  // ------------------------------------------------------------------
  // anchor dragging (pure frontend eval, rAF-coalesced)
  // ------------------------------------------------------------------

  private beginDrag(hit: AnchorHit, sx: number, sy: number): void {
    const pk = usePeaks()
    const peak = pk.list.value.find((q) => q.id === hit.peakId)
    if (!peak) return
    // Cache the data-resolvable width floor once per gesture (scanning the
    // full x/y arrays on every rAF frame would be wasteful).
    // 每次手势只计算一次“数据可分辨宽度”下限（每帧扫描全量数据太浪费）。
    const sp = useSpectrum()
    const ctx = guardContextFrom(sp.x.value ?? [], sp.y.value ?? [])
    this.drag = {
      peakId: peak.id,
      kind: hit.kind,
      startP: { ...peak.p },
      startGeom: this.geomOf(peak),
      sx,
      sy,
      minWidth: ctx ? minMeaningfulWidth(ctx) : 0,
    }
    this.mode = 'drag'
    selectPeak(peak.id)
  }

  private dragLatest: { x: number; y: number } | null = null

  private scheduleDragApply(x: number, y: number): void {
    this.dragLatest = { x, y }
    if (this.rafId) return
    this.rafId = requestAnimationFrame(() => {
      this.rafId = 0
      const d = this.dragLatest
      if (d && this.mode === 'drag') this.applyDrag(d.x, d.y)
    })
  }

  private applyDrag(px: number, py: number): void {
    const u = this.u1
    const d = this.drag
    if (!u || !d) return
    const pk = usePeaks()
    const peak = pk.list.value.find((q) => q.id === d.peakId)
    if (!peak) return

    const dx = u.posToVal(px, 'x') - u.posToVal(d.sx, 'x')
    const dy = u.posToVal(py, 'y') - u.posToVal(d.sy, 'y')

    if (d.kind === 'main') {
      // 主锚：水平拖 = 中心；垂直拖 = 幅值（尊重锁定）
      if (!peak.locked['a1']) peak.p['a1'] = d.startP['a1'] + dx
      if (!peak.locked['a0']) {
        const startH = d.startGeom.height
        const targetH = startH + dy
        if (Math.abs(startH) > 1e-12) {
          peak.p['a0'] = d.startP['a0'] * (targetH / startH)
        } else {
          peak.p['a0'] = d.startP['a0'] + dy
        }
      }
    } else {
      // 半高锚 / FW25 形状锚：几何反解宽度与形状参数（另一侧保持不动）
      const targetX = u.posToVal(px, 'x')
      const solved = solveAnchorDrag({
        fn: peak.fn,
        startP: d.startP,
        startGeom: d.startGeom,
        kind: d.kind,
        targetX,
        locked: peak.locked,
      })
      // REPRODUCED FAILURE (2026-10-20): dragging a half-height anchor ACROSS
      // the peak center has no geometric solution; the inverse solve runs to
      // the registry floor (a2 = 1e-12). Such a peak is narrower than one data
      // step — its model is zero at every sample, the fit's width Jacobian
      // vanishes and the ±50 % soft box re-anchors on 1e-12 forever, so no
      // later fit can recover it ("手调半峰宽后无法进行后续拟合"). Reject a
      // degenerate solve and keep the drag-start width instead.
      // 复现的故障：半高锚拖过峰心没有几何解，反解会一路跑到注册表下限
      // (a2 = 1e-12)。这种峰窄于一个数据步长——所有采样点模型为零、拟合宽度
      // 雅可比消失，±50% 软约束又永远锚在 1e-12，此后任何拟合都无法恢复它。
      // 这里拒绝退化解，保留拖拽起点的宽度。
      const minW = d.minWidth
      let degenerate = false
      if (minW > 0) {
        for (const k of widthKeysOfSpec(peak)) {
          const v = solved[k]
          if (typeof v === 'number' && (!Number.isFinite(v) || v < minW)) degenerate = true
        }
      }
      // A half-height flank can never cross the peak center: a target on the
      // opposite side has NO geometric solution (the solver then just
      // collapses the width toward zero). Reject the whole solve so the
      // anchor simply stops at the last valid position.
      // 半高侧翼不可能越过峰心：目标点落在对侧时根本没有几何解（反解只会把
      // 宽度压向零）。整次反解作废，锚点停在最后一个有效位置。
      const centerX = d.startGeom.centerX
      if (
        (d.kind === 'leftHalf' && targetX >= centerX) ||
        (d.kind === 'rightHalf' && targetX <= centerX)
      ) {
        degenerate = true
      }
      if (!degenerate) {
        for (const k of Object.keys(solved)) {
          const v = solved[k]
          if (typeof v === 'number' && Number.isFinite(v)) peak.p[k] = v
        }
      } else {
        // Snap the width back to the drag-start value: a gesture that crossed
        // the center must not leave a half-collapsed peak behind (the last
        // still-valid rAF frame used to be kept, so releasing past the center
        // could still shrink the peak ~5× and degrade the next fit).
        // 把宽度回退到拖拽起点：越过峰心的手势不能留下“半塌缩”的峰（以前会保留
        // 最后一个仍有效的 rAF 帧，松手在峰心另一侧时峰仍会缩窄约 5 倍）。
        for (const k of widthKeysOfSpec(peak)) {
          if (typeof d.startP[k] === 'number') peak.p[k] = d.startP[k]
        }
      }
      // Area-parameterized peaks (EMG/GMG/HVL/NLC) would sink as they widen:
      // hold the peak height constant while dragging width/shape anchors.
      if (!peak.locked['a0'] && d.startGeom.height > 1e-12) {
        const g = measurePeakGeometry(peak.fn, peak.p)
        if (g.height > 1e-12) {
          const nextA0 = (peak.p['a0'] * d.startGeom.height) / g.height
          // A non-finite / absurd amplitude would freeze the peak in the
          // fitter's step guard; only accept a sane rescale.
          // 非有限/离谱的幅值会让峰在拟合步长守卫中被冻结，只接受合理缩放。
          if (Number.isFinite(nextA0) && Math.abs(nextA0) < 1e12 * Math.max(1e-12, Math.abs(d.startP['a0']))) {
            peak.p['a0'] = nextA0
          }
        }
      }
    }
    this.refreshChart(false, d.peakId)
    this.updateHoverReadout()
  }

  private commitDrag(): void {
    const d = this.drag
    if (!d) return
    const pk = usePeaks()
    const peak = pk.list.value.find((q) => q.id === d.peakId)
    if (!peak) return
    const before = { ...d.startP }
    const after = { ...peak.p }
    if (JSON.stringify(before) === JSON.stringify(after)) return
    const spec = peak
    const label =
      d.kind === 'main'
        ? '拖动主锚（峰位/幅值）'
        : d.kind === 'quarter'
          ? '拖动形状锚（FW25）'
          : '拖动半高锚（峰宽/不对称）'
    pushCommand({
      label,
      undo: () => {
        for (const k of Object.keys(before)) spec.p[k] = before[k]
        pk.curvesVersion.value++
      },
      redo: () => {
        for (const k of Object.keys(after)) spec.p[k] = after[k]
        pk.curvesVersion.value++
      },
    })
  bumpEdit()
  }

  // ------------------------------------------------------------------
  // zoom box
  // ------------------------------------------------------------------

  private applyZoomRect(): void {
    const u = this.u1
    const z = this.zoomRect
    if (!u || !z) return
    const x0 = Math.min(z.x0, z.x1)
    const x1 = Math.max(z.x0, z.x1)
    const y0 = Math.min(z.y0, z.y1)
    const y1 = Math.max(z.y0, z.y1)
    if (x1 - x0 < 4 || y1 - y0 < 4) return
    const xmin = u.posToVal(x0, 'x')
    const xmax = u.posToVal(x1, 'x')
    const ymin = u.posToVal(y0, 'y')
    const ymax = u.posToVal(y1, 'y')
    u.batch(() => {
      u.setScale('x', { min: xmin, max: xmax })
      u.setScale('y', { min: ymin, max: ymax })
    })
  }

  // ------------------------------------------------------------------
  // wheel zoom (X axis only, anchored under the cursor)
  // ------------------------------------------------------------------

  /**
   * Bind the wheel on uPlot's `.over` in the CAPTURE phase and stop it there:
   * X-FAIS owns zooming (horizontal only) and the page behind must never
   * scroll. The listener dies with the element on rebuild.
   * 滚轮缩放只作用于横轴（光标处为锚点），并在捕获阶段截断：页面不会跟着滚动。
   * uPlot 重建时元素随旧图销毁，监听器随之失效，需在新图上重新绑定。
   */
  private bindWheelZoom(): void {
    const u = this.u1
    if (!u) return
    const el = u.over
    if (this.wheelEl === el) return
    this.unbindWheelZoom()
    el.addEventListener('wheel', this.onWheel, { capture: true, passive: false })
    this.wheelEl = el
  }

  private unbindWheelZoom(): void {
    if (!this.wheelEl) return
    this.wheelEl.removeEventListener('wheel', this.onWheel, { capture: true })
    this.wheelEl = null
  }

  private onWheel = (e: WheelEvent): void => {
    const u = this.u1
    if (!u) return
    // The chart owns the gesture: no page scroll / browser pinch-zoom here.
    e.preventDefault()
    e.stopPropagation()

    // `.u-over` IS the plot area (uPlot positions it at bbox.left/top), so its
    // own rect already excludes the axis margins — bbox.left must NOT be
    // subtracted again (that would shift the anchor by the axis width).
    // .u-over 本身就是绘图区（uPlot 把它定位在 bbox.left/top），其 rect 已排除
    // 坐标轴边距——绝不能再减 bbox.left（否则锚点会偏移一个轴宽）。
    const rect = u.over.getBoundingClientRect()
    const wCss = u.bbox.width / uPlot.pxRatio
    const hCss = u.bbox.height / uPlot.pxRatio
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top
    if (px < 0 || px > wCss || py < 0 || py > hCss) return

    const sp = useSpectrum()
    const xMinData = sp.meta.xMin
    const xMaxData = sp.meta.xMax
    const fullSpan = xMaxData - xMinData
    if (!(fullSpan > 0)) return
    const sx = u.scales.x
    if (typeof sx.min !== 'number' || typeof sx.max !== 'number') return
    const curMin = sx.min
    const curMax = sx.max
    const curSpan = curMax - curMin
    if (!(curSpan > 0)) return

    const anchorVal = u.posToVal(px, 'x')
    // Normalize line/page delta modes to pixels; deltaY < 0 (wheel up / trackpad
    // pinch-in) zooms in, deltaY > 0 zooms out.
    const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * 100 : e.deltaY
    const factor = Math.exp(dy * 0.0015)
    const minSpan = fullSpan * 1e-6
    // Never zoom out beyond the full data domain.
    const span = Math.min(Math.max(curSpan * factor, minSpan), fullSpan)
    // Keep the data value under the cursor at the same relative position.
    const rel = (anchorVal - curMin) / curSpan
    let newMin = anchorVal - rel * span
    let newMax = newMin + span
    // Clamp into [xMinData, xMaxData] by SHIFTING (never shrinking below minSpan).
    if (newMin < xMinData) {
      newMin = xMinData
      newMax = newMin + span
    }
    if (newMax > xMaxData) {
      newMax = xMaxData
      newMin = newMax - span
    }
    if (!(newMax > newMin)) return
    const eps = curSpan * 1e-9
    if (Math.abs(newMin - curMin) <= eps && Math.abs(newMax - curMax) <= eps) return

    // Y is never touched: the wheel zooms the horizontal axis only. Pin the
    // current y range so the rAF view refresh cannot re-range it.
    // 只设 x——y 轴保持不变；同时锁定当前 y 量程，防止刷新时被重算。
    const sy = u.scales.y
    if (typeof sy.min === 'number' && typeof sy.max === 'number') {
      this.wheelYLock = { min: sy.min, max: sy.max }
    }
    u.setScale('x', { min: newMin, max: newMax })
    // Lock the residual chart's x immediately (its setData/sync runs on rAF).
    this.u2?.setScale('x', { min: newMin, max: newMax })
  }

  // ------------------------------------------------------------------
  // hover readout
  // ------------------------------------------------------------------

  private updateHoverReadout(): void {
    const ui = useUi()
    const sp = useSpectrum()
    const hp = this.hoverPx
    if (!hp || !this.insidePlot(hp)) {
      if (ui.hover.value !== null) ui.hover.value = null
      return
    }
    const u = this.u1
    const xv = sp.x.value
    const yv = sp.y.value
    if (!u || !xv || !yv) return
    const idx = indexAtX(u.posToVal(hp.x, 'x'))
    if (idx < 0) {
      ui.hover.value = null
      return
    }
    ui.hover.value = { x: xv[idx], y: yv[idx] }
  }

  // ------------------------------------------------------------------
  // overlay drawing
  // ------------------------------------------------------------------

  private scheduleOverlayDraw(): void {
    if (this.rafId) return
    this.rafId = requestAnimationFrame(() => {
      this.rafId = 0
      this.drawOverlay()
    })
  }

  drawOverlay(): void {
    const ctx = this.octx
    const ov = this.overlay
    const u = this.u1
    if (!ctx || !ov || !u) return
    const pk = usePeaks()
    const sp = useSpectrum()
    const ui = useUi()

    ctx.setTransform(uPlot.pxRatio, 0, 0, uPlot.pxRatio, 0, 0)
    ctx.clearRect(0, 0, ov.width / uPlot.pxRatio, ov.height / uPlot.pxRatio)

    if (!this.view) return
    const px = (v: number): number => u.valToPos(v, 'x')
    const py = (v: number): number => u.valToPos(v, 'y')

    // -- excluded data points: grey × on the DATA step only --
    // The curve itself already carries the gap on every step (null columns);
    // the × marks exist so the user can see and restore them on 数据. Later
    // steps show neither the points nor the marks.
    // One batch path + a single stroke per frame; points outside the current
    // x view / plot rect are culled before any canvas work. The hard grey
    // #94a3b8 stays distinguishable from the data line (--chart-data) even at
    // 6–8 px mark size, which the muted --chart-text (#64748b) did not.
    // 已排除的数据点：灰色 × 只在「数据」步绘制（曲线在所有步骤都以断口呈现，
    // × 仅用于在数据步定位并恢复被排除的点）。后续步骤既不画点也不画 ×。
    const mask = sp.mask.value
    if (mask && ui.step.value === 'data') {
      const { xs, ys, rawIdx } = this.view
      const plotW = u.bbox.width / uPlot.pxRatio
      const plotH = u.bbox.height / uPlot.pxRatio
      // Visible x window in data units (cull before converting coordinates).
      const sMin = u.scales.x.min
      const sMax = u.scales.x.max
      const hasXScale = typeof sMin === 'number' && typeof sMax === 'number' && Number.isFinite(sMin) && Number.isFinite(sMax)
      const xLo = hasXScale ? Math.min(sMin as number, sMax as number) : -Infinity
      const xHi = hasXScale ? Math.max(sMin as number, sMax as number) : Infinity
      const ARM = 3.5 // half-size of the × (7 px strokes), CSS px
      ctx.save()
      // #94a3b8 is the grey the review's pixel probe expects; the lineWidth is
      // in CSS px — the canvas transform above already scales it by pxRatio,
      // exactly like anchors / crosshair / zoom rect in this file.
      ctx.strokeStyle = '#94a3b8'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      let marks = 0
      for (let k = 0; k < rawIdx.length; k++) {
        if (mask[rawIdx[k]] !== 0) continue
        const xv = xs[k]
        if (xv < xLo || xv > xHi) continue
        const cx = px(xv)
        const cy = py(ys[k])
        if (!Number.isFinite(cx) || !Number.isFinite(cy)) continue
        if (cx < -ARM || cx > plotW + ARM || cy < -ARM || cy > plotH + ARM) continue
        ctx.moveTo(cx - ARM, cy - ARM)
        ctx.lineTo(cx + ARM, cy + ARM)
        ctx.moveTo(cx + ARM, cy - ARM)
        ctx.lineTo(cx - ARM, cy + ARM)
        marks++
      }
      if (marks > 0) ctx.stroke()
      ctx.restore()
    }

    // -- 自动拟合 baseline point set: used = bright, excluded = dark gray --
    const bl = useBaselineWork()
    const baselineActive = ui.step.value === 'baseline' && bl.active.value
    const used = bl.used.value
    if (baselineActive && used && used.length > 0) {
      const { xs, ys, rawIdx } = this.view
      // Thin out on dense datasets (≤ ~800 marks; rawIdx keeps the mapping).
      const stride = Math.max(1, Math.floor(xs.length / 800))
      ctx.fillStyle = withAlpha(this.pal.accent, 0.95)
      ctx.beginPath()
      for (let k = 0; k < xs.length; k += stride) {
        const ri = rawIdx[k]
        if (!used[ri]) continue
        const cx = px(xs[k])
        const cy = py(ys[k])
        ctx.moveTo(cx + 2, cy)
        ctx.arc(cx, cy, 2, 0, Math.PI * 2)
      }
      ctx.fill()
      ctx.fillStyle = withAlpha(this.pal.text, 0.42)
      ctx.beginPath()
      for (let k = 0; k < xs.length; k += stride) {
        const ri = rawIdx[k]
        if (used[ri]) continue
        const cx = px(xs[k])
        const cy = py(ys[k])
        ctx.moveTo(cx + 1.5, cy)
        ctx.arc(cx, cy, 1.5, 0, Math.PI * 2)
      }
      ctx.fill()
    }

    // -- crosshair (idle only) --
    if (this.hoverPx && !this.zoomRect && !this.pending && this.mode !== 'drag' && this.insidePlot(this.hoverPx)) {
      ctx.strokeStyle = this.pal.cursor
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(this.hoverPx.x, 0)
      ctx.lineTo(this.hoverPx.x, u.bbox.height / uPlot.pxRatio)
      ctx.moveTo(0, this.hoverPx.y)
      ctx.lineTo(u.bbox.width / uPlot.pxRatio, this.hoverPx.y)
      ctx.stroke()
    }

    // -- zoom rubber band / section band --
    if (this.zoomRect) {
      const z = this.zoomRect
      const x0 = Math.min(z.x0, z.x1)
      const x1 = Math.max(z.x0, z.x1)
      const y0 = Math.min(z.y0, z.y1)
      const y1 = Math.max(z.y0, z.y1)
      const w = x1 - x0
      const band = this.band
      const plotW = u.bbox.width / uPlot.pxRatio
      const plotH = u.bbox.height / uPlot.pxRatio
      if (band) {
        // Section semantics: the band spans the full plot height (x range only).
        const tint = band.dir === 'exclude' ? this.pal.danger : this.pal.success
        ctx.fillStyle = withAlpha(tint, 0.16)
        ctx.strokeStyle = tint
        ctx.lineWidth = 1
        ctx.fillRect(x0, 0, w, plotH)
        ctx.strokeRect(x0 + 0.5, 0.5, w, plotH - 1)
        const n = band.hi - band.lo + 1
        const label = band.dir === 'exclude' ? `排除 ${n} 点 →` : `← 恢复 ${n} 点`
        const tx = Math.max(6, Math.min(plotW - 140, x0 + 6))
        this.drawPill(ctx, label, tx, 10, tint)
      } else {
        const h = y1 - y0
        ctx.fillStyle = withAlpha(this.pal.accent, 0.1)
        ctx.strokeStyle = this.pal.selection
        ctx.lineWidth = 1
        ctx.fillRect(x0, y0, w, h)
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w, h)
      }
    }

    // -- anchors --
    const dragId = this.drag?.peakId ?? null
    const popId = ui.popover.value?.peakId ?? null
    const showAnchors = this.anchorsEnabled()
    for (const p of pk.list.value) {
      // data / baseline steps reserve interactions for point & section edits
      if (!showAnchors) break
      const a = this.anchorsOf(p)
      const mx = px(a.main[0])
      const my = py(a.main[1])
      const isHover = this.hoverAnchor?.peakId === p.id
      const isDrag = dragId === p.id
      const isSel = pk.selectedId.value === p.id || popId === p.id
      if (!Number.isFinite(mx) || !Number.isFinite(my)) continue

      if (isDrag) {
        // 十字辅助线
        ctx.save()
        ctx.strokeStyle = withAlpha(p.color ?? this.pal.accent, 0.5)
        ctx.setLineDash([3, 3])
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(0, my)
        ctx.lineTo(u.bbox.width / uPlot.pxRatio, my)
        ctx.moveTo(mx, 0)
        ctx.lineTo(mx, u.bbox.height / uPlot.pxRatio)
        ctx.stroke()
        ctx.restore()
      }

      // main anchor: larger dot with rim; disabled = hollow
      const r = isDrag || isHover ? 7 : 5.5
      if (isSel || isHover) {
        ctx.beginPath()
        ctx.arc(mx, my, r + 5, 0, Math.PI * 2)
        ctx.fillStyle = withAlpha(p.color ?? this.pal.accent, isHover ? 0.2 : 0.1)
        ctx.fill()
      }
      ctx.beginPath()
      ctx.arc(mx, my, r, 0, Math.PI * 2)
      if (p.enabled) {
        ctx.fillStyle = p.color ?? this.pal.accent
        ctx.fill()
        ctx.lineWidth = 2
        ctx.strokeStyle = this.pal.plotBg
        ctx.stroke()
      } else {
        ctx.lineWidth = 1.5
        ctx.strokeStyle = withAlpha(p.color ?? this.pal.accent, 0.6)
        ctx.stroke()
      }
      if (isSel) {
        ctx.beginPath()
        ctx.arc(mx, my, r + 3, 0, Math.PI * 2)
        ctx.strokeStyle = this.pal.accent
        ctx.lineWidth = 1.2
        ctx.stroke()
      }

      // secondary anchors: left/right half maxima (width/asymmetry) and the
      // quarter-maxima FW25 anchor (shape). Drawn for every enabled peak;
      // emphasized for the selected/hovered one.
      if (p.enabled) {
        const hoverKind = this.hoverAnchor?.peakId === p.id ? this.hoverAnchor.kind : null
        const base = p.color ?? this.pal.accent

        const diamond = (pt: [number, number] | null, kind: AnchorKind): void => {
          if (!pt) return
          const x = px(pt[0])
          const y = py(pt[1])
          if (!Number.isFinite(x) || !Number.isFinite(y)) return
          const hovered = hoverKind === kind
          const size = hovered ? 7 : isSel ? 5.6 : 4.4
          // soft halo makes the handle easy to spot
          if (isSel || hovered) {
            ctx.beginPath()
            ctx.arc(x, y, size + 4, 0, Math.PI * 2)
            ctx.fillStyle = withAlpha(base, hovered ? 0.22 : 0.12)
            ctx.fill()
          }
          ctx.beginPath()
          ctx.moveTo(x, y - size)
          ctx.lineTo(x + size, y)
          ctx.lineTo(x, y + size)
          ctx.lineTo(x - size, y)
          ctx.closePath()
          ctx.fillStyle = hovered ? base : withAlpha(base, isSel ? 0.95 : 0.55)
          ctx.fill()
          ctx.lineWidth = 1.6
          ctx.strokeStyle = this.pal.plotBg
          ctx.stroke()
        }

        const triangle = (pt: [number, number] | null): void => {
          if (!pt) return
          const x = px(pt[0])
          const y = py(pt[1])
          if (!Number.isFinite(x) || !Number.isFinite(y)) return
          const hovered = hoverKind === 'quarter'
          const size = hovered ? 7.4 : isSel ? 6 : 4.8
          if (isSel || hovered) {
            ctx.beginPath()
            ctx.arc(x, y, size + 4, 0, Math.PI * 2)
            ctx.fillStyle = withAlpha(base, hovered ? 0.22 : 0.12)
            ctx.fill()
          }
          ctx.beginPath()
          ctx.moveTo(x, y - size)
          ctx.lineTo(x + size, y + size * 0.8)
          ctx.lineTo(x - size, y + size * 0.8)
          ctx.closePath()
          ctx.fillStyle = hovered ? base : withAlpha(base, isSel ? 0.95 : 0.55)
          ctx.fill()
          ctx.lineWidth = 1.6
          ctx.strokeStyle = this.pal.plotBg
          ctx.stroke()
        }

        // Selected peak: dashed FWHM span between the half anchors.
        if (isSel && a.leftHalf && a.rightHalf) {
          ctx.save()
          ctx.setLineDash([3, 4])
          ctx.lineWidth = 1
          ctx.strokeStyle = withAlpha(base, 0.45)
          ctx.beginPath()
          ctx.moveTo(px(a.leftHalf[0]), py(a.leftHalf[1]))
          ctx.lineTo(px(a.rightHalf[0]), py(a.rightHalf[1]))
          ctx.stroke()
          ctx.restore()
        }

        diamond(a.leftHalf, 'leftHalf')
        diamond(a.rightHalf, 'rightHalf')
        triangle(a.quarter)
      }
    }

    // hovered-anchor tooltip (what will this drag do?)
    const ha = this.hoverAnchor
    if (ha && this.anchorsEnabled() && !this.pending) {
      const hp = pk.list.value.find((q) => q.id === ha.peakId)
      if (hp) {
        const ag = this.anchorsOf(hp)
        const pt = ha.kind === 'main' ? ag.main : ha.kind === 'leftHalf' ? ag.leftHalf : ha.kind === 'rightHalf' ? ag.rightHalf : ag.quarter
        if (pt) {
          const label =
            ha.kind === 'main'
              ? '拖动：峰位 / 幅值'
              : ha.kind === 'quarter'
                ? '拖动：形状 (FW25)'
                : '拖动：峰宽 / 不对称'
          const tx = px(pt[0]) + 12
          const ty = py(pt[1]) - 12
          ctx.font = '11px system-ui, sans-serif'
          const w = ctx.measureText(label).width + 12
          ctx.fillStyle = this.pal.plotBg
          ctx.globalAlpha = 0.92
          ctx.beginPath()
          ctx.roundRect(tx, ty - 14, w, 18, 4)
          ctx.fill()
          ctx.globalAlpha = 1
          ctx.strokeStyle = withAlpha(this.pal.accent, 0.5)
          ctx.lineWidth = 1
          ctx.stroke()
          ctx.fillStyle = this.pal.text
          ctx.fillText(label, tx + 6, ty - 1)
        }
      }
    }

    // Cursor hint on the placement step.
    // 放峰步骤的光标提示。
    if (
      ui.step.value === 'peaks' &&
      this.hoverPx &&
      !this.pending &&
      !this.zoomRect &&
      pk.list.value.length === 0
    ) {
      const hint = '单击放峰'
      ctx.font = '11px system-ui, sans-serif'
      ctx.fillStyle = this.pal.text
      ctx.fillText(hint, this.hoverPx.x + 12, this.hoverPx.y - 10)
    }

    // baseline step before detection: tell the user where the mode is armed
    if (ui.step.value === 'baseline' && !bl.active.value) {
      const hint = '先在右侧面板点【自动检测基线】进入点选模式'
      ctx.font = '11px system-ui, sans-serif'
      const w = ctx.measureText(hint).width + 14
      const plotW = u.bbox.width / uPlot.pxRatio
      this.drawPill(ctx, hint, Math.max(8, (plotW - w) / 2), 10, withAlpha(this.pal.accent, 0.55))
    }
  }

  /** Small rounded overlay label (section band count, baseline hint). */
  private drawPill(ctx: CanvasRenderingContext2D, text: string, tx: number, ty: number, border: string): void {
    ctx.save()
    ctx.font = '11px system-ui, sans-serif'
    const w = ctx.measureText(text).width + 14
    ctx.fillStyle = this.pal.plotBg
    ctx.globalAlpha = 0.92
    ctx.beginPath()
    ctx.roundRect(tx, ty, w, 20, 4)
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.strokeStyle = border
    ctx.lineWidth = 1
    ctx.stroke()
    ctx.fillStyle = this.pal.text
    ctx.fillText(text, tx + 7, ty + 14)
    ctx.restore()
  }

  // ------------------------------------------------------------------
  // export
  // ------------------------------------------------------------------

  async exportPng(): Promise<Uint8Array | null> {
    const c1 = this.u1?.ctx.canvas
    const c2 = this.u2?.ctx.canvas
    if (!c1 || !c2) return null
    const gap = Math.round(8 * uPlot.pxRatio)
    const out = document.createElement('canvas')
    out.width = Math.max(c1.width, c2.width)
    out.height = c1.height + c2.height + gap
    const ctx = out.getContext('2d')
    if (!ctx) return null
    ctx.fillStyle = this.pal.plotBg
    ctx.fillRect(0, 0, out.width, out.height)
    ctx.drawImage(c1, 0, 0)
    ctx.drawImage(c2, 0, c1.height + gap)
    const blob = await new Promise<Blob | null>((resolve) => out.toBlob(resolve, 'image/png'))
    if (!blob) return null
    return new Uint8Array(await blob.arrayBuffer())
  }
}
