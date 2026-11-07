# Hardware stop cited to one fetched companion

Round 1 of the ext-integrator-B review left the package directory and the waiting-routing override out. The final package decision is block, and the admission rule requires accept. The opt-in hardware-stop checker in the SDK remains, tested with fixtures rather than the shipped package.

User decision 4 of 2026-11-05 allows `gh.rplab/wil_pycro_control_app` (an R1 microscope stage) to cite Micro-Manager `CMMCore::stop` in the fetched clone `micro-manager__mmCoreAndDevices@ce92a47dc1b0`. This change is that exception and nothing wider. A ROS companion is unchanged. A bound, `estop_physical_ref`, `action_space_ref` and every other binding still cite the package clone. The hardware backend still needs a human `reviewed_by` with scope `hardware` before it may start. The citation does not waive that signature, at any risk. This record does not write `reviewed_by`. No hardware run and no simulator run were performed. The fake-backend gate fails G6 and G8, so this package does not record `contract_checked`.

The stopped trees were inspected and nothing was taken. `development/p5b-hw-companion/project` is absent. `development/ext-p5b-hw-companion.fast-stopped/project` differed in 0 files from its base manifest.

## Rule

`MHS/handoff/REVIEW.md` item 13 (lines 155-163) states the limit: only a package the user decided so for may cite a fetched companion from its stop and from the fresh read-back that confirms that stop, and only when that companion's card entry sets `hardware_stop` true. The profile is not a ROS profile. The card `ref` is the full commit `ce92a47dc1b06317756317b1f27d8cbc64b9c412`, and the text of `lock` after `@` is `ce92a47dc1b0`. The two members are not members of the package clone. Every call of them is during the e-stop, the stop before the read-back, and the e-stop contains at least one such pair.

`work/companions/LOCK.json` already lists this package in `needed_by` for that clone. This change does not edit `LOCK.json`.

## Package

`authored_by` stays `{kind: model, model_id: deepseek-v4.1-flash:1017, run_id: helper-wave-2-012, date: 2026-11-05}`. `reviewed_by` stays null. Risk stays R1 because `cap.imaging.focus.v1` is catalogue class R1 (`MHS/spec/capabilities.json:4464`) and the hazard table places low-energy, reversible, bounded motion at R1 (`MHS/spec/04-safety.md:67`). SAFE-045 (`MHS/spec/04-safety.md:376-382`) is the rule for an R2 or R3 hardware device. This package stays at the catalogue floor. The per-axis writes still bypass `move_stage` (`stage.py:191-214` of the package clone); that residual stays disclosed.

The package is blocked on `NO_HARDWARE_FREE_PATH`. No cited call attributes an error-qualified idle reading to each requested axis, so the native stop is not claimed as repaired.

`driver.py:196-201` declares `companion_stop`: `stop_stages` shows `CMMCore::stop` at `MMCore/MMCore.cpp:1607-1650`, and `stages_settled` shows `serialAnswer_` at `DeviceAdapters/ASITiger/ASIHub.cpp:150-157`. `driver.py:266-304` is the e-stop. It calls `stop_stages`, then `stages_settled`. Any exception raises `MHS.SAFETY.SAFE_STATE_UNREACHED`. A result that is not exactly `True` raises the same code. A result that is exactly `True` also raises it, because a read-back from this companion is not an idle proof. The latch stays held. RESET is not sent, `wait_for_device` is not called, and there is no re-enable. A later position write is refused while the latch is held. `safe_state` is `driver.py:192-195` (334 characters).

`native.py:69-86` attempts `core.stop` on `ASI_XY_STAGE_NAME` (default `ASI-XYStage`), then `XY_STAGE_NAME`, then `Z_STAGE_NAME`. A failure of one call does not skip the others. The aggregated error is raised after those attempts, and the e-stop then skips the read-back. `stages_settled` (`native.py:88-100`) always raises. It sends no serial command. This wrapper was not run on hardware.

`QueryCommand` writes one shared `serialAnswer_` (`ASIHub.cpp:150-157`). `OnSerialCommand` ignores the query's return code and copies that buffer (`ASIHub.cpp:589-595`). A changed `SerialResponse` can be another command's reply. `GetSerialAnswer` leaves the string unassigned when the port read fails (`DeviceBase.h:1018-1028`). Comparing two reply strings does not prove the `RS` query of the requested axis succeeded.

