/**
 * serialize.ts — Agent-facing serialization of the guided-teaching registry
 * (2026-10-25): the "internal tutorial" handed to external MCP agents.
 *
 * One GuideDefinition becomes plain JSON: localized title, the ordered steps
 * with their `data-ai-id` anchors, each step's LIVE done-state evaluated
 * against the workspace-state bridge, and whether the anchor is currently in
 * the DOM (anchorPresent). That answers the three questions an agent has when
 * it docks with a running instance — what is this module for, what does each
 * control do, and WHERE is the user in the workflow right now (they may have
 * already done some steps; the done flags ARE the position).
 *
 * Two shapes:
 *  - serializeGuide(route):  the full step table (MCP `guide` command).
 *  - guideBriefing(route):   a compact position/next-step digest embedded in
 *                            the `state` command so a single get_state call
 *                            gives the agent its situational briefing.
 *
 * serialize.ts —— 引导注册表的 agent 侧序列化（内部教程）。步骤的 done 对
 * 实时快照求值（=用户当前位置），anchorPresent 查 DOM（=该控件此刻是否
 * 可操作——条件面板/其他模式分支会缺席）。
 */

import { NAV_CATALOG, currentLocale, navTitle } from '../context'
import { workspaceSnapshotOf } from '@/lib/workspace-state'
import type { GuideDefinition, ModuleManual } from './types'
import { GUIDES } from './registry'
import { MODULE_CAPS } from './caps'
import { MODULE_MANUALS } from './manuals'

const pick = (bi: { zh: string; en: string }): string =>
  currentLocale() === 'en' ? bi.en : bi.zh

/** Localized bullet text, preferring the active locale then zh. */
const pickOr = (bi: { zh: string; en: string }): string => {
  const v = pick(bi)
  return v || bi.zh || bi.en
}

function anchorInDom(aiId: string | undefined): boolean {
  if (!aiId) return false
  try {
    const sel = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(aiId) : aiId
    return document.querySelector(`[data-ai-id="${sel}"]`) != null
  } catch {
    return false
  }
}

/**
 * Is the anchored control currently ENABLED (not grayed out)? Many buttons
 * stay disabled until their preconditions are met (e.g. 完成本环 needs ≥3
 * guide points, Run needs files); surfacing this lets the agent tell the
 * user WHY a click would fail instead of discovering it by failing.
 * 锚点控件当前是否可用（非灰度）：很多按钮在条件达成前是禁用的，提前告知
 * agent「现在点了会失败、为什么」，而不是让它点了才报错。
 */
function anchorEnabled(aiId: string | undefined): boolean {
  if (!aiId) return false
  try {
    const sel = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(aiId) : aiId
    const el = document.querySelector(`[data-ai-id="${sel}"]`)
    if (!(el instanceof HTMLElement)) return false
    if ((el instanceof HTMLButtonElement && el.disabled)) return false
    if ((el instanceof HTMLInputElement && el.disabled)) return false
    if (el.getAttribute('aria-disabled') === 'true') return false
    return true
  } catch {
    return false
  }
}

function guideFor(routeName: string): GuideDefinition | null {
  return GUIDES[routeName] ?? null
}

export interface SerializedGuideStep {
  id: string
  /** Anchor to click/spotlight; null on info-only steps. */
  aiId: string | null
  /** False when the control is not in the DOM right now (other mode /
   *  conditional panel / not mounted yet) — do not click, tell the user. */
  anchorPresent: boolean
  /** False when the control is in the DOM but GRAYED OUT — its
   *  preconditions are not met yet (usually the earlier steps). */
  enabled: boolean
  title: string
  tip: string
  /** Evaluated against the LIVE workspace snapshot — done steps are where the
   *  user already is; the first not-done step is "next". */
  done: boolean
  /** Safe-action marker from the registry (load/run/export only). */
  autoClick: boolean
}

export interface SerializedGuide {
  routeName: string
  title: string
  /** False when the module's current mode/branch has no step table. */
  applicable: boolean
  /** inapplicableNote (localized) when applicable=false, else null. */
  note: string | null
  /** Index of the first not-done step; null when every step is done. */
  position: number | null
  doneCount: number
  total: number
  steps: SerializedGuideStep[]
  /**
   * Capability card (2026-10-25): purpose / capabilities / live-query
   * recipes / related modules / routing keywords — the "what can this app
   * do" layer that stops agents guessing. Null when no card is authored.
   * 能力卡：干啥/能干啥/可实时查询配方/替代模块/关键词。
   */
  caps: SerializedCaps | null
}

