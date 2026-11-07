# Facts and tags for gh.tetheria/aero-hand-open

Every fact cites the pinned clone at commit `7bb2f23485a7d440960c21046da642de132b7745`. `upstream_code` refs name
`path/in/clone:LINE`; a bounded range is used where the statement spans adjacent lines. The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| AeroHand is the SDK's hardware class; its constructor opens a serial port with a 0.01 s read and write timeout and takes the port and baudrate as arguments. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:53-64 |
| AeroHand copies joint_lower_limits, joint_upper_limits, actuation_lower_limits and actuation_upper_limits from AeroHandConstants onto the instance. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:66-75 |
| set_joint_positions accepts 16 or 7 joint positions in degrees, expands the compact 7-joint form to 16, clamps each position to the joint limits and sends CTRL_POS after normalizing the actuations to the uint16 range. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:134-164 |
| set_joint_positions catches a SerialTimeoutException from the CTRL_POS write, prints it and returns without raising. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:163-167 |
| set_actuations accepts 7 actuations in degrees, clamps each to the actuation limits and sends the same CTRL_POS frame, printing a SerialTimeoutException instead of raising it; the docstring warns that the thumb actuations are not independent and an uncoupled command can derail the thumb tendons. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:191-227 |
| get_actuations sends GET_POS, requires the full 16-byte reply and the GET_POS opcode, and returns None on a short read or an unexpected opcode. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:427-460 |
| get_joint_positions_compact returns 7 joint positions in degrees and returns None when get_actuations returns None. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:406-425 |
| get_actuator_speeds sends GET_VEL and converts each signed raw value with the factor 0.732 RPM. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:519-545 |
| get_actuator_currents sends GET_CURR and converts each signed raw value with the factor 6.5 mA. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:462-489 |
| get_actuator_temperatures sends GET_TEMP and returns the unsigned values directly as degrees Celsius. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:491-517 |
| set_speed takes an actuator id 0..6 and a speed 0..32766, sends SET_SPE and waits for the matching acknowledgement. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:259-281 |
| set_torque takes an actuator id 0..6 and a torque value 0..1000, sends SET_TOR and waits for the matching acknowledgement. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:283-305 |
| calibrate_mid takes an actuator id 0..6, sends CALIBRATE_MID and requires firmware protocol version 1, a non-error status and non-sentinel raw values. | upstream_code | sdk/src/aero_open_sdk/aero_hand.py:339-374 |
| AeroHandConstants declares the 16 joint names and the 16 joint lower and upper limits. | upstream_code | sdk/src/aero_open_sdk/aero_hand_constants.py:20-41 |
| AeroHandConstants declares the 7 actuation names and the 7 actuation lower and upper limits. | upstream_code | sdk/src/aero_open_sdk/aero_hand_constants.py:44-54 |
| The SDK GUI's 'Set to Open Position' button calls on_zero_all. | upstream_code | sdk/src/aero_open_sdk/gui.py:155 |
| on_zero_all sets the sliders to 0.0 and sends list(self.hand.joint_lower_limits) through set_joint_positions. | upstream_code | sdk/src/aero_open_sdk/gui.py:481-491 |
| The firmware control opcodes include HOMING, SET_ID, TRIM, CALIBRATE_MID, CTRL_POS, CTRL_TOR, GET_POS, GET_VEL, GET_CURR, GET_TEMP, SET_SPE and SET_TOR; it declares no stop, disable, brake or torque-off opcode. | upstream_code | firmware/main/firmware.ino:26-37 |
| The firmware handles CTRL_POS by switching to position mode when needed and calling SyncWritePosEx with the per-servo speed, acceleration and torque limits; it does not acknowledge the frame. | upstream_code | firmware/main/firmware.ino:517-546 |
| The firmware handles CTRL_TOR by raising each torque magnitude to at least HOLD_MAG, signing it toward the grasp direction and writing it in torque mode. | upstream_code | firmware/main/firmware.ino:548-584 |
| While homing is busy the firmware loop reads and discards every host byte. | upstream_code | firmware/main/firmware.ino:687-692 |
| The ROS 2 node creates subscriptions on the right/left joint_control or actuator_control topics, by control_space, and publishers on the right/left actuator_states topics. | upstream_code | ros2/src/aero_hand_open/aero_hand_open/aero_hand_node.py:60-130 |
| LICENSE.md licenses the firmware and SDK under Apache-2.0 and the hardware design files and documentation under CC BY-NC-SA 4.0. | vendor_doc | LICENSE.md:9-10 |

