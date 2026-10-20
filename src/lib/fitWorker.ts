/**
 * fitWorker.ts — 曲线拟合 Web Worker（X-FAIS 0.3.3）
 *
 * Runs the ported PeakWorkbench numeric core (pwcore) off the UI thread:
 * the synchronous Levenberg–Marquardt loop never blocks the renderer, and
 * one FitIterEvent per iteration streams back for live telemetry.
 * 在独立 Worker 中运行移植的 pwcore 数值核心：同步 LM 循环不再阻塞渲染
 * 线程，且逐次迭代事件流式回传供实时遥测。
 *
 * NOTE: the LM loop is fully synchronous, so stop/abort MESSAGES cannot be
 * received mid-fit (they would queue until the loop ends). The renderer's
 * stop/abort therefore TERMINATES the worker and reconstructs the best-so-far
 * state from the last streamed iteration event (see fitEngine.ts). The
 * control object below is still wired so a future SharedArrayBuffer path
 * could flip it cooperatively. / LM 循环完全同步，stop/abort 消息无法在拟合
 * 中途送达（会排队到循环结束）。渲染侧的停止/中止因此直接 terminate 本
 * Worker，并按最后一条迭代事件重建“当前最优”状态（见 fitEngine.ts）。
 * 下方的 control 仍接好线，留待未来 SharedArrayBuffer 协作式中断。
 */
import { runFitSync } from './pwcore/core/fit'
import { makeControl } from './pwcore/core/fitter'
import type { FitRequest } from './pwcore/shared/types'

let control = makeControl()

interface FitMessage {
  type: 'fit'
  request: FitRequest
}
type Inbox = FitMessage | { type: 'stop' } | { type: 'abort' }

self.onmessage = (e: MessageEvent<Inbox>) => {
  const msg = e.data
  if (msg.type === 'stop') {
    control.stop = true
    return
  }
  if (msg.type === 'abort') {
    control.abort = true
    return
  }
  if (msg.type === 'fit') {
    control = makeControl()
    const raw = msg.request
    // Structured clone round-trips typed arrays intact, but be defensive: a
    // plain-array revival path keeps the worker usable from any sender.
    // 结构化克隆本可完整往返类型数组；此处再防御一层普通数组形态。
    const req: FitRequest = {
      ...raw,
      x: raw.x instanceof Float64Array ? raw.x : new Float64Array(raw.x),
      y: raw.y instanceof Float64Array ? raw.y : new Float64Array(raw.y),
      w: raw.w
        ? (raw.w instanceof Float64Array ? raw.w : new Float64Array(raw.w))
        : undefined,
      mask: raw.mask instanceof Uint8Array ? raw.mask : new Uint8Array(raw.mask),
    }
    const outcome = runFitSync(req, {
      control,
      onIter: (event) => {
        self.postMessage({ type: 'iter', event })
      },
    })
    self.postMessage({ type: 'done', outcome })
  }
}
