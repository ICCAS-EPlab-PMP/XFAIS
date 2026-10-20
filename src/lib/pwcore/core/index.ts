/**
 * Ported from PeakWorkbench (REA/peakfit) pure numeric core for X-FAIS curve fitting (0.3.3).
 * Original: zero-dependency TS core (special/models/statsfn/geometry/fitter/fit/baseline/
 * baseline-asls/detect/smooth/parse/demo) — all modules ported byte-identically.
 */

/**
 * PeakWorkbench 谱峰工作台 numerical core — pure TypeScript, zero runtime dependencies.
 *
 * This barrel is consumed by the Electron main-process fit worker, the
 * renderer (live curve evaluation, peak detection, smoothing, file parsing),
 * and `scripts/smoke.ts`. Nothing here may import Node, DOM or Electron.
 */
export * from './special'
export * from './models'
export * from './statsfn'
export * from './geometry'
export * from './fitter'
export * from './smooth'
export * from './baseline'
export * from './detect'
export * from './parse'
export * from './demo'
export * from './fit'

// Convenience re-exports for scripts/tests that drive the core directly.
export type {
  BaselineSpec,
  DetectOptions,
  FitIterEvent,
  FitOptions,
  FitRequest,
  PeakConstraints,
  PeakSpec
} from '../shared/types'
