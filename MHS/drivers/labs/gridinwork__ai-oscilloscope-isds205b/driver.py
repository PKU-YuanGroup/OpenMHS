"""OpenMHS driver for gh.gridinwork/ai-oscilloscope-isds205b: the INSTRUSTAR ISDS205B USB oscilloscope.

A direct Driver over the upstream class ``instrustar.device:Scope``.  The upstream class wraps the vendor's Windows
``vdso.dll`` through ctypes and is not a text-protocol object: its methods take Python arguments and return Python
objects, and the vendor calls behind them are ctypes functions assembled at run time.  The card's helper hint
(PythonObjectDriver) is a static-scan guess; the device interface needs an @estop, an action with an inline output
schema and a read/write pair over the same state field, which the fixed family tables cannot express, so this package
is a direct Driver with a ``native.py`` factory (DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: availability, sample rate, the voltage resolution of both channels, the coupling read-back of both channels,
  the DDS output state, the memory depth and the support flags the upstream exposes;
* writes: the sample rate (the five rates the clone lists for this unit), the DDS waveform style and the trigger
  mode, style, source, level and pre-trigger percentage.  The upstream wrapper has no trigger read-back, so those
  fields report the last value written; the trigger level is ``Limit.operator_required`` because no text file states
  its bound;
* actions: one capture of both channels with scalar Vmin/Vmax/Vpp/Vavg/Vrms measurements, one input-range request
  that reads back the applied voltage resolution, and the DDS output enable.  The requested range is
  ``Limit.operator_required``: the clone says SetOscChannelRange silently clamps, the usable range depends on the probe
  and the grounding is not confirmed isolated, so the site supplies the range of its probe;
* the e-stop disables the DDS output (``generator_enable(False)``), the only driven output of the oscilloscope.

NOT COVERED: the captured sample arrays.  No catalogue class carries a waveform array, so this package serves the
per-channel scalar measurements and the settings of the oscilloscope, not the samples.  The coupling write (a
documented no-op on this unit), the DDS frequency and duty-cycle writes (the clone states no unit or bound and has no
getter), the roll mode, the pulse-width and hysteresis trigger fields and the GUI are not exposed.

Every Fact and Limit cites a line of the clone at the pinned commit (cb1bdda97869e5c897d742d6008a8a359128a61a).
The package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware; at R1
the loader does not require a reviewed_by signature, so the hardware backend stays an operator decision.
"""

from math import sqrt

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The five sample rates the clone lists for this unit (docs/ISDS205B_PROTOCOL.md:59).
SAMPLE_RATES = [1000000, 4000000, 8000000, 16000000, 48000000]
#: The DDS waveform style codes of the upstream BoxingStyle enum (instrustar/device.py:59-65).
WAVEFORMS = [0, 1, 2, 3, 4]
#: TriggerMode values (instrustar/device.py:41-43).
TRIGGER_MODES = [0, 1]
#: TriggerStyle bitmask values (instrustar/device.py:46-56).
TRIGGER_STYLES = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256]
#: Trigger source 0 is CH1 and 1 is CH2 (docs/ISDS205B_PROTOCOL.md:70).
TRIGGER_SOURCES = [0, 1]
#: Channel 0 is CH1 and 1 is CH2 (docs/ISDS205B_PROTOCOL.md:55).
CHANNELS = [0, 1]


def _stats(samples):
    """Vmin, Vmax, Vpp, Vavg and Vrms of one channel's returned samples."""
    values = [float(item) for item in samples]
    if not values:
        raise DriverFailed("MHS.DEVICE.FAULTED", "the capture returned an empty channel")
    v_min = min(values)
    v_max = max(values)
    v_avg = sum(values) / len(values)
    v_rms = sqrt(sum(item * item for item in values) / len(values))
    return {"v_min": v_min, "v_max": v_max, "v_pp": v_max - v_min, "v_avg": v_avg, "v_rms": v_rms}


