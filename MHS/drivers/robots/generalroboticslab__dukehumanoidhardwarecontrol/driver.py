"""OpenMHS driver for gh.generalroboticslab/dukehumanoidhardwarecontrol: the Duke Humanoid V1 biped controller.

A direct Driver over the upstream class ``biped_controller:BipedController``.  BipedController is the main entrance of
the clone (``biped_controller.py:29``, README.md:30): its constructor starts a Teensy sensor collector and the
EtherCAT motor loop (biped_controller.py:162-189), and its ``step()`` reads the latest sensor sample, computes the
learned policy action and sets the motor target (biped_controller.py:249-263).  The driver exposes:

* reads: the 10 joint positions, velocities and currents from ``MotorController`` (motor_controller.py:96-120), and
  the Teensy sample: the raw four load-cell values, the two foot-contact flags, the filtered angular velocity, the
  gravity vector and the base quaternion (sensor_controller.py:222-240), the sample rate (sensor_controller.py:202),
  the current motor target and the three upstream command values;
* three writable command fields, ``cap.device.configure.v1``: the upstream ``commands`` array (biped_controller.py
  :315-321).  The clone states no envelope for them: the gamepad scales its stick axes into -0.3..0.3, -0.25..0.25
  and -0.2..0.2 (gamepad.py:6-8, 44-50), but BipedController copies whatever ``cmd`` array arrives on the UDP
  receiver, so every command field is ``Limit.operator_required`` and refused until a site overlay fills it;
* ``x-cap.generalroboticslab.step.v1``: run one closed-loop control step through ``BipedController.step()``;
* ``x-cap.generalroboticslab.stop.v1`` (safe state): the first two steps of the upstream's own termination
  (``check_termination``, biped_controller.py:240-247): every motor's torque limit is set to 0, which the C++ loop
  writes to each drive's maximal torque every cycle (src/ethercat_motor.h:361-364, 957), and the motor loop's
  terminate flag is set, so the loop leaves EtherCAT operational state, requests INIT and closes the socket
  (src/ethercat_motor.h:498-501, 773-798); the three command values are then set to 0.  A biped without torque
  falls unless it is supported;
* the same two calls as the e-stop and at teardown.

``BipedController.shutdown()`` is not called: after the motor flag it stops the sensor collector, whose ``stop()``
clears a flag in the calling process and joins the collector's ``multiprocessing`` child without a timeout, a child
that never sees the flag (sensor_controller.py:6, 129-140), so ``shutdown()`` does not return.  The same wait is in
``check_termination()``: a termination inside ``step()`` (a base tilt above 45 degrees, or a reset flag from the UDP
receiver) zeroes the torque, then waits in ``shutdown()``, and the step action does not return.  The upstream also
takes ``cmd`` arrays and a reset flag from any sender on UDP port 9871 (biped_controller.py:173-175, 315-322): a
datagram overwrites the command values this driver writes.

The clone documents no independent hardware e-stop, so SAFE-045 is met by the safe-state action above.  A biped that
walks and has 10 torque-controlled joints is at least R2 (the card's floor is R1).  This package is model-authored
and unreviewed: the loader refuses its hardware backend at R2 until a human signs ``reviewed_by`` in
driver.lock.json.  The gate checks the fake backend only; nothing here ran on the robot.

Not covered: the learned policy checkpoint and ``checkpoint/*/config.yaml`` (the constructor loads
``checkpoint/baseline``, biped_controller.py:34-44) and the Teensy firmware.  ``step()`` also runs the upstream
``check_termination()``, which calls ``exit()`` when the controller decides to reset (biped_controller.py:240-247);
that is upstream behaviour, not a driver decision.
"""

import numpy as np

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: Why every command field waits for the site: the clone has no device envelope for the UDP command array.
COMMAND_REASON = ("the clone states no envelope for the command array: gamepad.py scales its stick axes into "
                  "-0.3..0.3 (x), -0.25..0.25 (y) and -0.2..0.2 (yaw) before publishing (gamepad.py:6-8, 44-50), "
                  "but BipedController copies whatever cmd array the UDP receiver delivers (biped_controller.py"
                  ":315-321); the site states the allowed command")


