"""OpenMHS driver for gh.iridiumwastaken/pumpy3: a Harvard PHD 2000 syringe pump over RS-232.

A direct Driver (decorated methods) over the upstream class ``pump:Pump2000`` (``pump.py:521-714``).  The upstream
assembles every serial command from the pump address, a command word and an argument
(``self.address + command + '\\r'``, ``pump.py:159-164``), and the PHD 2000 overrides the Ultra pump's stop and rate
methods (``pump.py:606-667``); a text-command family cannot reproduce that address prefix, so the package uses the
upstream object directly with a ``native.py`` factory (driver-authoring.md, "Choosing the shape").

DEVIATION FROM THE CARD: a direct Driver with native.py rather than the PythonObjectDriver helper, for the reason
above.  The package binds the card's PHD 2000 entry symbol ``pump:Pump2000``.

* reads: the configured syringe diameter (mm), flow rate (uL/min), target volume (mL), infused volume (mL) and the
  running state;
* writes: the syringe diameter, the flow rate and the target volume.  The diameter range is stated by the clone
  (0.1 to 35 mm, ``pump.py:184``); the flow-rate range depends on the installed syringe and is not stated by a text
  file, and the clone states no target-volume range, so both are ``Limit.operator_required``: every write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies its range (``site-limits.example.json`` shows the overlay);
* actions: ``x-cap.iridiumwastaken.start_pump.v1`` starts infusing (RUN) or withdrawing (REV) with the rate and target
  that are already configured; ``x-cap.iridiumwastaken.stop_pump.v1`` is the safe-state action (STP);
* the native stop (STP) is the e-stop (``pump.py:606-614``).

Every Fact cites a line of the clone at the pinned commit (0819cd6f9c402ce75e12eb697672a8b3559f93c1).  This package
is model-authored and unreviewed: it is checked on the fake backend only (driver.lock.json).
"""

import re

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

D = "pump.py"


def _number(reply, what):
    """The first number in a pump reply; the upstream replies are text such as ``'12.34 mm'``."""
    match = re.search(r"-?\d+(?:\.\d+)?", str(reply or ""))
    if match is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"the pump's reply for the {what} holds no number")
    return float(match.group(0))