`UseFastSequence` is created only inside the ring-buffer block (`ASIZStage.cpp:341-380`). A failed read of a property that exists is a different event from the property being absent. The wrapper does not treat that exception as absence.

The focus device's axis letter can repeat a letter on another controller. A query sent through the XY serial label does not show that the focus device belongs to that controller.

`SerialCommand`, `SerialResponse` and `OnlySendSerialCommandOnChange` are created on the hub (`ASIHub.cpp:60-80`), not on `CXYStage`. `CMMCore::stop` throws `CMMError` when the label is not a stage (`MMCore.cpp:1648-1649`). Relabeling the hub does not put those properties on a device `stop` accepts.

A false busy flag leaves the stop unconfirmed. `CMMCore::deviceBusy` (`MMCore.cpp:1166-1173`) is specified `throw (CMMError)`. `DeviceManager::GetDevice` throws when the label is absent or null (`DeviceManager.cpp:173-194`). ASI Tiger `CXYStage::Busy` returns false when the serial query or the parse fails (`ASIXYStage.cpp:599-637`). `CZStage::Busy` returns false when `runningFastSequence_` is set and when the query or the parse fails (`ASIZStage.cpp:490-516`). The XY link check is the `W` command: `CXYStage::GetPositionUm` is commented out (`ASIXYStage.h:72-77`), the default `GetPositionUm` returns the `GetPositionSteps` error (`DeviceBase.h:1920-1928`), and `GetPositionSteps` uses `QueryCommandVerify` (`ASIXYStage.cpp:496-509`). That `W` reply is a different command from the `RS` status query. `CZStage::GetPositionUm` uses `QueryCommandVerify` (`ASIZStage.cpp:412-419`). The e-stop does not use a position read. `device_busy` is not called.

`CMMCore::stop` (`MMCore.cpp:1607-1650`) calls `StageInstance::Stop` or `XYStageInstance::Stop` and returns. A label that is neither throws. It does not unpause and it does not resume a stored command. ASI Tiger `CXYStage::Stop` sends `<addr>HALT` (`ASIXYStage.cpp:589-596`) and `CZStage::Stop` sends `<addr>halt` (`ASIZStage.cpp:471-477`). Neither path is `QueryCommandVerify`. HALT is card-wide. The package offers no re-enable, so SAFE-042 does not arise as an unpause. `stop`, `device_busy` and `get_property` are inferred snake_case names for pycromanager 0.20.0 (`requirements.txt:16` of the package clone). `stage.py` already calls `set_property`. A missing name raises `AttributeError`, which the e-stop reports as `SAFE_STATE_UNREACHED`.

The package tests construct `StageBackend` over an in-memory core. An idle-looking `SerialResponse` with the axes still moving does not confirm and sends no `SerialCommand` (`test_driver.py:282-302`). An unreadable `UseFastSequence` whose stored value is `Armed` is `SAFE_STATE_UNREACHED` (`test_driver.py:304-319`). A focus axis on another controller is not confirmed from the XY hub (`test_driver.py:321-337`). A hub label that `stop` rejects does not confirm a moving stage (`test_driver.py:339-356`). A true read-back is still `SAFE_STATE_UNREACHED` (`test_driver.py:119-134`). An XY stop failure still stops focus, and a focus stop failure still stops XY. Those cores are not hardware and not a simulator.

`MHS/spec/driver-profile.md` records the same limit. DRV-021 (line 144) allows `companion_stop` only for a package the user decided so for. DRV-040 (line 154) requires `reviewed_by` scope `hardware` before that hardware backend starts, at every risk including R1. DRV-050 (line 164) and the G7 row (line 184) exempt the two cited members from the package-surface rule when the card sets `hardware_stop` true, and the stop call still precedes the read-back.

Version evidence the gate checks, as substrings of the cited lines: `Micro-Manager-2.0-gamma 20230120` in the package clone `requirements.txt:2`; `pycromanager==0.20.0` at `requirements.txt:16`; and `MMCore_versionMajor = 10, MMCore_versionMinor = 4, MMCore_versionPatch = 0` in `MMCore.cpp:116` (74 characters, without a leading `const int` or a trailing semicolon, because the full source line exceeds the 80-character token limit). The profile string `micromanager-2.0-gamma-20230120` is the card profile. It is not claimed to be a verbatim source line. The nightly-to-commit mapping is the `LOCK.json` note (commit `ce92a47dc1b0` of mmCoreAndDevices, gitlink of micro-manager main `a2376baac153`, last first-parent on or before 2023-01-20 UTC). The gate does not prove that the nightly build contains that commit.