// ── Capability cards / 模块能力卡 ─────────────────────────────────────────────

export interface SerializedCaps {
  routeName: string
  purpose: string
  capabilities: string[]
  /** run_task recipes the agent should USE instead of guessing facts. */
  liveQueries: Array<{ note: string; command: string; params: Record<string, unknown> }>
  related: Array<{ routeName: string; note: string }>
  keywords: string[]
  /**
   * Detailed module manual (2026-10-27): overview / prerequisites / real
   * ordered workflow / outputs / pitfalls / teach-first agent tips. Present
   * whenever a manual is authored for the module — the "read before
   * operating" layer. 模块详细说明：操作前必读层。
   */
  manual?: SerializedManual
}

export interface SerializedManual {
  overview: string
  inputs: string[]
  workflow: Array<{ title: string; detail: string }>
  outputs: string[]
  pitfalls: string[]
  agentTips: string[]
}

function serializeManual(manual: ModuleManual): SerializedManual {
  return {
    overview: pickOr(manual.overview),
    inputs: manual.inputs.map(pickOr),
    workflow: manual.workflow.map((s) => ({ title: pickOr(s.title), detail: pickOr(s.detail) })),
    outputs: manual.outputs.map(pickOr),
    pitfalls: manual.pitfalls.map(pickOr),
    agentTips: manual.agentTips.map(pickOr),
  }
}

/**
 * Full capability card for one route — works even when the route has no step
 * guide (the card + manual layer is independent of the tour). Unifies
 * serializeGuide's caps and the `modules route=` branch so both always carry
 * the detailed manual. 模块完整卡：与步骤教程解耦，一律附详细说明。
 */
export function moduleCard(routeName: string): SerializedCaps | null {
  const card = MODULE_CAPS[routeName] ?? null
  const manual = MODULE_MANUALS[routeName] ?? null
  if (!card && !manual) return null
  const entry = NAV_CATALOG.find((e) => e.routeName === routeName)
  return {
    routeName,
    purpose: card ? pickOr(card.purpose) : navTitle(routeName),
    capabilities: (card?.capabilities ?? []).map(pickOr),
    liveQueries: (card?.liveQueries ?? []).map((q) => ({
      note: pickOr(q.note),
      command: q.command,
      params: q.params,
    })),
    related: (card?.related ?? []).map((r) => ({ routeName: r.routeName, note: pickOr(r.note) })),
    keywords: card?.keywords ?? [],
    manual: manual ? serializeManual(manual) : undefined,
  }
}

export interface ModuleDirectoryEntry {
  routeName: string
  title: string
  path: string
  purpose: string
  keywords: string[]
}

export interface ModuleDirectory {
  modules: ModuleDirectoryEntry[]
  /**
   * Golden rule (anti-hallucination): agents must consult this directory /
   * get_guide and its live-query recipes BEFORE claiming the app cannot do
   * something. / 反幻觉金律：断言“应用不支持 X”之前必须先查目录与配方。
   */
  rule: string
}

const GOLDEN_RULE_ZH =
  '金律一（反幻觉）：在未查询本目录（modules）与相应模块 get_guide（含 liveQueries 配方）之前，禁止声称"X-FAIS 没有某功能/某数据"——尤其标样、探测器、格式等事实均可 run_task 实时查询；内置没有的东西往往能用相关模块生成或本地上传。'
const GOLDEN_RULE_EN =
  'Golden rule 1 (anti-hallucination): never claim "X-FAIS cannot do X / has no X" before consulting this directory (modules) and the module’s get_guide (including its liveQueries recipes) — calibrants, detectors, formats and similar facts are live-queryable via run_task; what is not built in can often be GENERATED by a related module or uploaded as a local file.'
const TEACH_RULE_ZH =
  '金律二（教学优先）：缺信息/不确定下一步时，先教后做——读该模块详细说明（modules route=<名> 的 manual），向用户解释并 highlight 对应控件，让用户自己完成文件选择等操作；只有用户明确要求代做、或动作安全（查询/加载）时才代替点击，关键动作（运行/导出/覆盖）必须 confirm。每次工具返回末尾的「态势」行已给出当前位置与下一步，先读它再行动。'
