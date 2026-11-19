"""OpenMHS driver for gh.lpender3672/mcp-hardware-tools: the Joy-IT JDS6600 DDS signal generator.

A direct Driver over the upstream class ``hwtools.drivers.joyit.jds6600:JDS6600`` (the card's second entry
symbol).  The upstream class speaks a framed line protocol it assembles from a command letter, a function code
and a data field (``:<op><fn>=<data>.\\r\\n``, jds6600.py:4-7), so this package uses the direct shape instead of a
command table: PythonObjectDriver cannot build the upstream's typed ``SignalGeneratorConfig``/``SigGenChannel``
arguments, and SerialDriver/ScpiDriver cannot carry the runtime-assembled frame.

The driver exposes both output channels as writable state:

* reads: identification, and per channel the waveform, frequency, peak-to-peak amplitude, DC offset, duty cycle
  and output-enable state; every channel read is a fresh device query in ``read_channel`` (jds6600.py:251-271)
  or ``output_enabled`` (jds6600.py:273-276), never a cached value;
* writes: the six channel parameters, each a read-modify-write of the full channel configuration through
  ``configure_channel`` (jds6600.py:191-204) or ``enable_output`` (jds6600.py:205-213);
* action: the channel-2-relative-to-channel-1 phase through ``set_phase_deg`` (jds6600.py:215-218);
* e-stop: attempts both ``enable_output`` disables even after one fails, then reads both enable flags;
  the native class has no separate stop call and the physical signal is not measured.

The upstream's arbitrary-waveform upload/download path (``upload_arbitrary`` and ``read_arbitrary``, 60 slots of
2048 samples) is NOT COVERED: an arbitrary sample array is not the standard waveform control this package serves.
The real size is named in RESULT.json notes.
The selected arbitrary slot is readable (0 means built-in); selecting a built-in shape clears that slot.

Every Fact and Limit cites the pinned clone (e13d9cd83962cc1bb80b3f25f0daa2fce52eb0f5).  This package is
model-authored and unreviewed: the fake backend is the only one that runs here (README.md).
"""

from types import SimpleNamespace

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: Waveform names of the upstream ``_SHAPE_CODE`` table (jds6600.py:51-69), in its order.
WAVEFORMS = (
    "SINE",
    "SQUARE",
    "PULSE",
    "TRIANGLE",
    "PARTIAL_SINE",
    "CMOS",
    "DC",
    "HALF_WAVE",
    "FULL_WAVE",
    "POS_STEP",
    "NEG_STEP",
    "NOISE",
    "EXP_RISE",
    "EXP_DECAY",
    "MULTI_TONE",
    "SINC",
    "LORENZ",
)

#: The attributes of one channel configuration the driver copies between native calls.
_SETUP_FIELDS = (
    "channel",
    "waveform",
    "frequency_hz",
    "amplitude_vpp",
    "offset_v",
    "duty_pct",
    "enabled",
    "arb_slot",
)

_FREQ = Limit(min=0, max=15e6, source="upstream_code",
              ref="src/hwtools/drivers/joyit/jds6600.py:85",
              reason="siggen.py:66")
_AMPL = Limit(min=0, max=20.0, source="upstream_code",
              ref="src/hwtools/drivers/joyit/jds6600.py:86",
              reason="siggen.py:67")
_OFFSET = Limit(min=-9.99, max=9.99, source="upstream_code",
                ref="src/hwtools/drivers/joyit/jds6600.py:17")
_DUTY = Limit(min=0, max=100, source="upstream_code", ref="src/hwtools/model/siggen.py:69")
_PHASE = Limit(min=0, max=360, source="upstream_code",
               ref="src/hwtools/drivers/joyit/jds6600.py:216")


def _copy_setup(current, **changes):
    """A new plain channel configuration: the native object's fields plus ``changes``."""
    values = {name: getattr(current, name) for name in _SETUP_FIELDS}
    values.update(changes)
    return SimpleNamespace(**values)


