# MUJOCO-UNBOUNDED-ACTUATORS — a MuJoCo actuator without a control range is operator_required, not unbounded

The MuJoCo bridge published an actuator that declares no control range inside the derived `action.ctrl` limit as
-/+1.7976931348623157e308, a number nobody stated. A model that mixes such actuators with ranged ones could not pass
the gate, a model without any range was served silently unbounded, and a large model's limit text overflowed the MCP
tool bound. Such a control is now `operator_required`: the endpoint refuses a step that sets it before the native step
until the operator's overlay bounds it. Gate G6 exercises that refusal, and the MCP description groups per-element
bounds. The blocked `tenfoldpaper/multipanda_ros2` passes, and eleven passing packages were repaired and re-recorded.

## The defect

Found by the review of ROS wave C ([ROS-WAVE-C.md](ROS-WAVE-C.md), "Found, not fixed"; the decisions of
`tenfoldpaper/multipanda_ros2` and `geo-jtao/unitree_robot_sim`). MuJoCo clamps the control of an actuator only when it
is ctrl-limited (`ctrllimited`, or a `ctrlrange` under `autolimits`); every other control is unclamped.
`MujocoBridge.ctrl_limits()` gave such an actuator the bounds `-/+sys.float_info.max`, and `action_limits()`
published them in the per-element `action.ctrl` rule, or published nothing when no actuator had a range.

- **A mixed model could not pass.** The gate's out-of-range probe cannot exceed `float_info.max`: for the dual Panda
  scene of `multipanda_ros2` (44 channels, 28 position and velocity servos without a range) the probe value was
  accepted and the integration turned non-finite (`G6.ENVELOPE_NOT_ENFORCED` for 56 bounds, G8 SAFE-014 failing with
  `qpos must contain exactly 25 finite numbers`). The package was blocked `SDK_BUG`; its author had first hidden the
  28 servo channels in the fake to pass.
