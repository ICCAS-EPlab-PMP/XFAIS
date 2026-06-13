/**
 * mask-store.ts — Mask state management
 *
 * Maintains a Uint8Array mask (0 = unmasked, 1 = masked in "single" mode)
 * with undo/redo history. Rectangle fill is executed directly in frontend
 * for responsiveness; all other shapes are delegated to the Python backend
 * via silx.image.shapes.
 */

import type { MaskStats } from '@/types/mask'

const MAX_HISTORY = 10

export class MaskStore {
  private mask: Uint8Array
  private width: number
  private height: number
  private undoStack: Uint8Array[] = []
  private redoStack: Uint8Array[] = []

  constructor(height: number, width: number) {
    this.height = height
    this.width = width
    this.mask = new Uint8Array(height * width)
  }

  // ── Accessors ──────────────────────────────────────────────────────────────

  getWidth(): number {
    return this.width
  }

  getHeight(): number {
    return this.height
  }

  getMask(): Uint8Array {
    return this.mask
  }

  getMaskCopy(): Uint8Array {
    return new Uint8Array(this.mask)
  }

  getMaskBase64(): string {
    return uint8ArrayToBase64(this.mask)
  }

  /** Replace mask entirely (e.g. from backend response or file load). */
  setMask(data: Uint8Array): void {
    if (data.length !== this.height * this.width) {
      throw new Error(
        `Mask size mismatch: expected ${this.height}×${this.width}=${this.height * this.width}, got ${data.length}`
      )
    }
    this.mask = new Uint8Array(data)
  }

  // ── Local operations (no backend needed) ────────────────────────────────────

  /** Fill a rectangular region. Runs entirely in frontend for responsiveness. */
  fillRect(
    row: number,
    col: number,
    h: number,
    width: number,
    level: number,
    doMask: boolean
  ): void {
    const r0 = Math.max(0, Math.min(row, this.height))
    const r1 = Math.max(0, Math.min(row + h, this.height))
    const c0 = Math.max(0, Math.min(col, this.width))
    const c1 = Math.max(0, Math.min(col + width, this.width))

    if (r0 >= r1 || c0 >= c1) return

    for (let r = r0; r < r1; r++) {
      const base = r * this.width + c0
      const count = c1 - c0
      if (doMask) {
        this.mask.fill(level, base, base + count)
      } else {
        for (let i = 0; i < count; i++) {
          if (this.mask[base + i] === level) {
            this.mask[base + i] = 0
          }
        }
      }
    }
  }

  /** Reset mask to all zeros. */
  reset(): void {
    this.mask.fill(0)
  }

  /** Invert mask: 0 ↔ 1. */
  invert(): void {
    for (let i = 0; i < this.mask.length; i++) {
      this.mask[i] = this.mask[i] === 0 ? 1 : 0
    }
  }

  /** Clear mask (same as reset). */
  clear(): void {
    this.reset()
  }

  // ── History management ──────────────────────────────────────────────────────

  /** Commit current state to undo history before modification. */
  commit(): void {
    this.undoStack.push(new Uint8Array(this.mask))
    if (this.undoStack.length > MAX_HISTORY) {
      this.undoStack.shift()
    }
    // Clear redo stack on new commit
    this.redoStack = []
  }

  undo(): boolean {
    if (this.undoStack.length === 0) return false
    this.redoStack.push(new Uint8Array(this.mask))
    this.mask = this.undoStack.pop()!
    return true
  }

  redo(): boolean {
    if (this.redoStack.length === 0) return false
    this.undoStack.push(new Uint8Array(this.mask))
    this.mask = this.redoStack.pop()!
    return true
  }

  canUndo(): boolean {
    return this.undoStack.length > 0
  }

  canRedo(): boolean {
    return this.redoStack.length > 0
  }

  // ── Statistics ──────────────────────────────────────────────────────────────

  getStats(): MaskStats {
    let maskedPixels = 0
    for (let i = 0; i < this.mask.length; i++) {
      if (this.mask[i] !== 0) maskedPixels++
    }
    const totalPixels = this.height * this.width
    return {
      maskedPixels,
      totalPixels,
      percentage: totalPixels > 0 ? (maskedPixels / totalPixels) * 100 : 0,
    }
  }

  // ── Import ──────────────────────────────────────────────────────────────────

  /**
   * Load mask from external data, auto-cropping or padding to match dimensions.
   * Assumes srcData is row-major uint8 with shape [srcH, srcW].
   */
  loadMask(srcData: Uint8Array, srcShape: [number, number]): void {
    const [srcH, srcW] = srcShape
    const newMask = new Uint8Array(this.height * this.width)

    const copyH = Math.min(srcH, this.height)
    const copyW = Math.min(srcW, this.width)

    for (let r = 0; r < copyH; r++) {
      const srcBase = r * srcW
      const dstBase = r * this.width
      for (let c = 0; c < copyW; c++) {
        newMask[dstBase + c] = srcData[srcBase + c] !== 0 ? 1 : 0
      }
    }

    this.mask = newMask
    // Clear history on import
    this.undoStack = []
    this.redoStack = []
  }
}

// ── Helper ────────────────────────────────────────────────────────────────────

function uint8ArrayToBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}
