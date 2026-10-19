"""Output extraction of the Tripoli5 model, in plain Python (regular expressions).

Each public function takes the case output directory and returns one output
value (None when absent). tools/make_model.py embeds the source of each
function, with the private helpers, in a ``python://`` output of
.fz/models/Tripoli5.json: this module must stay self-contained (standard
library only) and the functions must not use names defined outside them,
except the private helpers and module-level constants below.

TRIPOLI-5 (0.3.0) is driven by a Python script; what it logs (spdlog format,
on stdout) is the only output that exists for every script:

    [2026-06-05 12:58:47.685] [info] *** Beginning of simulation ***
    [2026-06-05 12:58:47.734] [info] Cycle: 1 of 110
    [2026-06-05 12:58:48.290] [info]   kstep = 1.00480   kstep_avg = 1.01375 +/- 0.00895
    [2026-06-05 13:02:30.723] [error] Exception raised during transport. ...
    [2026-01-30 16:45:41.188] [warning] The sum of fractions for mixture ...

The kstep_avg of the last cycle is the k-effective that
``simu.getKStep()`` returns (mean, sqrt(var)); the first ``discard`` cycles
log only kstep. The log is read from tripoli5.log (written by Tripoli5.sh),
else from fz's out.txt. A script may run several simulations: keff, cycles,
kstep and the timings refer to the last one.

Optional files read when present:
- a KSTEP file written by ``kstep.writeToFile(...)`` ("KSTEP statistics :
  <mean> <std>"), used for keff when the log has no kstep_avg;
- tripoli5_results.json, written by the script itself (any JSON value): the
  ``results`` output, to return quantities that are not logged (scores...).
"""

import json
import re
from datetime import datetime
from pathlib import Path

LOGS = ("tripoli5.log", "out.txt")
RESULTS = "tripoli5_results.json"
# "[2026-06-05 12:58:47.685] [info] message"
LINE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d+)?)\] \[(\w+)\] ?(.*)$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
BEGIN = "*** Beginning of simulation ***"
CYCLE = re.compile(r"^Cycle: (\d+) of (\d+)")
KSTEP = re.compile(r"^\s*kstep = (\S+)(?:\s+kstep_avg = (\S+) \+/- (\S+))?")
# "Number of discarded cycles >= total number of cycles: 10 >= 5", logged before the run
DISCARD = re.compile(r"^Number of discarded cycles >= total number of cycles.*$")
KSTEP_FILE = re.compile(r"^KSTEP statistics\s*:\s*(\S+)\s+(\S+)")
# last line of a Python traceback: "RuntimeError: ...", "tripoli5.Error: ..."
EXCEPTION = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Interrupt|Exit)\b:?.*)$")
CRASH = re.compile(r"[Ss]egmentation fault|SIGSEGV|SIGABRT|Aborted|Killed|core dumped"
                   r"|command not found|commande introuvable|MPI_ABORT")


def _text(d):
    """Log text of the case (ANSI colors removed), or None."""
    for name in LOGS:
        path = Path(d) / name
        if path.is_file():
            return ANSI.sub("", path.read_bytes().decode("utf-8", "replace"))
    return None


def _records(d):
    """Log records [(time, level, message)] of the case, or None without log."""
    text = _text(d)
    if text is None:
        return None
    records = []
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            records.append((m.group(1), m.group(2), m.group(3)))
    return records


def _last_simulation(d):
    """Records of the last simulation (from its last BEGIN line), or None."""
    records = _records(d)
    if not records:
        return None
    starts = [i for i, r in enumerate(records) if r[2].strip() == BEGIN]
    return records[starts[-1]:] if starts else None


def _time(stamp):
    """datetime of a log time stamp ("2026-06-05 12:58:47.685")."""
    return datetime.strptime(stamp if "." in stamp else stamp + ".0", "%Y-%m-%d %H:%M:%S.%f")


def _cycles(d):
    """(last cycle started, number of cycles) of the last simulation, or None."""
    sim = _last_simulation(d)
    last = None
    for _, _, message in sim or []:
        m = CYCLE.match(message)
        if m:
            last = (int(m.group(1)), int(m.group(2)))
    return last