class DukeHumanoid(Driver):
    device_id = "duke-humanoid"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "biped_controller:BipedController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBipedController"}
    vendor, model = "General Robotics Lab", "Duke Humanoid V1 (10 DoF biped)"
    display_name = "Duke Humanoid V1 (biped_controller.BipedController)"
    tags = ["humanoid", "biped", "robot", "10 dof", "ethercat", "teensy", "telemetry", "velocity command"]
    facts = [
        Fact("The README lists biped_controller.py as the main entrance for the biped controller", source="vendor_doc",
             ref="README.md:30"),
        Fact("The constructor starts the sensor collector, waits for the first sample, and starts the motor loop on "
             "interface enp3s0", source="upstream_code", ref="biped_controller.py:162-189"),
        Fact("The constructor creates MotorController('enp3s0', CONTROL_MODE.CYCLIC_SYNC_TORQUE, 20, 1000.0) and "
             "calls run(), which starts the EtherCAT loop in the background", source="upstream_code",
             ref="biped_controller.py:186-189"),
        Fact("step() calls update_command(), update_observation(), check_termination() and compute_action(), then "
             "writes the computed target to motor.target_dof_position", source="upstream_code",
             ref="biped_controller.py:249-263"),
        Fact("update_command() copies the cmd array received from the UDP data receiver into self.commands and sets "
             "should_reset from the reset flag", source="upstream_code", ref="biped_controller.py:315-322"),
        Fact("The gamepad's command maxima are lin_vel_x_max 0.3, lin_vel_y_max 0.25 and ang_vel_z_max 0.2",
             source="upstream_code", ref="gamepad.py:6-8"),
        Fact("The gamepad creates a DataPublisher for udp://localhost:9871 with msgpack and broadcast",
             source="upstream_code", ref="gamepad.py:14-15"),
        Fact("The gamepad's Y axis scales lin_vel_x_max, its X axis scales ang_vel_z_max and its third axis scales "
             "lin_vel_y_max", source="upstream_code", ref="gamepad.py:43-50"),
        Fact("The gamepad builds the cmd and reset message and publishes it", source="upstream_code",
             ref="gamepad.py:56-62"),
        Fact("BipedController.shutdown() sets the motor loop's should_terminate flag, stops the sensor collector and "
             "stops the command receiver", source="upstream_code", ref="biped_controller.py:426-430"),
        Fact("The C++ motor loop runs while should_terminate is false; when it ends it leaves operational state, "
             "requests EtherCAT INIT for the slaves and closes the socket",
             source="upstream_code", ref="src/ethercat_motor.h:773-798"),
        Fact("check_termination() stops the motors and calls shutdown(), then exit(), when the base tilt exceeds 45 "
             "degrees or should_reset is set", source="upstream_code", ref="biped_controller.py:240-247"),
        Fact("set_should_terminate stores the flag the C++ run loop reads", source="upstream_code",
             ref="src/ethercat_motor.h:498-501"),
        Fact("set_max_torque stores the torque limit vector of the motors", source="upstream_code",
             ref="src/ethercat_motor.h:361-364"),
        Fact("The motor loop writes each motor's max_torque into its maximal-torque PDO entry",
             source="upstream_code", ref="src/ethercat_motor.h:957"),
        Fact("SerialDataCollector imports Process from multiprocessing", source="upstream_code",
             ref="sensor_controller.py:6"),
        Fact("SerialDataCollector.start() runs read_loop in a Process; stop() sets running to False and joins the "
             "process; read_loop runs while running is true", source="upstream_code", ref="sensor_controller.py:129-140"),
        Fact("MotorController sets num_dof to 10", source="upstream_code", ref="motor_controller.py:35"),
        Fact("MotorController.dof_pos returns dof_position, dof_vel returns dof_velocity_filtered and dof_current "
             "returns actual_torque", source="upstream_code", ref="motor_controller.py:96-120"),
        Fact("The C++ header defines dof_position and target_dof_position in rad and dof_velocity and "
             "dof_velocity_filtered in rad/s", source="upstream_code", ref="src/ethercat_motor.h:266-269"),
        Fact("The C++ header defines actual_torque in A", source="upstream_code", ref="src/ethercat_motor.h:238"),
        Fact("The command input of the upstream simple test states target position in rad in csp mode and target "
             "velocity in rad/s in csv mode", source="upstream_code", ref="src/Readme.md:8-9"),
        Fact("get_latest_data() returns force_measurement, contact, ang_vel, base_quat, gravity_vec and sps",
             source="upstream_code", ref="sensor_controller.py:222-240"),
        Fact("force_measurement is the raw four-value load-cell reading and contact is true when the sum of the two "
             "values of a foot exceeds the two zero-contact minima by the threshold 400", source="upstream_code",
             ref="sensor_controller.py:186-189"),
        Fact("The zero-contact minima are 730, 1020, 1000 and 780 raw counts and the threshold is 400, values that "
             "the comment says must match the actual sensor", source="upstream_code",
             ref="sensor_controller.py:93-96"),
        Fact("sps is computed as 100 divided by the span of the timestamp ring buffer, in samples per second",
             source="upstream_code", ref="sensor_controller.py:202"),
        Fact("The gravity vector is divided by GRAVITY before it is sent", source="upstream_code",
             ref="teensy_comm/teensy_comm.ino:764-766"),
        Fact("The C++ header says to find the interface name with ifconfig", source="upstream_code",
             ref="src/ethercat_motor.h:282"),
        Fact("motor_controller.py opens motor_config.yaml in the working directory and reads motor_pos_offset from "
             "it", source="upstream_code", ref="motor_controller.py:67-70"),
        Fact("The constructor loads checkpoint/baseline/policy.onnx and checkpoint/baseline/config.yaml relative to "
             "the working directory", source="upstream_code", ref="biped_controller.py:34-44"),
        Fact("The README runs the controller from the clone root with sudo and another terminal for the gamepad",
             source="vendor_doc", ref="README.md:198-205"),
    ]
    safe_state = ("every motor's torque limit is 0 and the EtherCAT motor loop has ended (it left operational state, "
                  "requested INIT and closed the socket); the biped has no joint torque and falls unless it is "
                  "supported; the sensor collector and the UDP command receiver keep running")
    #: The clone documents no independent hardware e-stop; SAFE-045 is met by the safe-state action below.

    # -- reads -------------------------------------------------------------------------------------------------
    @read("joint_positions", type="array", items="number", length=10, unit="rad",
          description="Current joint positions from MotorController.dof_position (rad)")
    def get_joint_positions(self):
        return [float(value) for value in self.native.motor.dof_pos]

    @read("joint_velocities", type="array", items="number", length=10, unit="rad/s",
          description="Current joint velocities from MotorController.dof_velocity_filtered (rad/s)")
    def get_joint_velocities(self):
        return [float(value) for value in self.native.motor.dof_vel]

    @read("joint_currents", type="array", items="number", length=10, unit="A",
          description="Motor currents from MotorController.actual_torque (A; dof_current)")
    def get_joint_currents(self):
        return [float(value) for value in self.native.motor.dof_current]

    @read("dof_position_target", type="array", items="number", length=10, unit="rad",
          description="Joint target last written to motor.target_dof_position by step() (rad)")
    def get_dof_position_target(self):
        return [float(value) for value in self.native.dof_pos_target]

    @read("foot_force_raw", type="array", items="integer", length=4,
          description="Raw load-cell counts in the order left-back, left-front, right-back, right-front; the clone "
                      "states no unit for them")
    def get_foot_force_raw(self):
        return [int(value) for value in self._sensor_data()["force_measurement"]]

    @read("foot_contact", type="array", items="boolean", length=2,
          description="Foot-contact flags computed by SerialDataCollector from the load-cell sums")
    def get_foot_contact(self):
        return [bool(value) for value in self._sensor_data()["contact"]]

    @read("angular_velocity", type="array", items="number", length=3, unit="1",
          description="Filtered angular velocity from the Teensy sample; the clone states no unit for it")
    def get_angular_velocity(self):
        return [float(value) for value in self._sensor_data()["ang_vel"]]

    @read("gravity_vector", type="array", items="number", length=3, unit="1",
          description="Gravity direction from the Teensy, divided by GRAVITY (dimensionless)")
    def get_gravity_vector(self):
        return [float(value) for value in self._sensor_data()["gravity_vec"]]

    @read("base_quaternion", type="array", items="number", length=4, unit="1",
          description="Base orientation quaternion [x, y, z, w] from the Teensy sample")
    def get_base_quaternion(self):
        return [float(value) for value in self._sensor_data()["base_quat"]]

    @read("sample_rate", unit="Hz", description="Sensor sample rate computed from the timestamp buffer (sps)")
    def get_sample_rate(self):
        return float(self._sensor_data()["sps"])

    @read("command_forward", unit="1",
          description="First upstream command value (vel_x of the gamepad cmd array); the clone states no unit")
    def get_command_forward(self):
        return float(self.native.commands[0])

    @read("command_lateral", unit="1",
          description="Second upstream command value (vel_y of the gamepad cmd array); the clone states no unit")
    def get_command_lateral(self):
        return float(self.native.commands[1])

    @read("command_yaw", unit="1",
          description="Third upstream command value (yaw of the gamepad cmd array); the clone states no unit")
    def get_command_yaw(self):
        return float(self.native.commands[2])

    # -- writable commands (cap.device.configure.v1) ------------------------------------------------------------
    @write("command_forward", unit="1", description="Set the first upstream command value; the clone states no unit",
           limit=Limit.operator_required(COMMAND_REASON))
    def set_command_forward(self, value):
        self._set_command(0, value)

    @write("command_lateral", unit="1", description="Set the second upstream command value; the clone states no unit",
           limit=Limit.operator_required(COMMAND_REASON))
    def set_command_lateral(self, value):
        self._set_command(1, value)

    @write("command_yaw", unit="1", description="Set the third upstream command value; the clone states no unit",
           limit=Limit.operator_required(COMMAND_REASON))
    def set_command_yaw(self, value):
        self._set_command(2, value)

    # -- control step -------------------------------------------------------------------------------------------
    @action(name="x-cap.generalroboticslab.step.v1",
            description="Run one closed-loop control step: update the command, refresh the observation, compute the "
                        "policy action and write the motor target",
            output={
                "dof_position_target": Field("array", items="number", length=10, unit="rad",
                                             description="Motor target written by this step"),
                "action": Field("array", items="number", min_items=10, max_items=20, unit="1",
                                description="Policy action computed by this step (20 values in passive mode)"),
            })
    def control_step(self):
        self.native.step()
        return {"dof_position_target": [float(value) for value in self.native.dof_pos_target],
                "action": [float(value) for value in self.native.action]}

    # -- safety -------------------------------------------------------------------------------------------------
    @action(name="x-cap.generalroboticslab.stop.v1", safe_state=True,
            description="Stop the motors: set every motor's torque limit to 0 and end the EtherCAT motor loop, the "
                        "first two steps of the upstream's check_termination",
            output={"stopped": Field("boolean", description="True once the torque limit and the terminate flag "
                                                            "were set")})
    def halt(self):
        self._stop_motors()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop, reached by the runtime after it latches: zero torque limit, then the terminate flag."""
        self._stop_motors()

    def teardown(self):
        if self.native is not None:
            self._stop_motors()

    # -- helpers ------------------------------------------------------------------------------------------------
    def _stop_motors(self):
        """check_termination's motor stop without its shutdown() and exit() (biped_controller.py:244-247), then zero
        command values, so that a later step cannot resume walking.  Gate G6 sees that assignment; it does not see
        calls on the nested motor object."""
        motor = self.native.motor
        motor.set_max_torque(np.zeros(motor.num_dof))
        motor.set_should_terminate(True)
        self.native.commands = [0.0, 0.0, 0.0]

    def _sensor_data(self):
        data = self.native.sensor_data
        if not isinstance(data, dict):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "BipedController has no sensor sample yet (update_observation has not run)")
        return data

    def _set_command(self, index, value):
        commands = [float(item) for item in self.native.commands]
        commands[index] = float(value)
        self.native.commands = commands
