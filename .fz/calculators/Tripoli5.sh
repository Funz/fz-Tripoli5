#!/bin/bash
# Tripoli5 calculator script for fz
#
# TRIPOLI-5 has no input file format: a simulation is a Python script using the
# tripoli5 module. This script runs the (compiled) Python script given by fz,
# keeps its log in tripoli5.log and decides success from the exit code and the log.
#
# Environment (all optional):
#   TRIPOLI5_PYTHON    Python interpreter where tripoli5 is importable
#                      (default: python3 on PATH, else python)
#   TRIPOLI5_LAUNCHER  command prefix, e.g. "mpirun -np 4" (MPI builds of TRIPOLI-5)
#                      or "srun"; default: none
#   TRIPOLI5_SCRIPT    script to run when the case holds several .py files
#                      (default: the one importing tripoli5, else the first .py)
#   T5_CATALOG_PATH    nuclear data catalog, read by tripoli5.delos.Catalog.fromEnvVariable()
#
# The script output (stdout and stderr) is written to tripoli5.log, read by the
# Tripoli5 model (keff, cycles, errors...). A script may also write
# tripoli5_results.json (any JSON value), returned as the "results" output.
#
# Exit codes:
#   0 normal end          1 no Python script        2 usage
#   4 interpreter or tripoli5 module not found
#   6 the script failed (Python exception or crash, cause on stderr)
#   7 the script ended without running any simulation
#   8 the last simulation stopped before its last cycle
#   9 the last (criticality) simulation has no keff: no active cycle (discard >= nb_cycles)

if [ $# -eq 0 ]; then
  echo "Usage: $0 <script.py ...|input_directory>" >&2
  exit 2
fi
if [ -d "$1" ]; then
  cd "$1" || exit 1
  set -- *
fi

# Python script to run
SCRIPT="${TRIPOLI5_SCRIPT:-}"
if [ -z "$SCRIPT" ]; then
  for f in "$@"; do
    case "$f" in
      *.py)
        [ -z "$SCRIPT" ] && SCRIPT="$f"
        if grep -qE '^[[:space:]]*(import|from)[[:space:]]+tripoli5' "$f"; then SCRIPT="$f"; break; fi
        ;;
    esac
  done
fi
if [ -z "$SCRIPT" ] || [ ! -f "$SCRIPT" ]; then
  echo "No TRIPOLI-5 Python script (.py) found in: $* (set TRIPOLI5_SCRIPT)" >&2
  exit 1
fi

# Interpreter
if [ -z "${TRIPOLI5_PYTHON:-}" ]; then
  TRIPOLI5_PYTHON="$(command -v python3 || command -v python)"
fi
if [ -z "$TRIPOLI5_PYTHON" ] || { [ ! -x "$TRIPOLI5_PYTHON" ] && ! command -v "$TRIPOLI5_PYTHON" >/dev/null 2>&1; }; then
  echo "Python interpreter not found: ${TRIPOLI5_PYTHON:-python3} (set TRIPOLI5_PYTHON)" >&2
  exit 4
fi

# Previous outputs would be mistaken for the new ones
rm -f tripoli5.log tripoli5_results.json

# -u: Python prints interleaved with the TRIPOLI-5 (C++) log lines
${TRIPOLI5_LAUNCHER:-} "$TRIPOLI5_PYTHON" -u "$SCRIPT" 2>&1 | tee tripoli5.log
RC=${PIPESTATUS[0]}

if grep -qE "No module named '?tripoli5" tripoli5.log; then
  echo "The tripoli5 module is not importable by $TRIPOLI5_PYTHON (set TRIPOLI5_PYTHON, PYTHONPATH or activate the TRIPOLI-5 environment)" >&2
  exit 4
fi
if [ "$RC" -ne 0 ]; then
  echo "TRIPOLI-5 script $SCRIPT failed (exit code $RC):" >&2
  grep -E '^[A-Za-z_][A-Za-z0-9_.]*(Error|Exception)\b' tripoli5.log | tail -1 >&2
  grep -m1 -E 'Segmentation fault|SIGSEGV|Aborted|Killed|core dumped|MPI_ABORT' tripoli5.log >&2
  [ "$RC" -gt 128 ] && echo "killed by signal $((RC - 128))" >&2
  exit 6
fi
if ! grep -qF '*** Beginning of simulation ***' tripoli5.log; then
  echo "TRIPOLI-5 script $SCRIPT ended without running a simulation (no simu.run()?)" >&2
  exit 7
fi
# "Cycle: n of m" of the last simulation
LAST=$(awk '/\*\*\* Beginning of simulation \*\*\*/{c=""} match($0, /Cycle: [0-9]+ of [0-9]+/){c=substr($0, RSTART+7, RLENGTH-7)} END{print c}' tripoli5.log)
if [ -n "$LAST" ]; then
  set -- $LAST
  if [ "$1" -lt "$3" ]; then
    echo "TRIPOLI-5 last simulation stopped at cycle $1 of $3" >&2
    exit 8
  fi
fi
# Criticality simulation without keff: kstep logged but no kstep_avg (all cycles
# discarded, TRIPOLI-5 only warns) and no kstep.writeToFile() result
KSTEPS=$(awk '/\*\*\* Beginning of simulation \*\*\*/{k=0; a=0} /kstep = /{k++} /kstep_avg = /{a++} END{print k+0, a+0}' tripoli5.log)
set -- $KSTEPS
if [ "$1" -gt 0 ] && [ "$2" -eq 0 ] && ! grep -qs '^KSTEP statistics' -- *; then
  echo "TRIPOLI-5 last simulation has no keff (no active cycle):" >&2
  grep -m1 -o 'Number of discarded cycles >= total number of cycles.*' tripoli5.log >&2
  exit 9
fi
exit 0
