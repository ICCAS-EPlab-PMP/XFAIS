// settings.ts — Application settings schema / 应用设置结构
// Single source of truth for user-tunable preferences persisted in
// localStorage (desktop renderer + web mode share the same store).
// 用户可调偏好的唯一事实来源，持久化于 localStorage（桌面渲染层与
// web 模式共用同一存储）。

export type IntegrationMethodSetting = 'splitpixel' | 'csr'

export interface PerformanceSettings {
  /** Initial value of the method selector for new tasks (default splitpixel = today's behavior) / 新任务算法选择器初始值（默认 splitpixel = 现状） */
  defaultMethod: IntegrationMethodSetting
  /** Multi-file batch via thread pool — OFF by default (serial) / 多文件批处理线程池并行——默认关闭（串行） */
  batchParallel: boolean
  /** Worker count for batch parallelism / 批处理并行的线程数 */
  batchWorkers: number
  /** OpenMP thread cap for the Python service ('auto' = do not set env) / Python 服务 OpenMP 线程上限（auto = 不设环境变量） */
  ompThreads: 'auto' | number
}

export interface AppSettings {
  locale: 'zh' | 'en'
  performance: PerformanceSettings
}

export const DEFAULT_SETTINGS: AppSettings = {
  locale: 'zh',
  performance: {
    defaultMethod: 'splitpixel',
    batchParallel: false,
    batchWorkers: 4,
    ompThreads: 'auto'
  }
}
