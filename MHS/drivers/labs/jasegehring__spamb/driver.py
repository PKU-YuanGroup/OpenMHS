"""OpenMHS driver for gh.jasegehring/spamb: the Chemyx Fusion 4000-X syringe pump of SPAMB.

SPAMB (Fluidics OS) drives a syringe pump, a selector valve and a pair of solenoid valves over serial
(README.md:3-5).  This package covers the pump, the fluid-moving actuator of the three: the ``PumpController``
of ``fluidics-control/hardware/pump.py`` (the card's first entry symbol).  The valve and the relay board use
framed binary protocols and are separate devices; they are not served by this one Driver class (RESULT.json
notes).

A direct Driver over the upstream class.  The upstream adapter builds every pump command from parts (a pump
number, a verb and values, ``hardware/chemyx_official/connect.py:117-118, 250-255``), so a SerialDriver command
table cannot express the interface; this is the direct shape of the guide.

* reads: running state, direction, the configured flow rate (mL/min), target volume (mL), syringe diameter
  (mm), and the volume dispensed and remaining (mL);
* writes: flow rate, target volume, syringe diameter and direction.  No text file of the clone states a pump
  or syringe bound: the README gives a configured example range and tells the operator to confirm the real
  limits for the pump and syringe (fluidics-control/README.md:322-323).  Those three numeric bounds are therefore
  ``Limit.operator_required``; the site overlay supplies them, and every write is refused ``LIMITS_UNSET`` until
  it does.  The direction allowed set is the upstream validation itself (pump.py:358-371);
* the catalogue action ``cap.actuation.pump.v1`` sets the direction, target volume and flow rate, starts the
  pump and reports the volume dispensed so far (0 uL at the moment the start command returns);
* the native stop (``PumpController.stop``, pump.py:449-457) is both the e-stop and the safe-state action
  ``x-cap.jasegehring.stop_pump.v1``, so the R2 pump has an independent stop path in the runtime.

The pump is R2: it dispenses liquid.  Every Fact and Limit cites a line of the clone at the pinned commit
06a404c1879d0d1f926ba59470f81f9b7e7987cb.  This package is model-authored and unreviewed; it is checked on the
fake backend only and never ran hardware (README.md of the package).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

PUMP = "fluidics-control/hardware/pump.py"
CHEMYX = "fluidics-control/hardware/chemyx_official/connect.py"
CONTROL_README = "fluidics-control/README.md"

#: The upstream direction words of PumpController.set_direction (pump.py:358-371).
DIRECTIONS = ["infuse", "withdraw"]

#: The catalogue direction words of cap.actuation.pump.v1, mapped to the upstream words.
CATALOGUE_DIRECTIONS = {"forward": "infuse", "reverse": "withdraw"}


def _status(native):
    """The upstream status document; a communication failure carries an ``error`` field (pump.py:614-627)."""
    status = native.get_status()
    if not isinstance(status, dict):
        raise DriverFailed("MHS.DEVICE.FAULTED", "PumpController.get_status returned no status document",
                           native_code="get_status")
    if status.get("error"):
        raise DriverFailed("MHS.DEVICE.FAULTED", str(status["error"]), native_code="get_status")
    return status


def _checked(result, what):
    """The upstream setters and start return a bool; a False is a device failure, not a success."""
    if result is False:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"PumpController.{what} returned False", native_code=what)
    return result


class SpambPump(Driver):
    device_id = "spamb-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "hardware.pump:PumpController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePumpController"}
    vendor, model = "Chemyx", "Fusion 4000-X"
    display_name = "SPAMB syringe pump (Chemyx Fusion 4000-X, PumpController)"
    tags = ["spamb", "fluidics", "syringe pump", "chemyx", "fusion 4000-x", "serial"]
    facts = [
        Fact("SPAMB drives a syringe pump, a 10-position selector valve and two solenoid valves over serial",
             source="vendor_doc", ref="README.md:3-5"),
        Fact("PumpController selects MockPump when mock=True and the Chemyx adapter otherwise",
             source="upstream_code", ref=f"{PUMP}:815-819"),
        Fact("set_diameter takes the syringe inner diameter in mm", source="upstream_code",
             ref=f"{PUMP}:298-299"),
        Fact("set_rate takes the flow rate in mL/min", source="upstream_code", ref=f"{PUMP}:314-315"),
        Fact("set_volume takes the target volume in mL and sends a negative volume for withdraw",
             source="upstream_code", ref=f"{PUMP}:331-341"),
        Fact("The pump direction is 'infuse' or 'withdraw'", source="upstream_code", ref=f"{PUMP}:358-364"),
        Fact("get_status reports is_running, rate, target_volume, dispensed_volume, volume_remaining, "
             "diameter and direction", source="upstream_code", ref=f"{PUMP}:666-676"),
        Fact("stop() sends the pump stop command for the configured pump number and clears the running state",
             source="upstream_code", ref=f"{PUMP}:449-457"),
        Fact("A command is sent as the command text plus a carriage return", source="upstream_code",
             ref=f"{CHEMYX}:124-125"),
        Fact("A response is complete at the '>' prompt", source="upstream_code", ref=f"{CHEMYX}:211-213"),
        Fact("In multipump mode a 'set' command is prefixed with the pump number", source="upstream_code",
             ref=f"{CHEMYX}:117-118"),
        Fact("The pump must be in Multi-Step Mode to accept computer commands", source="upstream_code",
             ref=f"{PUMP}:248-258"),
        Fact("The 60 mL BD plastic syringe of the example configuration has a 26.59 mm inner diameter",
             source="vendor_doc", ref=f"{CONTROL_README}:130"),
        Fact("The example configuration declares a 50000 uL syringe capacity and a 45000 uL warning threshold",
             source="vendor_doc", ref=f"{CONTROL_README}:131-132"),
        Fact("The README gives a configured flow rate range of 1 to 50000 uL/min and tells the operator to "
             "confirm the real limits for the pump and syringe", source="vendor_doc",
             ref=f"{CONTROL_README}:322-323"),
        Fact("The pump-hardware notes use a 10 mL syringe with diameter 14.5 mm, rate 1.0 mL/min and volume "
             "5.0 mL in an example", source="vendor_doc", ref="docs/pump-hardware.md:41-43"),
    ]
    safe_state = "pump stopped; no volume is being delivered"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("running", type="boolean", description="True while the pump is delivering")
    def running(self):
        return bool(self.native.is_running())

    @read("direction", type="string", enum=DIRECTIONS,
          description="Configured pumping direction: infuse or withdraw")
    def direction(self):
        return self.native.get_direction()

    @read("flow_rate", unit="mL/min", description="Configured flow rate of the pump")
    def flow_rate(self):
        return float(_status(self.native).get("rate") or 0.0)

    @read("target_volume", unit="mL", description="Configured target volume of the running or next operation")
    def target_volume(self):
        return float(_status(self.native).get("target_volume") or 0.0)

    @read("syringe_diameter", unit="mm", description="Configured inner diameter of the installed syringe")
    def syringe_diameter(self):
        return float(_status(self.native).get("diameter") or 0.0)

    @read("dispensed_volume", unit="mL", description="Volume dispensed since the last start")
    def dispensed_volume(self):
        return float(_status(self.native).get("dispensed_volume") or 0.0)

    @read("volume_remaining", unit="mL", description="Target volume not yet dispensed")
    def volume_remaining(self):
        return float(_status(self.native).get("volume_remaining") or 0.0)

    # -- writes -----------------------------------------------------------------------------------------------
    @write("flow_rate", unit="mL/min", description="Flow rate of the pump; the site supplies the range",
           limit=Limit.operator_required(
               "no text file of the clone states the pump's flow-rate range: the README gives a configured "
               "1-50000 uL/min example and tells the operator to confirm the real limits for the pump and "
               "syringe (fluidics-control/README.md:322-323); the site supplies the range"))
    def set_flow_rate(self, value):
        _checked(self.native.set_rate(value), "set_rate")
        return float(_status(self.native).get("rate") or 0.0)

    @write("target_volume", unit="mL", description="Target volume of the next operation; the site supplies the range",
           limit=Limit.operator_required(
               "the deliverable volume depends on the installed syringe; the clone states only example syringe "
               "capacities, never a bound of the pump (fluidics-control/README.md:130-132); the site supplies the "
               "range"))
    def set_target_volume(self, value):
        _checked(self.native.set_volume(value), "set_volume")
        return float(_status(self.native).get("target_volume") or 0.0)

    @write("syringe_diameter", unit="mm", description="Inner diameter of the installed syringe; the site supplies "
                                                      "the range",
           limit=Limit.operator_required(
               "the syringe diameter is a property of the installed syringe; the clone shows example diameters "
               "(fluidics-control/README.md:130, docs/pump-hardware.md:41) but no device bound; the site supplies "
               "the range"))
    def set_syringe_diameter(self, value):
        _checked(self.native.set_diameter(value), "set_diameter")
        return float(_status(self.native).get("diameter") or 0.0)

    @write("direction", type="string", enum=DIRECTIONS,
           description="Pumping direction: infuse or withdraw",
           limit=Limit(allowed=DIRECTIONS, source="upstream_code", ref=f"{PUMP}:358-364"))
    def set_direction(self, value):
        _checked(self.native.set_direction(value), "set_direction")
        return self.native.get_direction()

    # -- catalogue action -------------------------------------------------------------------------------------
    @action(cap="cap.actuation.pump.v1",
            description="Run the syringe pump at a flow rate and direction for a target volume",
            input={
                "flow_rate": Field(
                    "number", unit="uL/s", native_unit="mL/min",
                    description="Flow rate of the pump; the site supplies the range",
                    limit=Limit.operator_required(
                        "the catalogue class gives only a generic pump bound; no text file of the clone states "
                        "the Fusion 4000-X bound, which depends on the installed syringe "
                        "(fluidics-control/README.md:322-323); the site supplies the range")),
                "direction": Field("string", enum=["forward", "reverse"],
                                   description="forward infuses, reverse withdraws"),
                "volume": Field(
                    "number", unit="uL", native_unit="mL",
                    description="Target volume to move; the site supplies the range",
                    limit=Limit.operator_required(
                        "the deliverable volume depends on the installed syringe; the clone states only example "
                        "syringe capacities (fluidics-control/README.md:130-132); the site supplies the range")),
            })
    def run_pump(self, flow_rate, direction, volume):
        native_direction = CATALOGUE_DIRECTIONS[direction]
        _checked(self.native.set_direction(native_direction), "set_direction")
        _checked(self.native.set_volume(volume), "set_volume")
        _checked(self.native.set_rate(flow_rate), "set_rate")
        _checked(self.native.start(), "start")
        status = _status(self.native)
        # The upstream volume is mL and the catalogue output is uL; the pump has just started, so this is the
        # volume moved so far (normally 0.0), not the target volume.
        return {"dispensed_volume": float(status.get("dispensed_volume") or 0.0) * 1000.0}

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.jasegehring.stop_pump.v1", safe_state=True,
            description="Stop the pump; this is the safe state and takes no input",
            output={"running": Field("boolean", description="False once the pump is stopped")})
    def stop_pump(self):
        self.native.stop()
        return {"running": bool(self.native.is_running())}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends the pump stop command."""
        self.native.stop()

    # -- backend hooks -----------------------------------------------------------------------------------------
    def setup(self):
        self.native.connect()

    def teardown(self):
        self.native.disconnect()