The fake (`fake.py:76-94`) has explicit `stop_stages` and `stages_settled` methods and no `__getattr__`. `stages_settled` increments the read-back count and raises. The default path does not confirm. A stop that raises skips the read-back.

The gate on the fake, with `--companions-root` pointed at `work/companions`, fails G6 (`ESTOP_FAILED`) and G8 (`SAFE-028`). G1-G5 and G7 pass. G9 is skipped because earlier gates failed. The stable digest is `sha256:134b2c29d84911d856e3fb5151f40a43879663bdb8a0495d3fe8c8369516f7fa`. It is recorded in `RESULT.json`. The round-1 passing digest `sha256:227acc2534e89d120d4737ade23a1d0976a88dbb61346b8e6a73f6afc87eb238` moved because the e-stop no longer completes. The original blocked digest was `sha256:f0055e64bd37eadcaf3eec1f726a73830c04a1e972aa52c2c82d6a7c372788e1`. `RESULT.json` keeps the two earlier MODEL REVIEW paragraphs as history of the old `reset_stage` block, and keeps one paragraph headed `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null):`. The opening describes the block. The registry record is hand-edited back to evidence `static_scan`, adapter `packaged`, ring 3, overlay status `blocked`, `blocked_on` `["NO_HARDWARE_FREE_PATH"]`, and the new gate digest. `LICENSE_UNKNOWN` remains. Rank stays 64 and wave stays 5. `build_registry.py` was not run. `build_index.py` rewrote `index.json`, `index.jsonl` and `records.csv`. `validate.py --no-corpus` then passed (2967 records, 0 errors).

`load_driver` refuses `backend="hardware"` with `LoadError` reason `review_required` while `reviewed_by` is null (`loader.py:145-151`, `adapter.py:167-170`). The package test observes that refusal without importing `native.py`.

## SDK

The exception is fail-closed and limited to `hardware_stop: true`.

- `mhs/driver/upstream.py:255-285`: a `hardware_stop` entry must have `lock`, a non-ROS profile (`HARDWARE_STOP_PROFILE`), card family `direct` or `python-object`, `safety.expected_mode` `hardware`, and `ref` equal to the full commit while the lock suffix is that commit's first 12 hex digits. Every other lock companion still requires `ref` equal to the text of `lock` after `@` and a ROS profile.
- `mhs/driver/hardware_stop.py`: `check_hardware_stop` accepts exactly one stop member and one read-back member, both absent from the package clone, each showing its token as a word in the companion. It returns those names as exempt only when the card authorizes them. A call outside the e-stop is `HARDWARE_STOP_SCOPE` and the names stay exempt, so `NOT_UPSTREAM` does not hide the phase error. A read-back before the stop, or no stop-then-read-back pair, is `HARDWARE_STOP_UNCONFIRMED`. A bad citation returns an empty set, so `NOT_UPSTREAM` also fires.
- `mhs/driver/source_gate.py:27-49`: an explicit source selector subtracts the exempt names. A surface that was not found still runs the check when the class declares `companion_stop`.
- `mhs/driver/check.py:2351-2354`: G7 reports `HARDWARE_STOP_SCOPE` for any other family before that family's shortcut return, so a ROS driver cannot skip the check. `check.py:2175-2179` still rejects a companion ref on a non-fact binding in G4. The class-surface path calls the same helper at `check.py:2459-2461`.
- `mhs/driver/loader.py:138-151` and `mhs/adapter.py:159-170`: a non-empty `companion_stop`, including a malformed one, requires `reviewed_by.scope == "hardware"` at every risk. An ordinary R1 driver with no such declaration is unchanged (`review_problem` returns `None` for that case).
- Registry: `triage.py` `check_companions`, `validate.py` `lock_shape_problems` and `check_companions`, and `build_registry.py` `attach_companions` carry the same flag. `COMPANION_KEYS` and the driver-lock schema do not gain `hardware_stop`. The override and task-card schemas put the ROS profile pattern in the `else` branch and the non-ROS pattern in the `hardware_stop` branch (`taskcard.schema.json:228-237`). A base ROS pattern on `profile` would reject this card, so it is not there.
- The companions array was added to the existing `waiting-routing.json` override for this package. The justification that the package clone has no stop was kept. No second override file was added.

