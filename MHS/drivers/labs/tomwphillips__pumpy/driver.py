"""OpenMHS driver for gh.tomwphillips/pumpy: a Harvard PHD 2000 syringe pump over its serial protocol.

A direct Driver (decorated methods) over the upstream class ``pumpy:PHD2000``.  The upstream assembles every command
from the pump address, a command word and an argument (``self.address + command + '\\r'``, ``pumpy.py:82-83``), and the
PHD2000 overrides the stop and target-volume replies of the Pump 11 (``pumpy.py:271-308``).  A text-command family
cannot reproduce that address prefix or the reply handling, so the package uses the upstream object directly with a
``native.py`` factory (driver-authoring.md, "Choosing the shape").

DEVIATION FROM THE CARD: a direct Driver with native.py rather than the PythonObjectDriver helper, for the reason
above.  The package binds the card's PHD2000 entry symbol.

* reads: the configured syringe diameter (mm), flow rate (uL/min) and target volume (uL);
* writes: the syringe diameter, the flow rate and the target volume.  The diameter range is stated by the clone
  (0.1 to 35 mm, ``pumpy.py:96``); the flow-rate range depends on the installed syringe and is not stated by a text
  file, and the clone states no target-volume range, so both are ``Limit.operator_required``: every write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies its range (``site-limits.example.json`` shows the overlay);
* one catalogue action, ``cap.actuation.pump.v1``: set the flow rate and target volume, start infusing or withdrawing,
  wait for the target and report the volume moved.  The catalogue flow rate is uL/s; the upstream flow rate is
  uL/min (``pumpy.py:143-151``), so the action converts by 60 before it writes the native value;
* the native stop (STP) is the e-stop and, as ``x-cap.tomwphillips.stop_pump.v1``, the safe-state action.

Every Fact cites a line of the clone at the pinned commit (3e49d71a73d23ea6f16082109bd4fac90a69119b).  This package
is model-authored and unreviewed: it is checked on the fake backend only (driver.lock.json).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

D = "pumpy.py"


class PumpyPHD2000(Driver):
    device_id = "pumpy-phd2000"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is R2 (MHS/spec/04-safety.md, section 2.1), above the card's R0 floor.
    risk = "R2"
    native = "pumpy:PHD2000"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePHD2000"}
    vendor, model = "Harvard Apparatus", "PHD 2000 syringe pump"
    display_name = "Harvard PHD 2000 syringe pump (pumpy.PHD2000)"
    tags = ["syringe pump", "harvard", "phd2000", "serial", "infuse", "withdraw", "pumpy"]
    facts = [
        Fact("pumpy controls a Harvard syringe pump or a Mighty Mini piston pump over an RS-232 interface",
             source="vendor_doc", ref="README.md:3"),
        Fact("The supported Harvard pumps are Pump 11, Pump 11 Plus and PHD2000", source="vendor_doc",
             ref="README.md:15-17"),
        Fact("The supported features for the Harvard pumps are infuse, withdraw, set diameter, set flow rate, set "
             "target volume and wait until target volume", source="vendor_doc", ref="README.md:22-28"),
        Fact("A pump is created on a Chain and the PHD2000 is created with an address", source="vendor_doc",
             ref="README.md:52-63"),
        Fact("The example flow rate is in uL/min and the example target volume is in uL", source="vendor_doc",
             ref="README.md:56-57"),
        Fact("PHD2000 requires withdraw, stop, infuse rather than withdraw, infuse", source="vendor_doc",
             ref="README.md:80"),
        Fact("PHD2000 only takes notice of target volumes when it has been put into volume mode using the keypad",
             source="vendor_doc", ref="README.md:81"),
        Fact("Chain opens a serial line with two stop bits, no parity and a 2 s timeout", source="upstream_code",
             ref=f"{D}:33"),
        Fact("A command is written as the pump address, the command text and a carriage return", source="upstream_code",
             ref=f"{D}:82-83"),
        Fact("Pump.__init__ stores the name, the serial chain, the two-digit address and the diameter, flow rate and "
             "target volume (initially None), then queries VER to check the pump and its address", source="upstream_code",
             ref=f"{D}:48-74"),
        Fact("setdiameter states that the Pump 11 syringe diameter range is 0.1-35 mm and the pump truncates precision "
             "beyond two decimal places", source="upstream_code", ref=f"{D}:93-98"),
        Fact("setdiameter sends MMD with the diameter and checks it with DIA", source="upstream_code",
             ref=f"{D}:120-141"),
        Fact("setflowrate takes microlitres per minute and says the range depends on the syringe diameter and is "
             "given by the Pump 11 manual", source="upstream_code", ref=f"{D}:143-151"),
        Fact("setflowrate sends ULM with the flow rate and checks it with RAT", source="upstream_code",
             ref=f"{D}:163-184"),
        Fact("infuse sends RUN and checks for the forward-running status character", source="upstream_code",
             ref=f"{D}:186-197"),
        Fact("withdraw sends REV and checks for the backward-running status character", source="upstream_code",
             ref=f"{D}:199-214"),
        Fact("Pump.stop sends STP and expects the stopped status character", source="upstream_code",
             ref=f"{D}:216-224"),
        Fact("Pump.settargetvolume takes microlitres, sends MLT and stores the target volume", source="upstream_code",
             ref=f"{D}:226-239"),
        Fact("PHD2000 overrides stop, sends STP and expects the '*' status character", source="upstream_code",
             ref=f"{D}:278-286"),
        Fact("PHD2000.settargetvolume takes microlitres, converts them to millilitres, sends MLT and stores the value "
             "back in microlitres", source="upstream_code", ref=f"{D}:288-308"),
        Fact("waituntiltarget polls VOL until the pump stops or two consecutive replies are equal", source="upstream_code",
             ref=f"{D}:241-269"),
    ]
    safe_state = "pump stopped by STP; no infusion or withdrawal continues until a new run"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("diameter", unit="mm", description="Syringe inside diameter configured on the pump")
    def diameter(self):
        value = self.native.diameter
        return None if value is None else float(value)

    @read("flowrate", unit="uL/min", description="Flow rate configured on the pump, in microlitres per minute")
    def flowrate(self):
        value = self.native.flowrate
        return None if value is None else float(value)

    @read("targetvolume", unit="uL", description="Target volume configured on the pump, in microlitres")
    def targetvolume(self):
        value = self.native.targetvolume
        return None if value is None else float(value)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("diameter", unit="mm", description="Syringe inside diameter written with MMD and checked with DIA",
           limit=Limit(min=0.1, max=35.0, source="upstream_code", ref=f"{D}:96",
                       reason="the clone states the Pump 11 syringe diameter range as 0.1-35 mm"))
    def set_diameter(self, value):
        self.native.setdiameter(float(value))

    @write("flowrate", unit="uL/min",
           description="Flow rate written with ULM and checked with RAT; the accepted range depends on the syringe",
           limit=Limit.operator_required(
               "the clone says the flow-rate range depends on the syringe diameter and is given by the Pump 11 "
               "manual, which is not a text file of the clone; the site supplies the range for its syringe"))
    def set_flowrate(self, value):
        self.native.setflowrate(float(value))

    @write("targetvolume", unit="uL",
           description="Target volume written with MLT; the PHD2000 converts uL to mL on the wire",
           limit=Limit.operator_required(
               "no text file of the clone states a target-volume range, and the usable volume depends on the "
               "installed syringe; the site supplies the range for its syringe"))
    def set_targetvolume(self, value):
        self.native.settargetvolume(float(value))

    # -- the catalogue pump action --------------------------------------------------------------------------------
    @action(
        cap="cap.actuation.pump.v1",
        description="Set the flow rate and target volume, start infusing (forward) or withdrawing (reverse) and wait "
                    "for the target volume to be reached",
        input={
            "flow_rate": Field(
                "number", unit="uL/s",
                description="Flow rate; the native pump takes uL/min, so the driver multiplies it by 60",
                limit=Limit.operator_required(
                    "the accepted flow-rate range depends on the syringe diameter and is given by the Pump 11 "
                    "manual, which is not a text file of the clone; the site supplies the range")),
            "direction": Field(
                "string", description="forward infuses (RUN) and reverse withdraws (REV)"),
            "volume": Field(
                "number", unit="uL",
                description="Target volume; the PHD2000 converts uL to mL on the wire",
                limit=Limit.operator_required(
                    "no text file of the clone states a target-volume range, and the usable volume depends on the "
                    "installed syringe; the site supplies the range")),
        },
    )
    def pump(self, flow_rate, direction, volume=None):
        if direction not in ("forward", "reverse"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unknown pump direction {direction!r}")
        target = self.native.targetvolume if volume is None else float(volume)
        if target is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "no target volume: pass volume or set the target volume first")
        self.native.setflowrate(float(flow_rate) * 60.0)     # uL/s -> uL/min (pumpy.py:143-144)
        self.native.settargetvolume(float(target))
        if direction == "forward":
            self.native.infuse()
        else:
            self.native.withdraw()
        self.native.waituntiltarget()
        return {"dispensed_volume": float(target)}

    # -- safe state and e-stop ------------------------------------------------------------------------------------
    @action(name="x-cap.tomwphillips.stop_pump.v1", safe_state=True,
            description="Stop the pump with STP (the native stop, the safe state); it takes no input",
            output={"stopped": Field("boolean", description="True once the stop command completed")})
    def stop_pump(self):
        self.native.stop()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the PHD2000 sends STP."""
        self.native.stop()

    def teardown(self):
        self.native.serialcon.close()       # Pump.__init__ keeps the Chain as serialcon (pumpy.py:50)
