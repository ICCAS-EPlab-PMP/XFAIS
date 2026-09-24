# Detector calibration workflow (pyFAI-calib2)

Purpose: produce a `.poni` geometry file that the integration views consume.

1. Pick a calibrant standard (e.g. LaB6, CeO2, AgBh for SAXS). Its d-spacings
   are the reference; a wrong calibrant poisons every downstream q value.
2. Enter the exact wavelength (Å) — from the source, not a guess. Cu Kα
   1.541838 Å, Mo Kα 0.7107 Å are the common ones.
3. Give an initial sample–detector distance (mm) close to reality; refinement
   converges from a rough value but fails from a wild one.
4. Peak picking ("massif"): click ~6–8 well-separated rings spread from low
   to high angle. More rings ≠ better if they blur together at high q.
5. Refine iteratively: distance first, then fit (poni1/poni2), then tilts
   (rot1–3) last. Watch the residual χ² drop each pass; stop when it plateaus.
6. Export the `.poni`. Verify by integrating the calibrant image — refined
   peaks must land on the calibrant's nominal q values within ~1e-3 Å⁻¹.
7. Use the PONI in 1D/azimuth/cake integration. Re-calibrate whenever the
   detector, distance, or beamline geometry changes.
