/**
 * agentLink.ts — Persistent renderer-side link for external AI agents (MCP).
 *
 * Opens a SECOND WebSocket to the Python backend (desktop: the reserved WS
 * port via the `python:ws-port` IPC; web: same-origin `/ws` upgrade path —
 * WebSocket is not CORS-restricted) and keeps it OPEN for the whole session:
 * agents observe and operate the running instance without any teardown
 * between operations. The backend's AgentBridge relays whitelisted commands
 * from `POST /api/agent_command` over this link; replies flow back on the
 * same socket.
 *
 * Commands executed here (state / guide / capture / click / highlight /
 * confirm / navigate / apply_options) are UI-level decisions only — destructive or
 * long-running work still goes through the module's own buttons, and `confirm`
 * renders an in-app modal so KEY actions always end with a human click.
 *
 * This module is imported only from the AI build (App.vue gates the mount on
 * isJevBuild()); the main build carries none of this code.
 */

import { nextTick, ref } from 'vue'
import router from '@/router'
import { version as APP_VERSION } from '../../package.json'
import { isJevBuild } from '@/lib/settings'
import { highlightTarget } from '@/ai/highlight'
import { APPLY_OPTIONS_EVENT } from '@/ai/agent'
import { NAV_CATALOG, PONI_PATH_KEY, currentLocale, navTitle } from '@/ai/context'
import { guideBriefing, moduleCard, moduleDirectory, serializeGuide } from '@/ai/guide/serialize'
import { MODULE_MANUALS } from '@/ai/guide/manuals'
import { workspaceSnapshotOf } from '@/lib/workspace-state'

export interface AgentConfirmRequest {
  reqId: string
  message: string
  aiId?: string
  note?: string
}

/** Currently pending confirm modal (rendered by AgentConfirmHost). */
export const pendingConfirm = ref<AgentConfirmRequest | null>(null)

/**
 * Agent-activity lamp (2026-10-25): the WS link itself is ALWAYS live in the
 * AI build (that just means "controllable"), so the honest "an agent is
 * operating me" signal is recency — true while an agent command arrived
 * within the linger window. Drives the blue edge glow (AgentBridgeHost) and
 * the purple halo on the bottom-right AI fab (AssistantBar) so the user
 * always SEES who is in control.
 * agent 活动灯：链路常开≠被控制；以「最近 LINGER 窗口内收到过 agent 命令」
 * 为准，驱动边缘蓝光与右下角 AI 圈紫光（hover 提示"Agent 正在控制"）。
 */
export const agentActive = ref(false)
const AGENT_ACTIVE_LINGER_MS = 60_000
let agentActiveTimer: number | null = null

function markAgentActivity(): void {
  agentActive.value = true
  if (agentActiveTimer !== null) window.clearTimeout(agentActiveTimer)
  agentActiveTimer = window.setTimeout(() => {
    agentActive.value = false
  }, AGENT_ACTIVE_LINGER_MS)
}

// ── Link lifecycle ────────────────────────────────────────────────────────────

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let reconnectAttempts = 0
let started = false

const RECONNECT_BASE_MS = 5_000
const RECONNECT_MAX_MS = 30_000

function send(payload: Record<string, unknown>): void {
  if (socket && socket.readyState === WebSocket.OPEN) {
    try {
      socket.send(JSON.stringify(payload))
    } catch {
      // link died mid-send; the reconnect loop will re-establish it
    }
  }
}

function helloPayload(): Record<string, unknown> {
  const current = router.currentRoute.value
  return {
    type: 'agent_hello',
    payload: {
      ai: true,
      version: APP_VERSION,
      platform: window.desktop ? 'desktop' : 'web',
      locale: currentLocale(),
      route: typeof current.name === 'string' ? current.name : '',
      routePath: current.path,
      label: document.title || 'X-FAIS',
    },
  }
}

async function resolveWsUrl(): Promise<string | null> {
  try {
    if (window.desktop) {
      const port = await window.desktop.python.wsPort()
      return `ws://127.0.0.1:${port}`
    }
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${scheme}://${window.location.host}/ws`
  } catch {
    return null
  }
}

function scheduleReconnect(): void {
  if (!started || (socket && socket.readyState <= WebSocket.OPEN)) return
  const delay = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * Math.pow(1.5, reconnectAttempts))
  reconnectAttempts += 1
  if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
  reconnectTimer = window.setTimeout(() => void connect(), delay)
}

