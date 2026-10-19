# fz-Tripoli5

[fz](https://github.com/Funz/fz) plugin for [TRIPOLI-5®](https://tripoli5.asnr.dev/documentation/),
the continuous-energy neutron transport Monte Carlo code developed by CEA and ASNR with
the support of EDF.

This plugin runs parametric studies (design of experiments, optimization, uncertainty
propagation) of TRIPOLI-5 simulations: it substitutes variables in a TRIPOLI-5 Python
script, runs one copy of the script per case, and reads keff and the run status from the
log of each case.

It ships no part of TRIPOLI-5. TRIPOLI-5 has to be installed separately, so that its
`tripoli5` Python module can be imported.

## Install

```bash
pip install funz-fz            # fz >= 1.2 (python:// outputs)
fz install model Tripoli5      # into ./.fz/ (add --global for ~/.fz/)
```

This installs the `Tripoli5` model (`.fz/models/Tripoli5.json`), the runner script
(`.fz/calculators/Tripoli5.sh`) and the local calculator alias
(`.fz/calculators/localhost_Tripoli5.json`).

## Input: a TRIPOLI-5 Python script

TRIPOLI-5 is driven through Python only (there is no text input format), so the fz
input is a Python script (`*.py`). It can also be a directory holding the script and the
files it reads.

- Variable syntax: `${name}`, or `${name~default}` (the default is used when the
  variable is not set)
- Formula syntax: `@{expression}`. Inside a formula, a variable is written `$name`.
- Comment character: `#`. Lines starting with `#@` hold Python code available to
  formulas, and Python ignores them.

Excerpt of [`examples/Tripoli5/jezebel.py`](examples/Tripoli5/jezebel.py), adapted from
the Jezebel example of the TRIPOLI-5 user guide:

```python
#@ import math
# Sphere volume (cm3): @{round(4 / 3 * math.pi * $radius**3, 1)}

import tripoli5
...
catalog = tripoli5.delos.Catalog.fromEnvVariable()      # T5_CATALOG_PATH
Pu = (
    tripoli5.materials.MixtureBuilder("concentrations")
    ...
    .add("PU239", ${pu239~0.037047})
    ...
)
sphere = tripoli5.agora.Sphere(Point(0.0, 0.0, 0.0), ${radius~6.39157})
...
param = tripoli5.simulation.SimulationParameters(
    nb_cycles=${nb_cycles~110}, nb_events=${nb_events~10000}, name="Jezebel",
    nb_threads=4, discard=10,
)
...
simu.run()
```

```bash
fzi --input_path jezebel.py --model Tripoli5
# {"nb_cycles": 110, "nb_events": 10000, "pu239": 0.037047, "radius": 6.39157, ...}
```

Caveat: fz treats any `$name` in the script as a variable, including inside strings.
Matplotlib LaTeX labels such as `r"$E$ (MeV)"` would therefore be read as variable `E`.
Keep plotting out of the parameterized script, or write the label without a bare
`$letter`. Python braces (`{}` in dicts and f-strings) are not affected: only `${...}`
and `@{...}` are substituted.

## Outputs

Every TRIPOLI-5 script writes its log to stdout (`[time] [level] message`, spdlog
format). The runner saves this log to `tripoli5.log`, and the model reads the following
outputs from it:

| output | value |
|---|---|
| `t5_status` | `OK`. Otherwise one of `ERROR: <Python exception or crash>`, `NO SIMULATION` (no `simu.run()`), `INCOMPLETE: cycle n of m` or `NO OUTPUT` |
| `keff`, `sigma_keff` | k-effective and its standard deviation: the `kstep_avg = M +/- S` of the last logged cycle. This is the value `simu.getKStep()` returns (mean, √var). If the log has none, it is read from a file written by `kstep.writeToFile(...)` |
| `cycles` | number of cycles (batches) run |
| `kstep` | list of the kstep of each cycle (convergence check) |
| `simulations` | number of simulations the script ran |
| `simulation_time` | wall time of the last simulation (s), taken from the log time stamps |
| `t5_errors` | number of `[error]` lines, e.g. particles killed after a transport exception |
| `t5_warnings` | distinct `[warning]` messages, with their count |
| `results` | content of `tripoli5_results.json` if the script writes it (any JSON value) |

When a script runs several simulations (e.g. surface tracking, then delta tracking),
`keff`, `cycles`, `kstep` and `simulation_time` refer to the **last** one.

Scores (flux, reaction rates, ...) are not written to the log. To return them, have the
script write them to `tripoli5_results.json`, e.g.:

```python
import json
json.dump({"keff": float(k.mean[0]), "flux": flux.mean.ravel().tolist()},
          open("tripoli5_results.json", "w"))
```

Another option is a custom output on a file written by `score.writeToFile(...)`
(whitespace-separated columns `volume_rank group_id E [MT name] mean mean_std`):

```bash
fzo --output_path 'results/*' --model Tripoli5 \
    --output-cmd flux_total="python://float(pd.read_csv('flux.log', sep=r'\s+')['mean'].sum())"
```

## Run

```bash
export T5_CATALOG_PATH=/opt/tripoli-5/delos/nuclide/endfb8r0_mcnp/endfb8r0_mcnp_v2.3.0.yaml
fzr --input_path examples/Tripoli5/jezebel.py --model Tripoli5 \
    --input_variables '{"radius": [6.2, 6.3, 6.4, 6.5]}' --results_dir results
```

```python
import fz
results = fz.fzr("examples/Tripoli5/jezebel.py", {"radius": [6.2, 6.3, 6.4, 6.5]},
                 "Tripoli5", results_dir="results")
print(results[["radius", "t5_status", "keff", "sigma_keff"]])
```

No `--calculators` argument is needed: the `localhost_Tripoli5` alias is found
automatically. With several local cases running in parallel (`FZ_MAX_WORKERS`), keep
`nb_threads` × parallel cases at or below the number of cores.

### Runner environment (`Tripoli5.sh`)

| variable | default | role |
|---|---|---|
| `TRIPOLI5_PYTHON` | `python3` on `PATH` | interpreter that can `import tripoli5` (e.g. the python of a venv or conda env) |
| `TRIPOLI5_LAUNCHER` | none | command prefix, e.g. `mpirun -np 4` or `srun` (MPI builds of TRIPOLI-5) |
| `TRIPOLI5_SCRIPT` | the `.py` importing `tripoli5`, else the first `.py` | script to run when the input holds several `.py` files |
| `T5_CATALOG_PATH` | none | nuclear data catalog, read by `tripoli5.delos.Catalog.fromEnvVariable()` |

Exit codes: 0 normal end, 1 no `.py` script, 2 usage, 4 interpreter or `tripoli5`
module not found, 6 the script failed (Python exception or crash; the cause is printed
on stderr), 7 no simulation run, 8 the last simulation stopped before its last cycle.
fz marks a case with a non-zero exit code as failed.

### Remote execution

Add aliases that use the same runner, e.g. `.fz/calculators/cluster_Tripoli5.json`:

```json
{
    "uri": "slurm://login.cluster:compute",
    "models": {"Tripoli5": "bash .fz/calculators/Tripoli5.sh"}
}
```

The runner and `TRIPOLI5_*` variables must then be valid on the remote host. See the fz
documentation on calculators (`sh://`, `ssh://`, `slurm://`).

## Development

```bash
pip install funz-fz pytest
pytest tests/                       # outputs, runner and fz end-to-end (fake TRIPOLI-5)
python3 tools/make_model.py         # regenerate .fz/models/Tripoli5.json
python3 tools/make_model.py --check # CI: the JSON matches tools/tripoli5_outputs.py
```

The output parsers are written as plain Python in
[`tools/tripoli5_outputs.py`](tools/tripoli5_outputs.py). `tools/make_model.py` embeds
them as `python://` expressions in the model JSON, so do not edit the JSON by hand.

The tests replay TRIPOLI-5 0.3.0 logs taken from the notebooks of the user guide (see
[`tests/fixtures/README.md`](tests/fixtures/README.md)) through a fake interpreter, so
they do not need TRIPOLI-5. Validate with a real installation before relying on a new
TRIPOLI-5 release: the log format is not a documented interface and may change.

## License

BSD 3-Clause (this plugin only). TRIPOLI-5® is distributed separately under its own
license.
