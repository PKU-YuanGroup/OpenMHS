OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5-BACKLOG-SDK-MISC — Ophyd export family, stop-once stamp test, MuJoCo recipe note

Grok (grok-4.7, a model and not a human) authored this record on 2026-11-05. `reviewed_by` stays null. Run id `ext-p5-backlog-sdk--misc-20261105`. This unit is BL-01, BL-02 and BL-03 from `result.backlog.items`. BL-20 and BL-24 are another unit; their files were left alone. No driver package was re-authored, and no `RESULT.json` note was edited.

Nothing was taken from the stopped Claude tree `development/p5-backlog-sdk` or the stopped Grok tree `development/ext-p5-backlog-sdk.fast-stopped`. Each tree was compared with its `base-manifest.json`: 0 files differed, and neither tree contains `MHS/changes/P5-BACKLOG-SDK-MISC.md`.

## BL-02 — `mhs.driver export` family for an Ophyd package

`export_adapter` writes `family` from `_family_of` (`MHS/sdk/src/mhs/driver/package.py`) and then validates the document against `adapter.schema.json`. The schema enum lists `bluesky-ophyd` (`MHS/schema/adapter.schema.json` and the copy under `MHS/sdk/src/mhs/_data/schema/`). It does not list `ophyd`. The tuple in `_family_of` mapped `OphydDriver` to `ophyd`, so `export_adapter` raised `DriverDefinitionError` on every Ophyd package.

The tuple entry is now `("OphydDriver", "bluesky-ophyd")`. `OphydDriver` stays ahead of `PythonObjectDriver` in that tuple, so an Ophyd class does not fall through to `python-object`. `OphydDriver.family` stays `"ophyd"` (`MHS/sdk/src/mhs/driver/families.py`); that string is the gate and card family, and this change does not touch it. The schema enum was left as it is. `_ADAPTER_FAMILIES` was left as it is (the scaffold kind `ophyd` is a template name, separate from the export family). A `TagDriver` package still exports as `other`, which the schema allows and which `MHS/sdk/docs/tag-bridge.md` already states.

Tests, in `ExportAndCatalogTests` (`MHS/sdk/tests/driver/test_cli.py`):

- `test_an_ophyd_package_exports_as_bluesky_ophyd` calls `export_adapter` on `MHS/sdk/tests/fixtures/ophyd_axis`, requires `family == "bluesky-ophyd"`, and requires `default_store().validate(document, "adapter.schema.json") == []`.
- `test_a_tag_package_still_exports_as_other` does the same for `MHS/sdk/tests/fixtures/tag_modbus` with family `other`.

Mutants, edited in, run, and restored (the tree keeps `bluesky-ophyd`):

- Mapping string `ophyd`: the ophyd test errors in `export_adapter` with `DriverDefinitionError: exported mhs-adapter.json is invalid: $.family: 'ophyd' is not one of [...]`.
- Mapping string `python-object`: the ophyd test fails `AssertionError: 'python-object' != 'bluesky-ophyd'`.

`QcodesDriver` (`families.py`, subclass of `PythonObjectDriver`) is still absent from the tuple, so an export of a QCoDeS package still says `python-object` even though the schema lists `qcodes`. That is outside BL-02 and was left unchanged.

## BL-03 — stop-once ledger re-check after native work

`MHS/sdk/src/mhs/bridge/ros.py` was read and not edited. `_shared_stop` still refuses a confirmed flight whose stamp is not the command's stamp:

```
if not flight.event.is_set() or not flight.ok or flight.stamp != stamp:
    return None
```

(the condition is at line 1735). The stamp is `(self._native_activity, self.estop_epoch)`. `_receive` increments `_native_activity` when a non-safety action records a new terminal (`_invalidate_safety_locked`). The server e-stop sends the native stop first (`bridge.estop`, which always transmits and records the flight) and then each `safe_state.achieved_by` action with `ctx.extra["estop_shared"]`. Only that action path consults the ledger.

`RosStopOnceTests.test_native_work_after_an_identical_request_makes_a_fresh_stop_due` (`MHS/sdk/tests/safety/test_estop_stop_once.py`) plants one sent, non-safety ROS 2 goal (`PendingAction`, id `mhs-action-interrupted`, profile `ros2-native`) on `driver.inner` after the reader has entered. The device declares no re-enable, so the server runs the stop path once. `estop_latency_ms` is 4000 so the safe-state action waits for the native stop instead of starting beside it. On the first `/uav1/land` service call the transport handler feeds that goal's cancelled terminal (`op` `action_result`, `status` 5, `result` True, `values` `{}`) and waits until `_native_activity` has moved, then returns the LAND reply. The reader handles the terminal before the reply, so the flight is recorded with the earlier stamp. The safe-state action captures the later stamp, sends LAND again, and the receipt completes with `safe_state_achieved` and without `shared_stop_requests`. The test also requires the goal status 5, a null goal error, and `_native_activity` increased by exactly one.

Removing ` or flight.stamp != stamp` and running that test fails with `AssertionError: 1 != 2` on `uav.count("/uav1/land")`: the action reused the native LAND. The line was restored; `ros.py` matches its base sha256 `e6a15814811bc9aeb9b107876ca72b059640832595532c646db74707f106c126`.

