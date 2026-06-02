declare module 'plotly.js-dist-min' {
  export interface PlotData {
    x?: (number | string)[]
    y?: (number | string)[]
    z?: (number | null)[][]
    name?: string
    type?: string
    mode?: string
    line?: { color?: string; width?: number; dash?: string; shape?: string }
    marker?: { color?: string | number[]; size?: number; symbol?: string; colorscale?: (string | number)[][] | string }
    colorscale?: (string | number)[][] | string
    showscale?: boolean
    colorbar?: Record<string, unknown>
    zmin?: number
    zmax?: number
    zauto?: boolean
    hoverinfo?: string
    hovertemplate?: string
    opacity?: number
    text?: string | string[]
    textposition?: string
    x0?: number
    y0?: number
    dx?: number
    dy?: number
    transpose?: boolean
    [key: string]: unknown
  }

  export interface LayoutAxis {
    title?: { text: string; font?: { color?: string; size?: number } } | string
    titlefont?: { color?: string; size?: number }
    color?: string
    gridcolor?: string
    zerolinecolor?: string
    showgrid?: boolean
    showline?: boolean
    zeroline?: boolean
    range?: (number | string)[]
    autorange?: boolean
    type?: string
    dtick?: number | string
    tick0?: number
    tickmode?: string
    scaleanchor?: string
    scaleratio?: number
    constrain?: string
    constrainrange?: (number | string)[]
    side?: string
    mirror?: boolean | string
    linewidth?: number
    tickfont?: { color?: string; size?: number; family?: string }
    [key: string]: unknown
  }

  export interface LayoutShape {
    type: 'line' | 'rect' | 'circle' | 'path'
    x0?: number | string
    y0?: number | string
    x1?: number | string
    y1?: number | string
    xref?: string
    yref?: string
    line?: { color?: string; width?: number; dash?: string }
    opacity?: number
    [key: string]: unknown
  }

  export interface PlotLayout {
    title?: { text: string; font?: { color?: string; size?: number } } | string
    paper_bgcolor?: string
    plot_bgcolor?: string
    font?: { color?: string; family?: string; size?: number }
    margin?: { t?: number; b?: number; l?: number; r?: number; pad?: number }
    xaxis?: LayoutAxis
    yaxis?: LayoutAxis
    showlegend?: boolean
    legend?: { font?: { color?: string; size?: number }; bgcolor?: string; x?: number; y?: number }
    autosize?: boolean
    width?: number
    height?: number
    shapes?: LayoutShape[]
    dragmode?: string
    hovermode?: string | false
    colorway?: string[]
    [key: string]: unknown
  }

  export interface PlotConfig {
    responsive?: boolean
    scrollZoom?: boolean
    displayModeBar?: boolean | 'hover'
    modeBarButtonsToRemove?: string[]
    displaylogo?: boolean
    toImageButtonOptions?: {
      format?: 'png' | 'svg' | 'jpeg' | 'webp'
      filename?: string
      width?: number
      height?: number
      scale?: number
    }
    staticPlot?: boolean
    doubleClick?: string | false
    [key: string]: unknown
  }

  interface PlotlyAPI {
    newPlot(
      root: HTMLElement | string,
      data: PlotData[],
      layout?: Partial<PlotLayout>,
      config?: Partial<PlotConfig>
    ): Promise<void>
    react(
      root: HTMLElement | string,
      data: PlotData[],
      layout?: Partial<PlotLayout>,
      config?: Partial<PlotConfig>
    ): Promise<void>
    relayout(root: HTMLElement | string, update: Record<string, unknown>): Promise<void>
    restyle(
      root: HTMLElement | string,
      update: Record<string, unknown>,
      traces?: number | number[]
    ): Promise<void>
    purge(root: HTMLElement | string): void
    downloadImage(
      root: HTMLElement | string,
      opts?: {
        format?: 'png' | 'svg' | 'jpeg' | 'webp'
        width?: number
        height?: number
        filename?: string
        scale?: number
        imageData?: string
      }
    ): Promise<void>
    toImage(
      root: HTMLElement | string,
      opts?: {
        format?: 'png' | 'svg' | 'jpeg' | 'webp'
        width?: number
        height?: number
        scale?: number
      }
    ): Promise<string>
    Plots: { resize(root: HTMLElement | string): void }
  }

  const Plotly: PlotlyAPI
  export default Plotly
}
