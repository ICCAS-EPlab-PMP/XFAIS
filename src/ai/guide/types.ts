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
}
