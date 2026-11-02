/**
 * types.ts — Guided-teaching step definitions for the AI assistant.
 *
 * A guide is an ordered list of steps for one workspace route. Each step
 * spotlights one control (`data-ai-id`), explains what to do (zh/en), knows
 * when its goal is satisfied from the workspace-state bridge, and may opt
 * into the auto-click countdown (safe actions only: load / run / export).
 * 教学引导：单页有序步骤。每步聚光一个控件、双语讲解、依据工作区状态桥
 * 判定完成条件；仅加载/运行/导出类安全动作可勾选自动代点。
 */

import type { WorkspaceSnapshot } from '@/lib/workspace-state'

export interface Bilingual {
  zh: string
  en: string
}

export interface GuideStep {
  id: string
  /** `data-ai-id` of the control to spotlight (info-only steps may omit). */
  aiId?: string
  title: Bilingual
  tip: Bilingual
  /** True when this step's goal is already satisfied by the current snapshot. */
  done: (snap: WorkspaceSnapshot | null) => boolean
  /**
   * Auto-click the spotlighted control after the cancellable countdown when
   * confidence allows. Only author this on load/run/export-style actions —
   * never on cancel/clear/delete controls.
   */
  autoClick?: boolean
  /** Extra gate for the auto-click (e.g. only click Run while canRun). */
  allowWhen?: (snap: WorkspaceSnapshot | null) => boolean
  /**
   * Marker hooks the agent can act on when the step is presented
   * (e.g. 'apply-template' runs the PONI-based template decision).
   */
  action?: 'apply-template'
}

export interface GuideDefinition {
  routeName: string
  title: Bilingual
  steps: GuideStep[]
  /**
   * Mode/branch gate (2026-10-25): when present and false against the live
   * snapshot, the tour does NOT start — some views have modes whose controls
   * do not exist in this step table (e.g. calibration's com / internal
   * branches). Absent = always applicable. The agent-facing serialization
   * (serialize.ts) returns applicable + note so external agents get the same
   * guard. 模式/支路门控：不适用时不启动教学；序列化给 agent 时同样带回。
   */
  applicable?: (snap: WorkspaceSnapshot | null) => boolean
  /** Shown/spoken when `applicable` rejects the current state. */
  inapplicableNote?: Bilingual
}

// ── Module manual (2026-10-27) / 模块详细说明 ─────────────────────────────────

/**
 * One ordered how-to step of a module manual. Prose only — the step-guide
 * layer (steps/*.ts) carries the data-ai-id anchors; manuals never reference
 * anchor ids so they cannot dangle. 流程步骤：纯文字，不引用 aiId。
 */
export interface ManualWorkflowStep {
  title: Bilingual
  detail: Bilingual
}

/**
 * ModuleManual — the per-module DETAILED description (2026-10-27 user
 * request): what the module is for, what must exist before starting, the
 * real ordered workflow, what it produces and where it flows, the pitfalls,
 * and teach-vs-operate guidance for external agents. Authored in
 * guide/manuals*.ts (grounded in the actual views) and serialized with the
 * capability card via `guide`/`modules`.
 * 模块详细说明：用途/前提/真实分步流程/产出去向/坑点/给 agent 的教学优先
 * 提示。经能力卡随 guide/modules 命令下发给外部 agent。
 */
export interface ModuleManual {
  /** 2–4 sentences: purpose, when to use, what it produces. */
  overview: Bilingual
  /** Prerequisites (files, PONI, mode selection, facts to query first…). */
  inputs: Bilingual[]
  /** The real ordered workflow, grounded in the actual UI. */
  workflow: ManualWorkflowStep[]
  /** Products and where they flow next. */
  outputs: Bilingual[]
  /** Gotchas, limits, common failure modes. */
  pitfalls: Bilingual[]
  /** Teach-first guidance for external agents on THIS module. */
  agentTips: Bilingual[]
}
