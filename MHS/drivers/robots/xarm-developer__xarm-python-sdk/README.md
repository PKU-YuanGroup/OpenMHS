OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Exemplar: gh.xarm-developer/xarm-python-sdk (a robot arm: array and nested limits, API return codes, a watchdog)

A UFACTORY xArm with 7 axes (`xarm.wrapper.xarm_api:XArmAPI`) as an R2 hardware driver. The package is model-authored
(`driver.lock.json` `authored_by` kind `model`) and unreviewed (`reviewed_by` null), so it runs on the **fake backend
only**: the loader refuses the hardware backend of a model-authored R2 driver until a human signs `reviewed_by`
(`mhs.adapter.load_driver(..., backend="hardware")` raises `LoadError` `review_required`; `test_driver.py` checks it).
Its evidence is `contract_checked` and never an MHS-Device level. Nothing here ran on an arm.

## Run the gate

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/drivers/robots/xarm-developer__xarm-python-sdk --backend fake
```

It passes with no warning. The joint table of the SDK writes nine of its bounds as `2 * math.pi` and `math.pi`; gate G4 reads
those expressions as numbers, so the cited lines are found to show the values the `Limit`s hold (6.283185307179586,
3.141592653589793).

## What it demonstrates

| Pattern | Where |
|---|---|
| Joint angles as a named array: `length=7`, per-joint `min`/`max` arrays with `names`, cited to the SDK's table for robot type `XARM7_X4`; a refusal names the joint (`joint_positions[1]`, `joint2`) and the line | `driver.py` `move_joints` |
| Nested limits on a Cartesian pose: `position.x`, `.y`, `.z` cited to the SDK's TCP table (one line each); the SDK itself does not enforce them (Fact) | `move_pose` |
| A bound no source states: `Limit.operator_required` for `orientation.roll`, `.pitch`, `.yaw` (the table says only the full circle), for the joint velocities and for the duration; several of them in one input | `move_pose`, `jog_joints`, `site-limits.example.json` |
| Every SDK call returns an API code: a non-zero code raises `DriverFailed` with the native code, `OutcomeUnknown` when the code says a timeout (below) | `_check_code` |
| Units: the SDK's default is degrees, so every call passes `is_radian=True` | `driver.py` |
| A device-side watchdog: the `duration` of a velocity command is sent to the arm, which sets the speed to 0 after it (firmware 1.8.0 or newer); `watchdog_ms` is declared with a Fact that says "watchdog"; a duration of 0 (which never stops) and older firmware are refused | `jog_joints` |
| `emergency_stop` as `@estop`; the documented physical stop as `estop_physical_ref` (SAFE-045 for R2 hardware without a safe-state action) | `stop` |
| No `@reset` hook: a reset only releases the latch and sends the arm nothing (SAFE-042). The declared re-enable (`reenable=True`, CORE-086) is the new start command: it clears errors and warnings, enables motion and selects mode 0 and state 0, the recovery the SDK documents after `clean_error` | `enable_motion` |
| Reads of properties and `(code, value)` getters; an object-valued read (`tcp_pose`) | `get_*` |
| A mode switch before a motion that refuses to clear somebody else's pause or stop | `_select_mode` |
| A fake with the upstream signatures and the SDK's own start values; underscore hooks for the tests | `fake.py` |
| An operator overlay that narrows a sourced limit (the SDK's 1305 table) and fills the `operator_required` ones | `site-limits.example.json` |
| A position-only input for the conformance run, so the move is exercised without the operator-required orientation | `fixtures/conformance.json` |

## Return codes

`doc/api/xarm_api_code.md:15-58` lists the codes; `0` is the only success. `_check_code` maps them:

| API code | Receipt | MHS code |
|---|---|---|
| 3 response timeout, 100 wait finish timeout, 101 too many failed checks | `unknown` | `MHS.OUTCOME.UNKNOWN` (the move may have happened) |
| -2 not ready (motion not enabled or state not set), 9 state not ready to move | `failed` | `MHS.DEVICE.PRECONDITION_UNMET` |
| -6 cartesian limit, -7 joint limit, -8 out of range (the arm's own checks) | `failed` | `MHS.SAFETY.ENVELOPE_VIOLATION` |
| any other, e.g. -9 emergency stop, -1 disconnected, 1 errors not cleared | `failed` | `MHS.DEVICE.FAULTED` |

The receipt keeps the number in `error.details.native_code`. A non-zero code from the read-back **after a move that finished**
(`get_servo_angle`, `get_position`) is always `unknown`: the arm moved, only where it is now cannot be read.

## Files

| File | Role |
|---|---|
| `task.json` | the registry task card (input; a copy of `MHS/registry/tasks/robots/xarm-developer__xarm-python-sdk.json`) |
| `driver.py` | the `XArm7` Driver class |
| `fake.py` | `FakeXArmAPI`: only members `XArmAPI` has, with its signatures (gate G7) |
| `native.py` | the hardware factory; the gate never imports it and nothing here ran it |
| `facts.md` | the facts and limits with their sources |
| `site-limits.example.json` | an operator overlay (narrow-only, plus the filled `operator_required` limits) |
| `fixtures/conformance.json` | a position-only pose input for G6 and G8 |
| `test_driver.py` | the gate harness call plus cases for this driver |
| `driver.lock.json` | pinned upstream, install, backends, `authored_by`, `reviewed_by` |
| `reference.json`, `REFERENCE.md` | generated: `python3 -m mhs.driver reference <dir>` |
| `RESULT.json` | `pass` with the gate digest the check printed |

## Honest limits of this package

- **Robot type.** The limits are the SDK's tables for the 7-axis type `XARM7_X4` (robot type 7). The SDK keeps one table per axis
  count and type (`x_config.py:51-157`, `158-245`), and `native.py` refuses an arm that reports another axis count or type.
  Another type needs its own package. The 1305 series uses a narrower table (`x_config.py:138-146`); the example overlay applies it.
- **The tool position limits are a bounding box.** The SDK lists `TCP_LIMITS` but its own check applies only the rotation entries
  and is off by default (`xarm_api.py:75-76`), so these ranges are the SDK's statement, not a reachability proof. Cartesian
  targets inside the box can still be unreachable, and the arm answers with an API code.
- **No speed or acceleration.** The motion classes have no such field, so a move runs at the SDK's last used speed (100 mm/s tool,
  20 deg/s joints after start, `base.py:128-131`). The SDK's ranges (`base.py:105-111`) are for position moves only; the SDK states
  none for velocity mode, which is why the velocity inputs are `operator_required`.
- **`reached`.** A move returns `reached: true` when the SDK's wait ended with code 0, that is, the arm finished the move without an
  error. The driver does not compare the final angles with the target.
- **`watchdog_ms` is 60000.** The SDK has no fixed watchdog, only the per-command `duration`. The value is the longest `duration_s`
  the catalogue class accepts (`cap.motion.joint_velocity.v1`, maximum 60); the operator's overlay cannot make it longer. It holds
  only for firmware 1.8.0 or newer (`xarm.py:1704`), which the driver checks through `version_number`.
- **`emergency_stop` can take up to 3 s** (`xarm.py:1111-1115`), more than the runtime's default 1 s e-stop budget. The latch is set at
  once; the receipt may then say `MHS.SAFETY.SAFE_STATE_UNREACHED` although the stop follows, and the runtime retries it. The wrapper's
  docstring says the stop also re-enables motion and returns to state 0 (`xarm_api.py:1897`); the code only sets state 4 and waits.
- **The mode is read from the report stream** (`xarm_api.py:443`): over a connection without it `mode` may be stale, and the driver
  could skip a needed `set_mode`.
- **The fake has no kinematics, no motion over time and none of the SDK's range checks.** Its tool pose and joint angles are
  independent, and a move finishes when the call returns. The hardware path (`native.py`, the controller's IP address, the blocking
  `wait=True` moves, the e-stop from another thread) was never run.
- **G6 and the example overlay.** A binding with several `operator_required` paths (here the orientation) failed the old G6 check;
  `MHS/changes/WP-11.md` lists the gate change that fills them together.
- `check-report.json` is generated by every gate run (new timestamps each time) and is not part of the package. `RESULT.json`
  records the digest the check printed (`gate digest (RESULT.json gate.digest)`), which stays the same while the gate result stays the same.
