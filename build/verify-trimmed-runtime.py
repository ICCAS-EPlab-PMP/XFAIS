"""
B4 verification: prove the TRIMMED packaged Python runtime still works.
Run with the PACKAGED python.exe + PACKAGED site-packages (trimmed by afterPack).

Checks:
  1. Every kept third-party package imports.
  2. The backend entrypoint (service_launcher) imports — exercises the full
     real import closure of the shipped app.
  3. A REAL pyFAI integrate1d runs on a synthetic image + geometry and returns
     the expected output shape (end-to-end scientific stack).
"""
import sys
import os

# Point at the PACKAGED python source so `import service_launcher` resolves.
# This script lives in BETA/build/, so the project root is one level up.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG_PYTHON = os.path.normpath(
    os.path.join(
        ROOT,
        "dist-electron-builder", "win-unpacked", "resources", "python",
    )
)
sys.path.insert(0, PKG_PYTHON)

failures = []

def check(label, fn):
    try:
        fn()
        print(f"  OK   {label}")
    except Exception as e:  # noqa: BLE001
        failures.append(f"{label}: {type(e).__name__}: {e}")
        print(f"  FAIL {label}: {type(e).__name__}: {e}")


print("[1] Importing every kept third-party package from the TRIMMED runtime:")
for mod in [
    "numpy", "scipy", "pandas", "matplotlib", "PIL",
    "h5py", "hdf5plugin", "pyarrow", "lxml",
    "silx", "fabio", "pyFAI",
]:
    check(f"import {mod}", lambda m=mod: __import__(m))

print()
print("[2] Import backend entrypoint (full real import closure):")
check("import service_launcher", lambda: __import__("service_launcher"))
check("from services import integrator", lambda: __import__("services.integrator", fromlist=["integrator"]))
check("from services import image_loader", lambda: __import__("services.image_loader", fromlist=["image_loader"]))

print()
print("[3] REAL pyFAI integrate1d on synthetic image + geometry:")
def real_integrate():
    import numpy as np
    from pyFAI import AzimuthalIntegrator

    # Synthetic 2D detector image with a Debye-Scherrer ring.
    H = W = 256
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W / 2.0, H / 2.0
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    img = np.exp(-((r - 60.0) ** 2) / (2 * 4.0 ** 2)) * 1000.0

    ai = AzimuthalIntegrator(
        dist=0.1, pixel1=1e-4, pixel2=1e-4,
        poni1=cy * 1e-4, poni2=cx * 1e-4, wavelength=1e-10,
    )
    q, I = ai.integrate1d(img, npt=200, unit="q_A^-1")
    assert q.shape == (200,), f"unexpected q shape {q.shape}"
    assert I.shape == (200,), f"unexpected I shape {I.shape}"
    assert np.isfinite(I).all(), "non-finite intensity values"
    assert I.max() > 0, "integration returned all-zero intensity"
    print(f"      -> integrate1d OK: q in [{q.min():.3g}, {q.max():.3g}], I_max={I.max():.1f}")
check("pyFAI integrate1d", real_integrate)

print()
if failures:
    print(f"=== VERIFICATION FAILED ({len(failures)} problem(s)) ===")
    for f in failures:
        print("  -", f)
    sys.exit(1)
else:
    print("=== VERIFICATION PASSED: trimmed runtime is healthy ===")
