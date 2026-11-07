"""OpenMHS driver for gh.giansimone/ctrl-syringe-pumps: a syringe pump over its "basic mode" serial protocol.

A direct Driver over the upstream class ``ctrl_syringe_pumps.control:Control`` (an ``Interface`` subclass).  The
upstream builds each line from a two-digit pump address, a command word and a carriage return
(``ctrl_syringe_pumps/control.py:33``, ``ctrl_syringe_pumps/interface.py:17``); a text-command family cannot express
that address prefix, so this package uses the upstream object directly instead of the card's SerialDriver.

* writes: the syringe inside diameter (``DIA``), the pump direction (``DIR INF``/``DIR WDR``) and the pumping rate
  (``RAT <value> <unit>``, one command).  The rate value and its unit are one command, so the rate is one object
  parameter: splitting it into a number and a token would put half a command on the wire.
* actions: run (``RUN``), stop (``STP``, also the safe-state action), test/version (``VER``) and reverse (``DIR REV``).
* no read: the clone has no query for the diameter, direction or rate; ``VER`` is the only query it builds.  The
  values this driver writes are reported back from the runtime's last-written state (``driver-authoring.md`` section 3).
* the native stop is ``stop_pump`` (``STP``).  At R2 the pump also has a safe-state action, ``stop_pump``.

The rate units are the four tokens the clone lists (``interface.py:8``); the clone does not say what they mean, so
the driver passes the operator's numeric value and token through unchanged and declares no unit for the value.  The
diameter range is the constant on ``interface.py:10``; the native check uses a strict comparison (``interface.py:40``),
so the two endpoints 0.1 and 50.0 are rejected by the device even though the constant is an inclusive-looking list.

Every Limit and Fact cites a line of the clone at the pinned commit
(3b0d3154003498f65150d8f04905f3a27cdd9017).  This package is model-authored and unreviewed; it is checked on the fake
backend only, and no hardware was attached.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, write

INTERFACE = "ctrl_syringe_pumps/interface.py"
CONTROL = "ctrl_syringe_pumps/control.py"

#: The four rate tokens the clone accepts (interface.py:8), in its order.  Their physical meaning is not stated.
RATE_UNITS = ["UM", "MM", "UH", "MH"]


class CtrlSyringePumps(Driver):
    device_id = "syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    risk = "R2"
    native = "ctrl_syringe_pumps.control:Control"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeControl"}
    vendor = "giansimone"
    model = "Serial syringe pump (basic mode)"
    display_name = "Syringe pump over serial (ctrl-syringe-pumps)"
    tags = ["syringe pump", "serial", "infuse", "withdraw", "pump"]
    facts = [
        Fact("A command line is the address string, the command text and a carriage return", source="upstream_code",
             ref=f"{CONTROL}:33"),
        Fact("The pump address is written as a zero-padded two-digit number before the command", source="upstream_code",
             ref=f"{INTERFACE}:17"),
        Fact("The two default pump addresses are 0 and 1", source="upstream_code", ref=f"{INTERFACE}:4-6"),
        Fact("DIAMETER_RANGE is [0.1, 50.0]", source="upstream_code", ref=f"{INTERFACE}:10"),
        Fact("The diameter unit is millimetres", source="upstream_code", ref=f"{INTERFACE}:43"),
        Fact("set_diameter sends 'DIA <value>' and accepts only 0.1 < value < 50.0, so the endpoints are rejected",
             source="upstream_code", ref=f"{INTERFACE}:39-43"),
        Fact("RATE_UNITS is ['UM', 'MM', 'UH', 'MH']", source="upstream_code", ref=f"{INTERFACE}:8"),
        Fact("set_pumping_rate sends 'RAT <value> <rate_unit>' as one command", source="upstream_code",
             ref=f"{INTERFACE}:61-66"),
        Fact("The infuse direction is 'DIR INF', withdraw is 'DIR WDR' and reverse is 'DIR REV'",
             source="upstream_code", ref=f"{INTERFACE}:46-58"),
        Fact("The pump is started with 'RUN' and stopped with 'STP'", source="upstream_code",
             ref=f"{INTERFACE}:68-76"),
        Fact("The version/test command is 'VER'", source="upstream_code", ref=f"{INTERFACE}:31-34"),
        Fact("The serial defaults are 9600 baud and a 0.5 s timeout", source="upstream_code",
             ref=f"{CONTROL}:7-11"),
        Fact("The serial frame is eight data bits with no parity", source="upstream_code", ref=f"{CONTROL}:35-43"),
    ]
    safe_state = "pump stopped with STP"

    # -- writes -------------------------------------------------------------------------------------------------
    @write("diameter", unit="mm", description="Inside diameter of the syringe (DIA)",
           limit=Limit(min=0.1, max=50.0, source="upstream_code", ref=f"{INTERFACE}:10",
                       reason="DIAMETER_RANGE is [0.1, 50.0]"))
    def set_diameter(self, value):
        self.native.set_diameter(self.native.adr1, value)

    @write("direction", type="string", enum=["INF", "WDR"],
           description="Pumping direction token: INF to infuse, WDR to withdraw (DIR INF/DIR WDR)",
           limit=Limit(allowed=["INF", "WDR"], source="upstream_code", ref=f"{INTERFACE}:46-58",
                       reason="the clone sends DIR INF and DIR WDR; DIR REV is the separate reverse action"))
    def set_direction(self, value):
        if value == "INF":
            self.native.set_direction_infuse(self.native.adr1)
        else:
            self.native.set_direction_withdraw(self.native.adr1)

    @write("pumping_rate", type="object",
           description="Pumping rate as one RAT command: the numeric value and the rate-unit token",
           properties={
               "value": Field("number", unit="1",
                              description="Numeric rate sent verbatim in RAT; its physical unit is the rate_unit token",
                              limit=Limit.operator_required(
                                  "the clone accepts any number in RAT and states no numeric rate range; the site "
                                  "supplies the range its pump and tubing allow")),
               "rate_unit": Field("string", enum=RATE_UNITS, description="Rate-unit token accepted by the clone",
                                  limit=Limit(allowed=RATE_UNITS, source="upstream_code", ref=f"{INTERFACE}:8")),
           })
    def set_pumping_rate(self, value):
        self.native.set_pumping_rate(self.native.adr1, value["value"], value["rate_unit"])

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.giansimone.run_pump.v1", description="Start the pump (RUN)",
            output={"reply": Field("string", description="Reply line the pump returned to RUN")})
    def run_pump(self):
        return {"reply": self.native.run_pump(self.native.adr1)}

    @action(name="x-cap.giansimone.stop_pump.v1", safe_state=True,
            description="Stop the pump (STP); the safe-state action",
            output={"reply": Field("string", description="Reply line the pump returned to STP")})
    def stop_pump(self):
        return {"reply": self.native.stop_pump(self.native.adr1)}

    @action(name="x-cap.giansimone.test_pump.v1", description="Send the version/test command (VER)",
            output={"reply": Field("string", description="Reply line the pump returned to VER")})
    def test_pump(self):
        return {"reply": self.native.test_pump(self.native.adr1)}

    @action(name="x-cap.giansimone.reverse_direction.v1",
            description="Reverse the flow for the selected pump (DIR REV)",
            output={"reply": Field("string", description="Reply line the pump returned to DIR REV")})
    def reverse_direction(self):
        return {"reply": self.native.set_direction_reverse(self.native.adr1)}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends STP."""
        self.native.stop_pump(self.native.adr1)
