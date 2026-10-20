/**
 * PeakWorkbench 谱峰工作台 — function registry (SHARED CONTRACT, read-only for agents).
 *
 * Metadata only: parameter keys, counts, labels, bounds and UI grouping.
 * The actual formulas live in `src/core/models.ts` and MUST be implemented
 * per the official the legacy reference application manual chapter 7 (see
 * `the reference manual chapter 7 text`, authoritative source).
 *
 * Conventions (matching original the reference application):
 * - Peak parameters are named a0, a1, a2, ... in the order the manual lists them:
 *   a0 = amplitude, a1 = center/position, a2 = width, a3/a4 = shape/skew/tails.
 * - Baseline parameters are named b0, b1, ...
 * - Width semantics differ per function (sigma for GAUSS, HWHM for LORENTZ, FWHM
 *   for PEARSON7, ...) — see `notes`; the fitting core reports a numeric FWHM
 *   and area for every peak regardless of parameterization.
 * - Width lower bound 1e-12 replicates the original GAUSS implementation.
 */

export type PeakFamily = 'basic' | 'chromatography' | 'statistics' | 'shape'

export type PeakFnId =
  // basic (spectroscopy workhorses)
  | 'gauss'
  | 'lorentz'
  | 'pearson7'
  | 'voigt'
  | 'glorsum'
  // chromatography (elution/kinetic shapes)
  | 'emg'
  | 'gmg'
  | 'hvl'
  | 'giddings'
  | 'nlc'
  // statistics family
  | 'lognorm'
  | 'lognorm4'
  | 'extrval'
  | 'extrval4'
  | 'logistic'
  | 'gamma'
  | 'weibull'
  | 'beta'
  | 'invgamma'
  | 'chisq'
  | 'laplace'
  | 'error'
  | 'student'
  // shape family
  | 'erfcpk'

export type BaselineFnId =
  | 'none'
  | 'bgconst'
  | 'bglin'
  | 'bgquad'
  | 'bgcub'
  | 'bgexp'
  | 'bgpow'
  | 'bglog'
  | 'bghyp'
  | 'bgsine'

/** Initial-value hint for UI: fixed number, click coordinates, or data-derived width. */
export type ParamInit = number | 'clickX' | 'clickY' | 'autoWidth'

export interface ParamMeta {
  key: string
  label: string
  /** Lower bound, or null for unbounded. */
  min: number | null
  /** Upper bound, or null for unbounded. */
  max: number | null
  init: ParamInit
}

export interface PeakFnMeta {
  id: PeakFnId
  /** Original the reference application function name (manual ch7). */
  name: string
  /** Short display label. */
  label: string
  family: PeakFamily
  params: ParamMeta[]
  /** Width semantics + formula summary; core must verify against manual. */
  notes: string
}

export interface BaselineFnMeta {
  id: BaselineFnId
  name: string
  label: string
  params: ParamMeta[]
  notes: string
}

const W_MIN = 1e-12

const amp = (initFactor = 1): ParamMeta => ({ key: 'a0', label: 'Amplitude', min: null, max: null, init: initFactor === 1 ? 'clickY' : initFactor })
const ctr = (): ParamMeta => ({ key: 'a1', label: 'Center', min: null, max: null, init: 'clickX' })
const wid = (): ParamMeta => ({ key: 'a2', label: 'Width', min: W_MIN, max: null, init: 'autoWidth' })

