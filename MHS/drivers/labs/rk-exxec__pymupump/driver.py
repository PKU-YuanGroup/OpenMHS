"""OpenMHS driver for gh.rk-exxec/pymupump: a Harvard Apparatus Microliter OEM syringe pump over serial.

A direct Driver (decorated methods) over the upstream class ``pymupump.pymupump:Microliter``.  The upstream builds
every command from the two-digit pump address, a command word and an argument (``self.address + command + '\\r'``,
``pymupump/pymupump.py:107``), and it reads fixed byte counts or the whole buffer instead of a terminated line
(``pymupump/pymupump.py:109-139``).  A text-command family cannot reproduce that address prefix or the reply handling,
so this package uses the upstream object directly with a ``native.py`` factory (driver-authoring.md, "Choosing the
shape").

DEVIATION FROM THE CARD: a direct Driver with native.py rather than the SerialDriver helper, for the reason above.
The package binds the card's Microliter entry symbol.

* reads: the configured syringe diameter (mm), flow rate (uL/min) and target volume (uL);
* writes: the syringe diameter, the flow rate and the target volume.  The diameter range is stated by the clone
  (0.1 to 4.61 mm, ``pymupump/pymupump.py:167``); the flow-rate range depends on the installed syringe and is not
  stated by a text file (``pymupump/pymupump.py:204-207``), and the clone states no target-volume range, so both are
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies its range
  (``site-limits.example.json`` shows the overlay);
* one catalogue action, ``cap.actuation.pump.v1``: set the flow rate and target volume, start infusing or withdrawing,
  wait for the target and report the commanded volume.  The catalogue flow rate is uL/s; the upstream flow rate is
  uL/min (``pymupump/pymupump.py:202``), so the action multiplies by 60 before it writes the native value;
* the native stop (STP) is the e-stop and, as ``x-cap.rk-exxec.stop_pump.v1``, the safe-state action.

Every Fact cites a line of the clone at the pinned commit (2de8fb492bbf11b44ad30f571ebb5e64239c6176).  This package
is model-authored and unreviewed: it is checked on the fake backend only (driver.lock.json).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

D = "pymupump/pymupump.py"


class PymupumpMicroliter(Driver):
    device_id = "pymupump-microliter"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is R2 (MHS/spec/04-safety.md, section 2.1), above the card's R0 floor.
    risk = "R2"
    native = "pymupump.pymupump:Microliter"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMicroliter"}
    vendor, model = "Harvard Apparatus", "Microliter OEM syringe pump"
    display_name = "Harvard Apparatus Microliter OEM syringe pump (pymupump.Microliter)"
    tags = ["syringe pump", "harvard apparatus", "microliter oem", "serial", "infuse", "withdraw", "pymupump"]
    facts = [
        Fact("pymupump controls a Harvard Apparatus Microliter OEM syringe pump", source="vendor_doc",
             ref="README.md:2"),
        Fact("A Chain is created on a serial port and a Microliter is created on that chain", source="vendor_doc",
             ref="README.md:16-17"),
        Fact("A second pump on the same port is selected by its address", source="vendor_doc",
             ref="README.md:18-20"),
        Fact("The syringe diameter is in mm and the README states the range 0.1 - 4.61 mm", source="vendor_doc",
             ref="README.md:22"),
        Fact("The flow rate is set in uL/min", source="vendor_doc", ref="README.md:23"),
        Fact("The infuse or withdraw target volume is in uL", source="vendor_doc", ref="README.md:25"),
        Fact("The README example runs infuse or withdraw, optionally waits for the target volume, and stops the pump",
             source="vendor_doc", ref="README.md:27-33"),
        Fact("Chain opens a serial line with two stop bits, no parity and a 2 s timeout", source="upstream_code",
             ref=f"{D}:51"),
        Fact("The pump address is formatted as two zero-padded digits", source="upstream_code", ref=f"{D}:69"),
        Fact("A command is written as the pump address, the command text and a carriage return", source="upstream_code",
             ref=f"{D}:107"),
        Fact("The constructor queries VER, reads 17 bytes and checks the two characters before the last against the "
             "address", source="upstream_code", ref=f"{D}:83-88"),
        Fact("diameter, flowrate and targetvolume start as None", source="upstream_code", ref=f"{D}:70-72"),
        Fact("The clone states the syringe diameter range as 0.1-4.61 mm and says the pump ignores precision beyond "
             "two decimal places", source="upstream_code", ref=f"{D}:166-169"),
        Fact("setdiameter rounds to three decimal places and rejects a diameter above 4.61 or below 0.1 mm",
             source="upstream_code", ref=f"{D}:171-173"),
        Fact("setdiameter sends MMD and checks the set value with DIA", source="upstream_code", ref=f"{D}:179-187"),
        Fact("setflowrate takes microlitres per minute", source="upstream_code", ref=f"{D}:202"),
        Fact("The clone says the accepted flow rate depends on the syringe diameter and the pump reports an "
             "out-of-range rate", source="upstream_code", ref=f"{D}:204-207"),
        Fact("setflowrate sends ULM and ULMW and checks the values with RAT and RATW", source="upstream_code",
             ref=f"{D}:216-235"),
        Fact("An out-of-range flow rate is reported as OOR", source="upstream_code", ref=f"{D}:244-245"),
        Fact("infuse sends RUN and requires the forward-running '>' status character", source="upstream_code",
             ref=f"{D}:253-255"),
        Fact("withdraw sends RUNW and requires the backward-running '<' status character", source="upstream_code",
             ref=f"{D}:262-264"),
        Fact("stop sends STP without waiting for a reply and requires one of ':*IWDT'", source="upstream_code",
             ref=f"{D}:273-275"),
        Fact("settargetvolume clears the four target settings with CLT, CLTW, CLV and CLVW, then sends ULT and ULTW",
             source="upstream_code", ref=f"{D}:280-286"),
        Fact("settargetvolume stores the target volume in microlitres", source="upstream_code", ref=f"{D}:278-292"),
        Fact("waituntiltarget polls VOL while the reply carries '<' or '>'", source="upstream_code",
             ref=f"{D}:302-319"),
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
           limit=Limit(min=0.1, max=4.61, source="upstream_code", ref=f"{D}:167",
                       reason="the clone states the syringe diameter range as 0.1-4.61 mm"))
    def set_diameter(self, value):
        self.native.setdiameter(float(value))

    @write("flowrate", unit="uL/min",
           description="Flow rate written with ULM and checked with RAT; the accepted range depends on the syringe",
           limit=Limit.operator_required(
               "the clone says the accepted flow rate depends on the syringe diameter and does not state a numeric "
               "range; the site supplies the range for its syringe"))
    def set_flowrate(self, value):
        self.native.setflowrate(float(value))

    @write("targetvolume", unit="uL",
           description="Target volume written with ULT and ULTW; the usable volume depends on the installed syringe",
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
                    "the accepted flow-rate range depends on the syringe diameter and no text file of the clone "
                    "states a numeric range; the site supplies the range")),
            "direction": Field(
                "string", description="forward infuses (RUN) and reverse withdraws (RUNW)"),
            "volume": Field(
                "number", unit="uL",
                description="Target volume; the pump stores it in microlitres",
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
        self.native.setflowrate(float(flow_rate) * 60.0)     # uL/s -> uL/min (pymupump.py:202)
        self.native.settargetvolume(float(target))
        if direction == "forward":
            self.native.infuse()
        else:
            self.native.withdraw()
        self.native.waituntiltarget()
        return {"dispensed_volume": float(target)}

    # -- safe state and e-stop ------------------------------------------------------------------------------------
    @action(name="x-cap.rk-exxec.stop_pump.v1", safe_state=True,
            description="Stop the pump with STP (the native stop, the safe state); it takes no input",
            output={"stopped": Field("boolean", description="True once the stop command completed")})
    def stop_pump(self):
        self.native.stop()
        return {"stopped": True}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the pump receives STP."""
        self.native.stop()

    def teardown(self):
        self.native.serialcon.close()       # Microliter.__init__ keeps the Chain as serialcon (pymupump.py:68)
