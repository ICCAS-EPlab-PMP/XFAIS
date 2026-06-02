/**
 * chart-utils.ts — Plotly layout, theme, and export utilities
 * Plotly 布局、主题和导出工具函数
 */

import type { PlotLayout, PlotConfig } from 'plotly.js-dist-min'

/* Dark theme colors derived from variables.css design tokens
 * 基于 variables.css 设计令牌派生的暗色主题色值 */
const THEME = {
  bgPrimary: '#0f172a',
  bgSurface: '#1e293b',
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  border: '#334155',
  accent: '#3b82f6',
  accentSecondary: '#10b981',
  grid: '#1e293b',
  zeroLine: '#475569',
} as const

/** Plotly layout preset for dark theme
 * Plotly 暗色主题布局预设 */
export const DARK_THEME: Partial<PlotLayout> = {
  paper_bgcolor: THEME.bgPrimary,
  plot_bgcolor: THEME.bgPrimary,
  font: { color: THEME.textPrimary, family: 'system-ui, sans-serif', size: 12 },
  margin: { t: 40, b: 56, l: 64, r: 24, pad: 4 },
  xaxis: {
    color: THEME.textSecondary,
    gridcolor: THEME.grid,
    zerolinecolor: THEME.zeroLine,
    tickfont: { color: THEME.textSecondary, size: 11 },
  },
  yaxis: {
    color: THEME.textSecondary,
    gridcolor: THEME.grid,
    zerolinecolor: THEME.zeroLine,
    tickfont: { color: THEME.textSecondary, size: 11 },
  },
  showlegend: true,
  legend: {
    font: { color: THEME.textPrimary, size: 11 },
    bgcolor: 'rgba(0,0,0,0)',
  },
  hovermode: 'closest',
  colorway: [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
  ],
}

/** Named colormap presets for Plotly
 * Plotly 色图预设 */
export const COLORMAP_PRESETS = {
  // XRD custom colormaps / XRD 自定义色图
  foxtrot: [[0.0, 'black'], [0.25, 'blue'], [0.50, 'rgb(51,255,51)'], [0.75, 'yellow'], [1.0, 'red']] as (string | number)[][],
  fit2d: [[0.0, 'black'], [0.20, 'blue'], [0.40, 'rgb(51,255,51)'], [0.60, 'yellow'], [0.80, 'red'], [1.0, 'white']] as (string | number)[][],
  // Plotly built-in names / Plotly 内置名称
  viridis: 'Viridis',
  inferno: 'Inferno',
  magma: 'Magma',
  plasma: 'Plasma',
  cividis: 'Cividis',
  jet: 'Jet',
  gray: 'Greys',
  hot: 'Hot',
  cool: 'Cool',
  turbo: 'Turbo',
} as const

export type ColormapName = keyof typeof COLORMAP_PRESETS

/** Display names for colormap options in UI
 * 色图选项的 UI 显示名称 */
export const COLORMAP_DISPLAY_NAMES: Record<ColormapName, string> = {
  foxtrot: 'Foxtrot (WAXS)',
  fit2d: 'FIT2D (WAXS)',
  viridis: 'Viridis',
  inferno: 'Inferno',
  magma: 'Magma',
  plasma: 'Plasma',
  cividis: 'Cividis',
  jet: 'Jet',
  gray: 'Grayscale',
  hot: 'Hot',
  cool: 'Cool',
  turbo: 'Turbo',
}

/**
 * Resolve a colormap key (preset or custom alias) to a Plotly-compatible colorscale.
 * 将色图键（预设或自定义别名）解析为 Plotly 兼容的 colorscale。
 */
export function resolveColorscale(key: string): string | (string | number)[][] {
  // Direct preset match / 直接预设匹配
  if (key in COLORMAP_PRESETS) {
    return COLORMAP_PRESETS[key as ColormapName]
  }
  // Custom aliases used by backend / 后端使用的自定义别名
  if (key === 'smooth_WAXS_foxtrot') return COLORMAP_PRESETS.foxtrot
  if (key === 'smooth_WAXS_fit2D') return COLORMAP_PRESETS.fit2d
  // Fallback / 回退
  return COLORMAP_PRESETS.viridis
}

