"""OpenMHS driver for gh.deepmodeling/uni-lab-os: a Runze syringe pump over its serial protocol.

This is a direct Driver over the card's entry class
``unilabos.devices.pump_and_valve.runze_backbone:RunzeSyringePump`` (runze_backbone.py:80).  The upstream class
builds every command at run time from the pump address and a letter, with an ``R`` suffix for non-queries
(runze_backbone.py:125-133), so the card's ``family=pylabrobot`` / ``helper=PyLabRobotDriver`` cannot express it:
PyLabRobotDriver serves a PyLabRobot ``LiquidHandler`` front end, and this class is a serial pump that only exposes
``aspirate``-like words through ``pull_plunger``/``push_plunger``.  The deviation is recorded in RESULT.json.

* reads: plunger position, maximum velocity, velocity grade, initial and end velocity, valve position, status and
  the command-buffer, backlash, auxiliary-input and software-version query strings;
* writes: absolute position and maximum velocity.  The clone takes both in mL (runze_backbone.py:300-306,
  321-326, 334-339) while the catalogue uses uL and uL/s, so the driver converts.  No text of the clone states a
  numeric bound; the syringe volume is a constructor option (runze_backbone.py:81-85), not a device bound, so every
  numeric write and action input is ``Limit.operator_required`` and the site supplies the envelope;
* action: ``cap.actuation.pump.v1`` sets the maximum velocity, then pulls (direction reverse) or pushes (direction
  forward) the requested volume.  A volume or a duration plus a flow rate is required; duration alone is converted
  to a volume at the declared flow rate;
* stop: the upstream ``stop_operation`` sends ``T`` through ``_run`` (runze_backbone.py:352-353), which takes
  ``_run_lock`` and waits for Idle (runze_backbone.py:152-164), so it would wait behind a running move.  The e-stop
  path therefore sends the same ``T`` through ``_query`` (runze_backbone.py:125-134), which holds only
  ``_query_lock``, and then reads the status until the pump reports Idle.  This is a protocol stop, not a physical
  e-stop: it does not flush bytes already in the serial driver, and the valve and plunger hold their last
  positions.  The clone documents no Runze command and nothing in it shows ``T`` holding a later command, so the
  pump action checks for cancellation right before its move command and the position write right after its move:
  no move command is sent once the e-stop has started, and a move the stop ended is reported cancelled, not
  applied (model review).
* the clone converts with ``total_steps = total_steps_vel = 6000`` (runze_backbone.py:86); the method that would
  change them for another mode is never called because ``set_mode`` is commented out (runze_backbone.py:206-210).
  Volumes are truncated to whole steps and velocities to whole pulse frequencies (runze_backbone.py:227, 318,
  331, 344).

Every Fact cites a line of the clone at the pinned commit 43923ec9473e2f6d33d3ca1ebca4bf4d507e06b2.  This package is
model-authored and unreviewed; it is checked on the fake backend only and nothing here ran a device.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SOURCE = "unilabos/devices/pump_and_valve/runze_backbone.py"

VOLUME_REASON = (
    "the usable volume depends on the installed syringe; max_volume is a constructor option "
    "(runze_backbone.py:81-85), not a bound stated by the clone, so the site sets the range of its syringe")
FLOW_REASON = (
    "the clone converts a velocity in mL/s to a pulse frequency (runze_backbone.py:225-229) but states no numeric "
    "velocity or flow range; the site sets the permitted range of its syringe and tubing")
POSITION_REASON = (
    "the plunger travel is read as pos_step / total_steps * max_volume (runze_backbone.py:294-298) and max_volume "
    "is a constructor option; no text of the clone states the travel range, so the site sets it")
DURATION_REASON = (
    "the clone has no timed run: it pushes or pulls a volume and polls until Idle (runze_backbone.py:152-164, "
    "321-345), so the duration is the site's bound on one converted volume")


class RunzeSyringePumpDriver(Driver):
    device_id = "runze-syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is at least R2 (MHS/spec/04-safety.md); the card's floor is R2.
    risk = "R2"
    native = "unilabos.devices.pump_and_valve.runze_backbone:RunzeSyringePump"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRunzeSyringePump"}
    vendor, model = "Runze", "syringe pump (RunzeSyringePump)"
    display_name = "Runze syringe pump"
    tags = ["syringe pump", "serial", "fluid", "runze", "pump"]
    facts = [
        Fact("RunzeSyringePump opens a pyserial link in its constructor and controls one addressed pump",
             source="upstream_code", ref=f"{SOURCE}:80-102"),
        Fact("The constructor takes port, address, max_volume (default 25.0) and mode; max_volume is a constructor "
             "option", source="upstream_code", ref=f"{SOURCE}:81-85"),
        Fact("The constructor sets total_steps and total_steps_vel to 6000", source="upstream_code",
             ref=f"{SOURCE}:86"),
        Fact("The constructor opens Serial(baudrate=9600, port=port)", source="upstream_code", ref=f"{SOURCE}:102"),
        Fact("send_command writes the command, sleeps 0.05 s and reads until a newline", source="upstream_code",
             ref=f"{SOURCE}:118-123"),
        Fact("The constructor catches OSError and SerialException and stores the port string in hardware_interface "
             "instead of raising", source="upstream_code", ref=f"{SOURCE}:94-106"),
        Fact("A command is framed as /<address><command><R?>\\r\\n; R is appended unless the command contains '?'",
             source="upstream_code", ref=f"{SOURCE}:125-133"),
        Fact("The status query Q maps a backtick reply to Idle and every other reply to Busy",
             source="upstream_code", ref=f"{SOURCE}:192-198"),
        Fact("Position is computed as pos_step / total_steps * max_volume",
             source="upstream_code", ref=f"{SOURCE}:294-298"),
        Fact("set_position moves to an absolute volume documented in mL; its max_velocity is documented in ml/s",
             source="upstream_code", ref=f"{SOURCE}:300-306"),
        Fact("pull_plunger and push_plunger move a fixed volume documented in mL",
             source="upstream_code", ref=f"{SOURCE}:321-339"),
        Fact("set_max_velocity converts the velocity to an integer pulse frequency (velocity / max_volume * "
             "total_steps_vel), caps it at 6000 and runs the V command", source="upstream_code",
             ref=f"{SOURCE}:225-229"),
        Fact("get_max_velocity converts the pulse frequency back with pulse_freq / total_steps_vel * max_volume",
             source="upstream_code", ref=f"{SOURCE}:231-236"),
        Fact("_adjust_total_steps would set total_steps to 6000 in Normal mode and 48000 otherwise, and "
             "total_steps_vel to 48000 in AccuratePosVel and 6000 otherwise", source="upstream_code",
             ref=f"{SOURCE}:114-116"),
        Fact("set_mode, which would set the mode and call _adjust_total_steps, is commented out",
             source="upstream_code", ref=f"{SOURCE}:206-210"),
        Fact("_run sends the command and polls get_status every 0.5 s until Idle, holding _run_lock for the whole "
             "operation", source="upstream_code", ref=f"{SOURCE}:152-164"),
        Fact("stop_operation runs the T command through _run", source="upstream_code", ref=f"{SOURCE}:352-353"),
        Fact("_query holds only _query_lock while it frames and sends one command and reads its reply",
             source="upstream_code", ref=f"{SOURCE}:125-134"),
        Fact("get_valve_position queries ?6 and returns the second character upper-cased",
             source="upstream_code", ref=f"{SOURCE}:281-286"),
        Fact("query_command_buffer_status, query_backlash_position, query_aux_input_status_1, "
             "query_aux_input_status_2 and query_software_version query the commands ?10, ?12, ?13, ?14 and ?23",
             source="upstream_code", ref=f"{SOURCE}:357-370"),
        Fact("close sets _closing and closes hardware_interface",
             source="upstream_code", ref=f"{SOURCE}:375-380"),
    ]
    safe_state = ("pump stopped by the protocol T command of stop_operation and confirmed Idle by the Q status "
                  "query; the valve and plunger hold their last positions, bytes already queued in the serial driver "
                  "are not flushed, and a status reply other than the idle byte leaves the stop unconfirmed "
                  "(SAFE_STATE_UNREACHED)")
    #: No text of the clone documents a physical e-stop; the independent stop is the safe_state=True action below,
    #: which sends the same T command as @estop.

    # -- reads -------------------------------------------------------------------------------------------------
    @read("position", unit="uL", description="Current absolute plunger position, converted from the clone's mL")
    def position(self):
        return round(float(self.native.get_position()) * 1000.0, 6)

    @read("plunger_position", unit="uL",
          description="Plunger position from the ?4 query, converted from the clone's mL")
    def plunger_position(self):
        return round(float(self.native.get_plunger_position()) * 1000.0, 6)

    @read("max_velocity", unit="uL/s", description="Maximum velocity, converted from the clone's mL/s")
    def max_velocity(self):
        return round(float(self.native.get_max_velocity()) * 1000.0, 6)

    @read("velocity_grade", type="string", description="Pulse-frequency grade returned by get_velocity_grade")
    def velocity_grade(self):
        return str(self.native.get_velocity_grade())

    @read("velocity_init", unit="uL/s",
          description="Initial velocity from the ?1 query, converted from the clone's mL/s")
    def velocity_init(self):
        _pulse_freq, velocity = self.native.get_velocity_init()
        return round(float(velocity) * 1000.0, 6)

    @read("velocity_end", unit="uL/s",
          description="End velocity from the ?3 query, converted from the clone's mL/s")
    def velocity_end(self):
        _pulse_freq, velocity = self.native.get_velocity_end()
        return round(float(velocity) * 1000.0, 6)

    @read("valve_position", type="string", description="Valve port label returned by the ?6 query")
    def valve_position(self):
        return str(self.native.get_valve_position())

    @read("status", type="string", description="Idle or Busy, from the Q query")
    def status(self):
        return str(self.native.get_status())

    @read("command_buffer_status", type="string", description="Raw reply of the ?10 command-buffer query")
    def command_buffer_status(self):
        return str(self.native.query_command_buffer_status())

    @read("backlash_position", type="string", description="Raw reply of the ?12 backlash query")
    def backlash_position(self):
        return str(self.native.query_backlash_position())

    @read("aux_input_status_1", type="string", description="Raw reply of the ?13 auxiliary-input query")
    def aux_input_status_1(self):
        return str(self.native.query_aux_input_status_1())

    @read("aux_input_status_2", type="string", description="Raw reply of the ?14 auxiliary-input query")
    def aux_input_status_2(self):
        return str(self.native.query_aux_input_status_2())

    @read("software_version", type="string", description="Raw reply of the ?23 software-version query")
    def software_version(self):
        return str(self.native.query_software_version())

    # -- writes ------------------------------------------------------------------------------------------------
    @write("position", unit="uL", description="Move to an absolute plunger position",
           limit=Limit.operator_required(POSITION_REASON))
    def set_position(self, value):
        self.native.set_position(float(value) / 1000.0)
        # A T stop (e-stop) ends the move early and the upstream _run then returns normally: report it cancelled,
        # not applied (model review).
        self.check_cancelled()

    @write("max_velocity", unit="uL/s", description="Set the maximum plunger velocity",
           limit=Limit.operator_required(FLOW_REASON))
    def set_max_velocity(self, value):
        self.native.set_max_velocity(float(value) / 1000.0)

    # -- action ------------------------------------------------------------------------------------------------
    @action(cap="cap.actuation.pump.v1", long_running=True, cancellable=True,
            description="Move a volume at a flow rate: direction forward pushes (dispenses) and reverse pulls "
                        "(aspirates). Give volume or duration_s; a duration alone is converted to a volume at the "
                        "declared flow rate. The pump keeps whatever valve position it had.",
            input={
                "flow_rate": Field(unit="uL/s", description="Flow rate in uL/s, converted to the clone's mL/s",
                                   limit=Limit.operator_required(FLOW_REASON)),
                "direction": Field(description="forward pushes the plunger, reverse pulls it"),
                "volume": Field(unit="uL", description="Volume to move in uL; required when duration_s is absent",
                                limit=Limit.operator_required(VOLUME_REASON)),
                "duration_s": Field(unit="s", description="Optional duration; used to derive a volume when volume "
                                                          "is absent",
                                    limit=Limit.operator_required(DURATION_REASON)),
            })
    def pump(self, flow_rate, direction, volume=None, duration_s=None):
        rate = float(flow_rate)
        if rate <= 0.0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "flow_rate must be greater than zero to move a volume")
        if direction not in ("forward", "reverse"):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"unknown direction {direction!r}")
        duration = None if duration_s is None else float(duration_s)
        if duration is not None and duration < 0.0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "duration_s must not be negative")
        moved = None if volume is None else float(volume)
        if moved is not None and moved < 0.0:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "volume must not be negative")
        if moved is None:
            if duration is None:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "give volume or duration_s; this pump moves a volume, not a free-running flow")
            moved = rate * duration
        if moved == 0.0:
            return {"dispensed_volume": 0.0, "duration_s": 0.0}

        self.check_cancelled()
        started = time.monotonic()
        self.native.set_max_velocity(rate / 1000.0)          # the clone takes mL/s
        self.check_cancelled()
        before = float(self.native.get_position())            # mL
        # Nothing in the clone shows T holding a later command: an e-stop that lands before the move command must
        # stop the command itself (model review).
        self.check_cancelled()
        if direction == "forward":
            self.native.push_plunger(moved / 1000.0)          # the clone takes mL
        else:
            self.native.pull_plunger(moved / 1000.0)
        elapsed = time.monotonic() - started
        self.check_cancelled()
        after = float(self.native.get_position())             # mL
        return {"dispensed_volume": round(abs(after - before) * 1000.0, 6), "duration_s": elapsed}

    # -- safety ------------------------------------------------------------------------------------------------
    def _stop_and_confirm(self):
        """Send the same T command as stop_operation without waiting for the move's _run_lock, then read status."""
        self.native._query("T")                               # runze_backbone.py:125-134, 352-353
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if self.native.get_status() == "Idle":
                return
            time.sleep(0.05)
        raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                           "the pump did not report Idle within 0.5 s after the T command")

    @action(name="x-cap.deepmodeling.stop_pump.v1", safe_state=True,
            description="Send the protocol T stop and confirm Idle; takes no input",
            output={"stopped": Field("boolean", description="True once the pump reports Idle after T")})
    def stop_pump(self):
        self._stop_and_confirm()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then this sends T and confirms Idle."""
        self._stop_and_confirm()

    def teardown(self):
        self.native.close()
