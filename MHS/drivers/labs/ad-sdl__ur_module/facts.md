# Facts and limits for gh.ad-sdl/ur_module

Every fact cites the pinned clone at commit `75f1c5fe53c70bccbe1f37eeeb55a382133e623e`; the path is from the clone
root (the clone is src-layout, so the library lives under `src/ur_interface/`). The same facts are in `driver.py`
`facts = [...]`; `reference.json` is generated from the driver, and the table below from `reference.json`.

| fact | source | ref |
|---|---|---|
| The UR dashboard server listens on TCP port 29999 and a command line ends with a newline | upstream_code | src/ur_interface/ur_dashboard.py:12-15 |
| UR_DASHBOARD.connect opens a TCP socket with a 5 s timeout and sets connection_error on a socket error | upstream_code | src/ur_interface/ur_dashboard.py:42-52 |
| UR_DASHBOARD.send_command sends the command and a newline, waits response_delay (0.1 s by default), reads up to 4096 bytes, prints and returns the stripped answer; it catches every exception, prints it and returns None | upstream_code | src/ur_interface/ur_dashboard.py:58-87 |
| UR_DASHBOARD.get_robot_mode splits the 'robotmode' answer at spaces and returns the second word, cut at a newline, or the word list when there is no second word | upstream_code | src/ur_interface/ur_dashboard.py:136-149 |
| UR_DASHBOARD.get_safety_status splits the 'safetystatus' answer at spaces and returns the second word, cut at a newline, or the word list when there is no second word | upstream_code | src/ur_interface/ur_dashboard.py:222-237 |
| UR.get_movement_state reads getj() and returns (state, joint values): READY when there is no earlier sample or the norm of the change from it is below 1e-3, otherwise BUSY; it stores the new sample and raises URMovementError on any failure | upstream_code | src/ur_interface/ur.py:189-210 |
| UR.home takes a six-joint location and sends movej (movel when linear_motion is true) with the class velocity and acceleration; it returns None and turns any exception into URMovementError | upstream_code | src/ur_interface/ur.py:212-230 |
| The README example homes the arm with robot.home([0, -1.57, 0, -1.57, 0, 0]) | upstream_code | README.md:65-69 |
| keyboard_control.py documents its joint step as a step size for joint rotations in radians | upstream_code | src/keyboard_control.py:50 |
| keyboard_control.step_joint adds the joint step to one getj() value and sends the result with movej | upstream_code | src/keyboard_control.py:85-91 |
| keyboard_control.py stops the robot on exit with ur_connection.stopl(2) | upstream_code | src/keyboard_control.py:270-275 |
| UR.run_urp_program transfers a given local file, loads /programs/<program_name> and calls ur_dashboard.run_program() | upstream_code | src/ur_interface/ur.py:955-967 |
| UR.run_urp_program polls every 3 s while program_status is BUSY and counts a poll only when get_movement_state() == 'READY'; six such polls in a row end the loop | upstream_code | src/ur_interface/ur.py:972-981 |
| UR_DASHBOARD.pause_program sends 'pause' and stop_program sends 'stop' over the dashboard socket | upstream_code | src/ur_interface/ur_dashboard.py:364-376 |
| UR_DASHBOARD.power_off sends 'power off'; brake_release sends 'brake release' and then sleeps 20 s | upstream_code | src/ur_interface/ur_dashboard.py:172-186 |
| UR_DASHBOARD.initialize returns at once after a connection error; otherwise it unlocks a protective stop, or closes the safety popup and restarts safety when the safety status lacks NORMAL, switches a MANUAL operational mode to automatic, returns when the mode is RUNNING with NORMAL safety, brake-releases a robot in POWER_OFF, BOOTING, POWER_ON or IDLE, and calls itself again | upstream_code | src/ur_interface/ur_dashboard.py:96-134 |
| UR_DASHBOARD.restart_safety sends 'restart safety', sleeps 10 s, reconnects the socket and brake-releases | upstream_code | src/ur_interface/ur_dashboard.py:210-220 |
| The upstream REST node's emergency stop calls ur_dashboard.power_off(); its safety_stop calls ur_dashboard.stop_program() | upstream_code | src/ur_rest_node.py:800-819 |
| UR raises TypeError for an empty hostname, then creates UR_DASHBOARD and the URX Connection, sets the TCP to tcp_pose, applies a base reference frame when one is given and samples the movement state | upstream_code | src/ur_interface/ur.py:92-122 |
| UR_DASHBOARD's constructor connects, raises when it cannot, waits 3 s and calls initialize() | upstream_code | src/ur_interface/ur_dashboard.py:36-40 |
| The clone's LICENSE is the MIT licence of UChicago Argonne, LLC for the software named Modular Autonomous Discovery for Science (MADSci) | upstream_code | LICENSE:1-9 |

## Limits

