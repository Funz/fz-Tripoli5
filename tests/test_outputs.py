"""Output extraction of the Tripoli5 model on TRIPOLI-5 0.3.0 logs (tests/fixtures).

Each output is checked twice: from tools/tripoli5_outputs.py, and through the
python:// expression of .fz/models/Tripoli5.json evaluated by fz (when fz >= 1.2
is installed), so the JSON is what is tested.

Run: pytest tests/test_outputs.py
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "tools"))
import tripoli5_outputs as outputs  # noqa: E402

MODEL = json.loads((ROOT / ".fz" / "models" / "Tripoli5.json").read_text())

EXPECTED = {
    # getKStep() of the notebook: 1.002383 +/- 0.00156918
    "jezebel": {"t5_status": "OK", "keff": 1.00238, "sigma_keff": 0.00157, "cycles": 110,
                "simulations": 1, "simulation_time": 5.132, "t5_errors": 0,
                "t5_warnings": None, "results": None},
    "sphere_u235": {"t5_status": "OK", "keff": 0.97139, "sigma_keff": 0.00506, "cycles": 100,
                    "simulations": 1},
    # the last simulation (delta tracking) is reported
    "pin_cell": {"t5_status": "OK", "keff": 1.17895, "sigma_keff": 0.00114, "cycles": 120,
                 "simulations": 2},
    # last simulation: fixed source, 1 cycle (no keff)
    "simulation_features": {"t5_status": "OK", "keff": None, "sigma_keff": None, "cycles": 1,
                            "kstep": None, "simulations": 9, "t5_errors": 8},
    "warnings": {"t5_status": "OK", "keff": 1.00238,
                 "t5_warnings": "The sum of fractions for mixture WATER differs from 1.0 by more "
                                "than 1e-10 (x2); The sum of fractions for mixture Water differs "
                                "from 1.0 by more than 1e-10; The sum of fractions for mixture "
                                "Fuel differs from 1.0 by more than 1e-10"},
    "python_error": {"t5_status": "ERROR: RuntimeError: Nuclide PU2390 not found in catalog",
                     "keff": None, "cycles": None, "simulations": 0},
    # partial estimate up to the last complete cycle (t5_status tells it is not final)
    "interrupted": {"t5_status": "ERROR: Killed", "keff": 1.00227, "sigma_keff": 0.00255,
                    "cycles": 40},
    "no_simulation": {"t5_status": "NO SIMULATION", "keff": None, "simulations": 0},
    "kstep_file": {"t5_status": "OK", "keff": 1.00238, "sigma_keff": 0.00157},
}


def _fz_eval(name, case_dir):
    outparsers = pytest.importorskip("fz.outparsers")
    return outparsers.evaluate_python_output(MODEL["output"][name], case_dir)


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_outputs(case):
    d = FIXTURES / case
    for name, value in EXPECTED[case].items():
        assert getattr(outputs, name)(d) == value, name


def test_kstep_series():
    values = outputs.kstep(FIXTURES / "jezebel")
    assert len(values) == 110
    assert values[0] == 1.39060 and values[-1] == 1.01120


def test_no_output(tmp_path):
    assert outputs.t5_status(tmp_path) == "NO OUTPUT"
    assert all(getattr(outputs, n)(tmp_path) is None for n in outputs.OUTPUTS if n != "t5_status")


def test_out_txt_fallback_and_results(tmp_path):
    """Without tripoli5.log (another calculator command), fz's out.txt is read."""
    shutil.copy(FIXTURES / "jezebel" / "tripoli5.log", tmp_path / "out.txt")
    (tmp_path / "tripoli5_results.json").write_text('{"leakage": 0.42}')
    assert outputs.keff(tmp_path) == 1.00238
    assert outputs.results(tmp_path) == {"leakage": 0.42}


def test_ansi_colors(tmp_path):
    text = (FIXTURES / "jezebel" / "tripoli5.log").read_text()
    (tmp_path / "tripoli5.log").write_text(text.replace("[info]", "[\x1b[32minfo\x1b[m]"))
    assert outputs.keff(tmp_path) == 1.00238


def test_model_matches_outputs():
    assert list(MODEL["output"]) == outputs.OUTPUTS
    assert MODEL["id"] == "Tripoli5" and MODEL["commentline"] == "#"


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_model_json_through_fz(case):
    d = FIXTURES / case
    for name, value in EXPECTED[case].items():
        assert _fz_eval(name, d) == value, name