async function connect(): Promise<void> {
  const url = await resolveWsUrl()
  if (!url) {
    scheduleReconnect()
    return
  }
  let ws: WebSocket
  try {
    ws = new WebSocket(url)
  } catch {
    scheduleReconnect()
    return
  }
  socket = ws
  ws.onopen = (): void => {
    reconnectAttempts = 0
    send(helloPayload())
  }
  ws.onmessage = (event): void => {
    let data: Record<string, unknown>
    try {
      data = JSON.parse(String(event.data)) as Record<string, unknown>
    } catch {
      return
    }
    if (data.type === 'agent_command') {
      void handleCommand(String(data.req_id ?? ''), String(data.command ?? ''), data.payload)
    }
  }
  ws.onclose = (): void => {
    if (socket === ws) socket = null
    scheduleReconnect()
  }
  ws.onerror = (): void => {
    // onclose follows; nothing else to do
  }
}

/** Start the link (AI build only; safe to call more than once). */
export function startAgentLink(): void {
  if (started || !isJevBuild()) return
  started = true
  void connect()
  // Route changes re-announce ourselves so the instance registry reflects
  // where the operator currently is (multi-open disambiguation).
  router.afterEach(() => {
    if (socket && socket.readyState === WebSocket.OPEN) send(helloPayload())
  })
  window.addEventListener('beforeunload', () => {
    send({ type: 'agent_bye' })
  })
}

// ── Command handlers ──────────────────────────────────────────────────────────

interface CanvasInfo {
  index: number
  width: number
  height: number
  cssWidth: number
  cssHeight: number
  role: string
}

function listCanvases(): CanvasInfo[] {
  const nodes = Array.from(document.querySelectorAll('canvas'))
  return nodes.map((canvas, index) => {
    const rect = canvas.getBoundingClientRect()
    let role = ''
    let el: HTMLElement | null = canvas
    for (let i = 0; i < 4 && el; i += 1) {
      const id = el.getAttribute('data-ai-id') ?? el.getAttribute('data-canvas') ?? ''
      if (id) {
        role = id
        break
      }
      el = el.parentElement
    }
    return {
      index,
      width: canvas.width,
      height: canvas.height,
      cssWidth: Math.round(rect.width),
      cssHeight: Math.round(rect.height),
      role,
    }
  })
}

function pickCanvas(selector: unknown): HTMLCanvasElement | null {
  const nodes = Array.from(document.querySelectorAll('canvas'))
  if (nodes.length === 0) return null
  if (typeof selector === 'number' && nodes[selector]) return nodes[selector]
  if (selector === 'largest' || selector == null) {
    return nodes.reduce((best, node) =>
      node.width * node.height > best.width * best.height ? node : best
    )
  }
  return null
}

async function commandState(): Promise<Record<string, unknown>> {
  const current = router.currentRoute.value
  const routeName = typeof current.name === 'string' ? current.name : ''
  const snapshots: Record<string, unknown> = {}
  for (const entry of NAV_CATALOG) {
    const snap = workspaceSnapshotOf(entry.routeName)
    if (snap) snapshots[entry.routeName] = snap
  }
  let poniPath = ''
  try {
    poniPath = localStorage.getItem(PONI_PATH_KEY) ?? ''
  } catch {
    poniPath = ''
  }
  return {
    route: { name: routeName, path: current.path, title: navTitle(routeName) },
    locale: currentLocale(),
    version: APP_VERSION,
    ai: true,
    platform: window.desktop ? 'desktop' : 'web',
    canvases: listCanvases(),
    snapshots,
    poniPath,
    // Is an external agent operating right now (activity lamp)? / agent 活动灯。
    agentActive: agentActive.value,
    // Situational briefing (2026-10-25): where the user is in this module's
    // guided workflow + the next step, so a single get_state call right after
    // docking tells the agent what is going on without a second round-trip.
    // 当前情况通报：所在模块教程进度 + 下一步——agent 首次对接 get_state 即知。
    guide: guideBriefing(routeName),
    // The current module has a detailed manual? The full text is one
    // `modules route=<name>` away — pointer only, to keep state compact.
    // 当前模块有详细说明？正文经 modules route= 取，state 里只给指针。
    hasManual: Object.prototype.hasOwnProperty.call(MODULE_MANUALS, routeName),
  }
}