- **A model without any range was silently unbounded.** Ten passing packages served `action.ctrl` with no limit at
  all (nine models state no range; the tenth's fake hid the ranges its model states); the gate said only
  `G8.SAFE014_NOT_APPLICABLE`, and every control value reached the engine.
- **Large limits overflowed the tool bound.** The projection printed each per-element bound by position, and a whole
  float as an integer: the sentinel became 309 digits, and the multipanda step tool was 2,576 bytes (`G8.TOOL_SIZE`,
  limit 2,048). Ranged models were close too: `amathislab/musclemimic_models` (126 times `-1..1`) was 2,038 bytes and
  `nely-epfl/flygym` 2,031.
- **Workarounds in passing packages.** An audit of the 82 `MujocoDriver` fakes against their models (below) found two
  more: the fake of `luckyrobots/g1-manipulation-challenge` gave 14 finger actuators without a range their joint range,
  published as the model's `ctrlrange` (`upstream_code`), while a bridge subclass of the package left them unbounded on
  a real model; and the fake of `turagalab/flybody` published no range at all, although the model ranges all 78
  actuators.

## The fix

**Bridge** (`mhs/bridge/mujoco.py`). `ctrl_ranges()` returns, per actuator, the finite `(min, max)` the model states or
`None`. `action_limits()` publishes:

| The model | `cap.world.step.v1` limits |
|---|---|
| every actuator has a range | one per-element rule on `action.ctrl`, `upstream_code`, `ref` `<model>:actuator_ctrlrange` (unchanged) |
| no actuator has one | `action.ctrl: operator_required` (one group: the overlay gives a scalar or one value per element) |
| some have one | one rule per element: `action.ctrl[N]` the model's range, or `operator_required` |

`action_limit_reasons()` says why each `operator_required` path has no bound; the reference prints it next to the
path. The bridge's own check still enforces the model's ranges and now also refuses a control that is not a finite
number (`MHS.CAPABILITY.INPUT_INVALID`), whoever calls it. `ctrl_limits()` keeps its lists for the package tests that
call it, documented as a placeholder that is never published.

**Runtime.** Nothing new: the strict server already refuses a value set at an unfilled `operator_required` path with
`MHS.SAFETY.LIMITS_UNSET` before any native call (stop classes excepted), and an overlay may only narrow the model's
ranges (a widening overlay is refused at load, `MHS.ADAPTER.MANIFEST_INVALID`). A step without `action` keeps the
controls as they are.

**Family** (`mhs/driver/families.py`). The simulator families copy the bridge's reasons into the binding's
`operator_reasons`, so `reference.json` and `REFERENCE.md` say why each such control has no bound. A rule the driver
declares on the step action (`Action(limits={"action.ctrl[7]": Limit(...)})`, or on the whole `action.ctrl`) takes
precedence over the derived one; before, `binding.limits.update(derived)` replaced it silently (review S5-1).
`MujocoBridge.derive_step_limits` derives only the controls no declared rule bounds on both sides: the model's range,
or `operator_required` per element, so an uncovered control still fails closed. A declared rule may only narrow a
model range: a wider one (on either side; an `allowed` set bounds by its smallest and largest number),
`Limit.operator_required` on a ranged actuator or on the whole vector of a model that ranges every actuator, or a
one-sided element rule that leaves the other side no free path is a definition problem (G3). A whole-vector
`operator_required` on a mixed model defers its unranged controls as one group; the model's ranges stay as element
rules. For a family without such a derivation (Gymnasium), a declared
rule on a derived path replaces it only when it narrows it, and is a definition problem otherwise. No passing package
declares a step limit (81 MuJoCo, 267 Gymnasium), so nothing published changed.

**Gate G6** (`mhs/driver/behaviour.py`). The synthesized valid step input leaves `action` empty, so G6 could not
build an input that carries `action.ctrl` and only warned `G6.NO_INPUT`. When that happens it now builds the path
inside the other limits (the container builder the envelope probes use), so the `operator_required` checks run: the
refusal without an overlay, the refusal with every other such path filled, and the completion with all filled. No
passing package had such a `NO_INPUT` warning, so no other finding changes.

**MCP projection** (`mhs/mcp.py`). Per-element bounds are listed by position or, when that is shorter, by value with
their index ranges (`action.ctrl[0-3,22-25] -87..87, [4-6,26-28] -12..12`; `action.ctrl[*] -1..1` when all are
equal), each group with the unit (`[0-2] -1..1 rad, [3-5] -2..2 rad`, review S5-3); rules on single elements of one
array are merged the same way, by reason; a whole float of 1e16 or more is printed as a float. A description never
grows: each form is used only when it is shorter than the positional one. The step tools of the
multipanda scene (with its example overlay), musclemimic and flygym are now 1,727, 1,164 and 1,813 bytes.

**Docs.** `sdk/docs/driver-authoring.md` (section 5), `sdk/docs/bridges.md` and `sdk/docs/mcp-projection.md`.

## Decisions

- **`operator_required`, not a refusal at definition.** "If no source states it, use `Limit.operator_required`" is
  the rule for every other bound (`driver-authoring.md` section 5). Refusing such a model at definition would block
  simulations that are fine once an operator bounds them, and needs a package-declared envelope API that no current
  package needs. The real engine path is fail-closed either way: an unbounded control is refused until an overlay
  exists.
- **One group, or one rule per element.** A per-element `min`/`max` list cannot leave an element out, and the limit
  grammar has no index ranges (`defs.schema.json` `limitPath`); extending it would change the spec. A model without
  any range is one path (one overlay entry; one G6 check, not 78). A mixed model gets element rules, so the operator
  writes only the unranged channels and the model's ranges still apply; an overlay on the whole `action.ctrl` does not
  fill element paths (the `LIMITS_UNSET` refusal names each unfilled path in `details.paths`).
- **A declared rule takes precedence, and only narrows.** A package that has a source for a control's bound (an
  upstream clamp of the command) declares it with a cited `Limit` on the step action; the bridge then derives nothing
  for that control. Narrowing only keeps the model's range from being widened by a declaration, and deriving every
  uncovered control keeps the vector fail-closed.
- **A joint range is not a control range.** Neither the bridge nor a reviewer turns one into a bound of the model. The
  example overlays may use one, with a reason that starts `example only:` and names its origin: they are operator
  data, which the gate serves to step the model.
- **The MuJoCo bridge only.** The Gymnasium bridge has the same sentinel for a `Box` with infinite bounds (found, not
  fixed below).

## The packages

Every changed package was copied before the change; the copies and the audit script are kept with the work's
private batch records.