class Isds205b(Driver):
    device_id = "isds205b"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "instrustar.device:Scope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScope"}
    vendor = "INSTRUSTAR"
    model = "ISDS205B"
    display_name = "INSTRUSTAR ISDS205B USB oscilloscope (instrustar.Scope)"
    tags = ["oscilloscope", "usb", "isds205b", "instrustar", "waveform", "dds", "voltage measurement"]
    facts = [
        Fact("Scope is the high-level handle to one ISDS205B; the class docstring says it is not thread-safe",
             source="upstream_code", ref="instrustar/device.py:154-155"),
        Fact("CaptureResult carries ch1 and ch2 sample arrays, the sample rate, requested and actual lengths in KB, "
             "elapsed time, out-of-range flags and a timestamp", source="upstream_code",
             ref="instrustar/device.py:75-84"),
        Fact("capture() raises ScopeError when Capture() returns zero or less or when IsDataReady times out, and "
             "the returned CaptureResult reports the actual capture length in KB", source="upstream_code",
             ref="instrustar/device.py:293-329"),
        Fact("set_channel_range takes channel 0 for CH1 and 1 for CH2 and a min/max range in mV",
             source="vendor_doc", ref="docs/ISDS205B_PROTOCOL.md:55"),
        Fact("The module docstring says SetOscChannelRange silently clamps to the widest internal gain step and "
             "get_voltage_resolution should be read after a range request", source="upstream_code",
             ref="instrustar/device.py:15-17"),
        Fact("The live support list of this unit has five discrete sample rates: 1000000, 4000000, 8000000, "
             "16000000 and 48000000 Hz", source="vendor_doc", ref="docs/ISDS205B_PROTOCOL.md:59"),
        Fact("set_sample_rate returns the applied rate and raises ScopeError when the device returns 0",
             source="upstream_code", ref="instrustar/device.py:248-253"),
        Fact("get_sample_rate reads the rate the device reports", source="upstream_code",
             ref="instrustar/device.py:255-257"),
        Fact("This unit has no hardware trigger: IsSupportHardTrigger returned 0 in the live test",
             source="vendor_doc", ref="docs/ISDS205B_PROTOCOL.md:67"),
        Fact("The trigger modes are AUTO=0 and CONTINUOUS=1", source="upstream_code",
             ref="instrustar/device.py:41-43"),
        Fact("Trigger styles are the bitmask values NONE=0x0000, RISE_EDGE=0x0001, FALL_EDGE=0x0002, EDGE=0x0004, "
             "POS_PULSE_MORE=0x0008, POS_PULSE_LESS=0x0010, POS_PULSE=0x0020, NEG_PULSE_MORE=0x0040, "
             "NEG_PULSE_LESS=0x0080 and NEG_PULSE=0x0100", source="upstream_code",
             ref="instrustar/device.py:46-56"),
        Fact("Trigger source 0 selects CH1 and 1 selects CH2; the trigger level is in mV", source="vendor_doc",
             ref="docs/ISDS205B_PROTOCOL.md:70-71"),
        Fact("The pre-trigger percent range is 5 to 95 percent", source="vendor_doc",
             ref="docs/ISDS205B_PROTOCOL.md:74"),
        Fact("AC coupling is a documented no-op on this unit; GetAcDc always reads back DC", source="upstream_code",
             ref="instrustar/device.py:13-14"),
        Fact("The DDS waveform styles are SINE=0x00, SQUARE=0x01, TRIANGULAR=0x02, UP_SAWTOOTH=0x03 and "
             "DOWN_SAWTOOTH=0x04", source="upstream_code", ref="instrustar/device.py:59-65"),
        Fact("DDS style-select and output-enable were confirmed on this unit; frequency and duty-cycle accuracy is "
             "unverified and the DLL has no Get counterpart", source="upstream_code",
             ref="instrustar/device.py:331-334"),
        Fact("generator_enable writes DDSOutputEnable and is_generator_enabled reads IsDDSOutputEnable",
             source="upstream_code", ref="instrustar/device.py:357-363"),
        Fact("set_generator applies the waveform style, frequency and duty cycle to the DDS",
             source="upstream_code", ref="instrustar/device.py:343-355"),
        Fact("has_hard_trigger, has_dds, has_io, has_roll_mode and has_pretrigger_percent return the device support "
             "flags", source="upstream_code", ref="instrustar/device.py:204-217"),
        Fact("memory_length_kb returns the capture memory depth in KB", source="vendor_doc",
             ref="docs/ISDS205B_PROTOCOL.md:60"),
        Fact("The clone says grounding between CH1, CH2 and USB is not confirmed isolated and the GUI defaults to a "
             "conservative +/-5 V range", source="vendor_doc", ref="README.md:192-196"),
        Fact("DDS amplitude and offset software trim is not supported on this unit", source="upstream_code",
             ref="instrustar/device.py:22-23"),
    ]
    safe_state = "DDS generator output disabled by Scope.generator_enable(False); the oscilloscope drives no other output"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("available", type="boolean", description="True while the device reports that it is available")
    def available(self):
        return bool(self.native.is_available)

    @read("sample_rate_hz", type="integer", unit="Hz", description="Sample rate the device reports")
    def sample_rate_hz(self):
        return int(self.native.get_sample_rate())

    @read("ch1_voltage_resolution_v", unit="V",
          description="Voltage resolution the device reports for CH1 after the last range request")
    def ch1_voltage_resolution_v(self):
        return float(self.native.get_voltage_resolution(0))

    @read("ch2_voltage_resolution_v", unit="V",
          description="Voltage resolution the device reports for CH2 after the last range request")
    def ch2_voltage_resolution_v(self):
        return float(self.native.get_voltage_resolution(1))

    @read("ch1_coupling_ac", type="boolean",
          description="True when CH1 reports AC coupling; the clone says this unit always reads DC")
    def ch1_coupling_ac(self):
        return bool(self.native.get_coupling(0))

    @read("ch2_coupling_ac", type="boolean",
          description="True when CH2 reports AC coupling; the clone says this unit always reads DC")
    def ch2_coupling_ac(self):
        return bool(self.native.get_coupling(1))

    @read("generator_enabled", type="boolean", description="True while the DDS generator output is enabled")
    def generator_enabled(self):
        return bool(self.native.is_generator_enabled())

    @read("has_hard_trigger", type="boolean", description="True when the device reports a hardware trigger")
    def has_hard_trigger(self):
        return bool(self.native.has_hard_trigger())

    @read("has_dds", type="boolean", description="True when the device reports a DDS generator")
    def has_dds(self):
        return bool(self.native.has_dds())

    @read("has_io", type="boolean", description="True when the device reports digital IO")
    def has_io(self):
        return bool(self.native.has_io())

    @read("has_pretrigger_percent", type="boolean",
          description="True when the device supports a pre-trigger percentage setting")
    def has_pretrigger_percent(self):
        return bool(self.native.has_pretrigger_percent())

    @read("has_roll_mode", type="boolean", description="True when the device reports roll mode support")
    def has_roll_mode(self):
        return bool(self.native.has_roll_mode())

    @read("memory_length_kb", type="integer", unit="1", description="Capture memory depth the device reports in KB")
    def memory_length_kb(self):
        return int(self.native.memory_length_kb())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("sample_rate_hz", type="integer", unit="Hz", description="Sample rate to select for the capture",
           limit=Limit(allowed=SAMPLE_RATES, source="vendor_doc", ref="docs/ISDS205B_PROTOCOL.md:59"))
    def set_sample_rate_hz(self, value):
        return int(self.native.set_sample_rate(int(value)))

    @write("generator_waveform", type="integer", unit="1",
           description="DDS waveform style: 0 sine, 1 square, 2 triangular, 3 up sawtooth, 4 down sawtooth",
           limit=Limit(allowed=WAVEFORMS, source="upstream_code", ref="instrustar/device.py:59-65"))
    def set_generator_waveform(self, value):
        self.native.set_generator(waveform=int(value))
        return int(value)

    @write("trigger_mode", type="integer", unit="1",
           description="Trigger mode: 0 AUTO, 1 CONTINUOUS (the upstream wrapper has no read-back)",
           limit=Limit(allowed=TRIGGER_MODES, source="upstream_code", ref="instrustar/device.py:41-43"))
    def set_trigger_mode(self, value):
        self.native.set_trigger(mode=int(value))
        return int(value)

    @write("trigger_style", type="integer", unit="1",
           description="Trigger style bitmask (0 none, 1 rise, 2 fall, 4 edge, 8/16/32 positive pulse, "
                       "64/128/256 negative pulse)",
           limit=Limit(allowed=TRIGGER_STYLES, source="upstream_code", ref="instrustar/device.py:46-56"))
    def set_trigger_style(self, value):
        self.native.set_trigger(style=int(value))
        return int(value)

    @write("trigger_source", type="integer", unit="1",
           description="Trigger source: 0 CH1, 1 CH2 (the upstream wrapper has no read-back)",
           limit=Limit(allowed=TRIGGER_SOURCES, source="vendor_doc", ref="docs/ISDS205B_PROTOCOL.md:70"))
    def set_trigger_source(self, value):
        self.native.set_trigger(source=int(value))
        return int(value)

    @write("trigger_level_mv", type="integer", unit="mV", description="Trigger level in mV",
           limit=Limit.operator_required(
               "no line of the clone states a trigger level bound; docs/ISDS205B_PROTOCOL.md:71 states only the "
               "millivolt unit, so the site sets the level window of its probe"))
    def set_trigger_level_mv(self, value):
        self.native.set_trigger(level_mv=int(value))
        return int(value)

    @write("trigger_pretrigger_percent", type="integer", unit="%",
           description="Pre-trigger share of the capture buffer in percent",
           limit=Limit(min=5, max=95, source="vendor_doc", ref="docs/ISDS205B_PROTOCOL.md:74"))
    def set_trigger_pretrigger_percent(self, value):
        self.native.set_trigger(pretrigger_percent=int(value))
        return int(value)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.gridinwork.capture.v1",
            description="Capture one waveform on both channels and return per-channel scalar measurements",
            output={
                "sample_rate_hz": Field("integer", unit="Hz", description="Sample rate of the capture"),
                "samples": Field("integer", unit="1", description="Samples returned in channel 1"),
                "ch1_v_min": Field("number", unit="V", description="CH1 minimum voltage"),
                "ch1_v_max": Field("number", unit="V", description="CH1 maximum voltage"),
                "ch1_v_pp": Field("number", unit="V", description="CH1 peak-to-peak voltage"),
                "ch1_v_avg": Field("number", unit="V", description="CH1 average voltage"),
                "ch1_v_rms": Field("number", unit="V", description="CH1 RMS voltage"),
                "ch1_out_of_range": Field("boolean", description="True when CH1 reports clipped samples"),
                "ch2_v_min": Field("number", unit="V", description="CH2 minimum voltage"),
                "ch2_v_max": Field("number", unit="V", description="CH2 maximum voltage"),
                "ch2_v_pp": Field("number", unit="V", description="CH2 peak-to-peak voltage"),
                "ch2_v_avg": Field("number", unit="V", description="CH2 average voltage"),
                "ch2_v_rms": Field("number", unit="V", description="CH2 RMS voltage"),
                "ch2_out_of_range": Field("boolean", description="True when CH2 reports clipped samples"),
            })
    def capture(self):
        result = self.native.capture()
        ch1 = _stats(result.ch1)
        ch2 = _stats(result.ch2)
        out_of_range = tuple(result.out_of_range)
        return {
            "sample_rate_hz": int(result.sample_rate_hz),
            "samples": len(result.ch1),
            "ch1_v_min": ch1["v_min"], "ch1_v_max": ch1["v_max"], "ch1_v_pp": ch1["v_pp"],
            "ch1_v_avg": ch1["v_avg"], "ch1_v_rms": ch1["v_rms"],
            "ch1_out_of_range": bool(out_of_range[0]),
            "ch2_v_min": ch2["v_min"], "ch2_v_max": ch2["v_max"], "ch2_v_pp": ch2["v_pp"],
            "ch2_v_avg": ch2["v_avg"], "ch2_v_rms": ch2["v_rms"],
            "ch2_out_of_range": bool(out_of_range[1]),
        }

    @action(name="x-cap.gridinwork.set_input_range.v1",
            description="Request one channel's input range in mV and read back the voltage resolution the device "
                        "reports",
            input={
                "channel": Field("integer", unit="1", description="Channel: 0 for CH1, 1 for CH2",
                                 limit=Limit(allowed=CHANNELS, source="vendor_doc",
                                             ref="docs/ISDS205B_PROTOCOL.md:55")),
                "min_mv": Field("integer", unit="mV", description="Lower end of the requested input range in mV",
                                limit=Limit.operator_required(
                                    "no line of the clone states a numeric input range for SetOscChannelRange; the "
                                    "module docstring says the device silently clamps and the usable range depends "
                                    "on the probe, whose grounding is not confirmed isolated, so the site sets the "
                                    "range of its probe")),
                "max_mv": Field("integer", unit="mV", description="Upper end of the requested input range in mV",
                                limit=Limit.operator_required(
                                    "no line of the clone states a numeric input range for SetOscChannelRange; the "
                                    "module docstring says the device silently clamps and the usable range depends "
                                    "on the probe, whose grounding is not confirmed isolated, so the site sets the "
                                    "range of its probe")),
            },
            output={
                "channel": Field("integer", unit="1", description="Channel that was configured"),
                "min_mv": Field("integer", unit="mV", description="Lower end that was requested"),
                "max_mv": Field("integer", unit="mV", description="Upper end that was requested"),
                "voltage_resolution_v": Field("number", unit="V",
                                              description="Resolution the device reports after the range request"),
            })
    def set_input_range(self, channel, min_mv, max_mv):
        self.native.set_channel_range(int(channel), int(min_mv), int(max_mv))
        return {"channel": int(channel), "min_mv": int(min_mv), "max_mv": int(max_mv),
                "voltage_resolution_v": float(self.native.get_voltage_resolution(int(channel)))}

    @action(name="x-cap.gridinwork.generator_enable.v1",
            description="Enable or disable the DDS generator output",
            input={"enable": Field("boolean", description="True to enable the DDS output, False to disable it")},
            output={"generator_enabled": Field("boolean",
                                               description="True when the device reports the DDS output enabled")})
    def generator_enable(self, enable):
        self.native.generator_enable(bool(enable))
        return {"generator_enabled": bool(self.native.is_generator_enabled())}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="generator_enable")
    def stop(self):
        """The native stop path: the runtime latches first, then the DDS output is disabled."""
        self.native.generator_enable(False)

    def teardown(self):
        self.native.disconnect()
