OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# SIMULATION-RISK-ERRATUM — align the safety examples with the catalogue

The safety chapter listed simulation stepping as an R1 example, while the
machine-readable `cap.world.step.v1` class, the generated capability catalogue,
the driver profile and the SDK simulator families use R0. The precedence rule in
`MHS/spec/README.md` places the JSON registries above the safety chapter and
requires an erratum to the lower document when they disagree.

`MHS/spec/04-safety.md` now places isolated simulation stepping in the R0 examples
and explains that a data-only command may change simulated state. Existing
session, schema, envelope, cancellation and evidence requirements still apply.
Bindings that affect physical equipment retain their hazard classification,
including when their mode is hybrid. No driver risk, catalogue entry, schema or
runtime control was changed.

The comparison used the current local catalogue and specification, not a hardware
or simulator run. This is a prose correction; the combined specification and
clean-export checks remain pending. The original chapter is preserved in the
private `work/handoff-runs/mhs-build-20261102/originals/simulation-risk-erratum/`.