Tests: `MHS/sdk/tests/driver/test_hardware_stop.py` (23 tests, including a non-hardware mode, a source without `hardware_stop`, and a 40-hex ref that differs from the commit) and `MHS/registry/tests/test_hardware_stop_override.py` (8 tests). Three further mutants, each in its own copy of the SDK sources, were killed by those tests: deleting `ref == commit` in `upstream.py`, deleting the `mode != "hardware"` return in `hardware_stop.py`, and deleting the `hardware_stop` authorization check in `hardware_stop.py`. The project tree was not modified by that run. The package tests are `test_driver.py` (23 cases, including the gate assertion that G6 and G8 fail).

`collect.py --strict` over the 729 `RESULT.json` files whose status is `pass`, with `--companions-root` pointed at `work/companions`, ran for about 3340s and exited 1. 725 of those 729 passed the gate, and 5 carried warnings. Every passing digest matches the digest already recorded in that package's `RESULT.json`. This package is blocked, so it is outside that set. Its digest moved from `sha256:227acc2534e89d120d4737ade23a1d0976a88dbb61346b8e6a73f6afc87eb238` to `sha256:134b2c29d84911d856e3fb5151f40a43879663bdb8a0495d3fe8c8369516f7fa`. The same four pass-status packages failed again: `gh.mattjax16/rigol-dho-mcp` (G6), `gh.christianrauch/raspicam2_node` (G6), `gh.lightwheelai/lw-benchhub` (G1) and `gh.misterblue/ros2_raspicam_node` (G6). `gh.amsikking/thorlabs_mcm3000` passed with the existing `UNVERIFIABLE_CITATION` on `MCM3000_Direct_Serial_Communication.pdf:2`. Those five `RESULT.json` files were left as they were. `REPORT.json` records the collect result.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-06 while composing the phase-5 units onto snapshot-7. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged the opt-in hardware-stop SDK and this record. Snapshot-6 and snapshot-7 were the same bytes on each direct copy:

- `MHS/sdk/src/mhs/driver/hardware_stop.py` (new)
- `MHS/sdk/src/mhs/driver/check.py`
- `MHS/sdk/src/mhs/driver/loader.py`
- `MHS/sdk/src/mhs/driver/source_gate.py`
- `MHS/sdk/src/mhs/driver/upstream.py`
- `MHS/sdk/src/mhs/adapter.py`
- `MHS/spec/driver-profile.md`
- `MHS/registry/schema/taskcard.schema.json`
- `MHS/registry/tests/test_hardware_stop_override.py` (new; the shipped-card case is an in-memory fixture)
- `MHS/sdk/tests/driver/test_hardware_stop.py` (new; the load_driver case is a temp fixture)

Three-way merges against snapshot-6, with snapshot-7 as ours and this unit as theirs, were clean (`diff3 -m`, both sides' added lines present): `MHS/registry/build_registry.py`, `MHS/registry/schema/overrides.schema.json`, `MHS/registry/triage.py`, `MHS/registry/validate.py`. The products are under `DEV/merge/`.

`MHS/handoff/REVIEW.md` is the merge described in `P5-SDK-NAMES-MULTI.md`. The inference unit also edited `check.py`, `upstream.py`, `driver-profile.md`, `build_registry.py`, `overrides.schema.json`, `taskcard.schema.json`, `triage.py`, and `REVIEW.md`. Those edits were left out with the open findings on `version_inference.py`.

Package `gh.rplab/wil_pycro_control_app`: round 1 (INT-B-001) removed the package directory and restored `MHS/registry/overrides/waiting-routing.json` to the snapshot-7 bytes. The final Codex package decision is `block`, and admission requires `accept`. The tree holds snapshot-7 `RESULT.json` digest `sha256:f0055e64bd37eadcaf3eec1f726a73830c04a1e972aa52c2c82d6a7c372788e1` (`NO_HARDWARE_FREE_PATH`). The round-0 re-record `sha256:134b2c29d84911d856e3fb5151f40a43879663bdb8a0495d3fe8c8369516f7fa` is not in the tree. `DEV/originals/r1-before/` keeps that round-0 text. The SDK tests no longer load this package or its shipped task card.

This unit's `lock_changes` is empty. `micro-manager__mmCoreAndDevices@ce92a47dc1b0` already lists `gh.rplab/wil_pycro_control_app` in `needed_by`. That line was already in the lock and was left in place. The real lock was not written.

Generated registry outputs and `CHANGELOG.md` were not copied.
