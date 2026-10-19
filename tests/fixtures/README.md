# Test fixtures

`tripoli5.log` files: TRIPOLI-5 log lines (spdlog format) as `Tripoli5.sh` writes them.

Extracted verbatim from the outputs of the notebooks of the TRIPOLI-5 0.3.0 user guide
(https://tripoli5.asnr.dev/documentation/latest-release/):

| fixture | notebook | content |
|---|---|---|
| `jezebel/` | examples/criticality/Jezebel | criticality, 110 cycles, discard 10; `getKStep()` = 1.002383 ± 0.00156918 |
| `sphere_u235/` | examples/criticality/sphere_u235 | criticality, 100 cycles; `KSTEP statistics : 0.97139 0.00506` |
| `pin_cell/` | examples/criticality/pin_cell | two criticality simulations (surface tracking 1.17550 ± 0.00109, then delta tracking 1.17895) |
| `simulation_features/` | examples/features/simulation | nine simulations (fixed source and criticality), `[error]` lines of killed particles |
| `warnings/` | examples/features/mixtures (the 4 `[warning]` lines) + the jezebel log | warnings |

Built from these logs (not produced by TRIPOLI-5 as such):

| fixture | content |
|---|---|
| `python_error/` | catalog loading then a Python traceback (`RuntimeError`) |
| `interrupted/` | jezebel log cut at cycle 40 of 110, then `Killed` |
| `no_simulation/` | catalog loading only (script without `simu.run()`) |
| `kstep_file/` | jezebel log without `kstep_avg`, plus a `kstep.writeToFile()` file |
