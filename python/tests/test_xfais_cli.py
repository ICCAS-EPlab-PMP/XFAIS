#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_xfais_cli.py — in-process tests for the X-FAIS CLI layer.

test_xfais_cli.py — X-FAIS 命令行层（xfais_cli.py）的进程内测试。

Every case calls ``xfais_cli.main([...])`` in-process and builds its own
synthetic data under pytest's ``tmp_path``, so nothing outside the repository
is required and no file is left behind. The CLI is exercised end to end:
argument parsing, service dispatch, file writing and exit codes.

所有用例都在进程内调用 ``xfais_cli.main([...])``，数据全部在 ``tmp_path``
下现造，不依赖仓库外文件、不残留临时文件，覆盖参数解析、服务分派、落盘与
退出码。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

# The CLI sits next to the services package (BETA/python), exactly like
# service_launcher.py — put that directory on sys.path before importing it.
# CLI 与 services 包同级（BETA/python），与 service_launcher.py 相同的导入前提。
PY_DIR = Path(__file__).resolve().parent.parent
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

import xfais_cli  # noqa: E402  (import order is intentional)

from services.image_loader import ImageLoader  # noqa: E402
from services.lamellar_analysis import analyze_lamellar  # noqa: E402
from services.orientation_analysis import (  # noqa: E402
    fwhm_orientation_index,
    hermans_orientation,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures / 合成数据辅助
# ---------------------------------------------------------------------------


def _write_poni(
    path: Path,
    distance_m: float = 0.2,
    poni1_m: float = 0.05,
    poni2_m: float = 0.05,
    pixel_m: float = 1.0e-4,
    wavelength_m: float = 1.0e-10,
) -> str:
    """Write a minimal but valid pyFAI PONI file. / 写一份最小可用的 PONI 文件。"""
    text = (
        "# Nota: C-Order, 1 refers to the Y axis, 2 to the X axis\n"
        "# xfais-cli synthetic calibration\n"
        "Detector: Detector\n"
        "PixelSize1: {pixel:.6e}\n"
        "PixelSize2: {pixel:.6e}\n"
        "Distance: {distance:.6e}\n"
        "Poni1: {poni1:.6e}\n"
        "Poni2: {poni2:.6e}\n"
        "Rot1: 0.0\n"
        "Rot2: 0.0\n"
        "Rot3: 0.0\n"
        "Wavelength: {wavelength:.6e}\n"
    ).format(
        pixel=pixel_m,
        distance=distance_m,
        poni1=poni1_m,
        poni2=poni2_m,
        wavelength=wavelength_m,
    )
    path.write_text(text, encoding="ascii")
    return str(path)


def _write_image(path: Path, array: np.ndarray) -> str:
    """Write a 2-D array as EDF / TIFF / HDF5. / 写二维数组为 EDF/TIFF/HDF5。"""
    payload = np.asarray(array, dtype=np.float32)
    suffix = path.suffix.lower()
    if suffix == ".edf":
        from fabio.edfimage import EdfImage

        EdfImage(data=payload).write(str(path))
    elif suffix in (".tif", ".tiff"):
        from fabio.tifimage import TifImage

        TifImage(data=payload).write(str(path))
    elif suffix == ".h5":
        import h5py

        with h5py.File(str(path), "w") as handle:
            handle.create_dataset("data", data=payload)
    else:  # pragma: no cover - test-authoring guard
        raise AssertionError("unsupported synthetic image suffix: {}".format(suffix))
    return str(path)


def _read_image(path: Path) -> np.ndarray:
    """Read an image back through the same loader the CLI uses. / 用 CLI 同源加载器回读。"""
    data, _dead, _meta = ImageLoader.load(str(path))
    assert data is not None, "ImageLoader returned no data for {}".format(path)
    return np.asarray(data, dtype=np.float64)


def _run(*args: object) -> int:
    """Invoke the CLI in-process and return its exit status. / 进程内调用并返回退出码。"""
    return int(xfais_cli.main([str(arg) for arg in args]))


def _write_ionchamber(path: Path, intensity: float) -> str:
    """Write a minimal SSRF-style ionchamber file. / 写一份最小 SSRF 风格电离室文件。"""
    text = (
        "# Time  Ionchamber0  Ionchamber1  Ionchamber2\n"
        "2026-01-19 12:34:34.130671238  {v:.6e}  2.0e-08  9.0e-10\n"
        "2026-01-19 12:34:35.230671238  {v:.6e}  2.0e-08  9.0e-10\n"
    ).format(v=intensity)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _steady_image(value: float, size: int = 16) -> np.ndarray:
    """Constant image of the given value. / 给定常数的图像。"""
    return np.full((size, size), value, dtype=np.float32)


def _radial_image(size: int = 64) -> np.ndarray:
    """Smooth radial bump — guarantees non-empty radial bins. / 平滑径向鼓包，避免空 bin。"""
    yy, xx = np.mgrid[0:size, 0:size]
    radius = np.hypot(yy - size / 2.0, xx - size / 2.0)
    return (100.0 * np.exp(-((radius / (size / 5.0)) ** 2)) + 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# version / help / 版本与帮助
# ---------------------------------------------------------------------------


def test_version_prints_runtime_versions(capsys):
    assert _run("version") == 0
    out = capsys.readouterr().out
    assert "xfais-cli" in out
    assert xfais_cli.__version__ in out
    assert "python" in out
    assert "numpy" in out
    assert "pyFAI" in out


def test_version_json_is_machine_readable(capsys):
    assert _run("version", "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cli"] == xfais_cli.__version__
    assert payload["python"].count(".") == 2
    assert isinstance(payload["xfais"], str)
    assert payload["numpy"]


def test_help_lists_every_subcommand(capsys):
    assert _run("--help") == 0
    out = capsys.readouterr().out
    for name in (
        "info",
        "poni",
        "average",
        "integrate",
        "bgsubtract",
        "transmission",
        "lamellar",
        "orientation",
        "version",
    ):
        assert name in out, "subcommand {} missing from --help".format(name)


def test_subcommand_help_is_bilingual_and_lists_options(capsys):
    assert _run("integrate", "--help") == 0
    out = capsys.readouterr().out
    assert "--npt" in out
    assert "--error-model" in out
    assert "--poni" in out
    # Chinese sentence + English sentence / 中文一句 + 英文一句
    assert "积分" in out
    assert "integration" in out.lower()


def test_no_arguments_prints_help_and_fails(capsys):
    assert _run() == 2
    out = capsys.readouterr().out
    assert "COMMAND" in out or "usage" in out.lower()


# ---------------------------------------------------------------------------
# info / 探测
# ---------------------------------------------------------------------------


def test_info_reports_shape_and_statistics(tmp_path, capsys):
    image = np.arange(16 * 16, dtype=np.float32).reshape(16, 16)
    path = _write_image(tmp_path / "scan.edf", image)

    assert _run("info", path) == 0
    out = capsys.readouterr().out
    assert "scan.edf" in out
    assert "16x16" in out
    assert "float32" in out
    assert "min=0" in out
    assert "max=255" in out
    assert "mean=127.5" in out


def test_info_json_matches_numpy(tmp_path, capsys):
    image = np.arange(16 * 16, dtype=np.float32).reshape(16, 16)
    path = _write_image(tmp_path / "scan.edf", image)

    assert _run("info", path, "--json") == 0
    rows = json.loads(capsys.readouterr().out)
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert row["shape"] == [16, 16]
    assert row["dtype"] == "float32"
    assert row["format"] == "EDF"
    assert row["min"] == pytest.approx(0.0)
    assert row["max"] == pytest.approx(255.0)
    assert row["mean"] == pytest.approx(float(np.mean(image)), rel=1e-9)


def test_info_reads_tif_and_h5(tmp_path, capsys):
    image = _radial_image(32)
    edf = _write_image(tmp_path / "a.edf", image)
    tif = _write_image(tmp_path / "b.tif", image)
    h5 = _write_image(tmp_path / "c.h5", image)

    assert _run("info", edf, tif, h5, "--json") == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["format"] for row in rows] == ["EDF", "TIF", "H5"]
    assert rows[2]["h5_dataset"] == "data"
    for row in rows:
        assert row["shape"] == [32, 32]
        assert row["max"] == pytest.approx(float(np.max(image)), rel=1e-6)


def test_info_missing_file_exits_non_zero(tmp_path, capsys):
    assert _run("info", str(tmp_path / "missing.edf")) == 1
    captured = capsys.readouterr()
    assert "error" in captured.err
    assert "missing.edf" in captured.err


# ---------------------------------------------------------------------------
# poni / 几何摘要
# ---------------------------------------------------------------------------


def test_poni_text_summary(tmp_path, capsys):
    poni = _write_poni(tmp_path / "calib.poni")

    assert _run("poni", poni) == 0
    out = capsys.readouterr().out
    assert "200 mm" in out
    assert "50 mm" in out
    assert "0 / 0 / 0 deg" in out
    assert "1 A" in out
    assert "12.3984 keV" in out
    assert "100 x 100 um" in out
    assert "500 x 500 px" in out


def test_poni_json_matches_geometry(tmp_path, capsys):
    poni = _write_poni(tmp_path / "calib.poni")

    assert _run("poni", poni, "--json") == 0
    info = json.loads(capsys.readouterr().out)
    assert info["dist_mm"] == pytest.approx(200.0, rel=1e-9)
    assert info["poni1_mm"] == pytest.approx(50.0, rel=1e-9)
    assert info["poni2_mm"] == pytest.approx(50.0, rel=1e-9)
    assert info["wavelength_A"] == pytest.approx(1.0, rel=1e-9)
    assert info["energy_keV"] == pytest.approx(12.398419843320026, rel=1e-9)
    assert info["pixel1_um"] == pytest.approx(100.0, rel=1e-9)
    assert info["center_x_px"] == pytest.approx(500.0, rel=1e-9)
    assert info["center_y_px"] == pytest.approx(500.0, rel=1e-9)
    assert info["detector"]


def test_poni_missing_file_exits_non_zero(tmp_path, capsys):
    assert _run("poni", str(tmp_path / "nope.poni")) == 1
    assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# average / 平均
# ---------------------------------------------------------------------------


def test_average_mean_and_modes(tmp_path, capsys):
    files = [
        _write_image(tmp_path / "img1.edf", _steady_image(1.0)),
        _write_image(tmp_path / "img2.edf", _steady_image(2.0)),
        _write_image(tmp_path / "img3.edf", _steady_image(3.0)),
    ]

    expectations = {"mean": 2.0, "median": 2.0, "min": 1.0, "max": 3.0, "sum": 6.0}
    for mode, expected in expectations.items():
        target = tmp_path / "out_{}.edf".format(mode)
        assert _run("average", "-o", target, "-m", mode, *files) == 0
        capsys.readouterr()
        values = _read_image(target)
        assert values.shape == (16, 16)
        assert np.allclose(values, expected, atol=1e-5)


def test_average_dark_and_flat(tmp_path, capsys):
    files = [
        _write_image(tmp_path / "s1.edf", _steady_image(10.0)),
        _write_image(tmp_path / "s2.edf", _steady_image(10.0)),
    ]
    dark = _write_image(tmp_path / "dark.edf", _steady_image(4.0))
    flat = _write_image(tmp_path / "flat.edf", _steady_image(2.0))
    target = tmp_path / "corrected.edf"

    assert _run("average", "-o", target, "--dark", dark, "--flat", flat, *files) == 0
    captured = capsys.readouterr()
    assert "2 files" in captured.out
    # (10 - 4) / 2 == 3 / 平均、扣暗场、除平场
    assert np.allclose(_read_image(target), 3.0, atol=1e-5)


def test_average_npy_output_appends_extension(tmp_path, capsys):
    files = [_write_image(tmp_path / "n1.edf", _steady_image(7.0))]
    target = tmp_path / "stack"

    assert _run("average", "-o", target, "-F", "npy", *files) == 0
    capsys.readouterr()
    written = Path(str(target) + ".npy")
    assert written.exists()
    assert np.allclose(np.load(str(written)), 7.0, atol=1e-5)


def test_average_shape_mismatch_fails(tmp_path, capsys):
    a = _write_image(tmp_path / "a.edf", _steady_image(1.0, size=16))
    b = _write_image(tmp_path / "b.edf", _steady_image(1.0, size=8))

    assert _run("average", "-o", str(tmp_path / "o.edf"), a, b) == 1
    assert "shapes differ" in capsys.readouterr().err


def test_average_refuses_to_overwrite_without_flag(tmp_path, capsys):
    files = [_write_image(tmp_path / "o1.edf", _steady_image(1.0))]
    target = tmp_path / "result.edf"

    assert _run("average", "-o", target, *files) == 0
    capsys.readouterr()
    assert _run("average", "-o", target, *files) == 1
    assert "already exists" in capsys.readouterr().err
    assert _run("average", "-o", target, "--overwrite", *files) == 0
    capsys.readouterr()


# ---------------------------------------------------------------------------
# integrate / 积分
# ---------------------------------------------------------------------------


def test_integrate_writes_header_and_two_columns(tmp_path, capsys):
    poni = _write_poni(tmp_path / "calib.poni")
    source = _write_image(tmp_path / "scan.edf", _radial_image(64))
    out_dir = tmp_path / "out"

    assert _run("integrate", "-p", poni, "-n", "256", "--unit", "q_nm^-1", "-o", out_dir, source) == 0
    captured = capsys.readouterr()
    assert "256 points" in captured.out

    target = out_dir / "scan.xy"
    assert target.exists()
    lines = target.read_text(encoding="utf-8").splitlines()
    header = [line for line in lines if line.startswith("#")]
    data = [line for line in lines if line.strip() and not line.startswith("#")]

    assert len(data) == 256
    assert all(len(line.split()) == 2 for line in data)
    joined = "\n".join(header)
    assert "poni:" in joined
    assert "unit: q_nm^-1" in joined
    assert "npt: 256" in joined
    assert "source:" in joined
    assert "scan.edf" in joined


def test_integrate_matches_direct_pyfai_call(tmp_path, capsys):
    poni = _write_poni(tmp_path / "calib.poni")
    source = _write_image(tmp_path / "scan.edf", _radial_image(64))
    out_dir = tmp_path / "out"
    npt = 128

    assert _run("integrate", "-p", poni, "-n", str(npt), "--unit", "q_nm^-1", "-o", out_dir, source) == 0
    capsys.readouterr()

    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    integrator = AzimuthalIntegrator()
    integrator.load(poni)
    expected = integrator.integrate1d(_read_image(Path(source)).astype(np.float32), npt, unit="q_nm^-1")
    parsed = np.loadtxt(str(out_dir / "scan.xy"))

    assert parsed.shape == (npt, 2)
    assert np.allclose(parsed[:, 0], np.asarray(expected[0]), rtol=1e-5, atol=1e-9)
    assert np.allclose(parsed[:, 1], np.asarray(expected[1]), rtol=1e-4, atol=1e-6)


def test_integrate_poisson_error_model_adds_sigma_column(tmp_path, capsys):
    poni = _write_poni(tmp_path / "calib.poni")
    source = _write_image(tmp_path / "scan.edf", _radial_image(64))
    out_dir = tmp_path / "out"

    assert (
        _run(
            "integrate",
            "-p",
            poni,
            "-n",
            "64",
            "--unit",
            "2th_deg",
            "--error-model",
            "poisson",
            "-o",
            out_dir,
            source,
        )
        == 0
    )
    capsys.readouterr()

    parsed = np.loadtxt(str(out_dir / "scan.xy"))
    assert parsed.shape == (64, 3)
    assert np.all(np.asarray(parsed[:, 2]) >= 0.0)


@pytest.mark.parametrize("unit", ["q_nm^-1", "q_A^-1", "2th_deg", "2th_rad", "r_mm"])
def test_integrate_supports_every_unit(tmp_path, capsys, unit):
    poni = _write_poni(tmp_path / "calib.poni")
    source = _write_image(tmp_path / "scan.edf", _radial_image(32))
    out_dir = tmp_path / ("out_" + unit.replace("^", "").replace("-", "m"))

    assert _run("integrate", "-p", poni, "-n", "32", "--unit", unit, "-o", out_dir, source) == 0
    capsys.readouterr()

    parsed = np.loadtxt(str(out_dir / "scan.xy"))
    assert parsed.shape == (32, 2)
    assert np.all(np.diff(np.asarray(parsed[:, 0])) > 0)


def test_integrate_mask_is_forwarded_to_pyfai(tmp_path, capsys):
    """A non-zero mask pixel must reach pyFAI verbatim (masked-out region).

    掩膜必须原样传给 pyFAI：CLI 结果要与直接用同一掩膜调用 integrate1d 完全一致。
    注意 pyFAI 按每个 bin 的有效像素数归一化，所以屏蔽一半图像并不会让强度变小，
    只能拿"同一掩膜的直调结果"来比对。
    """
    poni = _write_poni(tmp_path / "calib.poni")
    image = _radial_image(64)
    source = _write_image(tmp_path / "scan.edf", image)
    mask = np.zeros_like(image, dtype=np.float32)
    mask[:32, :] = 1.0  # non-zero == masked
    mask_path = _write_image(tmp_path / "mask.edf", mask)
    npt = 64

    plain_dir = tmp_path / "plain"
    masked_dir = tmp_path / "masked"
    assert _run("integrate", "-p", poni, "-n", str(npt), "-o", plain_dir, source) == 0
    capsys.readouterr()
    assert _run("integrate", "-p", poni, "-n", str(npt), "--mask", mask_path, "-o", masked_dir, source) == 0
    capsys.readouterr()

    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    integrator = AzimuthalIntegrator()
    integrator.load(poni)
    expected = integrator.integrate1d(
        _read_image(Path(source)).astype(np.float32),
        npt,
        unit="q_nm^-1",
        mask=np.asarray(_read_image(Path(mask_path))) != 0,
    )

    plain = np.loadtxt(str(plain_dir / "scan.xy"))
    masked = np.loadtxt(str(masked_dir / "scan.xy"))
    assert masked.shape == (npt, 2)
    assert np.allclose(masked[:, 1], np.asarray(expected[1]), rtol=1e-4, atol=1e-6)
    # The mask must actually change the profile. / 掩膜必须真的改变结果。
    assert not np.allclose(masked[:, 1], plain[:, 1], rtol=1e-3, atol=1e-6)


def test_integrate_refuses_to_overwrite(tmp_path, capsys):
    poni = _write_poni(tmp_path / "calib.poni")
    source = _write_image(tmp_path / "scan.edf", _radial_image(32))
    out_dir = tmp_path / "out"

    assert _run("integrate", "-p", poni, "-n", "32", "-o", out_dir, source) == 0
    capsys.readouterr()
    assert _run("integrate", "-p", poni, "-n", "32", "-o", out_dir, source) == 1
    assert "already exists" in capsys.readouterr().err
    assert _run("integrate", "-p", poni, "-n", "32", "-o", out_dir, "--overwrite", source) == 0
    capsys.readouterr()


# ---------------------------------------------------------------------------
# bgsubtract / 背景扣除
# ---------------------------------------------------------------------------


def test_bgsubtract_default_transmission_is_one(tmp_path, capsys):
    background = _write_image(tmp_path / "bg.edf", _steady_image(40.0))
    sample = _write_image(tmp_path / "sample.edf", _steady_image(100.0))
    out_dir = tmp_path / "out"

    assert _run("bgsubtract", "-b", background, "-o", out_dir, sample) == 0
    captured = capsys.readouterr()
    assert "T=1 (default)" in captured.out

    written = out_dir / "sample_bgsub.h5"
    assert written.exists()
    assert np.allclose(_read_image(written), 60.0, atol=1e-5)

    import h5py

    with h5py.File(str(written), "r") as handle:
        assert float(handle.attrs["transmission"]) == pytest.approx(1.0)
        assert handle.attrs["transmission_source"] == "default"
        assert handle["data"].dtype == np.float32


def test_bgsubtract_manual_percent(tmp_path, capsys):
    background = _write_image(tmp_path / "bg.edf", _steady_image(40.0))
    sample = _write_image(tmp_path / "sample.edf", _steady_image(100.0))
    out_dir = tmp_path / "out"

    assert _run("bgsubtract", "-b", background, "-T", "50", "-o", out_dir, sample) == 0
    captured = capsys.readouterr()
    assert "T=0.5 (manual)" in captured.out
    # 100 / 0.5 - 40 == 160
    assert np.allclose(_read_image(out_dir / "sample_bgsub.h5"), 160.0, atol=1e-4)


def test_bgsubtract_ionchamber_folder_matching(tmp_path, capsys):
    background = _write_image(tmp_path / "bg_00002.edf", _steady_image(40.0))
    sample = _write_image(tmp_path / "sample_00001.edf", _steady_image(100.0))

    ion_dir = tmp_path / "ion"
    ion_dir.mkdir()
    _write_ionchamber(ion_dir / "bg_00002.Ionchamber", 5.0e-07)
    _write_ionchamber(ion_dir / "sample_00001.Ionchamber", 2.5e-07)

    out_dir = tmp_path / "out"
    assert (
        _run("bgsubtract", "-b", background, "--ion-folder", ion_dir, "-o", out_dir, sample)
        == 0
    )
    captured = capsys.readouterr()
    assert "background ionchamber: bg_00002.Ionchamber" in captured.out
    assert "T=0.5 (ionchamber" in captured.out
    assert "sample_00001.Ionchamber" in captured.out

    written = out_dir / "sample_00001_bgsub.h5"
    # I(2.5e-7) / I_bg(5.0e-7) == 0.5  →  100 / 0.5 - 40 == 160
    assert np.allclose(_read_image(written), 160.0, atol=1e-4)

    import h5py

    with h5py.File(str(written), "r") as handle:
        assert float(handle.attrs["transmission"]) == pytest.approx(0.5)
        assert handle.attrs["transmission_source"] == "ionchamber"


def test_bgsubtract_explicit_bg_ion_file(tmp_path, capsys):
    background = _write_image(tmp_path / "bg_00002.edf", _steady_image(40.0))
    sample = _write_image(tmp_path / "sample_00001.edf", _steady_image(100.0))

    ion_dir = tmp_path / "ion"
    ion_dir.mkdir()
    bg_ion = _write_ionchamber(ion_dir / "bg_00002.Ionchamber", 4.0e-07)
    _write_ionchamber(ion_dir / "sample_00001.Ionchamber", 2.0e-07)

    out_dir = tmp_path / "out"
    assert (
        _run(
            "bgsubtract",
            "-b",
            background,
            "--ion-folder",
            ion_dir,
            "--bg-ion",
            bg_ion,
            "-o",
            out_dir,
            sample,
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "T=0.5 (ionchamber" in captured.out
    assert np.allclose(_read_image(out_dir / "sample_00001_bgsub.h5"), 160.0, atol=1e-4)


def test_bgsubtract_edf_output_format(tmp_path, capsys):
    background = _write_image(tmp_path / "bg.edf", _steady_image(10.0))
    sample = _write_image(tmp_path / "sample.edf", _steady_image(30.0))
    out_dir = tmp_path / "out"

    assert _run("bgsubtract", "-b", background, "-T", "100", "--format", "edf", "-o", out_dir, sample) == 0
    capsys.readouterr()
    written = out_dir / "sample_bgsub.edf"
    assert written.exists()
    assert np.allclose(_read_image(written), 20.0, atol=1e-4)


def test_bgsubtract_requires_background_image(tmp_path, capsys):
    sample = _write_image(tmp_path / "sample.edf", _steady_image(1.0))
    assert _run("bgsubtract", "-o", str(tmp_path / "out"), sample) == 2
    assert "bg" in capsys.readouterr().err


def test_bgsubtract_bg_ion_requires_ion_folder(tmp_path, capsys):
    background = _write_image(tmp_path / "bg.edf", _steady_image(1.0))
    sample = _write_image(tmp_path / "sample.edf", _steady_image(1.0))
    ion = _write_ionchamber(tmp_path / "bg.Ionchamber", 1.0e-07)

    assert (
        _run("bgsubtract", "-b", background, "--bg-ion", ion, "-o", str(tmp_path / "out"), sample)
        == 1
    )
    assert "--ion-folder" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# transmission / 透过率
# ---------------------------------------------------------------------------


def test_transmission_rect_ratio(tmp_path, capsys):
    bright = _write_image(tmp_path / "bright.edf", _steady_image(100.0, size=64))
    dim = _write_image(tmp_path / "dim.edf", _steady_image(50.0, size=64))

    assert _run("transmission", bright, dim, "--region", "rect:10,10,20,20") == 0
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines[0].split()[0] == "file"
    assert lines[1].split()[0] == "bright.edf"
    assert "10000" in lines[1]
    assert "0.5" in lines[2]
    assert "bright.edf" in out.splitlines()[-1]


def test_transmission_json_and_pixel_count(tmp_path, capsys):
    bright = _write_image(tmp_path / "bright.edf", _steady_image(100.0, size=64))
    dim = _write_image(tmp_path / "dim.edf", _steady_image(50.0, size=64))

    assert _run("transmission", bright, dim, "--region", "rect:10,10,20,20", "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 2
    assert payload[0]["transmission"] == pytest.approx(1.0)
    assert payload[1]["transmission"] == pytest.approx(0.5)
    assert payload[0]["pixel_count"] == 100
    assert payload[0]["intensity"] == pytest.approx(10000.0)
    assert payload[1]["intensity"] == pytest.approx(5000.0)


def test_transmission_csv_export_and_last_reference(tmp_path, capsys):
    bright = _write_image(tmp_path / "bright.edf", _steady_image(100.0, size=64))
    dim = _write_image(tmp_path / "dim.edf", _steady_image(50.0, size=64))
    csv_path = tmp_path / "T.csv"

    assert (
        _run(
            "transmission",
            bright,
            dim,
            "--region",
            "rect:10,10,20,20",
            "--reference",
            "last",
            "--csv",
            csv_path,
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "wrote CSV" in captured.err
    assert csv_path.exists()

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        table = list(csv.reader(handle))
    assert table[0] == ["file", "intensity", "transmission"]
    assert table[1][0] == "bright.edf"
    assert float(table[1][2]) == pytest.approx(2.0)
    assert table[2][0] == "dim.edf"
    assert float(table[2][2]) == pytest.approx(1.0)


def test_transmission_explicit_reference_name(tmp_path, capsys):
    bright = _write_image(tmp_path / "bright.edf", _steady_image(100.0, size=64))
    dim = _write_image(tmp_path / "dim.edf", _steady_image(50.0, size=64))

    assert (
        _run("transmission", bright, dim, "--region", "rect:10,10,20,20", "--reference", "dim.edf", "--json")
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload[1]["transmission"] == pytest.approx(1.0)
    assert payload[0]["transmission"] == pytest.approx(2.0)


def test_transmission_bad_region_exits_non_zero(tmp_path, capsys):
    image = _write_image(tmp_path / "a.edf", _steady_image(1.0, size=32))

    assert _run("transmission", image, "--region", "rect:0,0,0,0") == 1
    assert "region" in capsys.readouterr().err.lower()

    assert _run("transmission", image, "--region", "rect:1,2,3") == 1
    assert "4 numbers" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# lamellar / 片晶分析
# ---------------------------------------------------------------------------


def _lamellar_curve(path: Path):
    """Synthetic correlation peak → (q, I) and the written file. / 合成相关峰曲线。"""
    q = np.linspace(0.05, 1.2, 300)
    intensity = 100.0 * (1.0 + np.cos(2.0 * np.pi * q * 10.0)) * np.exp(-((q / 0.9) ** 2)) + 2.0
    np.savetxt(str(path), np.column_stack([q, intensity]), fmt="%.12g")
    return q, intensity


def test_lamellar_json_matches_service(tmp_path, capsys):
    curve_path = tmp_path / "curve.txt"
    q, intensity = _lamellar_curve(curve_path)

    assert _run("lamellar", curve_path, "--json") == 0
    payload = json.loads(capsys.readouterr().out)

    expected = analyze_lamellar(q, intensity)
    assert payload["quality"]["n_points"] == 300
    assert payload["results"] == expected["results"]
    assert payload["results"][0]["method"] == "correlation"
    # --json keeps the intermediate curves / --json 保留中间曲线
    assert len(payload["q_nm"]) == 300
    assert len(payload["gamma_r"]) == len(payload["gamma"])


def test_lamellar_summary_is_compact_and_out_writes_full_report(tmp_path, capsys):
    curve_path = tmp_path / "curve.txt"
    _lamellar_curve(curve_path)
    report_path = tmp_path / "report.json"

    assert _run("lamellar", curve_path, "--out", report_path) == 0
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert "wrote report" in captured.err

    assert "results" in summary
    assert "n_points" not in summary  # quality carries it / 点数在 quality 内
    assert "q_nm" not in summary
    assert "gamma" not in summary

    full = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(full["q_nm"]) == 300
    assert full["results"] == summary["results"]


def test_lamellar_accepts_comma_separated_curve(tmp_path, capsys):
    curve_path = tmp_path / "curve.csv"
    q = np.linspace(0.05, 1.2, 120)
    intensity = 50.0 * (1.0 + np.cos(2.0 * np.pi * q * 9.0)) + 1.0
    with open(curve_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# q,I\n")
        for x, y in zip(q, intensity):
            handle.write("{:.10g},{:.10g}\n".format(x, y))

    assert _run("lamellar", curve_path) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["quality"]["n_points"] == 120


def test_lamellar_rejects_short_curve(tmp_path, capsys):
    curve_path = tmp_path / "tiny.txt"
    curve_path.write_text("1 2\n3 4\n", encoding="utf-8")
    assert _run("lamellar", curve_path) == 1
    assert "at least 3" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# orientation / 取向
# ---------------------------------------------------------------------------


def _orientation_curve(path: Path):
    chi = np.linspace(-90.0, 90.0, 181)
    intensity = 1.0 + 20.0 * np.exp(-(((np.abs(chi) - 45.0) / 12.0) ** 2))
    np.savetxt(str(path), np.column_stack([chi, intensity]), fmt="%.12g")
    return chi, intensity


def test_orientation_both_methods_match_service(tmp_path, capsys):
    curve_path = tmp_path / "chi.txt"
    chi, intensity = _orientation_curve(curve_path)

    assert _run("orientation", curve_path, "--method", "both") == 0
    payload = json.loads(capsys.readouterr().out)

    expected_hermans, _ = hermans_orientation(chi, intensity)
    expected_fwhm, _ = fwhm_orientation_index(chi, intensity)

    assert payload["n_points"] == 181
    assert payload["hermans"]["f"] == pytest.approx(expected_hermans["f"])
    assert payload["hermans"]["cos2_normal"] == pytest.approx(expected_hermans["cos2_normal"])
    assert payload["fwhm"]["f"] == pytest.approx(expected_fwhm["f"])
    assert payload["fwhm"]["fwhm_deg"] == pytest.approx(expected_fwhm["fwhm_deg"])
    assert payload["fwhm"]["peak_chi"] == pytest.approx(45.0)
    # summary mode strips the folded quadrant arrays / 摘要模式剔除折叠曲线
    assert "quadrant_chi" not in payload["hermans"]["meta"]
    assert payload["hermans"]["meta"]["n_points"] == 91


def test_orientation_json_keeps_folded_curve(tmp_path, capsys):
    curve_path = tmp_path / "chi.txt"
    _orientation_curve(curve_path)

    assert _run("orientation", curve_path, "--method", "hermans", "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert "fwhm" not in payload
    assert len(payload["hermans"]["meta"]["quadrant_chi"]) == 91
    assert len(payload["hermans"]["meta"]["quadrant_intensity"]) == 91


def test_orientation_peak_window_option(tmp_path, capsys):
    curve_path = tmp_path / "chi.txt"
    _orientation_curve(curve_path)

    assert _run("orientation", curve_path, "--method", "fwhm", "--peak-window", "30") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fwhm"]["meta"]["peak_window"] == pytest.approx(30.0)
    assert payload["fwhm"]["f"] > 0.5


# ---------------------------------------------------------------------------
# glob expansion / 通配符展开
# ---------------------------------------------------------------------------


def test_glob_pattern_is_expanded_by_the_cli(tmp_path, capsys):
    for index, value in enumerate((1.0, 2.0, 3.0), start=1):
        _write_image(tmp_path / "g{}.edf".format(index), _steady_image(value))
    pattern = str(tmp_path / "g*.edf")

    assert _run("info", pattern) == 0
    out = capsys.readouterr().out
    assert len([line for line in out.splitlines() if line.strip()]) == 3

    target = tmp_path / "glob_mean.edf"
    assert _run("average", "-o", target, pattern) == 0
    capsys.readouterr()
    assert np.allclose(_read_image(target), 2.0, atol=1e-5)


def test_glob_without_matches_exits_non_zero(tmp_path, capsys):
    assert _run("average", "-o", str(tmp_path / "o.edf"), str(tmp_path / "zzz*.edf")) == 1
    assert "no file matches" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Exit codes / 退出码
# ---------------------------------------------------------------------------


def test_unknown_subcommand_exits_two(capsys):
    assert _run("bogus") == 2
    err = capsys.readouterr().err
    assert "error" in err
    assert "bogus" in err


def test_unknown_option_exits_two(capsys):
    assert _run("version", "--bogus") == 2
    assert "error" in capsys.readouterr().err


def test_missing_required_option_exits_two(capsys):
    assert _run("integrate", "whatever.edf") == 2
    assert "--poni" in capsys.readouterr().err


def test_missing_input_file_exits_one(tmp_path, capsys):
    assert _run("average", "-o", str(tmp_path / "o.edf"), str(tmp_path / "nope.edf")) == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err
    assert captured.out == ""


def test_invalid_unit_choice_exits_two(capsys):
    assert _run("integrate", "-p", "x.poni", "--unit", "q_cm^-1", "a.edf") == 2
    assert "invalid choice" in capsys.readouterr().err


def test_main_never_raises_system_exit(capsys):
    """main() must return a status, never propagate SystemExit. / main() 不抛 SystemExit。"""
    for argv in (["--help"], ["version"], ["bogus"], []):
        status = xfais_cli.main(argv)
        assert isinstance(status, int)
        capsys.readouterr()
