# WAXS (wide-angle) 1D integration workflow

- Scope: wide-angle scattering, typically q ≈ 0.5–5 Å⁻¹ (crystalline peaks,
  chain packing). Sample–detector distances are short (~30–300 mm).
- Geometry: use a calibrated PONI (from pyFAI-calib2). Verify distance and
  wavelength before trusting peak positions.
- Integration settings that work for most WAXS patterns:
  - unit `q_A^-1` (Å⁻¹) so peaks line up with literature values;
  - npt 1500–2000 radial points (WAXS peaks are narrow; keep 1800 as default);
  - npt_azim 360 (full ring) unless an oriented sample needs sectors;
  - algorithm `splitpixel`, correct_solid_angle on, drop empty bins on.
- q range: leave auto (full detector) first; narrow afterwards around the
  amorphous halo + crystal peaks once the curve looks sane.
- Masking: beamstop shadow and detector gaps/dead pixels must be masked or the
  low-q end will show artifacts. A prepared .mask file can be reloaded.
- Batch: identical settings across a series (temperature/ramp) — compare peak
  positions (unit q) rather than raw pixel radii.
- Sanity checks: peak positions in q should not shift when the sample is
  moved on the beam; a shift means geometry (PONI) changed.