## Scope and card deviation

The card is `family:ros` with `RosDriver`. The confirmed surfaces are the hardware SDK class
(`aero_open_sdk.aero_hand:AeroHand`, the card's first entry symbol), the ROS 2 topic node, and the MuJoCo/RL
environments. The ROS 2 node exposes only four control subscriptions and two state publications
(`aero_hand_node.py:60-130`); it has no stop, pause, reset or safe-state service or action, so a RosDriver over it
could not provide the independent safe-state path the safety contract requires and could not expose the SDK's
calibration, speed or torque commands. The package therefore uses a direct Driver over the SDK class. This is a
deliberate deviation from the card helper, recorded in `RESULT.json`; the card's `task.json` was not edited.

Served scope: five feedback reads (actuations, compact joint positions, actuator speeds, currents, temperatures);
two motion extensions (`x-cap.tetheria.joint_position.v1` with 16 joint targets in degrees and
`x-cap.tetheria.actuation.v1` with 7 direct actuations in degrees); the per-actuator `speed` and `max_torque`
writes; the native `x-cap.tetheria.calibrate_mid.v1`; and the input-free `x-cap.tetheria.open_hand.v1` open command
(an ordinary action since the model review, not a safe state).

NOT COVERED: the ROS 2 topic node and its remapping/QoS, `send_homing` (a blocking ACK wait of up to 175 s with no
cancellation check), `run_trajectory` (an upstream `time.sleep` loop with no cancellation check), `set_id` (a
one-time servo re-identification command), `trim_servo`, `ctrl_torque` (torque mode), `get_forward_kinematics` and
`get_joint_positions` (both raise `NotImplementedError` upstream), the MuJoCo/RL environments, and the firmware's
thermal or soft-limit behavior. The firmware and ROS 2 packages were not run. The card's four MuJoCo playground
entry symbols and its MJCF models live in the git submodules `sim_rl/mujoco_playground` and `sim_rl/simulation`
(`.gitmodules`), which are not part of the pinned parent commit (model review).

## Safety

The hand is a tendon-driven manipulator with a pinch hazard, so the package is R2 even though the card floor is R1.
The native API has no stop, disable, brake or torque-off command: the firmware opcode table at
`firmware/main/firmware.ino:26-37` has no such code, CTRL_TOR keeps at least `HOLD_MAG` toward the grasp
(`firmware.ino:548-584`), and the SDK class has no such method. `open_hand` writes the upstream joint lower limits,
the pose of the SDK GUI's "Set to Open Position" button (`gui.py:155`, `:481-491`). That is a finger motion, not a
hold or a stop: CTRL_POS is written without a frame acknowledgement (`firmware.ino:517-546`), the firmware discards
every host byte while homing is busy (`firmware.ino:687-692`), and `set_joint_positions` prints and swallows a
`SerialTimeoutException` (`aero_hand.py:163-167`), so a completed call does not prove a write.

Model review (2026-11-05): the author had declared `open_hand` as the `safe_state=True` action and the e-stop as the
same unacknowledged write, so the runtime reported an achieved safe state. That is the unacknowledged-setpoint stop
the review rules do not accept. `open_hand` is now an ordinary action, and the `@estop` sends the open command and
then raises `MHS.SAFETY.SAFE_STATE_UNREACHED`, so the latch stays held. With no safe-state action and no
`estop_physical_ref`, the hardware view of this R2 device fails G3 (SAFE-045), as for the other hardware packages
without a source-backed stop; the package is blocked (`NO_HARDWARE_FREE_PATH`). The hardware backend stays
unreachable until a human sets `reviewed_by` in `driver.lock.json`.

## Fidelity contract (fake)

The fake backend is a ROS-free Python double of the `AeroHand` public surface, not a recording and not the SDK.
It opens no serial port, parses no firmware frame, runs no tendon model or physics, and does not reproduce the
device's timing. Its start positions, limits, speed/torque settings, current and temperature samples and
calibration replies are all placeholders. It clamps commands to the same constant arrays as the SDK, expands a
7-joint command to 16 with the upstream mapping, and projects the last command into the read arrays so writes have
an observable effect; that projection is analytic test data, not the tendon kinematics. The fake has no fidelity
block in `driver.py` because the driver class is `mode = "hardware"`; the gate serves the fake as a simulated
backend and `RESULT.json` records the F0 contract.

## Tags

`tetheria`, `chestnut-robotics`, `aero hand`, `dexterous hand`, `tendon-driven`, `serial`, `sdk`, `joint position`,
`actuation`
