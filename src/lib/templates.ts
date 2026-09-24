/**
 * templates.ts — Standard integration templates for the 1D integration view.
 *
 * A template is a curated `advanced` parameter block the AI assistant (or a
 * user) can apply in one shot; Integrate1dView consumes the CustomEvent detail
 * produced by `templateDetail()` (`xfaos:ai-apply-template`).
 */

export interface IntegrateTemplate {
  key: 'waxs' | 'saxs'
  advanced: {
    nptRad: number
    /** Base unit; the AI unit decision may override to 2th_deg (Cu WAXS). */
    unit: 'q_A' | 'q_nm' | '2th_deg'
    radialMin: number | null
    radialMax: number | null
    algorithm: 'splitpixel'
    dropEmptyBins: boolean
    correctSolidAngle: true
    nptAzim: number
  }
  maskHint: string
  zh: string
  en: string
}

/** WAXS: wide-angle, q in Å⁻¹, fine radial sampling for narrow peaks. */
export const WAXS_TEMPLATE: IntegrateTemplate = {
  key: 'waxs',
  advanced: {
    nptRad: 1800,
    unit: 'q_A',
    radialMin: null,
    radialMax: null,
    algorithm: 'splitpixel',
    dropEmptyBins: true,
    correctSolidAngle: true,
    nptAzim: 360,
  },
  maskHint: 'Mask beamstop shadow + detector gaps; peaks are narrow — keep npt high. / 掩膜挡光阴影与探测死区。',
  zh: '广角（WAXS）常规模板',
  en: 'WAXS standard template',
}

/** SAXS: low-q, q in nm⁻¹, moderate sampling for broad features. */
export const SAXS_TEMPLATE: IntegrateTemplate = {
  key: 'saxs',
  advanced: {
    nptRad: 600,
    unit: 'q_nm',
    radialMin: null,
    radialMax: null,
    algorithm: 'splitpixel',
    dropEmptyBins: true,
    correctSolidAngle: true,
    nptAzim: 360,
  },
  maskHint: 'Mask the beamstop generously — low-q leakage ruins Guinier fits. / 务必充分遮挡直通光束。',
  zh: '小角（SAXS）常规模板',
  en: 'SAXS standard template',
}

/** Registry keyed by template name used across the AI layer. */
export const INTEGRATE_TEMPLATES: Record<'waxs' | 'saxs', IntegrateTemplate> = {
  waxs: WAXS_TEMPLATE,
  saxs: SAXS_TEMPLATE,
}

/**
 * Build the `xfaos:ai-apply-template` CustomEvent detail payload for the
 * given template (consumed by Integrate1dView). `unitOverride` carries the
 * template+unit judgement's radial unit (Cu-target WAXS → 2th_deg); radial
 * bounds stay null so unit-dependent stale ranges can never survive.
 * 构建事件载荷；`unitOverride` 携带模板+单位联合判定的积分轴（铜靶 WAXS →
 * 2th_deg）；径向范围保持 null，避免跨单位残留旧范围。
 */
export function templateDetail(
  t: IntegrateTemplate,
  unitOverride?: 'q_A' | 'q_nm' | '2th_deg'
): {
  template: 'waxs' | 'saxs'
  advanced: IntegrateTemplate['advanced']
  maskHint: string
  zh: string
  en: string
} {
  return {
    template: t.key,
    advanced: {
      ...t.advanced,
      ...(unitOverride ? { unit: unitOverride, radialMin: null, radialMax: null } : {}),
    },
    maskHint: t.maskHint,
    zh: t.zh,
    en: t.en,
  }
}
