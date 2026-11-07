"""OpenMHS driver for gh.cukelarter/chemyx-syringe-pump: a CHEMYX syringe pump over its serial text protocol.

The upstream class ``python_dist.CHEMYX_python.core.connect:Connection`` is a Python object that wraps a pyserial
line: each method assembles a text command, appends a carriage return, waits 0.4 s and returns the reply lines as a
list (connect.py:97-143).  The card's ``SerialDriver`` is a one-command/one-reply command table; it cannot express a
multi-line ``view parameter`` reply or keep the last written value in the resource state, so this package is a
direct ``Driver`` over the upstream object (the card deviation is noted in RESULT.json).

* writes: the unit set (the four labels of ``units_dict``), the syringe diameter, the flow rate, the volume, the
  delay and the time.  The clone states no numeric range for diameter, rate, volume, delay or time, so each of those
  is ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the operator overlay
  supplies the envelope of the installed syringe (``site-limits.example.json`` is an example, not a device bound).
* reads: the raw reply of ``pump status``, ``view parameter``, ``read limit parameter``, ``dispensed volume`` and
  ``elapsed time``.  The two volume/time replies are reduced to the last number of the reply; the clone does not
  state their unit, so the fields carry the dimensionless UCUM unit ``1``.
* actions: start, pause, restart and stop the configured run.  The stop action is the R2 safe-state action.
* the e-stop and the safe-state action both send ``stop`` through ``stopPump``.

A pump that dispenses liquid is at least R2 (MHS/spec/04-safety.md), so the risk is R2 even though the card's floor
is R1.  The clone names no independent hardware emergency stop, so the safe-state action is the R2 stop path
(SAFE-045).  This package is model-authored and unreviewed; it was checked on the fake backend only, and no hardware
was attached.

Every Fact and Limit cites a line of the clone at the pinned commit 14011ba2aeb2fcedff7a9b1718e58dc9acefb97f.
"""

import re

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

CLONE = "python_dist/CHEMYX_python/core/connect.py"
GUI = "python_dist/CHEMYX_python/CHEMYX_GUI.py"
INSTRUCTIONS = "documentation/instructions/python_instructions.md"

#: The four unit labels of ``units_dict`` and the index each one sends (connect.py:221-222).
UNITS = ["mL/min", "mL/hr", "μL/min", "μL/hr"]

