# Conformance reports and recordings (self-issued)

The published reference reports live in
[`MHS/conformance/reports/`](../../../conformance/reports/) (see
[`MHS/conformance/README.md`](../../../conformance/README.md) for the list and
the commands that reproduce them). This directory keeps the two reports that
the reference endpoints cite from here, and the recording the replay endpoint
serves:

| file | subject | claimed / achieved (suite 1.4.1) |
|---|---|---|
| `conformance-arm-2dof-seeded.json` | 2-DOF arm with seeded noise (`--reference arm --noise`) | CL4 / CL4 |
| `conformance-replay-recorded.json` | read-only replay of a recorded conveyor session (`--reference replay --bundle replay-bundle-conveyor.json`) | CL4 / CL2 |
| `replay-bundle-conveyor.json` | recording bundle served by the replay endpoint | — |

Both reports are suite 1.4.1 runs made in-process against fresh reference
endpoints. They carry per-test `required` flags and `spec_ref`,
`subject.manifest_digest` and the disclaimers (`not_certified`,
`not_affiliated`, `simulation_only`, `self_issued`), validate against
`MHS/schema/conformance-report.schema.json`, and their `report_digest` can be
recomputed from the JSON alone (`sha256(JCS(report minus report_digest and
issuer.signature))`). `issuer.kind` is `self`: these are self-issued reference
results, not third-party certification, and MHS remains not a safety-rated
channel (`MHS.SAFETY.NOT_CERTIFIED`).

Regenerate and verify them from the repository root:

```bash
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=MHS/sdk/src
python3 -m mhs.conformance --reference arm --noise --profile MHS-Sim --level CL4 \
  --out MHS/sdk/docs/reports/conformance-arm-2dof-seeded.json
python3 -m mhs.conformance --reference replay --bundle MHS/sdk/docs/reports/replay-bundle-conveyor.json \
  --profile MHS-Sim --level CL4 --out MHS/sdk/docs/reports/conformance-replay-recorded.json   # exits 5: CL2 < CL4
python3 -m mhs.conformance verify MHS/sdk/docs/reports/conformance-arm-2dof-seeded.json --reference arm --noise
python3 -m mhs.conformance verify MHS/sdk/docs/reports/conformance-replay-recorded.json \
  --reference replay --bundle MHS/sdk/docs/reports/replay-bundle-conveyor.json
```

The replay endpoint refuses every command, so `SAFE-014` (required at CL3)
has no limited actuating binding to probe and the report stops at CL2; the
suite 1.1.0 run reported CL1 because `OP-001` was then required without a
probe.

`conformance-conveyor-workcell.json` and `conformance-lab.json` used to sit
here as byte-identical copies of `MHS/conformance/reports/conveyor-cl4.json`
and `lab-cl2.json`. They were moved, unchanged, to
[`_archive/sdk-docs-reports/`](../../../../_archive/sdk-docs-reports/) in
WP-07 milestone 07b, together with the superseded suite 1.1.0 runs of the
other reports.
