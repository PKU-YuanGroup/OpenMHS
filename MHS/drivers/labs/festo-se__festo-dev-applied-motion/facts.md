# Facts and tags for gh.festo-se/festo-dev-applied-motion

Every fact cites its source at commit `c1926f02d8e69cec7f8d265dba20e9e5b474f425`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The FPosBAPI server on the CECC-X PLC listens on TCP port 1234 and speaks a line-oriented ASCII protocol; a successful response ends with 0, NULL, SUCCESS | upstream_code | src/applied_motion/backends/fposbapi_client.py:4-14 |
| MOVE_LOC is a coordinated 3-axis move to explicit X, Y and Z target coordinates in mm (a1, a2, a3) | upstream_code | src/applied_motion/backends/fposbapi_client.py:482-487 |
| HOME homes all axes through one PLC command | upstream_code | src/applied_motion/backends/fposbapi_client.py:439-440 |
| HALT halts the current motion | upstream_code | src/applied_motion/backends/fposbapi_client.py:512-513 |
| ROB_POS reports the current position as x_mm, y_mm and z_mm | upstream_code | src/applied_motion/backends/fposbapi_axis.py:151-154 |
| Velocity is written to PLC parameter 103 (global speed) in mm/s | upstream_code | src/applied_motion/backends/fposbapi_axis.py:78-86 |
| SYS_STATUS returns the system status string of the PLC | upstream_code | src/applied_motion/backends/fposbapi_client.py:738-746 |
| IS_ERROR reports whether the gantry is in an error state | upstream_code | src/applied_motion/backends/fposbapi_client.py:763-771 |
| FPB_ERROR and READ_ERR report the fieldbus error state and the current error description | upstream_code | src/applied_motion/backends/fposbapi_client.py:788-820 |
| RESET_ERR resets the active controller error | upstream_code | src/applied_motion/backends/fposbapi_client.py:542-543 |
| Always home the gantry before commanding absolute moves | vendor_doc | docs/examples/fposbapi.md:92 |
| The library can command real mechanical motion: commission and test the hardware first, keep the machine clear, and verify that every target position and velocity is safe | vendor_doc | README.md:13 |

The three axes are X, Y and Z with 1-based FPosBAPI indices 1, 2 and 3 (`docs/user-guide/fposbapi.md:126-130`), and
positions are in millimetres (`docs/user-guide/fposbapi.md:310`). The driver exposes all three coordinates with
`ROB_POS`; it does not use the `MOVE_AXIS` per-axis wrapper or the Modbus/`festo-edcon` backend.

## Limits

- `global_speed` (PLC parameter 103, mm/s) is `Limit.operator_required`. No text file of the clone states the speed
  range of a configured gantry; the drives, the mechanics and the process set it. `site-limits.example.json` shows
  the operator overlay and is an example, not a statement about any machine.
- The X, Y and Z targets of `cap.motion.cartesian_pose.v1` are `Limit.operator_required` for the same reason: the
  clone documents the coordinate format but not the travel envelope of a configured gantry.
- The home operation is the extension `x-cap.festo-se.home_axes.v1` with an empty input. `cap.motion.home.v1` also
  publishes optional `axes` and `speed_scale` inputs, but the FPosBAPI `HOME` command homes all axes and takes no
  speed, so the package does not bind that class and cannot honor those fields.
- The stop operation is the extension `x-cap.festo-se.halt_motion.v1` with an empty input. `cap.motion.stop.v1`
  publishes an optional `deceleration`, but the native `HALT` command takes no deceleration; the class also exempts
  stop actions from limits, so the driver does not bind that class.

## Safety

- The gantry commands real mechanical motion, so the driver declares R2 even though the card's floor is R1.
- The stop path is the PLC `HALT` command. It is the `@estop` method and, as `x-cap.festo-se.halt_motion.v1` with
  `safe_state=True`, the safe-state action. The clone documents no independent, safety-rated hardware e-stop, so
  `estop_physical_ref` is absent and this package does not claim one.
- `HALT` shares the serialised FPosBAPI socket with a running motion command, so the stop latency depends on the PLC
  answering the outstanding command first. The e-stop path was never run on hardware.
- This package is model-authored and unreviewed. The loader refuses its hardware backend at R2 until a human sets
  `reviewed_by`; the gate and the tests here exercise the fake backend only.

Tags: gantry, cartesian, motion, fposbapi, cecc-x, plc
