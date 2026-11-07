OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# SIMULATION-TIMING — opt-in physics accounting for fixed-decimation Gym environments

The old Gym bridge counted one native environment call as one tick, even when
that call advanced several physics timesteps. An optional backend timing
declaration now publishes separate physics/control periods, requires whole
control periods in the input, measures actual clock deltas and carries truthful
per-command timing through the stock server's receipts and reconciliation path.
The API and restrictions are documented in `MHS/sdk/docs/simulation-timing.md`.

Independent review of the first implementation found three defects: reset
advancement could disappear from the receipt, an invalid observation could be
overwritten by a later native call, and accumulated floating-clock error could
incorrectly fault a valid simulation. The second implementation fixes them and
retains the failing probes and original version as evidence.

The final isolated regression passed 140 tests (38 new timing cases and 102
existing cases). An independent reviewer reran all seven stock-server failure
probes and the 38 timing tests against the second version. Integration applied
ten exact-context file patches while preserving the source-selector validation
and Gym dictionary-key fixes. The 45 integrated timing and dictionary-key tests
passed. Full combined SDK, corpus and export checks are tracked separately and
remain pending in this record until their results are available.

A 14,070-byte legacy fixture for CartPole and MuJoCo manifests/references plus
CartPole state/snapshot data remains byte-identical. This is compatibility
evidence for undeclared backends, not a claim that they satisfy physics-tick
accounting. No package has been migrated by this SDK patch itself. No upstream
simulator or hardware was executed.

`MHS/spec/05-fidelity.md` clarifies the existing receipt extension used for timing
notes. The stable step output, fidelity object and schemas are unchanged.
`progress.ticks` is measured command progress; wall-clock `duration_ms` is retained.

## Remaining work

The stock Gym snapshot followed by stock restore currently fails its state-hash
comparison even without this patch. That existing defect was independently
reproduced and remains open; direct bridge snapshot tests do not close it.
Package migration, runtime-specific source/deployment validation and live
simulation testing remain separate work. The opt-in contract intentionally
rejects variable decimation, native autoreset, external clock advancement and
resets that integrate physics.

Private evidence and preserved originals are under
`work/handoff-runs/mhs-build-20261102/ros-readiness/l14-sdk-dev/`,
`completion-audit/l14-review/` and `originals/simulation-timing-v2/` in that run.
