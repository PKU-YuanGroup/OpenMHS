# Tutorial driver package: the TH-1 thermostat (synthetic)

A complete driver package for a made-up thermostat, small enough to read in
one sitting, that passes the acceptance gate. It has the same layout as a
per-repository package in `MHS/drivers/<track>/<owner>__<repo>/`, with one
difference: the TH-1 is not a real product, so there is no upstream
repository. Its `task.json` says `"upstream": null` and its stand-in clone
is `vendor/` inside the package (a manual and an SDK module that the gate
parses but never imports). Real task cards always pin an upstream
repository, commit and licence; `upstream: null` under `MHS/drivers/` fails
gate G2.

## Run the gate

From the repository root:

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/sdk/examples/thermostat --backend fake
```

It prints one line per gate (G1 to G9), ends with `PASS: evidence contract_checked`, exits 0 and writes
`check-report.json` here. A failing gate exits 1 and prints its findings. The command never imports the
package itself: it runs the gates in a child process with the network and device files disabled, and exits 0
only when that process wrote a valid passing report. After editing `driver.py`,
regenerate the reference file (gate G5 compares it):

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver reference MHS/sdk/examples/thermostat
```

Serve the fake backend in-process (mode `simulated`, device `mhs://localhost/tutorial-thermostat/fake`):

```sh
PYTHONPATH=MHS/sdk/src python3 -c "from mhs.adapter import load; print(list(load('MHS/sdk/examples/thermostat').devices))"
```

## Files

| File | Role |
|---|---|
| `task.json` | the (synthetic) task card; input, never edited |
| `driver.py` | the `Thermostat` Driver class: parameters, actions, e-stop, interlock, limits, facts |
| `fake.py` | the fake backend; only methods that `vendor/thermo/controller.py:Controller` has (G7) |
| `native.py` | the hardware backend factory (never imported by the gate) |
| `facts.md` | the facts and limits with their sources |
| `test_driver.py` | `check_driver(HERE)`: the package's own test, run by gate G9 |
| `driver.lock.json` | pinned upstream (`null` here), backends, `authored_by`, `reviewed_by` |
| `reference.json`, `REFERENCE.md` | generated reference file |
| `site-limits.example.json` | an operator overlay: fills `fan_speed`, narrows `setpoint` |
| `RESULT.json` | the outcome recorded after a passing run (`status` `pass` with the report digest); CI re-runs the gate and never trusts it |
| `vendor/` | the synthetic upstream: `MANUAL.md` and the `thermo` SDK |

## What the driver demonstrates

- `@read` parameters (`temperature`, `setpoint`) served by `mhs.resource.read`.
- `@write` parameters with limits that cite their source: `setpoint` 5..80 Cel (`MANUAL.md:9`), the
  per-element array limit of `zone_trim` (front -5..5 K, back -3..3 K, `thermo/controller.py:7`) and
  `fan_speed`, which no source bounds: `Limit.operator_required(...)` refuses it with
  `MHS.SAFETY.LIMITS_UNSET` until an overlay such as `site-limits.example.json` supplies the range.
- A catalogue action (`cap.thermal.setpoint.v1`, method parameters named like the class fields) and an
  extension action (`x-cap.openmhs-tutorial.heater_off.v1`) that is also the safe-state action.
- `@estop` calling the native stop, `estop_physical_ref` citing the hardware switch, and an
  `@interlock` that gates the setpoint action.
