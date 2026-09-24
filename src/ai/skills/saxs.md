# SAXS (low-q) 1D integration workflow

- Scope: low-q scattering, typically q ≈ 0.01–0.35 Å⁻¹ (0.1–3.5 nm⁻¹): sizes
  2–60 nm, lamellae, colloids, phase separation. Long distances (~1–10 m).
- Unit: prefer `q_nm^-1` (nm⁻¹ is the community convention for SAXS).
- Resolution: npt 500–800 radial points is enough — SAXS features are broad;
  oversampling only adds noise (600 as default).
- Beamstop is the critical masking step: the direct beam and its shadow
  dominate the low-q signal. Mask generously, then verify the lowest usable q
  bin sits just outside the beamstop edge.
- Background: subtract an empty-cell / solvent measurement (Bg-Subtract view)
  before fitting Guinier/Porod regimes.
- Corrections: keep correct_solid_angle on; at long distances the flat-field
  variation across the detector matters more than at WAXS.
- Sanity checks: Guinier plot (ln I vs q²) should be linear at low q;
  upward curvature there usually means beamstop leakage or aggregation.
- Lamellar long period: hand off the 1D curve to the correlation-function
  (Strobl–Schneider) pipeline in the lamellar view — do not use Bragg spacing.
