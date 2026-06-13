/**
 * mask.ts — Mask Maker type definitions
 *
 * All types used across the Mask Maker module (views, components, store).
 * Aligned with the "single" mask mode (values 0 = unmasked, 1 = masked).
 */

// ── Drawing tool selection ────────────────────────────────────────────────────

export type MaskTool =
  | 'pan'
  | 'rectangle'
  | 'disk'
  | 'ellipse'
  | 'polygon'
  | 'line'

export type MaskMode = 'mask' | 'unmask'

// ── Shape parameter payloads sent to Python backend ───────────────────────────

export interface RectangleParams {
  row: number
  col: number
  height: number
  width: number
}

export interface DiskParams {
  crow: number
  ccol: number
  radius: number
}

export interface EllipseParams {
  crow: number
  ccol: number
  radius_r: number
  radius_c: number
}

export interface PolygonParams {
  vertices: Array<[number, number]> // [row, col] pairs
}

export interface LineParams {
  row0: number
  col0: number
  row1: number
  col1: number
  width?: number
}

export type ShapeParams =
  | RectangleParams
  | DiskParams
  | EllipseParams
  | PolygonParams
  | LineParams

// ── Threshold modes ───────────────────────────────────────────────────────────

export type ThresholdMode = 'below' | 'above' | 'between' | 'not_finite'

// ── Export formats ────────────────────────────────────────────────────────────

export type MaskExportFormat = 'edf' | 'tif' | 'npy' | 'h5' | 'msk'

export const MASK_EXPORT_FORMATS: Array<{
  value: MaskExportFormat
  label: string
  extensions: string[]
}> = [
  { value: 'edf', label: 'EDF (.edf)', extensions: ['edf'] },
  { value: 'tif', label: 'TIFF (.tif)', extensions: ['tif', 'tiff'] },
  { value: 'npy', label: 'NumPy (.npy)', extensions: ['npy'] },
  { value: 'h5', label: 'HDF5 (.h5)', extensions: ['h5', 'hdf5'] },
  { value: 'msk', label: 'Fit2D Mask (.msk)', extensions: ['msk'] },
]

// ── Mask statistics ───────────────────────────────────────────────────────────

export interface MaskStats {
  maskedPixels: number
  totalPixels: number
  percentage: number
}

// ── Image info ────────────────────────────────────────────────────────────────

export interface MaskImageInfo {
  filePath: string
  fileName: string
  width: number
  height: number
  fileType: string
  stats?: {
    min: number
    max: number
    std: number
  }
}

// ── Drawing state for canvas interaction ──────────────────────────────────────

export interface DrawState {
  active: boolean
  startX: number
  startY: number
  currentX: number
  currentY: number
  /** For polygon: accumulated vertices [[row, col], ...] */
  polygonPoints: Array<[number, number]>
}

// ── Mask backend response ─────────────────────────────────────────────────────

export interface MaskBackendResponse {
  mask_data: string     // base64-encoded Uint8Array
  masked_pixels: number // count of masked pixels after operation
}

export interface MaskLoadResponse {
  mask_data: string     // base64-encoded Uint8Array
  shape: [number, number]
}

export interface MaskExportResponse {
  status: 'ok'
  path: string
  shape: number[]
  dtype: string
  masked_pixels: number
}