| Package | Before | Change | Gate after |
|---|---|---|---|
| `tenfoldpaper/multipanda_ros2` | blocked `SDK_BUG` | 16 ranged channels `upstream_code`, 28 servos `operator_required`; example overlay (servo joint ranges, Panda velocity limits of `panda_limits.h:14-16`); docstring, gaps, a fact, tests | pass |
| `blackcoffeerobotics/bcr_bot`, `catachiii/crl-humanoid-ros`, `ccrprepo/robomimic_deploy`, `cxy1997/robotiq-ur5`, `isri-aist/jvrc_mj_description`, `noetix-robotics/noetix_n2_gym`, `openai/mujoco-worldgen`, `shanpenghui/robomimicdeploy_g1`, `yueruyin/robot-unitree-g1` | pass, unbounded, `G8.SAFE014_NOT_APPLICABLE` | `action.ctrl` `operator_required`; example overlay `-10..10` (illustrative); the text that said any value is accepted; tests (four asserted that 1e6 or 200 was accepted) | pass, new digest |
| `turagalab/flybody` | pass, unbounded on the fake | the fake reads the model's 78 ranges from its default classes; docstring, gap, a fact (`fruitfly.xml:11`), a test | pass, new digest |
| `luckyrobots/g1-manipulation-challenge` | pass, invented finger envelope | the fake reports the 14 finger actuators as MuJoCo compiles them; bridge subclass removed; example overlay (finger joint ranges); text, tests | pass, digest unchanged |