class JDS6600(Driver):
    device_id = "jds6600"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "hwtools.drivers.joyit.jds6600:JDS6600"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeJDS6600"}
    vendor, model = "Joy-IT", "JDS6600-15"
    display_name = "Joy-IT JDS6600-15 DDS signal generator"
    tags = ["signal-generator", "waveform", "dds", "serial"]
    safe_state = ("both channel output-enable flags read back false after disabling both outputs; "
                  "the physical signal is not measured")

    facts = [
        Fact("The JDS6600 speaks a 115200 8N1 USB-CDC serial line protocol, one command per line framed "
             "':<op><fn>=<data>.' with CRLF, where 'w' writes and 'r' reads", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:4-7"),
        Fact("Frequency is encoded in centi-Hz with unit code 0 ('round(hz*100)'), so a 1 MHz setting reads "
             "100000000,0", source="upstream_code", ref="src/hwtools/drivers/joyit/jds6600.py:13-15"),
        Fact("Amplitude is millivolt peak-to-peak, offset is hundredths of a volt biased so 1000 is 0 V, duty "
             "is tenths of a percent and phase is tenths of a degree", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:16-19"),
        Fact("Function code 20 is the shared both-channels output-enable register written as 'a,b'; codes 21/22 "
             "waveform, 23/24 frequency, 25/26 amplitude, 27/28 bias, 29/30 duty are per channel, and 31 is the "
             "channel-2-versus-channel-1 phase", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:21-24"),
        Fact("The driver's capability table records 15 MHz as the JDS6600-15 frequency maximum, 20 Vpp as the "
             "amplitude maximum and 9.99 V as the symmetric offset maximum", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:83-87"),
        Fact("The upstream model validates frequency > 0, amplitude >= 0 and duty between 0 and 100 percent",
             source="upstream_code", ref="src/hwtools/model/siggen.py:66-69"),
        Fact("The JDS6600-15 provides two channels, seventeen built-in waveforms, 60 arbitrary slots of 2048 "
             "points with 12-bit codes", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:51-91"),
        Fact("The native set_phase_deg accepts 0 to 360 degrees and rejects anything outside that range",
             source="upstream_code", ref="src/hwtools/drivers/joyit/jds6600.py:215-217"),
        Fact("read_channel queries the waveform, frequency, amplitude, offset, duty and output-enable state of "
             "one channel", source="upstream_code", ref="src/hwtools/drivers/joyit/jds6600.py:251-271"),
        Fact("enable_output reads the shared output pair, flips only the requested channel's bit and writes it "
             "back", source="upstream_code", ref="src/hwtools/drivers/joyit/jds6600.py:205-213"),
        Fact("idn reads function codes 00 and 01 and formats JDS6600-<model> SN:<serial>", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:159-163"),
        Fact("The arbitrary-waveform path uses 60 slots of exactly 2048 points with 12-bit codes, and a channel "
             "plays slot N as waveform code 100 + N", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:72-79"),
        Fact("When an arbitrary slot is selected, read_channel returns its slot and uses SINE as a "
             "don't-care built-in waveform field", source="upstream_code",
             ref="src/hwtools/drivers/joyit/jds6600.py:251-271"),
    ]

    # -- reads -------------------------------------------------------------------------------------------------
    @read("identification", type="string",
          description="Instrument identification from protocol function codes 00 and 01")
    def identification(self):
        return self.native.idn()

    @read("ch1_waveform", type="string", enum=WAVEFORMS,
          description="CH1 built-in shape; SINE is a fallback when ch1_arbitrary_slot is nonzero")
    def ch1_waveform(self):
        return str(self.native.read_channel(1).waveform)

    @read("ch1_arbitrary_slot", type="integer",
          description="CH1 stored arbitrary slot; 0 means a built-in waveform is selected")
    def ch1_arbitrary_slot(self):
        return int(self.native.read_channel(1).arb_slot or 0)

    @read("ch1_frequency_hz", unit="Hz", description="CH1 freq")
    def ch1_frequency_hz(self):
        return float(self.native.read_channel(1).frequency_hz)

    @read("ch1_amplitude_vpp", unit="V", description="CH1 Vpp")
    def ch1_amplitude_vpp(self):
        return float(self.native.read_channel(1).amplitude_vpp)

    @read("ch1_offset_v", unit="V", description="CH1 offset")
    def ch1_offset_v(self):
        return float(self.native.read_channel(1).offset_v)

    @read("ch1_duty_pct", unit="%", description="CH1 duty %")
    def ch1_duty_pct(self):
        return float(self.native.read_channel(1).duty_pct)

    @read("ch1_enabled", type="boolean", description="True while channel 1 output is enabled")
    def ch1_enabled(self):
        return bool(self.native.output_enabled(1))

    @read("ch2_waveform", type="string", enum=WAVEFORMS,
          description="CH2 built-in shape; SINE is a fallback when ch2_arbitrary_slot is nonzero")
    def ch2_waveform(self):
        return str(self.native.read_channel(2).waveform)

    @read("ch2_arbitrary_slot", type="integer",
          description="CH2 stored arbitrary slot; 0 means a built-in waveform is selected")
    def ch2_arbitrary_slot(self):
        return int(self.native.read_channel(2).arb_slot or 0)

    @read("ch2_frequency_hz", unit="Hz", description="CH2 freq")
    def ch2_frequency_hz(self):
        return float(self.native.read_channel(2).frequency_hz)

    @read("ch2_amplitude_vpp", unit="V", description="CH2 Vpp")
    def ch2_amplitude_vpp(self):
        return float(self.native.read_channel(2).amplitude_vpp)

    @read("ch2_offset_v", unit="V", description="CH2 offset")
    def ch2_offset_v(self):
        return float(self.native.read_channel(2).offset_v)

    @read("ch2_duty_pct", unit="%", description="CH2 duty %")
    def ch2_duty_pct(self):
        return float(self.native.read_channel(2).duty_pct)

    @read("ch2_enabled", type="boolean", description="True while channel 2 output is enabled")
    def ch2_enabled(self):
        return bool(self.native.output_enabled(2))

    # -- writes -------------------------------------------------------------------------------------------------
    @write("ch1_frequency_hz", unit="Hz", description="CH1 Hz",
           limit=_FREQ)
    def set_ch1_frequency_hz(self, value):
        return self._update(1, frequency_hz=float(value))

    @write("ch1_amplitude_vpp", unit="V", description="CH1 Vpp",
           limit=_AMPL)
    def set_ch1_amplitude_vpp(self, value):
        return self._update(1, amplitude_vpp=float(value))

    @write("ch1_offset_v", unit="V", description="CH1 DC", limit=_OFFSET)
    def set_ch1_offset_v(self, value):
        return self._update(1, offset_v=float(value))

    @write("ch1_duty_pct", unit="%", description="CH1 duty", limit=_DUTY)
    def set_ch1_duty_pct(self, value):
        return self._update(1, duty_pct=float(value))

    @write("ch1_waveform", type="string", enum=WAVEFORMS, description="CH1 shape")
    def set_ch1_waveform(self, value):
        return self._update(1, waveform=str(value))

    @write("ch1_enabled", type="boolean", description="CH1 on")
    def set_ch1_enabled(self, value):
        return self._set_enabled(1, bool(value))

    @write("ch2_frequency_hz", unit="Hz", description="CH2 Hz",
           limit=_FREQ)
    def set_ch2_frequency_hz(self, value):
        return self._update(2, frequency_hz=float(value))

    @write("ch2_amplitude_vpp", unit="V", description="CH2 Vpp",
           limit=_AMPL)
    def set_ch2_amplitude_vpp(self, value):
        return self._update(2, amplitude_vpp=float(value))

    @write("ch2_offset_v", unit="V", description="CH2 DC", limit=_OFFSET)
    def set_ch2_offset_v(self, value):
        return self._update(2, offset_v=float(value))

    @write("ch2_duty_pct", unit="%", description="CH2 duty", limit=_DUTY)
    def set_ch2_duty_pct(self, value):
        return self._update(2, duty_pct=float(value))

    @write("ch2_waveform", type="string", enum=WAVEFORMS, description="CH2 shape")
    def set_ch2_waveform(self, value):
        return self._update(2, waveform=str(value))

    @write("ch2_enabled", type="boolean", description="CH2 on")
    def set_ch2_enabled(self, value):
        return self._set_enabled(2, bool(value))

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.lpender3672.set_phase.v1",
            description="Set the phase of channel 2 relative to channel 1",
            input={"degrees": Field("number", unit="deg",
                                    description="Phase offset in degrees, 0 to 360",
                                    limit=_PHASE)},
            output={"phase_deg": Field("number", unit="deg",
                                       description="Phase applied by the device, in whole tenths of a degree")})
    def set_phase(self, degrees):
        self.native.set_phase_deg(float(degrees))
        return {"phase_deg": round(float(degrees) * 10) / 10}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="enable_output")
    def stop_outputs(self):
        """Attempt both disables even after an exchange fails, then check both enable flags."""
        errors = []
        for channel in (1, 2):
            try:
                self.native.enable_output(channel, False)
            except Exception as exc:
                errors.append(f"CH{channel} disable failed: {exc}")
        for channel in (1, 2):
            try:
                if self.native.output_enabled(channel) is not False:
                    errors.append(f"CH{channel} output was not confirmed disabled")
            except Exception as exc:
                errors.append(f"CH{channel} readback failed: {exc}")
        if errors:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED", "; ".join(errors))

    def teardown(self):
        self.native.disconnect()

    # -- helpers ------------------------------------------------------------------------------------------------
    def _update(self, channel, **changes):
        """Read the full channel setup, change one field, apply and return the device's value."""
        if "frequency_hz" in changes and round(changes["frequency_hz"] * 100) <= 0:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "frequency_hz must round to a positive centi-Hz value")
        if "waveform" in changes:
            changes["arb_slot"] = None
        current = self.native.read_channel(channel)
        self.native.configure_channel(_copy_setup(current, **changes))
        applied = self.native.read_channel(channel)
        name = next(iter(changes))
        value = getattr(applied, name)
        return str(value) if name == "waveform" else value

    def _set_enabled(self, channel, on):
        self.native.enable_output(channel, on)
        return bool(self.native.output_enabled(channel))
