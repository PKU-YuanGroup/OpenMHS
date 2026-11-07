"""OpenMHS driver for gh.croningp/pycont: one Tricontinent C3000 syringe pump.

A direct Driver (decorated methods) over the upstream device class pycont.controller:C3000Controller.  The upstream
object owns a PumpIO serial connection and speaks the framed Tricontinent protocol; the commands are assembled from
parts (a command letter plus an operand and a CR terminator, pycont/dtprotocol.py:12-13), so this is a direct Driver
with a native.py factory rather than a SerialDriver command table.

* reads: the syringe volume, the plunger position, the valve position, the top velocity, the default top velocity,
  and the idle/initialized state;
* one write: the valve position.  Its allowed set is the four named valve positions plus the 6-way positions, all
  written out in the clone (pycont/controller.py:49-58);
* one catalogue action: cap.actuation.pump.v1.  It converts the catalogue uL and uL/s to the upstream mL and
  steps/s.  The flow rate and the usable syringe volume depend on the configured syringe and microstep mode, so both
  are Limit.operator_required: every pump call is refused MHS.SAFETY.LIMITS_UNSET until the site supplies a range
  (site-limits.example.json shows the overlay);
* the native terminate command is the e-stop and, as x-cap.croningp.terminate.v1, the safe-state action.

The pump dispenses liquid, so the device is R2 even though the catalogue class floor is R1.  This package is
model-authored and unreviewed: the loader refuses the hardware backend until a human signs reviewed_by.  Every Fact
cites the clone at commit 3f6dacb2a6ee82ce1806f6e471013a9ab809c0e6.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The named valve positions and the 6-way valve positions (pycont/controller.py:49-58).
VALVE_POSITIONS = ["I", "O", "B", "E", "1", "2", "3", "4", "5", "6"]


class PycontPump(Driver):
    device_id = "pycont-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "pycont.controller:C3000Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeC3000Controller"}
    vendor, model = "Tricontinent", "C3000 syringe pump (pycont)"
    display_name = "Tricontinent C3000 syringe pump (pycont.C3000Controller)"
    tags = ["syringe-pump", "tricontinent", "c3000", "fluid", "serial"]
    facts = [
        Fact("pycont is a Python library to control Tricontinent C3000 pumps", source="vendor_doc", ref="README.md:3"),
        Fact("Volumes in the pycont API are always in mL", source="vendor_doc", ref="README.md:142"),
        Fact("The syringe volume, the operating speed and the microstep mode are per-pump configuration fields",
             source="vendor_doc", ref="README.md:60-64"),
        Fact("C3000Controller stores the configured syringe volume in mL and derives steps_per_ml from the microstep "
             "count", source="upstream_code", ref="pycont/controller.py:385-386"),
        Fact("The valve positions are input 'I', output 'O', bypass 'B' and extra 'E'; a 6-way valve adds positions "
             "'1' to '6'", source="upstream_code", ref="pycont/controller.py:49-58"),
        Fact("Microstep mode 0 uses 3000 steps and microstep mode 2 uses 24000 steps", source="upstream_code",
             ref="pycont/controller.py:65-68"),
        Fact("The maximum top velocity is 6000 steps/s in microstep mode 0 and 48000 steps/s in microstep mode 2",
             source="upstream_code", ref="pycont/controller.py:70-73"),
        Fact("The top velocity is expressed in steps per second", source="upstream_code",
             ref="pycont/controller.py:673"),
        Fact("The serial I/O defaults to 9600 baud and a 1 s timeout", source="upstream_code",
             ref="pycont/controller.py:75-78"),
        Fact("A C3000 instruction packet starts with '/' and ends with a carriage return", source="upstream_code",
             ref="pycont/dtprotocol.py:12-13"),
        Fact("terminate() sends the command that terminates the current action", source="upstream_code",
             ref="pycont/controller.py:1239-1243"),
    ]
    safe_state = "plunger and valve motion stopped by the native terminate command"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("volume", unit="uL", native_unit="mL",
          description="Volume currently in the syringe, read from the plunger position")
    def volume(self):
        return self.native.get_volume()

    @read("plunger_position", type="integer", unit="1",
          description="Plunger position in microsteps, as reported by the pump")
    def plunger_position(self):
        return self.native.get_plunger_position()

    @read("valve_position", type="string", enum=VALVE_POSITIONS,
          description="Valve position: I input, O output, B bypass, E extra, or 1 to 6 on a 6-way valve")
    def valve_position(self):
        return self.native.get_valve_position()

    @read("top_velocity", type="integer", unit="1/s",
          description="Current top velocity in steps per second")
    def top_velocity(self):
        return self.native.get_top_velocity()

    @read("default_top_velocity", type="integer", unit="1/s",
          description="Default top velocity in steps per second")
    def default_top_velocity(self):
        return self.native.get_default_top_velocity()

    @read("busy", type="boolean", description="True while the pump reports that it is busy")
    def busy(self):
        return self.native.is_busy()

    @read("initialized", type="boolean", description="True when the pump reports that it is initialized")
    def initialized(self):
        return self.native.is_initialized()

    # -- the valve write ------------------------------------------------------------------------------------------
    @write("valve_position", type="string", enum=VALVE_POSITIONS,
           description="Valve position: I input, O output, B bypass, E extra, or 1 to 6 on a 6-way valve",
           limit=Limit(allowed=VALVE_POSITIONS, source="upstream_code", ref="pycont/controller.py:49-58"))
    def set_valve_position(self, value):
        self.native.set_valve_position(value, secure=True)
        return self.native.get_valve_position()

    # -- the pump action ------------------------------------------------------------------------------------------
    @action(cap="cap.actuation.pump.v1",
            description="Aspirate (direction reverse) or dispense (direction forward) a volume at a flow rate",
            input={
                "flow_rate": Field(
                    unit="uL/s", description="Flow rate in microlitres per second",
                    limit=Limit.operator_required(
                        "the reachable flow rate depends on the configured syringe volume and microstep mode, "
                        "which the clone derives steps_per_ml from; the site states the range for its pump")),
                "direction": Field(description="forward dispenses from the syringe, reverse aspirates into it"),
                "volume": Field(
                    unit="uL", description="Volume to move in microlitres",
                    limit=Limit.operator_required(
                        "the usable syringe volume is per-pump configuration (C3000Controller takes total_volume "
                        "from the setup file); the site states the range for its syringe")),
            })
    def run_pump(self, flow_rate, direction, volume):
        started = time.monotonic()
        volume_ml = volume / 1000.0
        speed = int(round(flow_rate * self.native.steps_per_ml / 1000.0))
        before = self.native.get_volume()
        if direction == "forward":
            if not self.native.is_volume_deliverable(volume_ml):
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the syringe does not hold the requested volume")
            moved = self.native.deliver(volume_ml, speed_out=speed, wait=True)
        else:
            if not self.native.is_volume_pumpable(volume_ml):
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "the syringe cannot aspirate the requested volume")
            moved = self.native.pump(volume_ml, speed_in=speed, wait=True)
        if not moved:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the pump rejected the requested volume")
        after = self.native.get_volume()
        return {"dispensed_volume": abs(after - before) * 1000.0,
                "duration_s": max(0.0, time.monotonic() - started)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.croningp.terminate.v1", safe_state=True,
            description="Stop the current pump or valve movement with the native terminate command",
            output={"terminated": Field("boolean", description="True once the terminate command was sent")})
    def terminate(self):
        self.native.terminate()
        return {"terminated": True}

    @estop(native="terminate")
    def stop(self):
        """The native terminate command: the runtime latches first, then stops the current action."""
        self.native.terminate()