// ── Situation context on every reply (2026-10-27) ────────────────────────────

interface SituationContext {
  route: { name: string; path: string; title: string }
  /** Compact digest of the CURRENT route's workspace snapshot. */
  snapshot: Record<string, unknown> | null
  /** Guided-workflow position + next step (same shape as state's guide). */
  guide: ReturnType<typeof guideBriefing>
}

function compactExtras(extras: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!extras) return {}
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(extras).slice(0, 12)) {
    if (typeof value === 'number' || typeof value === 'boolean') out[key] = value
    else if (typeof value === 'string') out[key] = value.slice(0, 60)
    else if (Array.isArray(value)) out[key] = `[${value.length}]`
  }
  return out
}

/**
 * Situational context attached to EVERY command reply (2026-10-27 user
 * request): route, workspace digest (files/poni/canRun/phase + scalar
 * extras), and the guided-workflow position — so a click/navigate/run reply
 * already answers "did it work, where am I, what's next" without a follow-up
 * get_state round trip (that round trip was the token sink).
 * 每次命令回复附当前态势：路由 + 工作区摘要 + 教程位置——点完/跑完即知结果
 * 与下一步，省掉补一次 get_state 的往返（正是 token 消耗大头）。
 */
async function situationContext(): Promise<SituationContext> {
  // One beat so Vue watchers flush workspace reporting after the command's
  // effect (click → snapshot update), keeping the context fresh.
  // 给视图快照上报留一拍刷新时间，保证态势是命令生效后的。
  await new Promise((resolve) => setTimeout(resolve, 120))
  const current = router.currentRoute.value
  const routeName = typeof current.name === 'string' ? current.name : ''
  const snap = workspaceSnapshotOf(routeName)
  return {
    route: { name: routeName, path: current.path, title: navTitle(routeName) },
    // Same shape as the workspace-state bridge (filesCount/hasPoni/canRun/
    // phase/extras) so the MCP side renders exactly one snapshot dialect.
    // 与工作区快照同形，MCP 侧只渲染一种形态。
    snapshot: snap ? { ...snap, extras: compactExtras(snap.extras) } : null,
    guide: guideBriefing(routeName),
  }
}

/**
 * `guide` command: the module's internal tutorial (2026-10-25) — the guided
 * step table serialized for the agent PLUS the module's capability card
 * (purpose / capabilities / live-query recipes / related modules / keywords).
 * `done` flags are evaluated against the LIVE snapshot (= the user's current
 * position; they may have clicked ahead), `anchorPresent`/`enabled` tell
 * whether each step's control is actually operable right now. Request another
 * route's guide with { route: '<routeName>' }.
 * guide 命令：步骤教程 + 模块能力卡。done 实时求值（=用户当前位置），
 * anchorPresent/enabled 标明该控件此刻是否可操作。
 */
function commandGuide(payload: Record<string, unknown>): Record<string, unknown> {
  const wanted = typeof payload.route === 'string' && payload.route ? payload.route : null
  const current = router.currentRoute.value
  const routeName = wanted ?? (typeof current.name === 'string' ? current.name : '')
  const serialized = routeName ? serializeGuide(routeName) : null
  if (!serialized) {
    return { hasGuide: false, routeName }
  }
  return { hasGuide: true, ...serialized }
}

/**
 * `modules` command (2026-10-25): the ALL-MODULE directory with routing
 * keywords and the anti-hallucination golden rule — the answer to "which
 * module should handle this request" and "is X really unavailable" BEFORE
 * the agent touches the UI. Add { route: '<routeName>' } for one module's
 * full capability card.
 * modules 命令：全模块目录（用途 + 路由关键词 + 反幻觉金律）；带 route
 * 参数时返回该模块的完整能力卡。
 */
function commandModules(payload: Record<string, unknown>): Record<string, unknown> {
  const wanted = typeof payload.route === 'string' && payload.route ? payload.route : null
  if (wanted) {
    // Full card (caps + detailed manual) — works even when the route has no
    // step guide, so every module's 详细说明 is reachable the same way.
    // 完整卡（能力 + 详细说明）：没有步骤教程的模块同样可取。
    const card = moduleCard(wanted)
    if (card) return { module: card }
    return { module: null, routeName: wanted }
  }
  return moduleDirectory() as unknown as Record<string, unknown>
}

