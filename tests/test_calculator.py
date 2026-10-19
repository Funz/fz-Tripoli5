"""Tripoli5.sh: script selection, exit codes, tripoli5.log (fake interpreter, see conftest.py).

Run: pytest tests/test_calculator.py
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".fz" / "calculators" / "Tripoli5.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def run(case, *args, env=None):
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=case, capture_output=True,
                          text=True, env=env)


@pytest.fixture
def case(tmp_path):
    d = tmp_path / "case"
    d.mkdir()
    shutil.copy(ROOT / "examples" / "Tripoli5" / "jezebel.py", d)
    return d


def test_normal_end(case, fake_t5):
    fake_t5("jezebel", results='{"leak": 1}')
    r = run(case, "jezebel.py")
    assert r.returncode == 0, r.stderr
    log = (case / "tripoli5.log").read_text()
    assert "kstep_avg = 1.00238 +/- 0.00157" in log
    assert "kstep_avg = 1.00238" in r.stdout  # also on stdout, captured by fz in out.txt
    assert (case / "tripoli5_results.json").read_text().strip() == '{"leak": 1}'


def test_script_importing_tripoli5_is_chosen(case, fake_t5):
    fake_t5("jezebel")
    (case / "aaa_helpers.py").write_text("X = 1\n")
    r = run(case, "aaa_helpers.py", "jezebel.py")
    assert r.returncode == 0, r.stderr
    assert "script=jezebel.py" in (case / "fake_call.txt").read_text()


def test_directory_argument_and_tripoli5_script(case, fake_t5, monkeypatch):
    fake_t5("jezebel")
    (case / "main.py").write_text("import tripoli5\n")
    monkeypatch.setenv("TRIPOLI5_SCRIPT", "jezebel.py")
    r = run(case.parent, str(case))
    assert r.returncode == 0, r.stderr
    assert "script=jezebel.py" in (case / "fake_call.txt").read_text()


def test_launcher_prefix(case, fake_t5, monkeypatch):
    fake_t5("jezebel")
    monkeypatch.setenv("TRIPOLI5_LAUNCHER", "env T5_FROM_LAUNCHER=1")
    r = run(case, "jezebel.py")
    assert r.returncode == 0, r.stderr


def test_no_script(case, fake_t5):
    fake_t5("jezebel")
    (case / "data.txt").write_text("x")
    r = run(case, "data.txt")
    assert r.returncode == 1
    assert "No TRIPOLI-5 Python script" in r.stderr


def test_usage():
    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2


def test_interpreter_not_found(case, monkeypatch):
    monkeypatch.setenv("TRIPOLI5_PYTHON", "/nonexistent/python3")
    r = run(case, "jezebel.py")
    assert r.returncode == 4
    assert "TRIPOLI5_PYTHON" in r.stderr


def test_module_not_found(case, monkeypatch):
    """A real interpreter without the tripoli5 module."""
    python = shutil.which("python3") or shutil.which("python")
    if python is None:
        pytest.skip("no python")
    probe = subprocess.run([python, "-c", "import tripoli5"], capture_output=True)
    if probe.returncode == 0:
        pytest.skip("tripoli5 is installed")
    monkeypatch.setenv("TRIPOLI5_PYTHON", python)
    (case / "main.py").write_text("import tripoli5\n")
    r = run(case, "main.py")
    assert r.returncode == 4
    assert "tripoli5 module is not importable" in r.stderr


def test_python_error(case, fake_t5):
    fake_t5("python_error", rc=1)
    r = run(case, "jezebel.py")
    assert r.returncode == 6
    assert "RuntimeError: Nuclide PU2390 not found in catalog" in r.stderr


def test_killed(case, fake_t5):
    fake_t5("interrupted", rc=137)
    r = run(case, "jezebel.py")
    assert r.returncode == 6
    assert "killed by signal 9" in r.stderr


def test_no_simulation(case, fake_t5):
    fake_t5("no_simulation")
    r = run(case, "jezebel.py")
    assert r.returncode == 7


def test_incomplete_last_simulation(case, fake_t5):
    fake_t5("interrupted", rc=0)
    r = run(case, "jezebel.py")
    assert r.returncode == 8
    assert "cycle 40 of 110" in r.stderr


def test_all_cycles_discarded(case, fake_t5):
    fake_t5("all_discarded")
    r = run(case, "jezebel.py")
    assert r.returncode == 9
    assert "Number of discarded cycles >= total number of cycles: 10 >= 5" in r.stderr


def test_keff_from_kstep_file(case, fake_t5):
    """No kstep_avg in the log, but a kstep.writeToFile() result: keff exists."""
    fake_t5("kstep_file")
    shutil.copy(ROOT / "tests" / "fixtures" / "kstep_file" / "kstep-jezebel.log", case)
    r = run(case, "jezebel.py")
    assert r.returncode == 0, r.stderr


def test_several_simulations(case, fake_t5):
    """Cycles are those of the last simulation (simulation_features: 9 runs, last 1 of 1)."""
    fake_t5("simulation_features")
    r = run(case, "jezebel.py")
    assert r.returncode == 0, r.stderr


def test_previous_outputs_removed(case, fake_t5):
    fake_t5("jezebel")
    (case / "tripoli5_results.json").write_text('{"old": true}')
    r = run(case, "jezebel.py")
    assert r.returncode == 0
    assert not (case / "tripoli5_results.json").exists()