_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _reply_lines(value):
    """The reply of a Connection method as a list of strings (the clone returns a list of stripped lines)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _reply_text(value):
    """The reply lines joined with a newline, for the raw-text state fields."""
    return "\n".join(_reply_lines(value))


def _last_number(value):
    """The last number of the last non-empty reply line, or a device fault when the reply has none.

    The upstream GUI takes the last space-separated token of a ``view parameter`` line as the value
    (CHEMYX_GUI.py:237); this parser is a little more forgiving and also accepts a number followed by a unit.
    """
    for line in reversed(_reply_lines(value)):
        for token in reversed(line.split()):
            try:
                return float(token)
            except ValueError:
                continue
        match = _NUMBER.search(line)
        if match:
            return float(match.group(0))
    raise DriverFailed("MHS.DEVICE.FAULTED", "the pump reply contains no number")


class ChemyxSyringePump(Driver):
    device_id = "chemyx-syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: R2, above the card's R1 floor: a pump that dispenses is at least R2 (MHS/spec/04-safety.md).
    risk = "R2"
    native = "python_dist.CHEMYX_python.core.connect:Connection"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeConnection"}
    vendor = "Chemyx"
    model = "CHEMYX syringe pump (serial)"
    display_name = "CHEMYX syringe pump"
    tags = ["syringe pump", "pump", "serial", "infuse", "withdraw", "chemyx"]
    facts = [
        Fact("Connection controls serial interfacing with CHEMYX syringe pumps", source="upstream_code",
             ref=f"{CLONE}:47-49"),
        Fact("The constructor takes a port and a baudrate that MUST match the pump's System Settings",
             source="upstream_code", ref=f"{CLONE}:51-57"),
        Fact("openConnection opens the serial line with timeout 0 and calls getPumpStatus", source="upstream_code",
             ref=f"{CLONE}:72-85"),
        Fact("A command is written as text followed by a carriage return", source="upstream_code",
             ref=f"{CLONE}:113"),
        Fact("The upstream waits 0.4 s after a command before it reads the reply", source="upstream_code",
             ref=f"{CLONE}:115"),
        Fact("In multipump mode a set command is prefixed with the current pump number", source="upstream_code",
             ref=f"{CLONE}:109-110"),
        Fact("start, stop, pause and restart are sent as those four words", source="upstream_code",
             ref=f"{CLONE}:163-216"),
        Fact("setUnits maps mL/min, mL/hr, microlitre/min and microlitre/hr to 0, 1, 2 and 3", source="upstream_code",
             ref=f"{CLONE}:221-222"),
        Fact("setDiameter, setRate, setVolume, setDelay and setTime send 'set <name> <value>'", source="upstream_code",
             ref=f"{CLONE}:226-259"),
        Fact("setRate, setVolume and setDelay join a list value with commas for a multi-step run",
             source="upstream_code", ref=f"{CLONE}:232-252"),
        Fact("getParameterLimits, getParameters, getDisplacedVolume, getElapsedTime and getPumpStatus send the query "
             "words 'read limit parameter', 'view parameter', 'dispensed volume', 'elapsed time' and 'pump status'",
             source="upstream_code", ref=f"{CLONE}:263-284"),
        Fact("The GUI parses the getParameters reply by the line indexes 1, 2, 6, 3 and 7 for units, diameter, "
             "volume, rate and delay and takes the last space-separated token as the value", source="upstream_code",
             ref=f"{GUI}:233-237"),
        Fact("The GUI treats a negative volume as withdraw", source="upstream_code", ref=f"{GUI}:243-244"),
        Fact("The GUI labels the syringe diameter in millimetres and the delay in seconds", source="upstream_code",
             ref=f"{GUI}:156-159"),
        Fact("The upstream instructions say the baud rate must match the value in the pump's System Settings",
             source="vendor_doc", ref=f"{INSTRUCTIONS}:21"),
    ]
    safe_state = "pump stopped with the stop command; no new motion starts until a start action"

    @write("units", type="string", enum=UNITS,
           description="Unit set used for rate and volume",
           limit=Limit(allowed=UNITS, source="upstream_code", ref=f"{CLONE}:221-222",
                       reason="units_dict maps exactly these four labels to 0, 1, 2 and 3"))
    def set_units(self, value):
        self.native.setUnits(value)

    @write("diameter", unit="mm", description="Syringe inside diameter",
           limit=Limit.operator_required(
               "the clone states no numeric diameter range; the site supplies the envelope of the installed syringe"))
    def set_diameter(self, value):
        self.native.setDiameter(value)

    @write("rate", unit="1", description="Flow rate in the unit selected by units",
           limit=Limit.operator_required(
               "the clone states no numeric flow-rate range; the site supplies the range of the installed syringe "
               "and tubing in the selected unit"))
    def set_rate(self, value):
        self.native.setRate(value)

    @write("volume", unit="1", description="Volume in the volume unit selected by units",
           limit=Limit.operator_required(
               "the clone states no numeric volume range; the site supplies the volume envelope in the selected "
               "unit"))
    def set_volume(self, value):
        self.native.setVolume(value)

    @write("delay", unit="s", description="Delay before the run (the GUI labels it Delay (sec))",
           limit=Limit.operator_required(
               "the clone states no numeric delay range; the site supplies the delay envelope"))
    def set_delay(self, value):
        self.native.setDelay(value)

    @write("time", unit="1", description="Time value sent as 'set time <value>'",
           limit=Limit.operator_required(
               "the clone sends the time value without a unit and states no range; the site supplies the envelope"))
    def set_time(self, value):
        self.native.setTime(value)

    @read("pump_status", type="string", description="Reply text of the pump status query")
    def pump_status(self):
        return _reply_text(self.native.getPumpStatus())

    @read("parameters", type="string", description="Reply text of the view parameter query")
    def parameters(self):
        return _reply_text(self.native.getParameters())

    @read("parameter_limits", type="string", description="Reply text of the read limit parameter query")
    def parameter_limits(self):
        return _reply_text(self.native.getParameterLimits())

    @read("displaced_volume", unit="1", description="Last number of the dispensed volume reply")
    def displaced_volume(self):
        return _last_number(self.native.getDisplacedVolume())

    @read("elapsed_time", unit="1", description="Last number of the elapsed time reply")
    def elapsed_time(self):
        return _last_number(self.native.getElapsedTime())

    @action(name="x-cap.cukelarter.start.v1",
            description="Start the configured run (start)",
            output={"reply": Field("array", items="string", description="Reply lines of the pump")})
    def start_run(self):
        return {"reply": _reply_lines(self.native.startPump())}

    @action(name="x-cap.cukelarter.pause.v1",
            description="Pause the current run (pause)",
            output={"reply": Field("array", items="string", description="Reply lines of the pump")})
    def pause_run(self):
        return {"reply": _reply_lines(self.native.pausePump())}

    @action(name="x-cap.cukelarter.restart.v1",
            description="Restart the pump (restart)",
            output={"reply": Field("array", items="string", description="Reply lines of the pump")})
    def restart_run(self):
        return {"reply": _reply_lines(self.native.restartPump())}

    @action(name="x-cap.cukelarter.stop.v1", safe_state=True,
            description="Stop the pump (stop), the safe state",
            output={"reply": Field("array", items="string", description="Reply lines of the pump")})
    def stop_run(self):
        return {"reply": _reply_lines(self.native.stopPump())}

    @estop(native="stopPump")
    def stop(self):
        """The native stop: the runtime latches first, then sends stop."""
        self.native.stopPump()
