// workspace-state.ts — reactive bridge between workspace views and consumers
// (the AI assistant layer in the Jev build) that need to observe per-view
// progress: files loaded, PONI present, runnability, run phase.
// 工作区状态桥——视图侧上报、AI 层观测的响应式中转站。
//
// MUST stay free of `@/ai/**` imports: main-build views import this module,
// and the AI subtree must never enter main bundles (see vite.config.ts alias).
// 本模块严禁引入 @/ai/**：主线视图会导入它，AI 子树不得进入主线产物。
import { reactive, readonly } from 'vue'

export type WorkspacePhase = 'idle' | 'running' | 'done' | 'error'

export interface WorkspaceSnapshot {
  /** Number of data files the user has loaded / 已加载数据文件数 */
  filesCount: number
  /** Whether a PONI geometry is active / 是否已启用 PONI 几何 */
  hasPoni: boolean
  /** Whether the view's primary action is currently runnable / 主操作是否可执行 */
  canRun: boolean
  /** Run lifecycle / 运行阶段 */
  phase: WorkspacePhase
  /** View-specific signals, e.g. calibration rings/chi2 / 视图特有信号 */
  extras?: Record<string, unknown>
}

const snapshots = reactive<Record<string, WorkspaceSnapshot>>({})

/** Full-replace report for a route; callers own the complete snapshot. */
export function reportWorkspace(routeName: string, snap: WorkspaceSnapshot): void {
  snapshots[routeName] = snap
}

/** Drop a route's snapshot (call from onUnmounted so stale state never lingers). */
export function clearWorkspace(routeName: string): void {
  delete snapshots[routeName]
}

/** Read-only reactive access for consumers (guide engine, agent). */
export function useWorkspaceSnapshots() {
  return readonly(snapshots)
}

/** One-shot read of a route's current snapshot (null when never reported). */
export function workspaceSnapshotOf(routeName: string): WorkspaceSnapshot | null {
  return snapshots[routeName] ?? null
}
