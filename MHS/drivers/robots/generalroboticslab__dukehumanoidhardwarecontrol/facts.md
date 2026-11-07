# Facts and tags for gh.generalroboticslab/dukehumanoidhardwarecontrol

Every fact cites the pinned clone at commit `3a9c3cd4c8daf6b3ffe2e41768360d0515f2df55`: `upstream_code` is a line of
the clone's code, `vendor_doc` a text file of the clone (its README or a source README).  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README lists biped_controller.py as the main entrance for the biped controller | vendor_doc | README.md:30 |
| The constructor starts the sensor collector, waits for the first sample, and starts the motor loop on interface enp3s0 | upstream_code | biped_controller.py:162-189 |
| The constructor creates MotorController('enp3s0', CONTROL_MODE.CYCLIC_SYNC_TORQUE, 20, 1000.0) and calls run() | upstream_code | biped_controller.py:186-189 |
| step() calls update_command(), update_observation(), check_termination() and compute_action(), then writes motor.target_dof_position | upstream_code | biped_controller.py:249-263 |
| update_command() copies the cmd array from the UDP receiver into self.commands and reads the reset flag | upstream_code | biped_controller.py:315-322 |
| The gamepad's command maxima are lin_vel_x_max 0.3, lin_vel_y_max 0.25 and ang_vel_z_max 0.2 | upstream_code | gamepad.py:6-8 |
| The gamepad creates a DataPublisher for udp://localhost:9871 with msgpack and broadcast | upstream_code | gamepad.py:14-15 |
| The gamepad's Y axis scales lin_vel_x_max, X scales ang_vel_z_max and the third axis scales lin_vel_y_max | upstream_code | gamepad.py:43-50 |
| The gamepad builds and publishes the cmd and reset message | upstream_code | gamepad.py:56-62 |
| BipedController.shutdown() sets should_terminate, stops the sensor collector and stops the command receiver | upstream_code | biped_controller.py:426-430 |
| The C++ loop runs while should_terminate is false, then leaves operational state, requests EtherCAT INIT and closes the socket | upstream_code | src/ethercat_motor.h:773-798 |
| check_termination() stops the motors, calls shutdown() and exit() when the base tilt exceeds 45 degrees or should_reset is set | upstream_code | biped_controller.py:240-247 |
| set_should_terminate stores the flag the C++ run loop reads | upstream_code | src/ethercat_motor.h:498-501 |
| set_max_torque stores the torque limit vector of the motors | upstream_code | src/ethercat_motor.h:361-364 |
| The motor loop writes each motor's max_torque into its maximal-torque PDO entry | upstream_code | src/ethercat_motor.h:957 |
| SerialDataCollector imports Process from multiprocessing | upstream_code | sensor_controller.py:6 |
| SerialDataCollector.start() runs read_loop in a Process; stop() sets running to False and joins the process; read_loop runs while running is true | upstream_code | sensor_controller.py:129-140 |
| MotorController sets num_dof to 10 | upstream_code | motor_controller.py:35 |
| MotorController.dof_pos returns dof_position, dof_vel returns dof_velocity_filtered and dof_current returns actual_torque | upstream_code | motor_controller.py:96-120 |
| dof_position and target_dof_position are in rad and dof_velocity and dof_velocity_filtered in rad/s | upstream_code | src/ethercat_motor.h:266-269 |
| actual_torque is in A | upstream_code | src/ethercat_motor.h:238 |
| The simple test states target position in rad in csp mode and target velocity in rad/s in csv mode | upstream_code | src/Readme.md:8-9 |
| get_latest_data() returns force_measurement, contact, ang_vel, base_quat, gravity_vec and sps | upstream_code | sensor_controller.py:222-240 |
| force_measurement is the raw four-value load-cell reading; contact is true when the sum of a foot's two values exceeds the two zero-contact minima by the threshold 400 | upstream_code | sensor_controller.py:186-189 |
| The zero-contact minima are 730, 1020, 1000 and 780 raw counts and the threshold is 400 | upstream_code | sensor_controller.py:93-96 |
| sps is 100 divided by the timestamp-buffer span, in samples per second | upstream_code | sensor_controller.py:202 |
| The gravity vector is divided by GRAVITY before it is sent | upstream_code | teensy_comm/teensy_comm.ino:764-766 |
| The C++ header says to find the interface name with ifconfig | upstream_code | src/ethercat_motor.h:282 |
| motor_controller.py opens motor_config.yaml in the working directory | upstream_code | motor_controller.py:67-70 |
| The constructor loads checkpoint/baseline/policy.onnx and config.yaml relative to the working directory | upstream_code | biped_controller.py:34-44 |
| The README runs the controller from the clone root and the gamepad in another terminal | vendor_doc | README.md:198-205 |

Limits: the clone states no envelope for the three command values, so every command field is
`Limit.operator_required` and every write is refused with `MHS.SAFETY.LIMITS_UNSET` until a site overlay fills it.
`site-limits.example.json` repeats the gamepad teleop scaling only as an example, marked as an operator choice; it is
not a device fact.

| path | bound | source |
|---|---|---|
| `command_forward` | operator_required | the clone copies the UDP cmd array; the gamepad scaling (gamepad.py:6-8) is teleop, not a device envelope |
| `command_lateral` | operator_required | same |
| `command_yaw` | operator_required | same |

Safety: the stop is the motor part of the upstream's own termination (`check_termination()`,
biped_controller.py:240-247): every motor's torque limit is set to 0, which the C++ loop writes to each drive's
maximal torque every cycle (src/ethercat_motor.h:361-364, 957), and the motor loop's terminate flag is set, so the
loop leaves EtherCAT operational state, requests INIT and closes the socket (src/ethercat_motor.h:498-501, 773-798);
the three command values are then set to 0.  A biped without joint torque falls unless it is supported.  The clone documents no independent hardware e-stop, so
`x-cap.generalroboticslab.stop.v1` is declared `safe_state=True`, and the e-stop and the teardown make the same two
calls.  `BipedController.shutdown()` is not called: after the motor flag it stops the sensor collector, whose
`stop()` clears a flag in the calling process and joins the collector's `multiprocessing` child without a timeout,
and the child never sees the flag (sensor_controller.py:6, 129-140), so `shutdown()` does not return.

Upstream behaviour the driver cannot change: `check_termination()` inside `step()` (a base tilt above 45 degrees, or
a reset flag) zeroes the torque and then waits in the same `shutdown()` before its `exit()`, so that step action does
not return; and BipedController takes `cmd` arrays and the reset flag from any sender on UDP port 9871
(biped_controller.py:173-175, 315-322), so a datagram overwrites the command values this driver writes.

Coverage: reads of the 10 joint positions/velocities/currents, the motor target, the four raw load-cell values, the
two contact flags, the filtered angular velocity, the gravity vector, the base quaternion, the sample rate and the
three upstream command values; writes of the three command values; one control step; the stop/safe state; the e-stop.
Not covered: the learned policy itself, the EtherCAT transport, the Teensy firmware and the physical e-stop.

The fake's numbers are test data, not facts.  Its public method is `step` of BipedController, its state attributes
are the names that class assigns, and its `motor` has the two Motor setters the stop calls.

Tags: humanoid, biped, robot, 10 dof, ethercat, teensy, telemetry, velocity command