async function commandCapture(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const canvas = pickCanvas(payload.canvas)
  if (!canvas) throw new Error('no canvas available on this page')
  const maxWidth = typeof payload.maxWidth === 'number' && payload.maxWidth > 0 ? payload.maxWidth : 0
  let source: HTMLCanvasElement = canvas
  let width = canvas.width
  let height = canvas.height
  if (maxWidth > 0 && canvas.width > maxWidth) {
    const scale = maxWidth / canvas.width
    width = Math.max(1, Math.round(canvas.width * scale))
    height = Math.max(1, Math.round(canvas.height * scale))
    const scaled = document.createElement('canvas')
    scaled.width = width
    scaled.height = height
    const ctx = scaled.getContext('2d')
    if (!ctx) throw new Error('2D context unavailable for scaling')
    ctx.drawImage(canvas, 0, 0, width, height)
    source = scaled
  }
  const dataUrl = source.toDataURL('image/png')
  if (!dataUrl.startsWith('data:image/png;base64,')) {
    throw new Error('canvas not captureable (tainted or empty)')
  }
  return { png: dataUrl.slice('data:image/png;base64,'.length), width, height }
}

function findElement(target: Record<string, unknown>): HTMLElement | null {
  const aiId = typeof target.aiId === 'string' ? target.aiId : ''
  const testId = typeof target.testId === 'string' ? target.testId : ''
  const text = typeof target.text === 'string' ? target.text.trim() : ''
  if (aiId) {
    return document.querySelector<HTMLElement>(`[data-ai-id="${cssEscape(aiId)}"]`)
  }
  if (testId) {
    return document.querySelector<HTMLElement>(`[data-testid="${cssEscape(testId)}"]`)
  }
  if (text) {
    const candidates = Array.from(
      document.querySelectorAll<HTMLElement>('button, a, [role="button"], summary, .csf-unit-btn')
    )
    return (
      candidates.find((el) => (el.textContent ?? '').trim().includes(text)) ??
      candidates.find((el) => (el.textContent ?? '').trim().toLowerCase().includes(text.toLowerCase())) ??
      null
    )
  }
  return null
}