`test_terminal_during_stop_invalidates_attempt_until_fresh_ack` and `test_stock_stop_bypasses_active_goal_and_requires_later_fresh_stop` in `tests/bridges/test_ros_action_safety.py` cover bridge safe-state invalidation. They do not call the stop-once ledger, and this record does not treat them as the BL-03 test.

## BL-01 — MuJoCo family page, unranged actuators

`MUJOCO-UNBOUNDED-ACTUATORS.md` asked the generated family page to add "operator_required where the model states none" to the step-row note. `render_recipes` (`MHS/registry/recipes.py`) copies each row note into `| {native} | {target} | {note} |`. The MuJoCo step note in `FAMILY["mujoco"]["rows"]` is now `ctrl limits come from actuator_ctrlrange, operator_required where the model states none`. The same sentence is the notes cell of `MHS/registry/families/mujoco.md` (the `data.ctrl` / `mujoco.mj_step` row). A check imported `recipes` and formatted that one row the way `render_recipes` does; the line is present in `mujoco.md`. `build_registry.py` was not run, so the page header stays `2026-10-20T00:00:00Z` and the record counts stay as they were. `MHS/site/_site/families/mujoco.html` still carries the old sentence; the integrator's site build is what refreshes it. Task cards, package digests, and `MujocoDriver`'s docstring were left as they were (the docstring already states the rule).

`CHANGELOG.md` indexes every file in `MHS/changes/`. Adding this record made `tools/build_changelog.py --check` fail. The generated fragment block was rewritten with `python3 tools/build_changelog.py` (115 sections). The hand-written summary above the markers was left as it was. `--check` then exits 0.

## Checks

The two export tests and `test_native_work_after_an_identical_request_makes_a_fresh_stop_due` ran together: 3 tests, 0.360s, OK. `ExportAndCatalogTests`, `RosStopOnceTests`, `DirectDriverTests` and `SharedReportTests` together: 26 tests, 4.230s, OK.

The SDK suite `python3 -m unittest discover -s MHS/sdk/tests -t MHS/sdk` ran once: 3793 tests in 638.864s, FAILED (failures=13, errors=7, skipped=16). One failure was `test_the_shipped_changelog_lists_every_fragment`, because this record was not yet in the generated changelog block. After `python3 tools/build_changelog.py` wrote 115 sections, that test passes alone and `python3 tools/build_changelog.py --check` exits 0. `test_stock_forty_unknown_late_cycles_keep_fence_then_estop_reset_recovers` failed in the suite (profile `ros1-actionlib`, receipt index 34, status `failed`, `MHS.OUTCOME.TIMEOUT`, "ROS request deadline expired before send", `duration_ms` 19) and passes alone. `ros.py` was not edited. The suite is not green: five pymmcore modules error on `No module named 'PIL'`, `test_reset_through_a_pseudo_terminal` raises `OSError: out of pty devices` alone as well as in the suite, and the MCP screenshot tests fail alone with status `failed` (`MHS.CAPABILITY.OUTPUT_INVALID`, "MCP result is invalid" on the `mcp_rigol` fixture gate). `mcp_client.py` calls `require_decoder()` for a PNG tool result (`MHS/sdk/src/mhs/bridge/mcp_client.py`). Those files were not edited. A second full suite was not run.

`python3 MHS/handoff/tools/collect.py --strict` over the 729 `RESULT.json` files whose status is `pass` exited 1: 725 gates passed, 5 rows with warnings. No warning is `RESULT_DIGEST_STALE`. `gh.amsikking/thorlabs_mcm3000` still passes and warns `UNVERIFIABLE_CITATION` for `MCM3000_Direct_Serial_Communication.pdf:2`. Four packages fail the same way when `check --backend fake` is run alone, and none of their files is in this diff: `gh.mattjax16/rigol-dho-mcp` fails G6 `G6.NOT_COMPLETED` (`MHS.CAPABILITY.OUTPUT_INVALID: MCP result is invalid`); `gh.christianrauch/raspicam2_node` and `gh.misterblue/ros2_raspicam_node` fail G6 `G6.NOT_COMPLETED` (`compressed ROS images require the optional openmhs[images] decoder`); `gh.lightwheelai/lw-benchhub` fails G1 `G1.CLONE_MODIFIED` on `lw_benchhub/utils/X7S/urdf/X7S/X7S.usd`. Their `RESULT.json` files were left as they were. A walk of regular files against `base-manifest.json`, without following directory symlinks, found only the seven paths this unit wrote.

## What was not claimed

No hardware run, no simulator run, and no human review. Evidence for the new tests is the unittest process. Package gate evidence from collect.py is `contract_checked` on the fake backend. The four gate failures above are recorded as problems. They were not repaired, and no passing digest was rewritten.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-06 while composing the phase-5 units onto snapshot-7. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged every non-generated change from this unit:

- `MHS/registry/recipes.py` (the MuJoCo table cell)
- `MHS/sdk/src/mhs/driver/package.py`
- `MHS/sdk/tests/driver/test_cli.py`
- `MHS/sdk/tests/safety/test_estop_stop_once.py`
- this change record

Snapshot-6 and snapshot-7 were the same bytes on each of those paths. `MHS/registry/families/mujoco.md` is generated from `recipes.py` and was not copied; the registry build regenerates it. `CHANGELOG.md` is regenerated. Nothing else from this unit was left out.
