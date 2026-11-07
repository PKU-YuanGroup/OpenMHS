OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Finite PyLabRobot liquid-handler helper

This change adds a config-only `PyLabRobotDriver` with one request profile, `plr-liquid-handler-v1`, for an
upstream whose control interface is a PyLabRobot `LiquidHandler` front end, used directly or held by an upstream
object. A package declares one immutable `PlrProfile`: the handler's attribute path, its setup and teardown, the
channel count, the lines that switch PyLabRobot tip and volume tracking on, a finite labware allowlist (each name
cited at the line that creates it), the bound operations and their volume and cycle limits, which an operation may
carry itself so that each cites its own line. The class may not define methods; capabilities, schemas, limits and
runtime maps are generated.

Three operations are bound as `x-cap` extensions. `transfer` and `mix` are self-contained: fresh tips are taken from
the named rack (the first run of adjacent rows that hold a tip within one column), then aspirate and dispense, then
the tips are discarded; both are R2. `tracked_volumes` reads PyLabRobot's volume tracker (bookkeeping, not a
measurement) at R0. The wells of one call lie in one column with strictly increasing rows and no repeat, as a
gantry head requires. Single-step aspirate, dispense and tip handling are not bound: their stateful preconditions
cannot pass the gate's stateless cases without a reviewed prerequisite profile. Labware is resolved on the
handler's deck only for declared names.

Failure outcomes follow where PyLabRobot raises. Its front end checks tips and tracked volumes before calling the
backend, so those bookkeeping errors become `MHS.DEVICE.PRECONDITION_UNMET` with the completed steps. Any other
error raised by a step, including a timeout, an I/O error or a firmware error, may have reached the device and is an
unknown outcome (`MHS.OUTCOME.UNKNOWN` with the step and completed steps, no native text); the python-object bridge
then fences new effects until a confirmed stop and an operator reset. An error before any step keeps the bridge's
redacted mapping. A failed or interrupted operation performs no cleanup motion: tips stay mounted, and since this
version has no operation that clears the head, an operator recovers the device (a simulated twin restarts).

The runtime is the existing python-object bridge with retained native execution. Before each PyLabRobot step the
bridge checks the driver's and its own e-stop epochs, the operation's cancel event and its closing flag, so no step
starts after an e-stop, a session close or an accepted cancellation, also on the software-only e-stop path where the
server never calls the driver. A step in progress is not interrupted. PyLabRobot `stop()` and any teardown are
refused as a stop; a native stop exists only as an explicit `PlrStop` that cites a pinned line and says what it does
not stop, and it must be safe to repeat because the server retries it in the background until it confirms. Without
one, the hardware backend is refused before its factory runs and gate G3 refuses a hardware package; an e-stop
during an operation is reported `MHS.SAFETY.SAFE_STATE_UNREACHED`, and whether a later reset is accepted depends on
whether the in-flight step ended before its caller observed the cancellation. The loader's review gate for
unreviewed model-written R2/R3 hardware is unchanged.

Gate G7 reads every profile reference as code at the pinned commit (`G7.PLR_REF`, `G7.PLR_SOURCE`): with `ast` in
Python files, one line per reference and at most 40 lines per operation span, so comments, docstrings and wide spans
do not count. It requires an assignment to the handler, definitions or calls of setup, teardown and the stop, the
channel count, `set_tip_tracking(True)` and `set_volume_tracking(True)`, each labware name as a call argument (or a
JSON `"name"` field) and a call of every PyLabRobot method of an operation on the handler. The new modules join the
gate's integrity snapshot. `mhs.testing.pylabrobot` gives package fakes a deterministic, stdlib-only model of the
front-end bookkeeping; no PyLabRobot code is imported by the SDK, a fake or the gate.

The exemplar is `MHS/drivers/labs/oelemento__star-sim`, the simulated Hamilton STARlet twin of oelemento/star-sim,
model-authored with `reviewed_by` null. It passes G1 to G9 on its fake backend with no finding and `collect.py
--strict` with no warning; its evidence is `contract_checked`. The `pylabrobot` registry family now names
`PyLabRobotDriver` and this exemplar, and its family page describes the profile, the stop policy, the recovery
limitation and which waiting repositories are not PyLabRobot liquid-handler front ends. A different-model review
(Claude Sonnet) asked for the unknown-outcome rule, the one-column rule, the code-reading G7 checks, per-operation
limits, documented reset and retry behaviour and more tests; this record describes the revised helper.

Validation (private copy of the 2026-11-04 baseline, Python 3.14.7): the complete SDK suite ran 3,151 tests with six skips and no failure (557 s), including 35 helper tests: profile validation and per-operation limits, generated schemas, fresh tips and bookkeeping failures, the unknown outcome and fence for step errors, a mid-step timeout and deadline expiry, the step fence under a real e-stop race and in the mix loop, a bound stop with its background retry, reset refused while native work runs, the one-column rule, unmappable input, hardware refusal before the factory, teardown, the deterministic model, MCP tool sizes, and a synthetic package through gates G1 to G8 with seeded G7 reference errors, including comments, wide spans and a comment named as the stop. The registry suite passes all 302 tests without the new package; with it, the overlay validator reports the expected mismatch between its pass result and the not yet regenerated card until the registry rebuild and package synchronisation run.

Not established: any PyLabRobot version's behaviour, the star-sim twin itself (no simulator backend is declared and
PyLabRobot was not installed), any hardware path, stop effect, motion, timing, liquid physics or channel geometry.
The MAVLink and LeRobot families remain planned: a source review found no stop that leaves a flying vehicle or a
gravity-loaded arm safe, so no helper was added for them. Human signatures, publication decisions and the registry
rebuild that removes the `helper:pylabrobot` blocker remain with the maintainers.