export const PEAK_FNS: PeakFnMeta[] = [
  {
    id: 'gauss', name: 'GAUSS', label: 'Gaussian', family: 'basic',
    params: [amp(), ctr(), wid()],
    notes: 'y = a0*exp(-0.5*((x-a1)/a2)^2); a2 = sigma (stddev). Core @0x4a02ac verified.'
  },
  {
    id: 'lorentz', name: 'LORENTZ', label: 'Lorentzian', family: 'basic',
    params: [amp(), ctr(), wid()],
    notes: 'y = a0/(1+((x-a1)/a2)^2); a2 = HWHM (half width at half max). Core @0x4a0c70 verified.'
  },
  {
    id: 'pearson7', name: 'PEARSON7', label: 'Pearson VII', family: 'basic',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Shape m', min: 0.5, max: null, init: 1.5 }],
    notes: 'a2 = FWHM; a3 = m (m=1 Lorentzian, m->inf Gaussian). Verify exponent vs manual.'
  },
  {
    id: 'voigt', name: 'VOIGTGL', label: 'Voigt (G/L widths)', family: 'basic',
    params: [amp(), ctr(), { ...wid(), label: 'Gauss sigma' }, { key: 'a3', label: 'Lorentz HWHM', min: W_MIN, max: null, init: 'autoWidth' }],
    notes: 'True Voigt via Faddeeva w(z); a2 = Gaussian sigma, a3 = Lorentzian HWHM.'
  },
  {
    id: 'glorsum', name: 'GLORSUM', label: 'Gauss+Lorentz Sum', family: 'basic',
    params: [amp(), ctr(), { ...wid(), label: 'FWHM' }, { key: 'a3', label: 'Gauss fraction', min: 0, max: 1, init: 0.5 }],
    notes: 'Additive Gaussian + Lorentzian sharing center; a2 = common FWHM, a3 = Gaussian mixing fraction in [0,1] (manual p.220).'
  },
  {
    id: 'emg', name: 'EMG', label: 'Exp. Modified Gaussian', family: 'chromatography',
    params: [amp(), ctr(), { ...wid(), label: 'Gauss sigma' }, { key: 'a3', label: 'Tau (skew)', min: W_MIN, max: null, init: 'autoWidth' }],
    notes: 'Gauss convolved with exp tail, needs erfc/erfcx for numerical stability.'
  },
  {
    id: 'gmg', name: 'GMG', label: 'Gamma Modified Gaussian', family: 'chromatography',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Tau (skew)', min: W_MIN, max: null, init: 'autoWidth' }],
    notes: 'Manual GMG formula; mind domain clipping near singularity.'
  },
  {
    id: 'hvl', name: 'HVL', label: 'Haarhoff-Van der Linde', family: 'chromatography',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Skew', min: null, max: null, init: 0.1 }],
    notes: 'a0 is area-like for HVL per manual; verify parameterization.'
  },
  {
    id: 'giddings', name: 'GIDDING', label: 'Giddings', family: 'chromatography',
    params: [amp(), ctr(), wid()],
    notes: 'Chromatographic Giddings shape, 3 params (manual GIDDING).'
  },
  {
    id: 'nlc', name: 'NLC', label: 'Nonlinear LC', family: 'chromatography',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Skew', min: null, max: null, init: 0.1 }],
    notes: 'NLC model, 4 params (manual NLC).'
  },
  {
    id: 'lognorm', name: 'LOGNORM', label: 'LogNormal', family: 'statistics',
    params: [amp(), ctr(), wid()],
    notes: 'Asymmetric lognormal, 3-param form (manual LOGNORM).'
  },
  {
    id: 'lognorm4', name: 'LOGNORM4', label: 'LogNormal 4P', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Asymmetry', min: W_MIN, max: null, init: 1 }],
    notes: '4-parameter lognormal with independent asymmetry (manual LOGNORM4).'
  },
  {
    id: 'extrval', name: 'EXTRVAL', label: 'Extreme Value', family: 'statistics',
    params: [amp(), ctr(), wid()],
    notes: 'Gumbel-type extreme value peak, 3 params (manual EXTRVAL).'
  },
  {
    id: 'extrval4', name: 'EXTRVAL4', label: 'Extreme Value 4P', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Tail', min: W_MIN, max: null, init: 1 }],
    notes: '4-parameter extreme value (manual EXTRVAL4).'
  },
  {
    id: 'logistic', name: 'LOGISTIC', label: 'Logistic', family: 'statistics',
    params: [amp(), ctr(), wid()],
    notes: '3-param logistic peak (manual LOGISTIC).'
  },
  {
    id: 'gamma', name: 'GAMMA', label: 'Gamma', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Shape k', min: 0.05, max: null, init: 2 }],
    notes: 'Gamma density peak, needs lngamma/incomplete gamma (manual GAMMA).'
  },
  {
    id: 'weibull', name: 'WEIBULL', label: 'Weibull', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Shape k', min: 0.05, max: null, init: 2 }],
    notes: 'Weibull peak (manual WEIBULL).'
  },
  {
    id: 'beta', name: 'BETA', label: 'Beta', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Alpha', min: 0.05, max: null, init: 2 }, { key: 'a4', label: 'Beta', min: 0.05, max: null, init: 2 }],
    notes: 'Beta density peak, needs beta/incomplete beta (manual BETA).'
  },
  {
    id: 'invgamma', name: 'IGAMMA', label: 'Inverse Gamma', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Shape', min: 0.05, max: null, init: 2 }],
    notes: 'Inverse gamma peak (manual IGAMMA).'
  },
  {
    id: 'chisq', name: 'CHISQ', label: 'Chi-Squared', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Shape (df/2)', min: 2.05, max: 335, init: 2.5 }],
    notes: 'y = a0*z^(a3/2-1)*exp(-z/2)/norm with z=(x-a1)/a2+(a3-2); manual range 2.01 < a3 < 335.84 (core also handles the k->2 limit).'
  },
  {
    id: 'laplace', name: 'LAPLACE', label: 'Laplace', family: 'statistics',
    params: [amp(), ctr(), wid()],
    notes: 'Two-sided exponential peak; width semantics per manual LAPLACE.'
  },
  {
    id: 'error', name: 'ERROR', label: 'Generalized Error', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'Shape (2/a3 power)', min: 0.05, max: null, init: 1 }],
    notes: 'Generalized error distribution y = a0*exp(-0.5*|z|^(2/a3)), z=(x-a1)/a2 (manual p.256); a3=1 Laplace-like, a3=2 Gaussian-like.'
  },
  {
    id: 'student', name: 'STUDENT', label: 'Student t', family: 'statistics',
    params: [amp(), ctr(), wid(), { key: 'a3', label: 'df', min: 0.1, max: null, init: 5 }],
    notes: 'Student-t density peak (manual STUDENT).'
  },
  {
    id: 'erfcpk', name: 'ERFCPK', label: 'Erfc Peak', family: 'shape',
    params: [amp(), ctr(), wid()],
    notes: 'y = a0*0.5*erfc((x-a1)/a2) style tail peak (manual ERFCPK).'
  }
]

