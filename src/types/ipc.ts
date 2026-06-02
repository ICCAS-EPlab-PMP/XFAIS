/**
 * ipc.ts — TypeScript types mirroring the Python service JSON protocol.
 * Matches service_launcher.py message schemas exactly.
 */

// ── Client → Server ────────────────────────────────────────────────────────

export interface TaskRequest {
  type: 'task_submit'
  task_id: string
  route: string
  payload: Record<string, unknown>
}

export interface TaskCancelWsRequest {
  type: 'task_cancel'
  task_id: string
}

export interface TaskCancelRequest {
  taskId: string
}

export type ClientMessage = TaskRequest | TaskCancelWsRequest

// ── Server → Client ────────────────────────────────────────────────────────

export interface TaskAccepted {
  type: 'task_accepted'
  task_id: string
}

export interface TaskProgress {
  type: 'task_progress'
  task_id: string
  progress: number
  message: string
}

export interface TaskResponse {
  type: 'task_complete'
  task_id: string
  result: Record<string, unknown>
}

export interface TaskError {
  type: 'task_error'
  task_id: string
  error: string
  code: string
}

export interface TaskCancelled {
  type: 'task_cancelled'
  task_id: string
}

export type ServerMessage =
  | TaskAccepted
  | TaskProgress
  | TaskResponse
  | TaskError
  | TaskCancelled

// ── HTTP ────────────────────────────────────────────────────────────────────

export interface HealthReport {
  dependency_status: string
  expected_python: string
  health_ok: boolean
  missing_dependencies: string[]
  python_executable: string
  python_version: string
  service_name: string
  ws_port?: number
}

// ── Route constants ─────────────────────────────────────────────────────────

export const API_ROUTES = [
  '/api/integrate1d',
  '/api/integrate_azimuth',
  '/api/integrate_cake',
  '/api/integrate_fiber',
  '/api/viewer_config',
  '/api/h5convert',
  '/api/h5convert_scan',
  '/api/h5_extract',
  '/api/h5_list_files',
  '/api/png_generate',
  '/api/calibrant_generate',
  '/api/cell_calibrant_generate',
  '/api/manual_calibrant_generate',
] as const

export type ApiRoute = (typeof API_ROUTES)[number]

// ── Electron IPC layer (camelCase) ──────────────────────────────────────────

export interface FileFilter {
  name: string
  extensions: string[]
}

export interface DialogOpenFileOptions {
  filters?: FileFilter[]
  defaultPath?: string
  multiSelections?: boolean
}

export type DialogOpenFileResult = string | string[] | null

export interface DialogSaveFileOptions {
  filters?: FileFilter[]
  defaultPath?: string
}

export type TaskCommand = string

export interface TaskSubmitRequest {
  command: string
  params: Record<string, unknown>
}

export interface TaskSubmitResponse {
  taskId: string
}

export interface ElectronTaskCancelRequest {
  type: 'task_cancel'
  taskId: string
}

export interface TaskProgressPayload {
  taskId: string
  progress: number
  message?: string
}

export interface TaskResultPayload {
  taskId: string
  data: unknown
}

export interface TaskErrorPayload {
  taskId: string
  error: string
  code?: string
}

// ── pyFAI 工具状态 / pyFAI tool status ─────────────────────────────────────

export interface PyfaiCheckResult {
  embedded: {
    available: boolean
    version: string | null
    calib2Path: string | null
    hasQtBinding: boolean
  }
  system: {
    available: boolean
    version: string | null
    calib2Path: string | null
    hasQtBinding: boolean
  }
  overall: 'available' | 'embedded_only' | 'system_only' | 'not_found'
}

export const XRAY_FILE_FILTERS: FileFilter[] = [
  { name: 'X-ray Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
  { name: 'PONI Files', extensions: ['poni'] },
  { name: 'NumPy Files', extensions: ['npy'] },
  { name: 'All Files', extensions: ['*'] },
]