Each re-recorded `RESULT.json` keeps `authored_by` and `reviewed_by: null` and gains a `MODEL REVIEW` paragraph; where
the notes would have exceeded 8,000 characters, the author's text before the first review paragraph was shortened
with " [...]". `qdeyna/ur10e_2f140_topic_based_ros2_control` stays blocked (it serves a test robot, not the
repository's device); its gate output changes the same way and its `RESULT.json` was not touched.

## The audit

An audit script loaded each `MujocoDriver` package on its fake and compared the actuators
and ranges the fake reports with an approximate reading of its MJCF (includes, default classes, `autolimits`,
`inheritrange`; `<attach>` read by hand for `manas-arumalla/openarm-control`). 80 of 82 agreed; `turagalab/flybody`
and `luckyrobots/g1-manipulation-challenge` did not and were corrected (above). The nine models without any range
and multipanda's 28 servos are what their MJCFs state.

## Tests

`tests/bridges/test_mujoco_unranged.py` (new, 30 tests): the three limit shapes and their reasons; ranges that are
not finite, inverted or without `ctrllimited`; the legacy `ctrl_limits()`; the bridge's refusal of a non-finite or
out-of-range control without a native step; through the strict server, the `LIMITS_UNSET` refusal before `mj_step`,
a step without `action`, an overlay that bounds the unranged control while the model's range still applies, a
widening overlay refused at load, a scalar overlay for a model without any range, and the reasons in the manifest and
the reference; G6 exercising the refusal and the overlay for both shapes, and noticing an endpoint that accepts an
unranged control; the grouped rendering (equal, repeating, distinct, 300 random arrays never longer than by position,
merged element rules, a property description, a huge float, the unit in every group) and a 44-channel mixed step tool
within 2,048 bytes with and without an overlay; declared rules: a whole-vector rule that replaces `operator_required`,
an element rule next to a per-element `operator_required` for the uncovered control (refused until an overlay bounds
it), declared bounds inside the model's ranges, rules that would widen a range on either side, drop it or leave a side
open (refused at definition), an `allowed` set that bounds an unranged control (and one that widens a range), a
whole-vector `operator_required` (refused when every actuator is ranged, one group on a mixed model), and a Gymnasium
rule kept only when it narrows the derived `Box` bound. The review's mutants D1 (no min-side widening check) and D12
(no `allowed` bounds) fail these tests.

## Found, not fixed

- **Gymnasium.** `GymnasiumBridge` gives an infinite `Box` bound the same `-/+float_info.max` placeholder: a `Box`
  with some infinite elements cannot pass the probe, and a wholly infinite one is served without a limit. The same
  treatment (an `operator_required` path or per-element rules) fits there.
- **Registry text.** The generated family page (`MHS/registry/families/mujoco.md`, from `MHS/registry/recipes.py:249`)
  says "ctrl limits come from actuator_ctrlrange"; it should add "operator_required where the model states none". A
  change there needs a registry rebuild.
- **multipanda's card** still names `RosDriver`, so `collect.py` reports `DECISION_DEVIATION` until a `mujoco` routing
  override is written (an entry is proposed with the work); the bare model drives all three actuator sets at once,
  which the upstream plugin's gain switching does not (disclosed in the package).
- **A declared rule on a derived Gymnasium `allowed` set** replaces it only with an `allowed` subset; a narrower
  `min`/`max` without `allowed` is refused (conservative). No derived Gymnasium rule has an `allowed` set today.
- **Overlay and engine.** An example overlay is written against the fake's model. On a real engine whose model
  differs, an overlay that would widen a range is refused at load (safe, but the deployment must write its own).
- **`flybody`'s fidelity** is published as engine `mujoco` F1 on its fake backend, which is a stand-in (as before).
- **Real MuJoCo.** The `mujoco` package is not in the validation environment; no model was compiled by MuJoCo here.
  The bridge reads `actuator_ctrlrange` and `actuator_ctrllimited` as before; only their interpretation changed.

## Result

Every check ran in a private copy of the tree of 2026-11-05, with the validated interpreter (Python 3.14.7, NumPy
2.5.3; no `mujoco` package).

- The SDK suite: 3,242 tests (30 new), 6 skipped; the untouched copy runs 3,212, 6 skipped. Of six full runs on the
  changed tree (the first started while it was still being edited; the machine was shared with other work at a load
  of 5 to 29), two passed every test (3,233 and 3,240 tests, before the last review tests were added) and each of the
  others failed one or two timing tests of modules this change does not touch: the MCP stdio contract tests
  (`MHS.DEVICE.BUSY`), the MCP stdio client's `test_hung_init_and_close_during_startup_keep_no_cancel_for_init`, and
  twice the ROS action retirement test `test_stock_forty_unknown_late_cycles_keep_fence_then_estop_reset_recovers`
  (a `RosDriver` reset after forty unknown safety goals). Each passes on its own (`test_mcp_stdio_contract.py` 9,
  `test_mcp_stdio.py` 35, `test_ros_action_safety_retirement.py` 18, five times in this copy and in the untouched one,
  and twelve times each under twelve concurrent runs); the bridge tests pass as one run (611 tests with the new module
  and the ROS modules; 581 in the untouched copy), as do the new module (30) and `tests/handoff/test_tools.py` (67,
  which checks the changelog).
- `collect.py --strict` over the 681 passing packages, multipanda and the blocked
  `qdeyna/ur10e_2f140_topic_based_ros2_control` (eight parallel chunks): 682 pass the gate. `qdeyna` fails G5 and G8
  (a model without any range and no example overlay); it stays blocked for serving a test robot, and its
  `RESULT.json` is unchanged. Exactly eleven gate digests differ from the recorded ones: the ten packages whose only
  finding change is the removal of `G8.SAFE014_NOT_APPLICABLE`, and multipanda (its 56 `G6.ENVELOPE_NOT_ENFORCED`
  errors and `G8.CONFORMANCE`, `G8.TEST` and `G8.TOOL_SIZE` gone). The other 671 passing packages keep their digests,
  so the projection and G6 changes altered no other finding; the only other warning is the historical
  `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`. After the twelve `RESULT.json` were re-recorded, the
  twelve were collected again: all pass with no warning (multipanda's `DECISION_DEVIATION` is a note). After the
  review fixes S5-1 and S5-3, all 682 passing packages were collected again: all pass, no digest differs from the
  one recorded, and the only warning is MCM3000's. After the last review round, the 348 passing MuJoCo (81) and
  Gymnasium (267) packages were collected again: all pass, no digest moved, no warning.
- `validate.py --no-corpus` reports only multipanda's registry card and record (`package_status` blocked, evidence
  `static_scan`), which the registry rebuild after this change updates. The registry suite passes 309 of 310 tests;
  the other, `test_validator_passes_without_the_corpus`, runs that validation and fails on the same two entries.
- `tools/build_changelog.py` indexes this record.
- Not run: `build_registry.py --check` and the rebuild (the records copy each package's status and evidence), the
  OpenAI4S integration tests and `tools/oss_export_check.py`; MuJoCo itself (not installed), so
  no model was compiled by the engine; no hardware. Every result is `contract_checked` on a fake, and the review is a
  model's, not a human's.
