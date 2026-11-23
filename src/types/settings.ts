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

/** 下载无损压缩缓存池 / lossless-compressed download cache pool. */
export interface RemoteCacheSettings {
  /** 「远端选择」下载入池时无损压缩（TIFF/HDF5），默认开 / compress downloads into the pool (default on) */
  compress: boolean
  /** 缓存保留时长（分钟），默认 1440 = 1 天 / retention in minutes (default 1 day) */
  ttlMinutes: number
  /** 缓存池根目录；空 = 系统临时目录/xfais-cache-pool / pool root (empty = system temp default) */
  dir: string
}

export interface RemoteSyncSettings {
  cache: RemoteCacheSettings
}

export interface AppSettings {
  locale: 'zh' | 'en'
  performance: PerformanceSettings
  remoteSync: RemoteSyncSettings
}

export const DEFAULT_SETTINGS: AppSettings = {
  locale: 'zh',
  performance: {
    defaultMethod: 'splitpixel',
    batchParallel: false,
    batchWorkers: 4,
    ompThreads: 'auto'
  },
  remoteSync: {
    cache: {
      compress: true,
      ttlMinutes: 1440,
      dir: ''
    }
  }
}