function cssEscape(value: string): string {
  return (window.CSS && CSS.escape) ? CSS.escape(value) : value.replace(/"/g, '\\"')
}

function syntheticClick(element: HTMLElement, clientX: number, clientY: number): void {
  const rect = element.getBoundingClientRect()
  const x = clientX || rect.left + rect.width / 2
  const y = clientY || rect.top + rect.height / 2
  const opts: MouseEventInit & { pointerId?: number; pointerType?: string; isPrimary?: boolean } = {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y,
    button: 0,
    buttons: 1,
  }
  // uPlot and Plotly listen to pointer events; plain DOM buttons react to the
  // mouse/click sequence. Dispatch both so canvas pickers AND buttons work.
  element.dispatchEvent(new PointerEvent('pointerdown', { ...opts, pointerId: 1, pointerType: 'mouse', isPrimary: true }))
  element.dispatchEvent(new MouseEvent('mousedown', opts))
  element.dispatchEvent(new PointerEvent('pointerup', { ...opts, pointerId: 1, pointerType: 'mouse', isPrimary: true }))
  element.dispatchEvent(new MouseEvent('mouseup', opts))
  element.dispatchEvent(new MouseEvent('click', opts))
}

async function commandClick(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const target = (payload.target ?? {}) as Record<string, unknown>
  const canvasPoint = target.canvas as Record<string, unknown> | undefined
  if (canvasPoint && typeof canvasPoint.x === 'number' && typeof canvasPoint.y === 'number') {
    // CSS-pixel coordinates on the chosen canvas (state lists cssWidth/cssHeight).
    const canvas = pickCanvas(target.canvasIndex ?? payload.canvas)
    if (!canvas) throw new Error('no canvas available for coordinate click')
    const rect = canvas.getBoundingClientRect()
    const clientX = rect.left + Math.min(Math.max(canvasPoint.x, 0), rect.width)
    const clientY = rect.top + Math.min(Math.max(canvasPoint.y, 0), rect.height)
    canvas.scrollIntoView({ block: 'nearest' })
    syntheticClick(canvas, clientX, clientY)
    return { clicked: true, on: 'canvas', x: canvasPoint.x, y: canvasPoint.y }
  }
  const element = findElement(target)
  if (!element) throw new Error('target not found (aiId/testId/text)')
  element.scrollIntoView({ block: 'center', behavior: 'instant' })
  await nextTick()
  if (element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true') {
    throw new Error('target is disabled')
  }
  syntheticClick(element, 0, 0)
  return { clicked: true, on: element.getAttribute('data-ai-id') ?? element.textContent?.trim().slice(0, 40) ?? 'element' }
}

function commandHighlight(payload: Record<string, unknown>): Record<string, unknown> {
  const aiId = typeof payload.aiId === 'string' ? payload.aiId : ''
  if (!aiId) throw new Error('aiId required')
  const ok = highlightTarget(aiId, typeof payload.note === 'string' ? payload.note : undefined)
  return { ok }
}

function commandNavigate(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const path = typeof payload.path === 'string' ? payload.path : ''
  if (!/^\/[A-Za-z0-9/_-]*$/.test(path)) throw new Error(`invalid path: ${path}`)
  return router.push(path).then(
    () => commandState(),
    () => {
      throw new Error(`navigation failed: ${path}`)
    }
  )
}

function commandApplyOptions(payload: Record<string, unknown>): Record<string, unknown> {
  const routeName = typeof payload.routeName === 'string' ? payload.routeName : ''
  const options = (payload.options ?? {}) as Record<string, unknown>
  if (!routeName || typeof options !== 'object') throw new Error('routeName and options required')
  window.dispatchEvent(new CustomEvent(APPLY_OPTIONS_EVENT, { detail: { routeName, options } }))
  return { dispatched: true }
}

/** Confirm: modal + optional spotlight; resolves on the user's click. */
function commandConfirm(reqId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const message = typeof payload.message === 'string' && payload.message.trim() ? payload.message.trim() : '确认执行该操作？'
  const aiId = typeof payload.aiId === 'string' ? payload.aiId : undefined
  const note = typeof payload.note === 'string' ? payload.note : undefined
  if (aiId) highlightTarget(aiId, note)
  return new Promise((resolve) => {
    pendingConfirm.value = { reqId, message, aiId, note }
    confirmResolver = resolve
  })
}

let confirmResolver: ((result: Record<string, unknown>) => void) | null = null

/** Called by AgentConfirmHost when the user clicks 确认/取消. */
export function resolveConfirm(confirmed: boolean): void {
  const resolver = confirmResolver
  pendingConfirm.value = null
  confirmResolver = null
  resolver?.({ confirmed })
}

async function handleCommand(
  reqId: string,
  command: string,
  rawPayload: unknown
): Promise<void> {
  markAgentActivity()
  const payload = (rawPayload && typeof rawPayload === 'object' ? rawPayload : {}) as Record<string, unknown>
  try {
    let data: Record<string, unknown>
    switch (command) {
      case 'state':
        data = await commandState()
        break
      case 'guide':
        data = commandGuide(payload)
        break
      case 'modules':
        data = commandModules(payload)
        break
      case 'capture':
        data = await commandCapture(payload)
        break
      case 'click':
        data = await commandClick(payload)
        break
      case 'highlight':
        data = commandHighlight(payload)
        break
      case 'confirm':
        data = await commandConfirm(reqId, payload)
        break
      case 'navigate':
        data = await commandNavigate(payload)
        break
      case 'apply_options':
        data = commandApplyOptions(payload)
        break
      default:
        throw new Error(`unknown command: ${command}`)
    }
    // Every reply except `state` (it IS the full context) and `navigate`
    // (whose reply is already a full state payload) carries the situation
    // context. Best-effort: a context failure must not fail the command.
    // 除 state（本身就是全量）与 navigate（回复已是全量 state）外，每次回复
    // 都附态势；失败不影响命令本身。
    if (command !== 'state' && command !== 'navigate') {
      try {
        data.context = await situationContext()
      } catch {
        // context is best-effort
      }
    }
    send({ type: 'agent_result', req_id: reqId, ok: true, data })
  } catch (err) {
    send({
      type: 'agent_result',
      req_id: reqId,
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    })
  }
}
