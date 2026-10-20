/**
 * Peak display palette + runtime theme color lookup.
 * Peak colors are assigned at peak creation and stored on the PeakSpec, so
 * they survive fits/undo regardless of theme (both palettes read fine on
 * either background).
 */

/** Categorical palette tuned for both dark and light chart surfaces. */
export const PEAK_PALETTE: readonly string[] = [
  '#4cc2ff',
  '#3dd68c',
  '#ffb454',
  '#ff5c7a',
  '#b18cff',
  '#4fd1c5',
  '#f6c177',
  '#7ee787',
  '#79c0ff',
  '#ffa657',
  '#d2a8ff',
  '#56d4dd',
]

export function paletteColor(i: number): string {
  return PEAK_PALETTE[i % PEAK_PALETTE.length]!
}

export interface ChartPalette {
  plotBg: string
  grid: string
  axis: string
  text: string
  data: string
  fit: string
  base: string
  resid: string
  cursor: string
  danger: string
  success: string
  accent: string
  selection: string
}

/** Read chart-relevant tokens off the document element (theme must be applied first). */
export function readChartPalette(): ChartPalette {
  const s = getComputedStyle(document.documentElement)
  const v = (name: string, fallback: string): string => s.getPropertyValue(name).trim() || fallback
  return {
    plotBg: v('--plot-bg', '#10151d'),
    grid: v('--chart-grid', '#202a38'),
    axis: v('--chart-axis', '#46536a'),
    text: v('--chart-text', '#8b96a5'),
    data: v('--chart-data', '#9fb3cc'),
    fit: v('--chart-fit', '#4cc2ff'),
    base: v('--chart-base', '#ffb454'),
    resid: v('--chart-resid', '#7f8ea3'),
    cursor: v('--chart-cursor', 'rgba(230,235,242,0.35)'),
    danger: v('--danger', '#ff5c7a'),
    success: v('--success', '#3dd68c'),
    accent: v('--accent', '#4cc2ff'),
    selection: v('--accent-line', 'rgba(76,194,255,0.45)'),
  }
}
