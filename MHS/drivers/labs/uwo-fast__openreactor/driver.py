"""OpenMHS driver for gh.uwo-fast/openreactor: one RLHT heater slice.

A direct Driver over ``openreactor.rlht:RlhtSlice``, the upstream object that
owns one RLHT heater board: it starts the slice safely, holds the two wanted
setpoints, sends them over CRUMBS/I2C, and reports the slice state.  The
hardware factory in ``native.py`` also runs the upstream ``Controller`` tick
that polls the slice, which is what feeds the slice's command watchdog.

* reads: the slice state, version, mode, e-stop flag, and each output's
  temperature and wanted setpoint;
* writes: the wanted setpoint of output 1 and of output 2, in degC, stored
  by the slice to its tenth of a degree;
* the safe state is ``RlhtSlice.send_safe`` (SET_SETPOINTS zero, then
  SET_OPEN_DUTY zero).  It is the native stop of the e-stop and also the
  ``safe_state=True`` action ``x-cap.uwo-fast.stop_heating.v1``; the latter
  satisfies SAFE-045 because no text file of the clone documents an
  independent hardware e-stop the driver can cite.

Every Fact cites a line of the clone at the pinned commit
(ade88dc17e1c06775ddcb1cdc9ca6c40e4083db0).  This package is model-authored
and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

# The slice takes a setpoint as an i16 in tenths of a degree; the API default
# cap is 3276.7 Cel when the config does not set a lower max_setpoint.
_SETPOINT_LIMIT = Limit(min=0, max=3276.7, unit="Cel", source="vendor_doc", ref="README.md:108-111")


class RlhtHeater(Driver):
    device_id = "rlht_heater"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "openreactor.rlht:RlhtSlice"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRlhtSlice"}
    vendor, model = "uwo-fast", "RLHT heater slice"
    display_name = "openreactor RLHT heater slice (openreactor.rlht.RlhtSlice)"
    tags = ["reactor", "heater", "thermal", "rlht", "i2c"]
    facts = [
        Fact(
            "Start-up sends the safe state (setpoints to zero, then open-loop duty to zero) before arming the "
            "command watchdog and setting closed-loop mode",
            source="upstream_code",
            ref="src/openreactor/rlht.py:290-320",
        ),
        Fact(
            "The safe state is always SET_SETPOINTS(0, 0) and then SET_OPEN_DUTY(0, 0), both sent even if the "
            "first fails",
            source="upstream_code",
            ref="src/openreactor/rlht.py:399-408",
        ),
        Fact(
            "An RLHT channel's setpoint is in degC to the slice's tenth of a degree: from 0 up to the channel's "
            "max_setpoint, or 3276.7 degC when the config sets none",
            source="vendor_doc",
            ref="README.md:108-111",
        ),
        Fact(
            "status() reports the slice state, version, capabilities, mode, e-stop flag, both outputs, the "
            "watchdog and the desired setpoints",
            source="upstream_code",
            ref="src/openreactor/rlht.py:410-437",
        ),
        Fact(
            "Each output status carries a temperature and setpoint in degC (from tenths) and an on-time and "
            "period in ms",
            source="upstream_code",
            ref="src/openreactor/rlht.py:146-171",
        ),
        Fact(
            "set_setpoint(output, deci) takes tenths of a degree and updates the desired setpoints only after "
            "the send",
            source="upstream_code",
            ref="src/openreactor/rlht.py:439-467",
        ),
        Fact(
            "An e-stop pressed on a slice sends stop-all, and its setpoints stay at zero until the operator sets "
            "them again",
            source="vendor_doc",
            ref="README.md:96-100",
        ),
        Fact(
            "The heater and motor boards run their own control loops and stop their outputs if they lose contact "
            "with the Pi",
            source="vendor_doc",
            ref="README.md:16-17",
        ),
        Fact(
            "An RLHT heater slice has two heater outputs, each with an onboard PID on one of two thermocouples",
            source="vendor_doc",
            ref="examples/openreactor.toml:38-39",
        ),
    ]
    safe_state = "both heater setpoints zero and open-loop duty zero (RlhtSlice.send_safe)"

    # -- helpers -----------------------------------------------------------------------------------------------
    def _status(self):
        return self.native.status()

    def _output_at(self, number: int):
        outputs = self._status().outputs or ()
        if len(outputs) < number:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the slice status has no output {number}")
        return outputs[number - 1]

    def _temperature(self, number: int) -> float:
        value = self._output_at(number).temperature_c
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"output {number} has no thermocouple reading")
        return float(value)

    def _desired(self, number: int) -> float:
        desired = self._status().desired_c
        if not desired or len(desired) < number:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the slice reports no desired setpoints")
        return float(desired[number - 1])

    # -- reads -------------------------------------------------------------------------------------------------
    @read("state", type="string", description="State of the heater slice, or why it is out of use")
    def state(self):
        return str(self._status().state)

    @read("version", type="string", description="Firmware and CRUMBS version the slice reported")
    def version(self):
        return str(self._status().version or "unknown")

    @read("mode", type="string", description="Control mode of the slice, closed loop or open loop")
    def control_mode(self):
        return str(self._status().mode or "unknown")

    @read("estop", type="boolean", description="True while the slice's own e-stop is held")
    def estop_held(self):
        value = self._status().estop
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the slice has not reported its e-stop state")
        return bool(value)

    @read("temperature_1", unit="Cel", description="Temperature the slice reads on thermocouple 1")
    def temperature_1(self):
        return self._temperature(1)

    @read("temperature_2", unit="Cel", description="Temperature the slice reads on thermocouple 2")
    def temperature_2(self):
        return self._temperature(2)

    @read("setpoint_1", unit="Cel", description="Wanted setpoint of heater output 1")
    def setpoint_1(self):
        return self._desired(1)

    @read("setpoint_2", unit="Cel", description="Wanted setpoint of heater output 2")
    def setpoint_2(self):
        return self._desired(2)

    # -- writes ------------------------------------------------------------------------------------------------
    @write(
        "setpoint_1",
        unit="Cel",
        description="Wanted setpoint of heater output 1, stored to the slice's tenth of a degree",
        limit=_SETPOINT_LIMIT,
        risk="R2",
    )
    def set_setpoint_1(self, value):
        deci = round(float(value) * 10)
        self.native.set_setpoint(1, deci)
        return deci / 10

    @write(
        "setpoint_2",
        unit="Cel",
        description="Wanted setpoint of heater output 2, stored to the slice's tenth of a degree",
        limit=_SETPOINT_LIMIT,
        risk="R2",
    )
    def set_setpoint_2(self, value):
        deci = round(float(value) * 10)
        self.native.set_setpoint(2, deci)
        return deci / 10

    # -- safety ------------------------------------------------------------------------------------------------
    @estop(native="send_safe")
    def emergency_stop(self):
        """The native stop: the runtime latches first, then sends the slice's safe state."""
        self.native.send_safe()

    @action(
        name="x-cap.uwo-fast.stop_heating.v1",
        verb="invoke",
        risk="R2",
        safe_state=True,
        description="Put both heater outputs in the safe state (setpoints zero, then open-loop duty zero)",
        output={
            "setpoint_1": Field("number", unit="Cel", description="Wanted setpoint of heater output 1 after it"),
            "setpoint_2": Field("number", unit="Cel", description="Wanted setpoint of heater output 2 after it"),
        },
    )
    def stop_heating(self):
        self.native.send_safe()
        desired = self.native.status().desired_c or (0.0, 0.0)
        return {"setpoint_1": float(desired[0]), "setpoint_2": float(desired[1])}