/** Resolve a colormap key to a CSS linear-gradient for UI colorbars.
 * 将色图键解析为用于 UI 色条的 CSS 渐变。 */
export function resolveColorbarGradient(key: string): string {
  const gradients: Record<string, string> = {
    foxtrot: 'linear-gradient(180deg, #ff3300 0%, #ffe600 25%, #33ff33 50%, #1d4ed8 75%, #000000 100%)',
    fit2d: 'linear-gradient(180deg, #ffffff 0%, #ff3300 20%, #ffe600 40%, #33ff33 60%, #2563eb 80%, #000000 100%)',
    viridis: 'linear-gradient(180deg, #fde725 0%, #5ec962 35%, #21918c 65%, #3b528b 82%, #440154 100%)',
    inferno: 'linear-gradient(180deg, #fcffa4 0%, #f98e09 35%, #bc3754 65%, #57106e 82%, #000004 100%)',
    magma: 'linear-gradient(180deg, #fcfdbf 0%, #f98e52 30%, #b5367a 60%, #51127c 82%, #000004 100%)',
    plasma: 'linear-gradient(180deg, #f0f921 0%, #fb9f3a 32%, #e16462 60%, #8b0aa5 82%, #0d0887 100%)',
    cividis: 'linear-gradient(180deg, #fee838 0%, #b5b932 30%, #6c8f6e 60%, #355f8d 82%, #00204c 100%)',
    jet: 'linear-gradient(180deg, #7f0000 0%, #ff4500 20%, #ffd700 40%, #00bfff 70%, #00007f 100%)',
    gray: 'linear-gradient(180deg, #ffffff 0%, #000000 100%)',
    hot: 'linear-gradient(180deg, #ffffff 0%, #ffff66 30%, #ff5a36 65%, #000000 100%)',
    cool: 'linear-gradient(180deg, #ff00ff 0%, #00ffff 100%)',
    turbo: 'linear-gradient(180deg, #ff6f00 0%, #ffd300 20%, #6dff7a 45%, #00b7ff 72%, #5e00ff 100%)',
    smooth_WAXS_foxtrot: 'linear-gradient(180deg, #ff3300 0%, #ffe600 25%, #33ff33 50%, #1d4ed8 75%, #000000 100%)',
    smooth_WAXS_fit2D: 'linear-gradient(180deg, #ffffff 0%, #ff3300 20%, #ffe600 40%, #33ff33 60%, #2563eb 80%, #000000 100%)',
  }

  return gradients[key] ?? gradients.viridis
}

/** Format a numeric value with an optional unit suffix
 * 格式化数值并附带可选单位后缀 */
export function formatUnit(value: number, unit?: string): string {
  const formatted = Number.isFinite(value)
    ? (Math.abs(value) >= 1000 || (Math.abs(value) < 0.01 && value !== 0)
        ? value.toExponential(3)
        : value.toPrecision(6))
    : String(value)
  return unit ? `${formatted} ${unit}` : formatted
}

/** Build axis title with unit in parentheses
 * 构建带单位的轴标题 */
export function axisTitle(label: string, unit?: string): string {
  return unit ? `${label} (${unit})` : label
}

/** Create Plotly config object for image export (PNG / SVG)
 * 创建用于图像导出的 Plotly 配置对象 */
export function createExportConfig(filename: string = 'chart'): Partial<PlotConfig> {
  return {
    toImageButtonOptions: {
      format: 'png',
      filename,
      width: 1200,
      height: 800,
      scale: 2,
    },
  }
}

/** Merge user layout on top of DARK_THEME
 * 在暗色主题基础上合并用户布局 */
export function mergeDarkLayout(userLayout: Partial<PlotLayout> = {}): Partial<PlotLayout> {
  return {
    ...DARK_THEME,
    ...userLayout,
    xaxis: { ...DARK_THEME.xaxis, ...userLayout.xaxis },
    yaxis: { ...DARK_THEME.yaxis, ...userLayout.yaxis },
    legend: { ...DARK_THEME.legend, ...userLayout.legend },
    margin: { ...DARK_THEME.margin, ...userLayout.margin },
    font: { ...DARK_THEME.font, ...userLayout.font },
  }
}
