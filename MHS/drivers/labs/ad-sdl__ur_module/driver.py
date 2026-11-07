"""OpenMHS driver for gh.ad-sdl/ur_module: a Universal Robots arm through ``ur_interface.ur:UR``.

A direct decorated Driver over the upstream Python object.  ``UR`` owns a URX connection (``ur_connection``) and a
``UR_DASHBOARD`` object (``ur_dashboard``); the driver reads the arm through both and moves it through ``UR.home``
(a blocking URX ``movej``).  The gate never imports the upstream package; the fake backend stands in for it and the
hardware backend is unreviewed and refused by the loader at R2.

Dashboard answers.  ``UR_DASHBOARD.send_command`` catches every exception, prints it and returns None
(src/ur_interface/ur_dashboard.py:58-87), so no dashboard command of the upstream raises: a socket error looks like
a silent success.  This driver treats a None answer as a failure everywhere, confirms the stop and the re-enable by
a fresh ``robotmode`` read, and accepts a program pause or stop only when the dashboard answers the success text of
the vendor manual shipped in the clone (resources/DashboardServer_e-Series.pdf, pages 6 and 8).  G4 cannot read a
PDF, so those texts are implementation constants of this driver, not Facts.

Covered here:

* reads: movement state and joint positions from ``UR.get_movement_state``; robot mode, safety status, operational
  mode, loaded program, program state, program run status and remote control from ``UR.ur_dashboard``;
* motion: ``cap.motion.joint_position.v1`` through ``UR.home`` with a six-joint target in radians.  No text file of
  the clone states this arm's joint travel range, so every move is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  operator supplies the joint envelope in ``site-limits.json`` (``site-limits.example.json`` is an example, not a
  statement about any unit);
* program control: pause and stop the loaded URP program through the dashboard.  ``UR.run_urp_program`` is not
  bound: it starts any program, and it compares ``get_movement_state()``, which returns a ``(state, joints)`` tuple
  (src/ur_interface/ur.py:206), with the string ``"READY"`` (src/ur_interface/ur.py:975), so its polling loop never
  ends;
* safety: the native e-stop is the upstream node's emergency stop, ``UR_DASHBOARD.power_off()`` (``URNode.e_stop``,
  src/ur_rest_node.py:800-809); it fails when the dashboard does not answer.  The input-free safe-state action sends
  ``power off`` again and succeeds only when a fresh ``robotmode`` read returns POWER_OFF within
  ``POWER_OFF_WAIT_S``.  The declared re-enable after a reset needs a permit (a human approval) for every call; only
  with safety status NORMAL it sends the dashboard ``brake release`` that the upstream ``initialize()`` uses for a
  robot in POWER_OFF, BOOTING, POWER_ON or IDLE (src/ur_interface/ur_dashboard.py:125-132), then confirms RUNNING
  by a fresh read.  It never runs the rest of ``initialize()``: it does not unlock a protective stop, restart safety
  or switch the operational mode, which the vendor manual leaves to an operator who inspected the cause.

Not covered: the tool workflows (gripper, pipette, screwdriver, droplet), ``UR.set_digital_io``, the operational-mode
write, Cartesian motion, the camera path, URP transfer, load and run, and the keyboard tool's URX ``stopl`` stop.

Every Fact cites a line of the clone at the pinned commit (75f1c5fe53c70bccbe1f37eeeb55a382133e623e).  This package
is model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null), so only the fake backend is run.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: Implementation bound of the wait for POWER_OFF after 'power off'; it is not a device limit or a Fact.
POWER_OFF_WAIT_S = 5.0
#: Pause between two ``robotmode`` reads of that wait (each read already waits the upstream's 0.1 s response delay).
POLL_S = 0.1
#: The robot modes from which the upstream ``initialize()`` brake-releases the arm (ur_dashboard.py:125-132).
BRAKE_RELEASE_MODES = ("POWER_OFF", "BOOTING", "POWER_ON", "IDLE")
#: Success answers of the dashboard manual in the clone (resources/DashboardServer_e-Series.pdf, page 6).
PAUSE_ANSWER = "Pausing program"
STOP_ANSWER = "Stopped"


def _answered(answer, command):
    """The dashboard answer, or a failed receipt when ``send_command`` swallowed an error and returned None."""
    if answer is None:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"no dashboard answer to {command!r}: UR_DASHBOARD.send_command returns None after any "
                           "socket error")
    return answer


class UrModule(Driver):
    device_id = "ur"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "ur_interface.ur:UR"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeUrModule"}
    vendor = "Universal Robots"
    display_name = "Universal Robots arm (ur_interface.ur:UR)"
    tags = ["universal-robots", "ur", "robot-arm", "urx", "dashboard"]
    facts = [
        Fact("The UR dashboard server listens on TCP port 29999 and a command line ends with a newline",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:12-15"),
        Fact("UR_DASHBOARD.connect opens a TCP socket with a 5 s timeout and sets connection_error on a socket error",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:42-52"),
        Fact("UR_DASHBOARD.send_command sends the command and a newline, waits response_delay (0.1 s by default), "
             "reads up to 4096 bytes, prints and returns the stripped answer; it catches every exception, prints it "
             "and returns None",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:58-87"),
        Fact("UR_DASHBOARD.get_robot_mode splits the 'robotmode' answer at spaces and returns the second word, cut at "
             "a newline, or the word list when there is no second word",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:136-149"),
        Fact("UR_DASHBOARD.get_safety_status splits the 'safetystatus' answer at spaces and returns the second word, "
             "cut at a newline, or the word list when there is no second word",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:222-237"),
        Fact("UR.get_movement_state reads getj() and returns (state, joint values): READY when there is no earlier "
             "sample or the norm of the change from it is below 1e-3, otherwise BUSY; it stores the new sample and "
             "raises URMovementError on any failure",
             source="upstream_code", ref="src/ur_interface/ur.py:189-210"),
        Fact("UR.home takes a six-joint location and sends movej (movel when linear_motion is true) with the class "
             "velocity and acceleration; it returns None and turns any exception into URMovementError",
             source="upstream_code", ref="src/ur_interface/ur.py:212-230"),
        Fact("The README example homes the arm with robot.home([0, -1.57, 0, -1.57, 0, 0])",
             source="upstream_code", ref="README.md:65-69"),
        Fact("keyboard_control.py documents its joint step as a step size for joint rotations in radians",
             source="upstream_code", ref="src/keyboard_control.py:50"),
        Fact("keyboard_control.step_joint adds the joint step to one getj() value and sends the result with movej",
             source="upstream_code", ref="src/keyboard_control.py:85-91"),
        Fact("keyboard_control.py stops the robot on exit with ur_connection.stopl(2)",
             source="upstream_code", ref="src/keyboard_control.py:270-275"),
        Fact("UR.run_urp_program transfers a given local file, loads /programs/<program_name> and calls "
             "ur_dashboard.run_program()",
             source="upstream_code", ref="src/ur_interface/ur.py:955-967"),
        Fact("UR.run_urp_program polls every 3 s while program_status is BUSY and counts a poll only when "
             "get_movement_state() == 'READY'; six such polls in a row end the loop",
             source="upstream_code", ref="src/ur_interface/ur.py:972-981"),
        Fact("UR_DASHBOARD.pause_program sends 'pause' and stop_program sends 'stop' over the dashboard socket",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:364-376"),
        Fact("UR_DASHBOARD.power_off sends 'power off'; brake_release sends 'brake release' and then sleeps 20 s",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:172-186"),
        Fact("UR_DASHBOARD.initialize returns at once after a connection error; otherwise it unlocks a protective "
             "stop, or closes the safety popup and restarts safety when the safety status lacks NORMAL, switches a "
             "MANUAL operational mode to automatic, returns when the mode is RUNNING with NORMAL safety, "
             "brake-releases a robot in POWER_OFF, BOOTING, POWER_ON or IDLE, and calls itself again",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:96-134"),
        Fact("UR_DASHBOARD.restart_safety sends 'restart safety', sleeps 10 s, reconnects the socket and "
             "brake-releases",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:210-220"),
        Fact("The upstream REST node's emergency stop calls ur_dashboard.power_off(); its safety_stop calls "
             "ur_dashboard.stop_program()",
             source="upstream_code", ref="src/ur_rest_node.py:800-819"),
        Fact("UR raises TypeError for an empty hostname, then creates UR_DASHBOARD and the URX Connection, sets the "
             "TCP to tcp_pose, applies a base reference frame when one is given and samples the movement state",
             source="upstream_code", ref="src/ur_interface/ur.py:92-122"),
        Fact("UR_DASHBOARD's constructor connects, raises when it cannot, waits 3 s and calls initialize()",
             source="upstream_code", ref="src/ur_interface/ur_dashboard.py:36-40"),
        Fact("The clone's LICENSE is the MIT licence of UChicago Argonne, LLC for the software named Modular "
             "Autonomous Discovery for Science (MADSci)",
             source="upstream_code", ref="LICENSE:1-9"),
    ]
    safe_state = ("arm powered off: the dashboard 'power off' of the upstream node's e_stop was answered and a fresh "
                  "'robotmode' read returned POWER_OFF, the mode from which the upstream initialize() recovers by "
                  "'brake release' (ur_dashboard.py:125-132); the URP program state and any attached tool are not "
                  "checked, and after a reset the arm stays off until the permit-gated re-enable or an operator "
                  "powers it on")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("movement_state", type="string",
          description="READY on the first sample or when the joint change since the previous sample of any read is "
                      "below a norm of 1e-3, BUSY otherwise; every read stores a new sample, so it is not a "
                      "motion-complete signal")
    def movement_state(self):
        return self.native.get_movement_state()[0]

    @read("joint_positions", type="array", items="number", length=6, unit="rad",
          description="Current joint values reported by the URX connection, in the arm's joint order")
    def joint_positions(self):
        return [float(value) for value in self.native.get_movement_state()[1]]

    @read("robot_mode", type="string",
          description="Second word of the dashboard 'robotmode' answer (for example RUNNING, POWER_OFF)")
    def robot_mode(self):
        return self.native.ur_dashboard.get_robot_mode()

    @read("safety_status", type="string",
          description="Second word of the dashboard 'safetystatus' answer (for example NORMAL)")
    def dashboard_safety_status(self):
        return self.native.ur_dashboard.get_safety_status()

    @read("operational_mode", type="string", description="Dashboard answer to 'get operational mode'")
    def operational_mode(self):
        return _answered(self.native.ur_dashboard.get_operational_mode(), "get operational mode")

    @read("program_state", type="string", description="Dashboard answer to 'programState'")
    def program_state(self):
        return _answered(self.native.ur_dashboard.get_program_state(), "programState")

    @read("loaded_program", type="string", description="Dashboard answer to 'get loaded program'")
    def loaded_program(self):
        return _answered(self.native.ur_dashboard.get_loaded_program(), "get loaded program")

    @read("program_run_status", type="string", description="Dashboard answer to the 'running' query")
    def program_run_status(self):
        return _answered(self.native.ur_dashboard.get_program_run_status(), "running")

    @read("remote_control", type="string", description="Dashboard answer to 'is in remote control'")
    def remote_control(self):
        return _answered(self.native.ur_dashboard.is_in_remote_control(), "is in remote control")

    # -- motion -----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1",
            description="Move the arm to a six-joint target with UR.home (a blocking URX movej); reached means "
                        "UR.home returned without raising, and the joint values are read back afterwards",
            input={"joint_positions": Field(
                "array", items="number", length=6, unit="rad",
                description="Target joint values in radians, in the arm's joint order",
                limit=Limit.operator_required(
                    "no text file of the clone states this arm's joint travel range; the site supplies the joint "
                    "envelope of its unit, the catalogue class cannot carry an invented default"))})
    def home(self, joint_positions):
        try:
            self.native.home(list(joint_positions))
        except Exception as exc:  # noqa: BLE001 - a failed native move is a failed receipt, never a success
            raise DriverFailed("MHS.DEVICE.FAULTED", f"UR.home failed: {exc}",
                               native_code=type(exc).__name__) from exc
        self.check_cancelled()
        _state, positions = self.native.get_movement_state()
        return {"reached": True, "joint_positions": [float(value) for value in positions]}

    # -- program control ---------------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.pause_program.v1",
            description="Pause the loaded URP program with the dashboard 'pause'; completed only when the dashboard "
                        "answers 'Pausing program'",
            output={"response": Field("string", description="Dashboard answer to 'pause'")})
    def pause_program(self):
        answer = _answered(self.native.ur_dashboard.pause_program(), "pause")
        if answer != PAUSE_ANSWER:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the dashboard answered {answer!r} to 'pause'",
                               native_code=str(answer)[:64])
        return {"response": answer}

    @action(name="x-cap.ad-sdl.stop_program.v1",
            description="Stop the loaded URP program with the dashboard 'stop' (the upstream node's safety_stop); "
                        "completed only when the dashboard answers 'Stopped'; not the e-stop",
            output={"response": Field("string", description="Dashboard answer to 'stop'")})
    def stop_program(self):
        answer = _answered(self.native.ur_dashboard.stop_program(), "stop")
        if answer != STOP_ANSWER:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the dashboard answered {answer!r} to 'stop'",
                               native_code=str(answer)[:64])
        return {"response": answer}

    # -- safe state --------------------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.power_off.v1", safe_state=True,
            description="Power the arm off with the dashboard 'power off' (the upstream node's e_stop) and confirm "
                        "POWER_OFF by fresh 'robotmode' reads; it takes no input",
            output={"robot_mode": Field("string", description="Robot mode read after 'power off' (POWER_OFF)")})
    def power_off_arm(self):
        dashboard = self.native.ur_dashboard
        _answered(dashboard.power_off(), "power off")
        deadline = time.monotonic() + POWER_OFF_WAIT_S
        while True:
            mode = dashboard.get_robot_mode()
            if mode == "POWER_OFF":
                return {"robot_mode": mode}
            if time.monotonic() >= deadline:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                   f"the robot mode is {mode!r}, not POWER_OFF, {POWER_OFF_WAIT_S:g} s after "
                                   "'power off'", native_code=str(mode)[:64])
            time.sleep(POLL_S)

    # -- recovery ----------------------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.power_on.v1", reenable=True, requires_permit=True,
            description="Re-enable after a reset (refused while latched, never run by the reset, a permit for each "
                        "call): with safety status NORMAL, send the dashboard 'brake release' to an arm in "
                        "POWER_OFF, BOOTING, POWER_ON or IDLE and confirm RUNNING; it never unlocks a protective "
                        "stop, restarts safety or changes the operational mode",
            output={"robot_mode": Field("string", description="Robot mode read after the re-enable (RUNNING)")})
    def power_on(self):
        dashboard = self.native.ur_dashboard
        safety = dashboard.get_safety_status()
        if safety != "NORMAL":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the safety status is {safety!r}, not NORMAL: an operator clears a protective stop, a "
                               "safety fault or an emergency stop at the robot after inspecting its cause; this "
                               "command never unlocks or restarts safety", native_code=str(safety)[:64])
        mode = dashboard.get_robot_mode()
        if mode == "RUNNING":
            return {"robot_mode": mode}
        if mode not in BRAKE_RELEASE_MODES:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the robot mode is {mode!r}; the upstream releases the brakes only from "
                               f"{', '.join(BRAKE_RELEASE_MODES)}", native_code=str(mode)[:64])
        _answered(dashboard.brake_release(), "brake release")
        mode = dashboard.get_robot_mode()
        if mode != "RUNNING":
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the robot mode is {mode!r}, not RUNNING, after 'brake release' and the upstream's "
                               "20 s wait", native_code=str(mode)[:64])
        return {"robot_mode": mode}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The upstream node's emergency stop: power the arm off through the dashboard (the runtime latches first).

        It fails when the dashboard does not answer; the safe-state action confirms POWER_OFF.
        """
        _answered(self.native.ur_dashboard.power_off(), "power off")

    # No @reset hook: a driver that declares a re-enable is reset by releasing the latch only (SAFE-042,
    # CORE-086).  Opening the hardware backend is not a reset either: see native.py.
