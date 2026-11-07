# Facts and limits for gh.itheima1/mcp_robot

Every fact cites its source at commit `18f9ea5ff42c6bf01bc16d659e422c048be6d312`: `vendor_doc` for a text file of
the clone and `upstream_code` for a code line of the clone. `sources/README.md` is the clone's own documentation;
`sources/servo_control_standalone.py` is the driver the entry symbol names. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The application runs simulations and controls a Bambot and an SO100 arm | vendor_doc | sources/README.md:3 |
| The application controls real robot arms with Feetech SCS servo motors whose IDs are 1 to 6 | vendor_doc | sources/README.md:14 |
| The servo IDs are configured from 1 to 6 matching the joint numbers, the bus runs at a fixed 1,000,000 bps and the protocol is SCS (1) | vendor_doc | sources/README.md:31-33 |
| The controller's constructor defaults are port COM4, 1,000,000 baud and a 0.1 s timeout | upstream_code | sources/servo_control_standalone.py:289 |
| The serial port is opened with eight data bits, no parity and one stop bit (8N1) | upstream_code | sources/servo_control_standalone.py:308-315 |
| Every SCS packet starts with two 0xFF bytes and carries the servo ID, the length, the instruction, its parameters and a one-byte checksum | upstream_code | sources/servo_control_standalone.py:369-374 |
| set_servo_angle accepts an angle of 0-180 degrees, converts it to the 1024-3072 position range and clamps it there | upstream_code | sources/servo_control_standalone.py:468-471 |
| A moving speed is 0-32767 and a speed of 0 means the highest speed | upstream_code | sources/servo_control_standalone.py:463 |
| read_position returns the present-position register value, documented as 0-4095 | upstream_code | sources/servo_control_standalone.py:565 |
| get_servo_angle converts the 1024-3072 present position back to 0-180 degrees | upstream_code | sources/servo_control_standalone.py:515-516 |
| enable_torque writes 1 and disable_torque writes 0 to the torque-enable register | upstream_code | sources/servo_control_standalone.py:814-826 |
| sync_disable_torque writes 0 to the torque-enable register of every named servo and falls back to disable_torque one servo at a time when the sync write fails | upstream_code | sources/servo_control_standalone.py:878-900 |
| sync_enable_torque writes 1 to the torque-enable register of every named servo and falls back to enable_torque one servo at a time when the sync write fails | upstream_code | sources/servo_control_standalone.py:841-863 |
| The upstream MCP tool arm_tighten enables the torque of servos 1 to 6 with sync_enable_torque and documents that the arm then holds its current position | upstream_code | sources/mcp_server.py:333-347 |
| go_home moves servos 1 to 6 to 90, 0, 180, 180, 90 and 90 degrees; the comment on servo 4 says 0 but the code writes 180 | upstream_code | sources/servo_control_standalone.py:922-929 |
| read_position returns None when the command send or the reply fails | upstream_code | sources/servo_control_standalone.py:573-589 |
| _write_register returns False when the command send or the reply fails | upstream_code | sources/servo_control_standalone.py:646-666 |

Limits:

| capability | path | bound | source | ref |
|---|---|---|---|---|
| cap.motion.joint_position.v1 | joint_positions (per joint) | 0 to pi rad, one bound per joint with names joint1 to joint6 | upstream_code | sources/servo_control_standalone.py:462-471 |
| cap.motion.home.v1 | speed_scale | operator_required: the catalogue class defines only a dimensionless 0..1 fraction and the clone states no speed-scale range; `site-limits.example.json` is an example overlay | | |

The bound is written in the clone as 0-180 degrees, which is 0 to pi rad; the catalogue class fixes the unit to rad.
Gate G4 therefore reports the pi upper bound as `REF_VALUE` because the cited lines show 180 but not 3.14159. The
conversion is the driver's unit conversion, not a second bound: `set_servo_angle` converts the same 0-180 degrees to
1024-3072 and clamps there (sources/servo_control_standalone.py:468-471).

Safety: the native stop is `sync_disable_torque` over servo IDs 1 to 6; `safe_state` is "torque disabled on servos 1
to 6, so the arm is limp". The clone documents no independent hardware e-stop, so SAFE-045 is satisfied by the
safe-state action `x-cap.itheima1.disable_all_torque.v1`, which takes no input and runs during an e-stop. A safety
reset releases the latch and re-arms nothing (SAFE-042): the package has no `@reset`, so the torque stays off. The
torque comes back only through the declared re-enable `x-cap.itheima1.enable_all_torque.v1` (`reenable=True`,
CORE-086), which calls `sync_enable_torque` over servo IDs 1 to 6, the call the upstream's own `arm_tighten` tool
makes. The runtime refuses it while the e-stop is latched; a reset receipt names it; it takes no input. Whether a
servo seeks its last goal position when its torque comes back is not documented in the clone; the upstream says the
arm holds its current position, so the re-enable is treated as an actuation. Until 2026-11-05 the `@reset` hook
re-enabled the torque itself, which SAFE-042 forbids; that hook is removed. The loader
refuses this unreviewed R2 package's hardware backend until a human sets `reviewed_by`. `site-limits.example.json` is an
example operator overlay: it fills and narrows the `speed_scale` fraction of the home action; it is not a statement
about any arm. No hardware was attached and nothing here ran on an arm.

Tags: robot arm, six joints, feetech, scs, servo bus, joint control, homing
