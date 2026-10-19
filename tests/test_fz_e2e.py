"""End-to-end run through fz (fzr) with a fake TRIPOLI-5 interpreter (see conftest.py).

Checks the whole chain: calculator alias discovery (localhost_Tripoli5), the
compiled Python script (variables substituted, formula evaluated), the case
directories named "radius=...", output parsing by the python:// outputs.

Run: pytest tests/test_fz_e2e.py
"""

import shutil
from pathlib import Path

import pytest

fz = pytest.importorskip("fz")
# python:// outputs of the Tripoli5 model need fz >= 1.2
pytest.importorskip("fz.outparsers", reason="fz >= 1.2 required (python:// outputs)")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch, fake_t5):
    shutil.copytree(ROOT / ".fz", tmp_path / ".fz")
    shutil.copy(ROOT / "examples" / "Tripoli5" / "jezebel.py", tmp_path)
    monkeypatch.setenv("FZ_MAX_RETRIES", "1")
    monkeypatch.chdir(tmp_path)
    return tmp_path, fake_t5


@pytest.mark.parametrize("calculators", ["localhost_Tripoli5", None])
def test_fzr(workspace, calculators):
    path, fake_t5 = workspace
    # radius substituted and formula (sphere volume) evaluated, else the fake fails
    fake_t5("jezebel", grep="Sphere(Point(0.0, 0.0, 0.0), 6.5)\n", results='{"leak": 0.1}')
    kwargs = {"calculators": calculators} if calculators else {}
    results = fz.fzr("jezebel.py", {"radius": [6.5]}, "Tripoli5",
                     results_dir=str(path / "results"), **kwargs)
    row = results.iloc[0]
    assert row["status"] == "done", row.to_dict()
    assert row["t5_status"] == "OK"
    assert float(row["keff"]) == pytest.approx(1.00238)
    assert float(row["sigma_keff"]) == pytest.approx(0.00157)
    assert int(row["cycles"]) == 110
    compiled = next((path / "results").rglob("jezebel.py")).read_text()
    assert "# Sphere volume (cm3): 1150.3" in compiled


def test_fzr_failed_case(workspace):
    path, fake_t5 = workspace
    fake_t5("python_error", rc=1)
    results = fz.fzr("jezebel.py", {"radius": [6.0]}, "Tripoli5",
                     calculators="localhost_Tripoli5", results_dir=str(path / "results"))
    row = results.iloc[0]
    assert row["status"] != "done"
    assert row["t5_status"] == "ERROR: RuntimeError: Nuclide PU2390 not found in catalog"