class PumpyPHD2000(Driver):
    device_id = "pumpy3-phd2000"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: A pump that dispenses liquid is R2 (MHS/spec/04-safety.md, section 2.1), above the card's R1 floor.
    risk = "R2"
    native = "pump:Pump2000"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePump2000"}
    vendor, model = "Harvard Apparatus", "PHD 2000 syringe pump"
    display_name = "Harvard PHD 2000 syringe pump (pumpy3.Pump2000)"
    tags = ["syringe pump", "harvard", "phd2000", "serial", "infuse", "withdraw", "pumpy3"]
    facts = [
        Fact("pumpy3 controls a Harvard syringe pump over an RS-232 interface and supports the PHD 2000 and the "
             "PHD Ultra", source="vendor_doc", ref="README.md:3-8"),
        Fact("The supported features are set pump volume, set pump diameter, set infuse and withdraw rate, set target "
             "volumes and wait until target volume", source="vendor_doc", ref="README.md:10-15"),
        Fact("The example creates Chain serial objects and pumps at addresses 0 and 2", source="vendor_doc",
             ref="README.md:31-39"),
        Fact("The PHD 2000 only takes notice of target volumes after it has been put into volume mode with the keypad",
             source="vendor_doc", ref="README.md:52-53"),
        Fact("The PHD 2000 sometimes does not wait until infusion or withdrawal is finished", source="vendor_doc",
             ref="README.md:54"),
        Fact("Chain opens the serial line with a 115200 baud default, two stop bits, no parity, eight data bits and a "
             "2 s timeout", source="upstream_code", ref=f"{D}:96-104"),
        Fact("Pump2000 stores the configured pump address as a two-digit string with '{0:02.0f}'",
             source="upstream_code", ref=f"{D}:527"),
        Fact("Pump.write prefixes the stored pump address and terminates every command with a carriage return",
             source="upstream_code", ref=f"{D}:159-164"),
        Fact("Pump.setdiameter states that the syringe diameter range is 0.1-35 mm", source="upstream_code",
             ref=f"{D}:182-193"),
        Fact("Pump.setinfusionrate says the accepted flow-rate range depends on the syringe diameter and is given by "
             "the pump manual", source="upstream_code", ref=f"{D}:264-272"),
        Fact("Pump.settargetvolume says the accepted target-volume range depends on the syringe and is given by the "
             "pump manual", source="upstream_code", ref=f"{D}:351-359"),
        Fact("Pump2000 queries VER during construction, requires 'PHD' in the reply and reads the status character "
             "':' (idle), '>' (infusing), '<' (withdrawing) or '*' (stalled)", source="upstream_code",
             ref=f"{D}:539-556"),
        Fact("Pump2000.run writes RUN and Pump2000.rev writes REV, then records the reported state",
             source="upstream_code", ref=f"{D}:576-590"),
        Fact("Pump2000.stop writes STP, reads the reply, pauses 0.1 s and raises if the state still reports infusing "
             "or withdrawing", source="upstream_code", ref=f"{D}:606-614"),
        Fact("Pump2000.set_rate maps m/m, u/m, m/h and u/h to MLM, ULM, MLH and ULH and writes the rate with four "
             "decimals", source="upstream_code", ref=f"{D}:640-656"),
        Fact("Pump2000.settargetvolume sets the target volume in mL with MLT", source="upstream_code",
             ref=f"{D}:663-667"),
        Fact("Pump2000.getdiameter queries DIA and reports the number in mm", source="upstream_code",
             ref=f"{D}:669-678"),
        Fact("Pump2000.getrate queries RAT and RNG and reports the rate and the first four characters of the RNG "
             "reply", source="upstream_code", ref=f"{D}:680-692"),
        Fact("Pump2000.ivolume queries VOL and reports the infused volume in mL", source="upstream_code",
             ref=f"{D}:694-703"),
        Fact("Pump2000.gettargetvolume queries TAR and reports the target volume in mL", source="upstream_code",
             ref=f"{D}:705-714"),
    ]
    safe_state = "pump stopped by STP; no infusion or withdrawal continues until a new run"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("diameter", unit="mm", description="Syringe inside diameter configured on the pump")
    def diameter(self):
        return _number(self.native.getdiameter(), "diameter")

    @read("rate", unit="uL/min",
          description="Flow rate configured on the pump in microlitres per minute; the driver writes ULM and reads "
                      "the number of the RAT reply")
    def rate(self):
        return _number(self.native.getrate(), "flow rate")

    @read("target_volume", unit="mL", description="Target volume configured on the pump")
    def target_volume(self):
        return _number(self.native.gettargetvolume(), "target volume")

    @read("infused_volume", unit="mL", description="Accumulated infused volume reported by the pump")
    def infused_volume(self):
        return _number(self.native.ivolume(), "infused volume")

    @read("running", type="boolean", description="True while the pump reports infusing or withdrawing")
    def running(self):
        return self.native.state in ("infusing", "withdrawing")

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("diameter", unit="mm", description="Syringe inside diameter written with MMD",
           limit=Limit(min=0.1, max=35.0, source="upstream_code", ref=f"{D}:184",
                       reason="the clone states the syringe diameter range as 0.1-35 mm"))
    def set_diameter(self, value):
        self.native.setdiameter(float(value))

    @write("rate", unit="uL/min",
           description="Flow rate written as ULM in microlitres per minute; the accepted range depends on the "
                       "syringe",
           limit=Limit.operator_required(
               "the clone says the accepted flow-rate range depends on the syringe diameter and is given by the "
               "pump manual (pump.py:264-272), which is not a text file of the clone; the site supplies the range "
               "for its syringe"))
    def set_rate(self, value):
        self.native.set_rate(float(value), "u/m")

    @write("target_volume", unit="mL",
           description="Target volume written with MLT in millilitres; the accepted range depends on the syringe",
           limit=Limit.operator_required(
               "the clone says the accepted target-volume range depends on the syringe and is given by the pump "
               "manual (pump.py:351-359), which is not a text file of the clone; the site supplies the range for "
               "its syringe"))
    def set_target_volume(self, value):
        self.native.settargetvolume(float(value))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.iridiumwastaken.start_pump.v1",
            description="Start infusing or withdrawing with the rate and target volume already configured",
            input={"direction": Field("string", enum=["forward", "reverse"],
                                      description="forward runs the pump (RUN) and reverse withdraws (REV)")},
            output={"running": Field("boolean",
                                     description="True while the pump reports infusing or withdrawing"),
                    "direction": Field("string", description="The direction this action started")})
    def start_pump(self, direction):
        if direction == "forward":
            self.native.run()
        elif direction == "reverse":
            self.native.rev()
        else:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"unknown pump direction {direction!r}")
        return {"running": self.native.state in ("infusing", "withdrawing"), "direction": direction}

    @action(name="x-cap.iridiumwastaken.stop_pump.v1", safe_state=True,
            description="Stop the pump with STP (the native stop, the safe state); it takes no input",
            output={"running": Field("boolean", description="False once the pump reports that it is stopped")})
    def stop_pump(self):
        self.native.stop()
        return {"running": self.native.state in ("infusing", "withdrawing")}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the PHD 2000 sends STP."""
        self.native.stop()

    def teardown(self):
        self.native.serialcon.close()       # Pump2000.__init__ keeps the Chain as serialcon (pump.py:526)