const TEACH_RULE_EN =
  'Golden rule 2 (teach first): when information is missing or the next step is unclear, teach before acting — read the module manual (modules route=<name>), explain to the user, highlight the control and let the user do file selections themselves; act on the user’s behalf only when asked or when the action is safe (query/load), and always confirm before run/export/overwrite. Every tool reply ends with a SITUATION line showing where you are and what is next — read it before acting.'

/**
 * All-module directory with routing keywords — answers "which module should
 * handle <user request>" (e.g. 聚丙烯标样 → cell-calibrant-generator +
 * calibration) before the agent ever touches the UI.
 */
export function moduleDirectory(): ModuleDirectory {
  const entries: ModuleDirectoryEntry[] = []
  for (const [routeName, card] of Object.entries(MODULE_CAPS)) {
    const path = NAV_CATALOG.find(e => e.routeName === routeName)?.path
      ?? (routeName === 'home' ? '/' : `/workspace/${routeName}`)
    entries.push({
      routeName,
      title: navTitle(routeName),
      path,
      purpose: pickOr(card.purpose),
      keywords: card.keywords,
    })
  }
  return {
    modules: entries,
    rule:
      currentLocale() === 'en'
        ? `${GOLDEN_RULE_EN}\n${TEACH_RULE_EN}`
        : `${GOLDEN_RULE_ZH}\n${TEACH_RULE_ZH}`,
  }
}

/** Full step table for one route (null when the route has no guide). */
export function serializeGuide(routeName: string): SerializedGuide | null {
  const guide = guideFor(routeName)
  if (!guide) return null
  const snap = workspaceSnapshotOf(routeName)
  const applicable = guide.applicable ? guide.applicable(snap) : true
  const steps: SerializedGuideStep[] = guide.steps.map(step => ({
    id: step.id,
    aiId: step.aiId ?? null,
    anchorPresent: anchorInDom(step.aiId),
    enabled: anchorEnabled(step.aiId),
    title: pick(step.title),
    tip: pick(step.tip),
    done: step.done(snap),
    autoClick: step.autoClick === true,
  }))
  const position = steps.findIndex(s => !s.done)
  const card = moduleCard(routeName)
  return {
    routeName,
    title: pick(guide.title),
    applicable,
    note: applicable ? null : pick(guide.inapplicableNote ?? { zh: '当前模式暂无对应教程', en: 'No tutorial for the current mode' }),
    position: position < 0 ? null : position,
    doneCount: steps.filter(s => s.done).length,
    total: steps.length,
    steps,
    caps: card,
  }
}

export interface GuideBriefingNext {
  aiId: string | null
  anchorPresent: boolean
  /** False when the control is grayed out (preconditions unmet). */
  enabled: boolean
  title: string
  tip: string
  autoClick: boolean
}

export interface GuideBriefing {
  hasGuide: boolean
  title: string | null
  applicable: boolean
  note: string | null
  /** First not-done step index; null = all done. */
  position: number | null
  doneCount: number
  total: number
  next: GuideBriefingNext | null
}

/** Compact digest for the `state` command — where the user is + what is next. */
export function guideBriefing(routeName: string): GuideBriefing {
  const guide = guideFor(routeName)
  if (!guide) {
    return {
      hasGuide: false, title: null, applicable: false, note: null,
      position: null, doneCount: 0, total: 0, next: null,
    }
  }
  const full = serializeGuide(routeName)
  // serializeGuide re-checked applicability against the same snapshot.
  const nextStep = full && full.position != null ? guide.steps[full.position] : null
  return {
    hasGuide: true,
    title: full?.title ?? '',
    applicable: full?.applicable ?? true,
    note: full?.note ?? null,
    position: full?.position ?? null,
    doneCount: full?.doneCount ?? 0,
    total: full?.total ?? 0,
    next: nextStep
      ? {
          aiId: nextStep.aiId ?? null,
          anchorPresent: anchorInDom(nextStep.aiId),
          enabled: anchorEnabled(nextStep.aiId),
          title: pick(nextStep.title),
          tip: pick(nextStep.tip),
          autoClick: nextStep.autoClick === true,
        }
      : null,
  }
}
