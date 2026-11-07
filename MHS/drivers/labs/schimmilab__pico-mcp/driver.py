"""OpenMHS driver for gh.schimmilab/pico-mcp: a PicoScope 5000A/B USB oscilloscope.

A direct Driver (decorated methods) over the upstream class ``pico_mcp.scope:Scope``
(src/pico_mcp/scope.py:100), the stateful handle of one connected PicoScope 5000A/B device.  The upstream class wraps
the picosdk ps5000a driver directly (scope.py:19, README.md:11); this package uses the same class, not the FastMCP
front end.

* reads: the connection state, the variant and serial strings, the ADC resolution and maximum value, and the
  enabled/coupling/range state of channels A to D;
* writes: the enabled, coupling and full-scale range of channels A to D, served through ``cap.device.configure.v1``;
  the range is the clone's 0.01 V to 20.0 V full-scale range (scope.py:24-30);
* actions: configure the built-in signal generator, turn it off (the safe-state action), and capture one block and
  return the scalar measurements.  The upstream class stores no signal-generator state and has no getter for it, so
  the generator is an ``x-cap`` invoke rather than a readable state field.  No catalogue class carries an
  oscilloscope block capture; ``cap.measure.voltage.v1`` binds instrument.dmm, instrument.smu and sensor, not an
  oscilloscope.  The waveform array is NOT COVERED (see RESULT.json notes): the upstream class returns a downsampled
  ``waveform_mv`` list (scope.py:380-392), but no catalogue class carries a trace array, so this package serves the
  scalar measurements and the settings;
* the native stop turns the signal generator off (DC at 0 V, scope.py:206-213); it is the e-stop and the safe-state
  action.  The card floor is R1; the scope is a passive measuring instrument plus a low-voltage built-in generator.

Every Fact and Limit cites a line of the clone at the pinned commit
(08fd81ee1c1e79b4d82e0997ca840b46adeef811).  This package is model-authored and unreviewed: it is checked on the
fake backend only, and nothing here ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The channel names and the coupling spellings the clone validates (scope.py:44-45, 180).
CHANNELS = ["A", "B", "C", "D"]
COUPLINGS = ["DC", "AC"]

#: The wave names the clone's signal-generator map uses (scope.py:34-35).
WAVES = ["sine", "square", "triangle", "ramp_up", "ramp_down", "dc"]

#: The full-scale voltage range table of the clone (scope.py:24-30; 0.01 V to 20.0 V).
RANGE_LIMIT = Limit(min=0.01, max=20.0, unit="V", source="upstream_code",
                    ref="src/pico_mcp/scope.py:25-29")

#: The two coupling spellings the clone maps to PS5000A_AC and PS5000A_DC (scope.py:180).
COUPLING_LIMIT = Limit(allowed=COUPLINGS, source="upstream_code",
                       ref="src/pico_mcp/scope.py:180")


class PicoScope(Driver):
    device_id = "picoscope-5000a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pico_mcp.scope:Scope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScope"}
    vendor = "Pico Technology"
    model = "PicoScope 5000A/B series USB oscilloscope"
    display_name = "PicoScope 5000A/B series oscilloscope (pico_mcp.scope.Scope)"
    tags = ["oscilloscope", "picoscope", "ps5000a", "usb", "signal-generator", "block-capture"]
    facts = [
        Fact("Scope is the stateful handle of one connected PicoScope 5000A device; it keeps the handle, the "
             "resolution, max_adc, the variant and serial strings and the configured channels",
             source="upstream_code", ref="src/pico_mcp/scope.py:100-108"),
        Fact("The clone targets the PicoScope 5000A/B series and was verified on a 5442B",
             source="upstream_code", ref="src/pico_mcp/scope.py:3-4"),
        Fact("The README describes a lean MCP server for PicoScope 5000A USB oscilloscopes developed and "
             "verified on a 5442B", source="vendor_doc", ref="README.md:3-4"),
        Fact("connect opens the unit, reads max_adc with ps5000aMaximumValue and reads the variant and serial with "
             "ps5000aGetUnitInfo", source="upstream_code", ref="src/pico_mcp/scope.py:115-143"),
        Fact("The resolution must be one of 8, 12, 14, 15 and 16 bits", source="upstream_code",
             ref="src/pico_mcp/scope.py:41-42"),
        Fact("The channel names are A, B, C and D", source="upstream_code", ref="src/pico_mcp/scope.py:44-45"),
        Fact("set_channel validates the channel, maps AC or DC to PS5000A_AC or PS5000A_DC, picks the smallest "
             "range in _RANGE_NAMES that covers the request and calls ps5000aSetChannel",
             source="upstream_code", ref="src/pico_mcp/scope.py:174-187"),
        Fact("The full-scale voltage ranges run from 0.01 V to 20.0 V", source="upstream_code",
             ref="src/pico_mcp/scope.py:24-30"),
        Fact("set_channel defaults to enabled=True, coupling='DC', range_volts=5.0 and analog_offset=0.0",
             source="upstream_code", ref="src/pico_mcp/scope.py:174-175"),
        Fact("The README states that set_channel covers channel A to D, enable, DC/AC and a range of 0.01 to 20 V",
             source="vendor_doc", ref="README.md:90"),
        Fact("The signal-generator wave names are sine, square, triangle, ramp_up, ramp_down and dc",
             source="upstream_code", ref="src/pico_mcp/scope.py:34-35"),
        Fact("set_signal_generator converts amplitude_v to peak-to-peak (amplitude * 2 * 1e6) and calls "
             "ps5000aSetSigGenBuiltInV2 with the frequency and wave", source="upstream_code",
             ref="src/pico_mcp/scope.py:190-204"),
        Fact("stop_signal_generator sets the generator to DC at 0 V to turn the output off",
             source="upstream_code", ref="src/pico_mcp/scope.py:206-213"),
        Fact("The README states that set_signal_generator and stop_signal_generator drive the built-in AWG with "
             "sine, square, triangle and ramp, frequency and amplitude", source="vendor_doc",
             ref="README.md:91"),
        Fact("capture_block captures one block on all enabled channels and returns the sample count, sample "
             "interval, sample rate, duration, timebase and per-channel measurements",
             source="upstream_code", ref="src/pico_mcp/scope.py:216-239"),
        Fact("The per-channel analysis returns vpp_mv, vmin_mv, vmax_mv, mean_mv, rms_mv, frequency_hz, "
             "over_range and a downsampled waveform_mv", source="upstream_code",
             ref="src/pico_mcp/scope.py:367-392"),
        Fact("The README states that capture_block returns Vpp/min/max/mean/rms, an estimated frequency and a "
             "downsampled waveform", source="vendor_doc", ref="README.md:92"),
        Fact("The capture waits up to 10 s for ps5000aIsReady and stops the unit when the deadline passes",
             source="upstream_code", ref="src/pico_mcp/scope.py:274-281"),
        Fact("The pyproject declares numpy and picosdk as runtime dependencies", source="upstream_code",
             ref="pyproject.toml:12-14"),
    ]
    safe_state = "signal generator output off (DC at 0 V); the scope then only measures passively"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("connected", type="boolean", description="True while the upstream handle is open")
    def connected(self):
        return bool(self.native.connected)

    @read("variant", type="string", description="Variant string the scope reports (for example 5442B)")
    def variant(self):
        return str(self.native.variant)

    @read("serial", type="string", description="Batch and serial number the scope reports")
    def serial(self):
        return str(self.native.serial)

    @read("resolution_bits", type="integer", unit="1", description="ADC resolution in bits")
    def resolution_bits(self):
        return int(self.native.resolution_bits)

    @read("max_adc", type="integer", unit="1", description="Largest ADC value of the current resolution")
    def max_adc(self):
        return int(self.native.max_adc)

    @read("channel_a_enabled", type="boolean", description="Channel A enabled")
    def channel_a_enabled(self):
        return self._channel_value("A", "enabled")

    @read("channel_a_coupling", type="string", description="Channel A coupling (DC or AC)")
    def channel_a_coupling(self):
        return self._channel_value("A", "coupling")

    @read("channel_a_range_v", unit="V", description="Channel A full-scale voltage range")
    def channel_a_range_v(self):
        return self._channel_value("A", "range_volts")

    @read("channel_b_enabled", type="boolean", description="Channel B enabled")
    def channel_b_enabled(self):
        return self._channel_value("B", "enabled")

    @read("channel_b_coupling", type="string", description="Channel B coupling (DC or AC)")
    def channel_b_coupling(self):
        return self._channel_value("B", "coupling")

    @read("channel_b_range_v", unit="V", description="Channel B full-scale voltage range")
    def channel_b_range_v(self):
        return self._channel_value("B", "range_volts")

    @read("channel_c_enabled", type="boolean", description="Channel C enabled")
    def channel_c_enabled(self):
        return self._channel_value("C", "enabled")

    @read("channel_c_coupling", type="string", description="Channel C coupling (DC or AC)")
    def channel_c_coupling(self):
        return self._channel_value("C", "coupling")

    @read("channel_c_range_v", unit="V", description="Channel C full-scale voltage range")
    def channel_c_range_v(self):
        return self._channel_value("C", "range_volts")

    @read("channel_d_enabled", type="boolean", description="Channel D enabled")
    def channel_d_enabled(self):
        return self._channel_value("D", "enabled")

    @read("channel_d_coupling", type="string", description="Channel D coupling (DC or AC)")
    def channel_d_coupling(self):
        return self._channel_value("D", "coupling")

    @read("channel_d_range_v", unit="V", description="Channel D full-scale voltage range")
    def channel_d_range_v(self):
        return self._channel_value("D", "range_volts")

    # -- channel writes -------------------------------------------------------------------------------------------
    @write("channel_a_enabled", type="boolean", description="Enable or disable channel A")
    def set_channel_a_enabled(self, value):
        return bool(self._apply_channel("A", enabled=bool(value))["enabled"])

    @write("channel_a_coupling", type="string", description="Channel A coupling (DC or AC)",
           limit=COUPLING_LIMIT)
    def set_channel_a_coupling(self, value):
        return str(self._apply_channel("A", coupling=str(value).upper())["coupling"])

    @write("channel_a_range_v", unit="V", description="Channel A full-scale voltage range",
           limit=RANGE_LIMIT)
    def set_channel_a_range_v(self, value):
        return float(self._apply_channel("A", range_volts=float(value))["range_volts"])

    @write("channel_b_enabled", type="boolean", description="Enable or disable channel B")
    def set_channel_b_enabled(self, value):
        return bool(self._apply_channel("B", enabled=bool(value))["enabled"])

    @write("channel_b_coupling", type="string", description="Channel B coupling (DC or AC)",
           limit=COUPLING_LIMIT)
    def set_channel_b_coupling(self, value):
        return str(self._apply_channel("B", coupling=str(value).upper())["coupling"])

    @write("channel_b_range_v", unit="V", description="Channel B full-scale voltage range",
           limit=RANGE_LIMIT)
    def set_channel_b_range_v(self, value):
        return float(self._apply_channel("B", range_volts=float(value))["range_volts"])

    @write("channel_c_enabled", type="boolean", description="Enable or disable channel C")
    def set_channel_c_enabled(self, value):
        return bool(self._apply_channel("C", enabled=bool(value))["enabled"])

    @write("channel_c_coupling", type="string", description="Channel C coupling (DC or AC)",
           limit=COUPLING_LIMIT)
    def set_channel_c_coupling(self, value):
        return str(self._apply_channel("C", coupling=str(value).upper())["coupling"])

    @write("channel_c_range_v", unit="V", description="Channel C full-scale voltage range",
           limit=RANGE_LIMIT)
    def set_channel_c_range_v(self, value):
        return float(self._apply_channel("C", range_volts=float(value))["range_volts"])

    @write("channel_d_enabled", type="boolean", description="Enable or disable channel D")
    def set_channel_d_enabled(self, value):
        return bool(self._apply_channel("D", enabled=bool(value))["enabled"])

    @write("channel_d_coupling", type="string", description="Channel D coupling (DC or AC)",
           limit=COUPLING_LIMIT)
    def set_channel_d_coupling(self, value):
        return str(self._apply_channel("D", coupling=str(value).upper())["coupling"])

    @write("channel_d_range_v", unit="V", description="Channel D full-scale voltage range",
           limit=RANGE_LIMIT)
    def set_channel_d_range_v(self, value):
        return float(self._apply_channel("D", range_volts=float(value))["range_volts"])

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.schimmilab.set_signal_generator.v1",
            description="Configure the built-in signal generator (AWG) through ps5000aSetSigGenBuiltInV2",
            input={
                "frequency_hz": Field(
                    "number", unit="Hz", description="Signal frequency",
                    limit=Limit.operator_required(
                        "the clone states no AWG frequency range: scope.py:190-202 passes the frequency straight "
                        "to ps5000aSetSigGenBuiltInV2 and README.md:91 states no bound")),
                "amplitude_v": Field(
                    "number", unit="V", description="Peak amplitude, half of peak-to-peak",
                    limit=Limit.operator_required(
                        "the clone states no AWG amplitude range: scope.py:196-197 converts the value to "
                        "peak-to-peak and README.md:91 states no bound")),
                "wave": Field("string", description="Waveform name", enum=WAVES),
            },
            output={
                "frequency_hz": Field("number", unit="Hz", description="Frequency applied"),
                "amplitude_v": Field("number", unit="V", description="Peak amplitude applied"),
                "offset_v": Field("number", unit="V", description="DC offset applied"),
                "wave": Field("string", description="Waveform applied"),
            })
    def set_signal_generator(self, frequency_hz, amplitude_v, wave):
        return self.native.set_signal_generator(float(frequency_hz), float(amplitude_v), str(wave))

    @action(name="x-cap.schimmilab.stop_signal_generator.v1", safe_state=True,
            description="Turn the built-in signal generator off (DC at 0 V); the safe state, no input",
            output={"signal_generator": Field("string",
                                              description="'off' once the native generator stop returned")})
    def stop_signal_generator(self):
        return self.native.stop_signal_generator()

    @action(name="x-cap.schimmilab.capture_block.v1",
            description="Capture one block on all enabled channels and return the scalar measurements",
            input={
                "samples": Field(
                    "integer", unit="1", description="Number of samples to capture",
                    limit=Limit.operator_required(
                        "the clone states no sample-count bound: scope.py:216-272 passes samples to "
                        "ps5000aRunBlock without a range and README.md:92 states none")),
                "timebase": Field(
                    "integer", unit="1", description="Timebase number selecting the sample interval",
                    limit=Limit.operator_required(
                        "the clone states no timebase range: scope.py:248-252 derives the sample interval from it "
                        "and README.md:92 states only that it sets the interval")),
                "trigger_channel": Field("string", description="Trigger channel, or none for an immediate capture",
                                         enum=CHANNELS + ["none"]),
                "trigger_mv": Field(
                    "number", unit="mV", description="Trigger level in millivolts",
                    limit=Limit.operator_required(
                        "the clone states no trigger-level range: scope.py:254-264 converts the value to ADC "
                        "counts and README.md:92 states none")),
                "trigger_direction": Field("string", description="Trigger edge", enum=["rising", "falling"]),
            },
            output={
                "samples": Field("integer", unit="1", description="Samples captured"),
                "sample_interval_ns": Field("number", unit="ns", description="Real sample interval"),
                "sample_rate_hz": Field("number", unit="Hz", description="Real sample rate", required=False),
                "duration_ms": Field("number", unit="ms", description="Captured duration"),
                "timebase": Field("integer", unit="1", description="Timebase used"),
                "measurements": Field(
                    "array", description="One measurement object per enabled channel",
                    items=Field("object", properties={
                        "channel": Field("string", description="Channel name"),
                        "vpp_mv": Field("number", unit="mV", description="Peak-to-peak voltage"),
                        "vmin_mv": Field("number", unit="mV", description="Minimum voltage"),
                        "vmax_mv": Field("number", unit="mV", description="Maximum voltage"),
                        "mean_mv": Field("number", unit="mV", description="Mean voltage"),
                        "rms_mv": Field("number", unit="mV", description="RMS voltage"),
                        "frequency_hz": Field("number", unit="Hz", description="Estimated frequency",
                                              required=False),
                        "over_range": Field("boolean", description="True when the ADC overflowed"),
                    })),
                "sampled_at": Field("string", description="Time the capture completed"),
            })
    def capture_block(self, samples, timebase, trigger_channel, trigger_mv, trigger_direction):
        trigger = None if str(trigger_channel).lower() == "none" else str(trigger_channel)
        result = self.native.capture_block(int(samples), int(timebase), trigger, float(trigger_mv),
                                           str(trigger_direction))
        out = {
            "samples": int(result["samples"]),
            "sample_interval_ns": float(result["sample_interval_ns"]),
            "duration_ms": float(result["duration_ms"]),
            "timebase": int(result["timebase"]),
            "measurements": [],
        }
        if result.get("sample_rate_hz") is not None:
            out["sample_rate_hz"] = float(result["sample_rate_hz"])
        for channel, measurement in result["channels"].items():
            item = {
                "channel": str(channel),
                "vpp_mv": float(measurement["vpp_mv"]),
                "vmin_mv": float(measurement["vmin_mv"]),
                "vmax_mv": float(measurement["vmax_mv"]),
                "mean_mv": float(measurement["mean_mv"]),
                "rms_mv": float(measurement["rms_mv"]),
                "over_range": bool(measurement["over_range"]),
            }
            if measurement.get("frequency_hz") is not None:
                item["frequency_hz"] = float(measurement["frequency_hz"])
            out["measurements"].append(item)
        return out

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="stop_signal_generator")
    def stop(self):
        """The native stop: the runtime latches first, then turns the AWG output off (DC at 0 V)."""
        self.native.stop_signal_generator()

    def teardown(self):
        self.native.disconnect()

    # -- helpers --------------------------------------------------------------------------------------------------
    def _channel_state(self, channel):
        return self.native.channels.get(channel)

    def _channel_value(self, channel, name):
        state = self._channel_state(channel)
        return None if state is None else getattr(state, name)

    def _apply_channel(self, channel, *, enabled=None, coupling=None, range_volts=None):
        state = self._channel_state(channel)
        if enabled is None:
            enabled = state.enabled if state is not None else True          # the upstream defaults (scope.py:174)
        if coupling is None:
            coupling = state.coupling if state is not None else "DC"        # the upstream defaults (scope.py:174)
        if range_volts is None:
            range_volts = state.range_volts if state is not None else 5.0   # the upstream defaults (scope.py:175)
        return self.native.set_channel(channel, enabled=enabled, coupling=coupling,
                                       range_volts=range_volts, analog_offset=0.0)
