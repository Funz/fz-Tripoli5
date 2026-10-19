"""Fake TRIPOLI-5 interpreter for the tests: replays a fixture log.

The fake replaces TRIPOLI5_PYTHON. Called as ``<fake> -u <script.py>``, it
checks the script, prints FAKE_T5_FIXTURE/tripoli5.log (a real TRIPOLI-5 log,
see tests/fixtures/README.md) and exits with FAKE_T5_RC (default 0).
"""

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

FAKE = r"""#!/bin/bash
[ "$1" = "-u" ] || { echo "expected -u, got: $*" >&2; exit 90; }
script="$2"
[ -f "$script" ] || { echo "python3: can't open file '$script'" >&2; exit 2; }
echo "fake-t5 script=$script args=$#" > fake_call.txt
if [ -n "${FAKE_T5_GREP:-}" ] && ! grep -qF "$FAKE_T5_GREP" "$script"; then
  echo "Traceback (most recent call last):"
  echo "AssertionError: '$FAKE_T5_GREP' not in $script"
  exit 1
fi
cat "$FAKE_T5_FIXTURE/tripoli5.log"
[ -n "${FAKE_T5_RESULTS:-}" ] && echo "$FAKE_T5_RESULTS" > tripoli5_results.json
exit "${FAKE_T5_RC:-0}"
"""

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


@pytest.fixture
def fake_t5(tmp_path, monkeypatch):
    """Install the fake interpreter; returns a function selecting the fixture to replay."""
    fake = tmp_path / "bin" / "fake-python"
    fake.parent.mkdir()
    fake.write_text(FAKE)
    fake.chmod(0o755)
    monkeypatch.setenv("TRIPOLI5_PYTHON", str(fake))
    monkeypatch.delenv("TRIPOLI5_LAUNCHER", raising=False)
    monkeypatch.delenv("TRIPOLI5_SCRIPT", raising=False)

    def use(fixture, rc=0, **env):
        monkeypatch.setenv("FAKE_T5_FIXTURE", str(FIXTURES / fixture))
        monkeypatch.setenv("FAKE_T5_RC", str(rc))
        for key, value in env.items():
            monkeypatch.setenv("FAKE_T5_" + key.upper(), value)
        return fake

    return use
