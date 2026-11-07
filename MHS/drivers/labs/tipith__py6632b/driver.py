"""OpenMHS driver for gh.tipith/py6632b: an HP 6632B DC source over its upstream serial class.

A direct Driver (decorated methods) over ``py6632B.py6632B:HP6632B``.  The upstream class is a ``threading.Thread``
whose constructor opens a serial line and whose ``run()`` is a CSV logging loop; it is not an SDK object with a
per-parameter getter/setter API.  The source is configured by one combined command, ``SOUR:VOLT %.3f; CURR %u MA``
(py6632B/py6632B.py:120-122), so voltage and current are set together by the ``set_source`` action instead of two
independent writes.  The output is enabled separately (``OUTP:STAT``); the measured voltage and current, the output
state and the identification reply are read-only state.

Every Fact cites a line of the clone at the pinned commit a91f78a004f592e7588d483f28daebcbab8572e8.  No text file of
the clone states an output voltage or current range, so both numeric inputs are ``Limit.operator_required``: without
an operator overlay every call that sets them is refused ``MHS.SAFETY.LIMITS_UNSET``.  This package is model-authored
and unreviewed; it runs on the fake backend only (the loader refuses its R2 hardware backend until a human signs
``reviewed_by``).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


class HP6632B(Driver):
    device_id = "py6632b"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R2"
    native = "py6632B.py6632B:HP6632B"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeHP6632B"}
    vendor, model = "Hewlett-Packard", "6632B"
    display_name = "HP 6632B DC source (py6632B.HP6632B)"
    tags = ["power-supply", "dc-source", "battery-charger", "serial"]
    facts = [
        Fact("The serial line is opened at 9600 baud with a 0.5 s read timeout", source="upstream_code",
             ref="py6632B/py6632B.py:36"),
        Fact("The constructor resets the instrument and identifies it with '*IDN?'; it accepts the unit when the "
             "reply contains 'HEWLETT-PACKARD,6632B'", source="upstream_code", ref="py6632B/py6632B.py:41-44"),
        Fact("A measurement is read with 'MEAS:VOLT?;CURR?' and split into voltage and current", source="upstream_code",
             ref="py6632B/py6632B.py:112-115"),
        Fact("The source is set with 'SOUR:VOLT %.3f; CURR %u MA': voltage in volts with three decimals and current "
             "in milliamperes as an integer", source="upstream_code", ref="py6632B/py6632B.py:119-122"),
        Fact("Output enable writes 'OUTP:STAT 1' or 'OUTP:STAT 0'; 'OUTP:STAT?' reads the state", source="upstream_code",
             ref="py6632B/py6632B.py:124-135"),
        Fact("The native stop sets the output state to 0, clears the logging run flag and joins the logging thread",
             source="upstream_code", ref="py6632B/py6632B.py:84-88"),
        Fact("A measurement query takes about 109 ms", source="upstream_code", ref="py6632B/py6632B.py:48-50"),
        Fact("The upstream code charges and discharges a Li-ion battery, deriving the current from the battery "
             "capacity", source="upstream_code", ref="py6632B/py6632B.py:178-185"),
        Fact("The upstream oscillate() sets 15 V and 1000 mA before toggling the output", source="upstream_code",
             ref="py6632B/py6632B.py:158-162"),
        Fact("The display accepts mode NORM or TEXT and at most 14 characters of text", source="upstream_code",
             ref="py6632B/py6632B.py:137-147"),
        Fact("stop() calls isAlive(), a Python 2 Thread method", source="upstream_code",
             ref="py6632B/py6632B.py:87"),
        Fact("oscillate() iterates with xrange(), a Python 2 built-in", source="upstream_code",
             ref="py6632B/py6632B.py:160"),
        Fact("The package __init__ imports HP6632B with an implicit relative import", source="upstream_code",
             ref="py6632B/__init__.py:1"),
    ]
    # R2: a source that the upstream code uses to charge and discharge Li-ion batteries is an energy source, not an
    # observation-only instrument.  The safe state is the output off; there is no independent hardware e-stop in the
    # clone, so the safe-state action below satisfies SAFE-045 instead of a physical reference.
    safe_state = "source output disabled (OUTP:STAT 0)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("voltage", unit="V", description="Measured output voltage")
    def voltage(self):
        return float(self.native.get_volt_and_curr().volt)

    @read("current", unit="A", description="Measured output current")
    def current(self):
        return float(self.native.get_volt_and_curr().curr)

    @read("output_enabled", type="boolean", description="True while the source output is enabled")
    def output_enabled(self):
        return str(self.native.get_output_state()).strip() == "1"

    @read("identity", type="string", description="Identification reply to '*IDN?'")
    def identity(self):
        return str(self.native.identify())

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.tipith.set_source.v1",
            description="Set the output voltage and current limit together with one native SOUR:VOLT/CURR command",
            input={
                "voltage_v": Field(
                    "number", unit="V", description="Output voltage set point",
                    limit=Limit.operator_required(
                        "no text file of the clone states the output voltage range; the operator sets the limit of "
                        "this unit")),
                "current_ma": Field(
                    "integer", unit="mA", description="Output current limit",
                    limit=Limit.operator_required(
                        "no text file of the clone states the output current range; the operator sets the limit of "
                        "this unit")),
            },
            output={
                "voltage_v": Field("number", unit="V", description="Voltage written to the source"),
                "current_ma": Field("integer", unit="mA", description="Current limit written to the source"),
            })
    def set_source(self, voltage_v, current_ma):
        applied_v = round(float(voltage_v), 3)      # the upstream command formats the voltage with '%.3f'
        applied_ma = int(current_ma)                # the upstream command formats the current with '%u'
        self.native.set_volt_and_curr(applied_v, applied_ma)
        return {"voltage_v": applied_v, "current_ma": applied_ma}

    @action(name="x-cap.tipith.set_output.v1", description="Enable or disable the source output",
            input={"enabled": Field("boolean", description="True to enable the output, false to disable it")},
            output={"output_enabled": Field("boolean", description="The state written to OUTP:STAT")})
    def set_output(self, enabled):
        self.native.set_output_state(1 if enabled else 0)
        return {"output_enabled": bool(enabled)}

    @action(name="x-cap.tipith.stop_output.v1", safe_state=True,
            description="Disable the source output (the safe state); it takes no input",
            output={"output_enabled": Field("boolean", description="False once the output is disabled")})
    def stop_output(self):
        self.native.set_output_state(0)
        return {"output_enabled": False}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then calls stop(), which sets OUTP:STAT 0."""
        self.native.stop()