export const BASELINE_FNS: BaselineFnMeta[] = [
  { id: 'none', name: 'NONE', label: 'None', params: [], notes: 'No baseline.' },
  { id: 'bgconst', name: 'BGCNST', label: 'Constant', params: [{ key: 'b0', label: 'Offset', min: null, max: null, init: 'clickY' }], notes: 'y = b0' },
  { id: 'bglin', name: 'BGLIN', label: 'Linear', params: [{ key: 'b0', label: 'Intercept', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'Slope', min: null, max: null, init: 0 }], notes: 'y = b0 + b1*x' },
  { id: 'bgquad', name: 'BGQUAD', label: 'Quadratic', params: [{ key: 'b0', label: 'c0', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'c1', min: null, max: null, init: 0 }, { key: 'b2', label: 'c2', min: null, max: null, init: 0 }], notes: 'y = b0 + b1*x + b2*x^2' },
  { id: 'bgcub', name: 'BGCUB', label: 'Cubic', params: [{ key: 'b0', label: 'c0', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'c1', min: null, max: null, init: 0 }, { key: 'b2', label: 'c2', min: null, max: null, init: 0 }, { key: 'b3', label: 'c3', min: null, max: null, init: 0 }], notes: 'y = b0 + b1*x + b2*x^2 + b3*x^3' },
  { id: 'bgexp', name: 'BGEXP', label: 'Exponential', params: [{ key: 'b0', label: 'Amplitude', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'Decay', min: null, max: null, init: -0.1 }, { key: 'b2', label: 'Offset', min: null, max: null, init: 0 }], notes: 'Exponential background (manual BGEXP).'
  },
  { id: 'bgpow', name: 'BGPOW', label: 'Power', params: [{ key: 'b0', label: 'Amplitude', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'Exponent', min: null, max: null, init: 1 }, { key: 'b2', label: 'Offset', min: null, max: null, init: 0 }], notes: 'Power-law background (manual BGPOW).' },
  { id: 'bglog', name: 'BGLOG', label: 'Logarithmic', params: [{ key: 'b0', label: 'Amplitude', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'Offset', min: null, max: null, init: 0 }], notes: 'Log background (manual BGLOG).' },
  { id: 'bghyp', name: 'BGHYP', label: 'Hyperbolic', params: [{ key: 'b0', label: 'Amplitude', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'Scale', min: W_MIN, max: null, init: 'autoWidth' }, { key: 'b2', label: 'Offset', min: null, max: null, init: 0 }], notes: 'Hyperbolic background (manual BGHYP).' },
  { id: 'bgsine', name: 'SINE (bg)', label: 'Sine', params: [{ key: 'b0', label: 'Amplitude', min: null, max: null, init: 'clickY' }, { key: 'b1', label: 'Period', min: W_MIN, max: null, init: 'autoWidth' }, { key: 'b2', label: 'Phase', min: null, max: null, init: 0 }], notes: 'Sinusoidal background for ripple (manual SINE).' }
]

export const PEAK_FN_MAP: ReadonlyMap<string, PeakFnMeta> = new Map(PEAK_FNS.map((f) => [f.id, f]))
export const BASELINE_FN_MAP: ReadonlyMap<string, BaselineFnMeta> = new Map(BASELINE_FNS.map((f) => [f.id, f]))

export const DEFAULT_PEAK_FN: PeakFnId = 'gauss'
export const DEFAULT_BASELINE_FN: BaselineFnId = 'bglin'

export const FAMILY_LABELS: Record<PeakFamily, string> = {
  basic: 'Basic (spectroscopy)',
  chromatography: 'Chromatography',
  statistics: 'Statistics',
  shape: 'Shape'
}
