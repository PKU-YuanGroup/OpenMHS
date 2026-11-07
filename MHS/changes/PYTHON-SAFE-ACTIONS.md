OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Retain Python safe-state actions through validated completion

A declared argument-free Python safe-state action now uses the independent retained safety lane. Its role comes from the resolved driver model, not caller metadata. This lets a native stop dispatch while an earlier ordinary setter remains active, while correctly refusing to report achieved safety until all earlier native execution has settled.

The bridge validates the mapped output against a copied resolved schema before committing its safety acknowledgement. Confirmation also requires an open bridge, unchanged activity/stop epochs and no retained execution. Invalid output, unknown completion, deadline expiry, concurrent activity and close cannot create a safety acknowledgement. Default and unrelated actions remain ordinary even if a caller forges safety metadata.

The first private version allowed a malformed acknowledgement to fail the public command while still committing bridge safety. The accepted second version closes that production-path defect. Independent verification passes 113 selected cases and three additional event-driven boundary tests. The actual composition with Gym checkpoint v3 passes 265 selected tests; those counts overlap. The original ordinary action could dispatch but invalidated the old safety stamp; the repaired baseline is not described as a permanent-latch refusal.

These checks use controlled native objects. They do not establish physical stop effectiveness or complete QCoDeS instrument support. Existing explicitly configured safety bindings keep their separate native-completion contract. Full SDK and current corpus regression remain pending. Originals, failed candidates, independent review and exact integration hashes are retained under `work/handoff-runs/mhs-build-20261102/`.