def _keff(d):
    """(mean, std) of the k-effective of the last simulation, or None."""
    sim = _last_simulation(d)
    for _, _, message in reversed(sim or []):
        m = KSTEP.match(message)
        if m and m.group(2):
            return float(m.group(2)), float(m.group(3))
    for path in sorted(Path(d).iterdir()):
        if path.is_file() and path.stat().st_size < 4096:
            m = KSTEP_FILE.match(path.read_bytes().decode("utf-8", "replace"))
            if m:
                return float(m.group(1)), float(m.group(2))
    return None


def _exception(d):
    """Last Python exception line ("RuntimeError: ...") after a traceback, or None."""
    text = _text(d) or ""
    err = Path(d) / "err.txt"
    if err.is_file():
        text += "\n" + err.read_bytes().decode("utf-8", "replace")
    found, after = None, False
    for line in text.splitlines():
        if line.startswith("Traceback (most recent call last)"):
            after = True
        elif after and EXCEPTION.match(line):
            found, after = line.strip(), False
    return found


def _crash(d):
    """First line reporting a crash (signal, missing command), or None."""
    for name in LOGS + ("err.txt",):
        path = Path(d) / name
        if path.is_file():
            for line in path.read_bytes().decode("utf-8", "replace").splitlines():
                if CRASH.search(line):
                    return " ".join(line.split())
    return None


def _no_keff(d):
    """Why a criticality simulation (kstep logged) has no keff, or None.

    TRIPOLI-5 logs kstep_avg only for the active cycles: with discard >= nb_cycles
    it only warns and runs every cycle as inactive, so there is no keff."""
    sim = _last_simulation(d)
    if not any(KSTEP.match(r[2]) for r in sim or []) or _keff(d):
        return None
    for _, level, message in reversed(_records(d)):
        if level == "warning" and DISCARD.match(message.strip()):
            return message.strip()
    return "no active cycle (discard >= nb_cycles?)"


def t5_status(d):
    """OK, or why the case has no complete result."""
    records = _records(d)
    if records is None:
        return "NO OUTPUT"
    error = _exception(d) or _crash(d)
    cycles = _cycles(d)
    if error:
        return "ERROR: " + error
    if _last_simulation(d) is None:
        return "NO SIMULATION"
    if cycles and cycles[0] < cycles[1]:
        return "INCOMPLETE: cycle %d of %d" % cycles
    no_keff = _no_keff(d)
    if no_keff:
        return "NO KEFF: " + no_keff
    return "OK"


def keff(d):
    """k-effective (mean of kstep over the active cycles) of the last simulation."""
    k = _keff(d)
    return k[0] if k else None


def sigma_keff(d):
    """Standard deviation of keff."""
    k = _keff(d)
    return k[1] if k else None


def cycles(d):
    """Number of cycles (batches) run by the last simulation."""
    c = _cycles(d)
    return c[0] if c else None


def kstep(d):
    """kstep of each cycle of the last simulation (criticality), as a list."""
    sim = _last_simulation(d)
    values = [float(m.group(1)) for m in (KSTEP.match(r[2]) for r in sim or []) if m]
    return values or None


def simulations(d):
    """Number of simulations run by the script (lines "Beginning of simulation")."""
    records = _records(d)
    if records is None:
        return None
    return sum(1 for r in records if r[2].strip() == BEGIN)


def simulation_time(d):
    """Wall time (s) of the last simulation, from its first to its last log line."""
    sim = _last_simulation(d)
    if not sim:
        return None
    return round((_time(sim[-1][0]) - _time(sim[0][0])).total_seconds(), 3)


def t5_errors(d):
    """Number of [error] log lines (e.g. particles killed after a transport exception)."""
    records = _records(d)
    if records is None:
        return None
    return sum(1 for r in records if r[1] in ("error", "critical"))


def t5_warnings(d):
    """Distinct [warning] messages (first sentence), with their count, or None."""
    counts = {}
    for _, level, message in _records(d) or []:
        if level == "warning":
            key = re.split(r"\.\s+(?=[A-Z])", message.strip(), maxsplit=1)[0].rstrip(".")
            counts[key] = counts.get(key, 0) + 1
    return "; ".join(k + (" (x%d)" % n if n > 1 else "") for k, n in counts.items()) or None


def results(d):
    """Content of tripoli5_results.json, written by the script (any JSON value)."""
    path = Path(d) / RESULTS
    if not path.is_file():
        return None
    return json.loads(path.read_bytes().decode("utf-8"))


OUTPUTS = ["t5_status", "keff", "sigma_keff", "cycles", "kstep", "simulations",
           "simulation_time", "t5_errors", "t5_warnings", "results"]
