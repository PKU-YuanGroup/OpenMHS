# Published reference conformance reports

`reports/<subject>-<level>.json` are self-issued suite runs against the
reference protocol fixtures (`mhs.reference`); the level in the file name is
the report's `level_achieved`. They are suite 1.4.1 runs made in-process, with
a fresh endpoint per test group; each carries per-test `required` flags and
`spec_ref`, `subject.manifest_digest` and the disclaimers (`not_certified`,
`not_affiliated`, `simulation_only`, `self_issued`). They are behavioural test
results, not a safety certification (`MHS.SAFETY.NOT_CERTIFIED`).

| report | subject | claimed / achieved | what caps it |
|---|---|---|---|
| `reports/conveyor-cl4.json` | conveyor workcell, normal profile | CL4 / CL4 | — (the harness injects the `door_closed` interlock; no test hooks) |
| `reports/lab-cl4.json` | lab endpoint (pipette, plate reader, sample mover) | CL4 / CL4 | — (was `lab-cl2.json`, capped by `SAFE-029`, until WP-06 06c fixed the plate reader's `achieved_by`) |
| `reports/arm-cl4.json` | 2-DOF arm, exact determinism | CL4 / CL4 | — (was `arm-cl3.json`, claimed at CL3, until WP-06 06c) |

`MHS/sdk/docs/reports/` holds the seeded-noise arm and replay reports (the
reference endpoints cite them from there).

Reproduce (from the repository root):

```bash
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=MHS/sdk/src
python3 -m mhs.conformance --reference conveyor --profile MHS-Sim --level CL4 --out MHS/conformance/reports/conveyor-cl4.json
python3 -m mhs.conformance --reference lab --profile MHS-Sim --level CL4 --out MHS/conformance/reports/lab-cl4.json
python3 -m mhs.conformance --reference arm --profile MHS-Sim --level CL4 --out MHS/conformance/reports/arm-cl4.json
```

Verify a report by re-running the suite and comparing the verdicts, levels,
test set and manifest digest:

```bash
python3 -m mhs.conformance verify MHS/conformance/reports/conveyor-cl4.json --reference conveyor
python3 -m mhs.conformance verify MHS/conformance/reports/lab-cl4.json --reference lab
python3 -m mhs.conformance verify MHS/conformance/reports/arm-cl4.json --reference arm
```

A report whose level changes is renamed to the new level; whoever cites it by
path (the reference endpoints in `mhs/reference/_common.py`, the site's
reference run) is updated at the same time.
