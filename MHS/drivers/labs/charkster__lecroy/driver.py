"""OpenMHS driver for gh.charkster/lecroy: a LeCroy oscilloscope over the upstream ``lecroy`` class.

A direct ``Driver`` over the upstream high-level class ``lecroy:lecroy``.  The card proposes a ``ScpiDriver``
(family ``scpi``, decision ``family-config``), but the upstream surface is an object with methods, not a table of
fixed command lines: every method assembles several VBS or SCPI commands from its arguments (``trigger_setup``
writes six lines, ``channel_setup`` writes dozens), and the class holds a pyvisa instrument, so a command table
cannot reproduce the lines the device receives.  This package is a direct Driver over the upstream class with a
``native.py`` factory (DEVIATION FROM THE CARD, recorded in RESULT.json notes).

* reads: the horizontal scale, the edge-trigger source, level, horizontal offset, slope, mode and type, the
  enabled analog channels (label, vertical scale, vertical offset, bandwidth limit and coupling), the enabled
  digital channel labels and the measurement slots (source and parameter);
* writes: the horizontal scale, the trigger level and horizontal offset, the trigger slope and mode; every setter
  calls the upstream method that sends the corresponding VBS or SCPI command and reads the result back;
* actions: configure the edge trigger in one call, force a trigger event, reset the instrument, read one numeric
  measurement result and set the display grid mode;
* the e-stop sends ``*RST`` through the native ``reset_scope``: the instrument returns to its power-on defaults
  and any acquisition configuration is cleared, which is this instrument's safe state.

NOT COVERED: the screen image.  ``get_screen_image`` writes a PNG file of the display and returns its byte
count; no catalogue class carries an image array for an instrument, and the clone writes to a local path, so this
package serves the scope's scalar settings and measurements, not the screenshot.  The channel, math, date/time,
intensity, memory-size and colour setters of the clone are not exposed either: the clone has no getter for them,
or no text states a bound, so a write could not be read back or bounded.  The measurement list of
``measurement_setup`` is described as a partial list by the clone itself (``lecroy.py:234``), so only the
statistics that ``getValueOnChannel`` actually implements are served.

Every Fact and Limit cites a line of the clone at the pinned commit
(da08c5168d8c63809d60b4c8b4b3529cbaf3de18).  This package is model-authored and unreviewed, is checked on the
fake backend only, and never ran on an instrument.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

TRIGGER_SLOPES = ["Positive", "Negative", "Either"]
TRIGGER_MODES = ["Single", "Normal", "Auto", "Stopped"]
GRID_MODES = ["Single", "Dual", "Quad", "Octal", "Tandem", "Quattro", "Auto"]
MEASUREMENT_SLOTS = [f"P{index}" for index in range(1, 13)]
NUMERIC_STATS = ["value", "mean", "max", "min", "num", "sdev"]


def _trigger_output() -> dict:
    return {
        "trigger_source": Field("string", description="Trigger source read back from the instrument"),
        "trigger_level": Field("number", unit="V", description="Trigger level read back from the instrument"),
        "trigger_horizontal_offset": Field("number", unit="s",
                                           description="Trigger horizontal offset read back from the instrument"),
        "trigger_slope": Field("string", description="Trigger edge slope read back from the instrument"),
        "trigger_mode": Field("string", description="Trigger mode read back from the instrument"),
        "trigger_type": Field("string", description="Trigger type read back from the instrument"),
    }


class Lecroy(Driver):
    device_id = "lecroy"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "lecroy:lecroy"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLecroy"}
    vendor = "LeCroy"
    model = "LeCroy oscilloscope (charkster/lecroy)"
    display_name = "LeCroy oscilloscope (lecroy.lecroy)"
    tags = ["oscilloscope", "lecroy", "scpi", "vbs", "visa", "instrument"]
    facts = [
        Fact("The class wraps a pyvisa instrument object passed to its constructor", source="upstream_code",
             ref="lecroy.py:7-10"),
        Fact("get_screen_image writes a PNG screenshot to a file and returns its byte count", source="upstream_code",
             ref="lecroy.py:15-27"),
        Fact("A screen image accepts the backcolor 'WHITE' or 'BLACK'", source="upstream_code", ref="lecroy.py:16"),
        Fact("trigger_setup takes the trigger channel, level, horizontal offset, slope and mode",
             source="upstream_code", ref="lecroy.py:29-36"),
        Fact("The trigger channel is a scope channel such as 'C1' or 'D1'", source="upstream_code",
             ref="lecroy.py:32"),
        Fact("The trigger slope is 'Positive', 'Negative' or 'Either'", source="upstream_code", ref="lecroy.py:35"),
        Fact("The trigger mode is 'Single', 'Normal', 'Auto' or 'Stopped'", source="upstream_code",
             ref="lecroy.py:36"),
        Fact("trigger_setup writes the VBS trigger commands and sets Trigger.Type to Edge", source="upstream_code",
             ref="lecroy.py:41-46"),
        Fact("get_trigger_setup returns the channel, level, horizontal offset, slope, mode and trigger type under "
             "keys 0 to 5", source="upstream_code", ref="lecroy.py:61-68"),
        Fact("get_analog_channel_setup returns the label, vertical scale, vertical offset, bandwidth limit and "
             "coupling of channels 1 to 8", source="upstream_code", ref="lecroy.py:170-182"),
        Fact("get_digital_channel_setup returns the label of each enabled digital channel 0 to 15",
             source="upstream_code", ref="lecroy.py:184-190"),
        Fact("get_measurement_setup reads measurement slots P1 to P12 and returns each source and parameter",
             source="upstream_code", ref="lecroy.py:262-269"),
        Fact("getValueOnChannel reads value, mean, max, min, num and sdev as a float and status as text",
             source="upstream_code", ref="lecroy.py:296-310"),
        Fact("setGrid accepts Single, Dual, Quad, Octal, Tandem, Quattro or Auto", source="upstream_code",
             ref="lecroy.py:312-318"),
        Fact("setHorizontal_delay writes the horizontal offset in Horizontal.HorOffset", source="upstream_code",
             ref="lecroy.py:320-321"),
        Fact("reset_scope sends *RST", source="upstream_code", ref="lecroy.py:323-324"),
        Fact("trigger_force sends FORCE_TRIGGER", source="upstream_code", ref="lecroy.py:192-194"),
        Fact("get_horizontal_scale reads Horizontal.HorScale", source="upstream_code", ref="lecroy.py:200-202"),
        Fact("The README describes the class as configuration, measurement and screen capture for a LeCroy "
             "oscilloscope", source="vendor_doc", ref="README.md:5"),
    ]
    safe_state = ("instrument reset to its power-on defaults (*RST); the trigger and acquisition configuration "
                  "is cleared")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("horizontal_scale", unit="s", description="Horizontal scale in seconds per division")
    def horizontal_scale(self):
        return float(self.native.get_horizontal_scale())

    @read("trigger_source", type="string", description="Trigger source reported by the instrument")
    def trigger_source(self):
        return str(self._trigger_state()["trigger_source"])

    @read("trigger_level", unit="V", description="Trigger level in volts")
    def trigger_level(self):
        return float(self._trigger_state()["trigger_level"])

    @read("trigger_horizontal_offset", unit="s", description="Trigger horizontal offset in seconds")
    def trigger_horizontal_offset(self):
        return float(self._trigger_state()["trigger_horizontal_offset"])

    @read("trigger_slope", type="string", description="Trigger edge slope")
    def trigger_slope(self):
        return str(self._trigger_state()["trigger_slope"])

    @read("trigger_mode", type="string", description="Trigger mode")
    def trigger_mode(self):
        return str(self._trigger_state()["trigger_mode"])

    @read("trigger_type", type="string", description="Trigger type")
    def trigger_type(self):
        return str(self._trigger_state()["trigger_type"])

    @read("analog_channels", type="object",
          description="Enabled analog channels: label, vertical scale, vertical offset, bandwidth limit and coupling")
    def analog_channels(self):
        found = {}
        for channel, setup in sorted(self.native.get_analog_channel_setup().items()):
            label, scale, offset, bandwidth, coupling = setup
            found[str(channel)] = {
                "label": str(label),
                "vertical_scale": float(scale),
                "vertical_offset": float(offset),
                "bandwidth_limit": str(bandwidth),
                "coupling": str(coupling),
            }
        return found

    @read("digital_channels", type="object",
          description="Labels of the enabled digital channels, keyed by channel number")
    def digital_channels(self):
        return {str(channel): str(label)
                for channel, label in sorted(self.native.get_digital_channel_setup().items())}

    @read("measurement_setup", type="object",
          description="Measurement slots with their source channel and measurement parameter")
    def measurement_setup(self):
        return {str(slot): {"source": str(source), "parameter": str(parameter)}
                for slot, (source, parameter) in sorted(self.native.get_measurement_setup().items())}

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("horizontal_scale", unit="s", description="Horizontal scale in seconds per division",
           limit=Limit.operator_required(
               "the clone states only the method default of 1E-3 s (lecroy.py:196), not the scale range of the "
               "instrument; the site supplies the timebase range it allows"))
    def set_horizontal_scale(self, value):
        self.native.horizontal_scale(float(value))
        return float(self.native.get_horizontal_scale())

    @write("trigger_level", unit="V", description="Trigger level in volts",
           limit=Limit.operator_required(
               "the clone states no trigger level range (lecroy.py:33); the site supplies the range of its "
               "trigger source"))
    def set_trigger_level(self, value):
        self._apply_trigger(trigger_level=value)
        return float(self.native.get_trigger_setup()[1])

    @write("trigger_horizontal_offset", unit="s", description="Trigger horizontal offset in seconds",
           limit=Limit.operator_required(
               "the clone states no horizontal offset range (lecroy.py:34); the site supplies the window of its "
               "timebase"))
    def set_trigger_horizontal_offset(self, value):
        self.native.setHorizontal_delay(float(value))
        return float(self.native.get_trigger_setup()[2])

    @write("trigger_slope", type="string", description="Trigger edge slope",
           limit=Limit(allowed=TRIGGER_SLOPES, source="upstream_code", ref="lecroy.py:35"))
    def set_trigger_slope(self, value):
        self._apply_trigger(trigger_slope=value)
        return str(self.native.get_trigger_setup()[3])

    @write("trigger_mode", type="string", description="Trigger mode",
           limit=Limit(allowed=TRIGGER_MODES, source="upstream_code", ref="lecroy.py:36"))
    def set_trigger_mode(self, value):
        self._apply_trigger(trigger_mode=value)
        return str(self.native.get_trigger_setup()[4])

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.charkster.trigger.v1",
            description="Configure the edge trigger level, horizontal offset, slope and mode",
            input={
                "trigger_level": Field(
                    "number", unit="V", description="Trigger level in volts",
                    limit=Limit.operator_required(
                        "the clone states no trigger level range (lecroy.py:33); the site supplies the range of "
                        "its trigger source")),
                "trigger_horizontal_offset": Field(
                    "number", unit="s", description="Trigger horizontal offset in seconds",
                    limit=Limit.operator_required(
                        "the clone states no horizontal offset range (lecroy.py:34); the site supplies the window "
                        "of its timebase")),
                "trigger_slope": Field(
                    "string", description="Trigger edge slope",
                    limit=Limit(allowed=TRIGGER_SLOPES, source="upstream_code", ref="lecroy.py:35")),
                "trigger_mode": Field(
                    "string", description="Trigger mode",
                    limit=Limit(allowed=TRIGGER_MODES, source="upstream_code", ref="lecroy.py:36")),
            },
            output=_trigger_output())
    def trigger(self, trigger_level, trigger_horizontal_offset, trigger_slope, trigger_mode):
        self._apply_trigger(
            trigger_level=trigger_level,
            trigger_horizontal_offset=trigger_horizontal_offset,
            trigger_slope=trigger_slope,
            trigger_mode=trigger_mode,
        )
        return self._trigger_state()

    @action(name="x-cap.charkster.force.v1", description="Force a trigger event (FORCE_TRIGGER)",
            output=_trigger_output())
    def force(self):
        self.native.trigger_force()
        return self._trigger_state()

    @action(name="x-cap.charkster.reset.v1",
            description="Reset the instrument to its power-on defaults (*RST)",
            output={**_trigger_output(),
                    "horizontal_scale": Field("number", unit="s",
                                              description="Horizontal scale after the reset")})
    def reset_instrument(self):
        self.native.reset_scope()
        state = self._trigger_state()
        state["horizontal_scale"] = float(self.native.get_horizontal_scale())
        return state

    @action(name="x-cap.charkster.measure.v1", description="Read one numeric measurement result",
            input={
                "assigned_channel": Field(
                    "string", description="Measurement slot, P1 to P12",
                    limit=Limit(allowed=MEASUREMENT_SLOTS, source="upstream_code", ref="lecroy.py:262-269")),
                "stat_type": Field(
                    "string", description="Numeric statistic of the measurement",
                    limit=Limit(allowed=NUMERIC_STATS, source="upstream_code", ref="lecroy.py:296-302")),
            },
            output={
                "assigned_channel": Field("string", description="Measurement slot that was read"),
                "stat_type": Field("string", description="Statistic that was read"),
                "value": Field("number",
                               description="Measurement result in the instrument's unit for the measurement"),
            })
    def measure(self, assigned_channel, stat_type):
        result = self.native.getValueOnChannel(assigned_channel, stat_type=stat_type)
        try:
            value = float(result)
        except (TypeError, ValueError):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"measurement {assigned_channel} {stat_type} returned {result!r}, not a numeric "
                               "result")
        return {"assigned_channel": assigned_channel, "stat_type": stat_type, "value": value}

    @action(name="x-cap.charkster.grid.v1",
            description="Set the display grid mode (app.Display.GridMode)",
            input={
                "grid_mode": Field(
                    "string", description="Display grid mode",
                    limit=Limit(allowed=GRID_MODES, source="upstream_code", ref="lecroy.py:315")),
            },
            output={"grid_mode": Field("string", description="Grid mode sent to the instrument")})
    def set_grid(self, grid_mode):
        self.native.setGrid(grid_mode)
        return {"grid_mode": grid_mode}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="reset_scope")
    def stop(self):
        """The native stop: the runtime latches first, then reset_scope sends *RST."""
        self.native.reset_scope()

    # -- helpers --------------------------------------------------------------------------------------------------
    def _trigger_state(self) -> dict:
        setup = self.native.get_trigger_setup()
        return {
            "trigger_source": str(setup[0]),
            "trigger_level": float(setup[1]),
            "trigger_horizontal_offset": float(setup[2]),
            "trigger_slope": str(setup[3]),
            "trigger_mode": str(setup[4]),
            "trigger_type": str(setup[5]),
        }

    def _apply_trigger(self, *, trigger_level=None, trigger_horizontal_offset=None,
                       trigger_slope=None, trigger_mode=None) -> None:
        """Change the named trigger settings and keep the source and the other settings the instrument reports."""
        current = self.native.get_trigger_setup()
        source = str(current[0])
        level = float(current[1]) if trigger_level is None else float(trigger_level)
        horizontal = float(current[2]) if trigger_horizontal_offset is None else float(trigger_horizontal_offset)
        slope = str(current[3]) if trigger_slope is None else str(trigger_slope)
        mode = str(current[4]) if trigger_mode is None else str(trigger_mode)
        self.native.trigger_setup(source, level, horizontal, slope, mode)