`cap.motion.joint_position.v1` has one operator-required input: the six-joint target in radians (the README example
`robot.home([0, -1.57, 0, -1.57, 0, 0])` and the keyboard tool's joint step, documented in radians and added to a
`getj()` value before `movej`, use radians). No text file of the clone states this arm's joint travel range (the
kinematics module holds only DH parameters), so the driver refuses every move with `MHS.SAFETY.LIMITS_UNSET` until the
operator supplies the envelope. `site-limits.example.json` shows an example (a symmetric +/-3.0 rad box, marked as
operator example data); it is not a claim about any real UR joint. The driver passes the values to `UR.home`
unchanged.

## Dashboard answers

`UR_DASHBOARD.send_command` catches every exception, prints it and returns None, so no upstream dashboard command
raises. The driver treats a None answer as a failed receipt everywhere (a read included: the read fails instead of
dropping the field). The success answers it accepts for `pause` ('Pausing program') and `stop` ('Stopped') are those
of the vendor manual shipped in the clone (`resources/DashboardServer_e-Series.pdf`, page 6); G4 cannot read a PDF,
so they are implementation constants, not facts. The same manual (pages 6 and 8) lists 'Powering off' for
`power off` and 'Brake releasing' for `brake release`, and marks `stop`, `pause`, `power on`, `power off`,
`brake release`, `unlock protective stop`, `close safety popup` and `restart safety` as remote-control commands; it
warns to inspect the cause of a protective stop before unlocking it and to check the error log before restarting
safety, and says that `set operational mode` disables PolyScope's mode switching and user password.

## Safety

- E-stop: `UR_DASHBOARD.power_off()`, the upstream REST node's `e_stop`. It fails when the dashboard does not
  answer.
- Safe state: the input-free safe-state action `x-cap.ad-sdl.power_off.v1` sends `power off` again and succeeds only
  when a fresh `robotmode` read returns POWER_OFF within 5 s (an implementation bound, not a device fact); otherwise
  the e-stop is `SAFE_STATE_UNREACHED` and the latch stays. POWER_OFF is the mode from which the upstream
  `initialize()` recovers by `brake release`. The program state and any attached tool are not checked.
- Reset: there is no `@reset` hook; the reset releases the latch only and the arm stays powered off.
- Re-enable: `x-cap.ad-sdl.power_on.v1` (`reenable=True`, refused while latched) needs a permit, a human approval,
  for every call. Only with safety status NORMAL and a robot in POWER_OFF, BOOTING, POWER_ON or IDLE does it send
  `brake release` (the upstream waits 20 s after it), and it succeeds only when a fresh read returns RUNNING. It never
  runs the rest of `initialize()`: no protective-stop unlock, no safety restart, no operational-mode switch.
- `x-cap.ad-sdl.stop_program.v1` (the upstream node's `safety_stop`) is an ordinary, latched command, not the
  e-stop: the clone does not say whether the dashboard `stop` ends a URScript motion that URX sent.
- No independent hardware stop is cited (the manual's emergency-stop safety states are in a PDF), so
  `estop_physical_ref` is unset; the safe-state action satisfies SAFE-045 for the contract.

## Hardware construction

Opening the hardware backend runs the upstream constructor: `UR_DASHBOARD` connects, waits 3 s and runs
`initialize()`, which unlocks a protective stop, restarts safety whenever the safety status lacks NORMAL (the
emergency-stop states included), switches MANUAL to automatic and brake-releases a powered-off arm, recursing until it
runs; then the URX connection opens and the TCP is set. The loader opens the backend when the endpoint starts, so
every start (a restart with a restored latch included) may do all of that before any further operator action. Every
dashboard command also prints to stdout, which would corrupt an MHS server talking over stdio.

## Licence and publication

The clone's `LICENSE` is UChicago Argonne's MIT licence. The clone also holds third-party files: the Universal Robots
manual `resources/DashboardServer_e-Series.pdf` ("Copyright 2009-2022 by Universal Robots A/S. All rights reserved";
"shall not be reproduced in whole or in part without prior written approval of Universal Robots A/S"), a Robotiq
proof-of-concept report `resources/PoC -Argonne National Laboratory.pdf` ("© Robotiq, 2018"), five Robotiq URCap
binaries under `src/ur_interface/scripts/urcaps/` and a model file `src/ur_interface/ur_tools/best.pt` whose origin
the clone does not state. The UR and Robotiq files carry their own copyright, not the MIT grant; the owner decides
publication.

## Not covered

`UR.run_urp_program` (it transfers, loads and plays any program, and its polling loop never ends because it
compares a tuple with a string), the tool workflows (gripper, pipette, screwdriver, droplet), `UR.set_digital_io`,
the operational-mode write, Cartesian motion, the camera path and the keyboard tool's URX `stopl(2)` stop are not
bound. The hardware path (URX and the dashboard socket) was never run; the fake is an analytic in-memory object (F0),
not a recording or the upstream simulator.

Tags: universal-robots, ur, robot-arm, urx, dashboard
