"""OpenMHS driver for gh.ilovebacteria/test-instrument-automation-open-version: the GW Instek AFG-2225.

A direct Driver (decorated methods) over the upstream PyMeasure class ``devices.afg2225:AFG2225``
(src/test_engine/devices/afg2225.py:90).  That class exposes two channel objects, ``ch1`` and ``ch2``
(afg2225.py:96-97), whose controls the driver translates one-for-one:

* reads: both channels' waveform, frequency, peak-to-peak amplitude, DC offset, phase, output-enable state,
  load, square-wave duty cycle and ramp symmetry, plus the instrument's error queue;
* writes (``cap.device.configure.v1``): each channel's waveform, frequency, amplitude, phase, output enable, load,
  duty cycle and ramp symmetry.  The upstream validators state the frequency, amplitude, phase, duty-cycle and
  ramp-symmetry ranges (afg2225.py:36, 43, 55, 79, 86);
* action: ``set_offset`` for the DC offset of one channel.  The clone states no offset range
  (afg2225.py:46-49), so its bound is ``Limit.operator_required`` and the write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the envelope of its unit;
* action: ``sync_phase``, the native SOURce1:PHASe:SYNChronize (afg2225.py:156-162);
* e-stop: both outputs off through the upstream ``output_enabled`` control (afg2225.py:58-65).  The upstream class
  has no separate stop method; its ``reset()`` writes ``*RST`` and is not bound as the safety reset because it
  changes the instrument, not only the communication.

Every Fact and Limit cites the pinned clone at commit 59499fa8b568d977aa5e2d5f1144725ee7f3cb0f.  The package is
model-authored and unreviewed: only the fake backend is exercised here, and no hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The waveform names AFG2225Channel maps to SCPI words (src/test_engine/devices/afg2225.py:18-21).
SHAPES = ("sine", "square", "ramp", "pulse", "noise", "user")
#: The load names AFG2225Channel maps to SCPI words (src/test_engine/devices/afg2225.py:22).
LOADS = ("50ohm", "highZ")

_FREQUENCY = Limit(min=1e-6, max=25e6, unit="Hz", source="upstream_code",
                   ref="src/test_engine/devices/afg2225.py:36")
_AMPLITUDE = Limit(min=0.001, max=10.0, unit="V", source="upstream_code",
                   ref="src/test_engine/devices/afg2225.py:43")
_PHASE = Limit(min=-360.0, max=360.0, unit="deg", source="upstream_code",
               ref="src/test_engine/devices/afg2225.py:55")
_DUTY_CYCLE = Limit(min=1.0, max=99.0, unit="%", source="upstream_code",
                    ref="src/test_engine/devices/afg2225.py:79")
_RAMP_SYMMETRY = Limit(min=0.0, max=100.0, unit="%", source="upstream_code",
                       ref="src/test_engine/devices/afg2225.py:86")
_SHAPE = Limit(allowed=SHAPES, source="upstream_code",
               ref="src/test_engine/devices/afg2225.py:18-21")
_LOAD = Limit(allowed=LOADS, source="upstream_code",
              ref="src/test_engine/devices/afg2225.py:22")
_CHANNEL = Limit(allowed=[1, 2], source="upstream_code",
                 ref="src/test_engine/devices/afg2225.py:96-97")
_OFFSET_REASON = ("no text of the clone states a DC offset range: the upstream offset control names only its unit "
                  "(V) and validates no envelope (afg2225.py:46-49); the site sets the offset envelope of its unit")


class AFG2225(Driver):
    """The GW Instek AFG-2225 two-channel arbitrary function generator."""

    device_id = "afg2225"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "devices.afg2225:AFG2225"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAFG2225"}
    vendor, model = "GW Instek", "AFG-2225"
    display_name = "GW Instek AFG-2225 arbitrary function generator"
    tags = ["signal-generator", "waveform", "function-generator", "scpi", "pymeasure"]
    safe_state = "both channel outputs read back as off after OUTPut1 OFF and OUTPut2 OFF"

    facts = [
        Fact("AFG2225 is a two-channel function generator whose channel attributes ch1 and ch2 are "
             "AFG2225Channel creators", source="upstream_code",
             ref="src/test_engine/devices/afg2225.py:90-97"),
        Fact("The channel shape control writes SOURce{ch}:FUNCtion using the SHAPES map: sine, square, ramp, "
             "pulse, noise and user", source="upstream_code",
             ref="src/test_engine/devices/afg2225.py:18-30"),
        Fact("The channel frequency control is in Hz and its strict_range accepts 1e-6 to 25e6",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:32-37"),
        Fact("The channel amplitude control is peak-to-peak volts and its strict_range accepts 0.001 to 10.0",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:39-44"),
        Fact("The channel DC offset control is in volts and the clone states no offset range",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:46-49"),
        Fact("The channel phase control is in degrees and its strict_range accepts -360 to 360",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:51-56"),
        Fact("The channel output_enabled control reads OUTPut{ch}? and writes OUTPut{ch} ON or OFF",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:58-65"),
        Fact("The LOADS map defines the load keys 50ohm and highZ", source="upstream_code",
             ref="src/test_engine/devices/afg2225.py:22"),
        Fact("The channel load control reads OUTPut{ch}:LOAD? and writes OUTPut{ch}:LOAD",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:67-73"),
        Fact("The channel duty-cycle control is percent and its strict_range accepts 1.0 to 99.0",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:75-80"),
        Fact("The channel ramp-symmetry control is percent and its strict_range accepts 0 to 100",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:82-87"),
        Fact("sync_phase writes SOURce1:PHASe:SYNChronize", source="upstream_code",
             ref="src/test_engine/devices/afg2225.py:156-162"),
        Fact("The error measurement reads SYSTem:ERRor?", source="upstream_code",
             ref="src/test_engine/devices/afg2225.py:172-175"),
        Fact("The upstream write method sleeps 0.5 s before every command",
             source="upstream_code", ref="src/test_engine/devices/afg2225.py:126-128"),
        Fact("setup() resets the instrument, sleeps 2 s, clears it and enables the OPC and status-byte summary; "
             "reset() writes *RST", source="upstream_code",
             ref="src/test_engine/devices/afg2225.py:113-124"),
    ]

    # -- reads: channel 1 ---------------------------------------------------------------------------------------
    @read("ch1_shape", type="string", enum=SHAPES, description="Shape")
    def ch1_shape(self):
        return str(self.native.ch1.shape)

    @read("ch1_freq", unit="Hz", description="Freq")
    def ch1_freq(self):
        return float(self.native.ch1.frequency)

    @read("ch1_vpp", unit="V", description="Vpp")
    def ch1_vpp(self):
        return float(self.native.ch1.amplitude)

    @read("ch1_offset_v", unit="V", description="CH1 DC offset")
    def ch1_offset_v(self):
        return float(self.native.ch1.offset)

    @read("ch1_phase", unit="deg", description="Phase")
    def ch1_phase(self):
        return float(self.native.ch1.phase)

    @read("ch1_output", type="boolean", description="Output")
    def ch1_output(self):
        return bool(self.native.ch1.output_enabled)

    @read("ch1_load", type="string", enum=LOADS, description="Load")
    def ch1_load(self):
        return str(self.native.ch1.load)

    @read("ch1_duty", unit="%", description="Duty")
    def ch1_duty(self):
        return float(self.native.ch1.duty_cycle)

    @read("ch1_sym", unit="%", description="Sym")
    def ch1_sym(self):
        return float(self.native.ch1.ramp_symmetry)

    # -- reads: channel 2 ---------------------------------------------------------------------------------------
    @read("ch2_shape", type="string", enum=SHAPES, description="Shape")
    def ch2_shape(self):
        return str(self.native.ch2.shape)

    @read("ch2_freq", unit="Hz", description="Freq")
    def ch2_freq(self):
        return float(self.native.ch2.frequency)

    @read("ch2_vpp", unit="V", description="Vpp")
    def ch2_vpp(self):
        return float(self.native.ch2.amplitude)

    @read("ch2_offset_v", unit="V", description="CH2 DC offset")
    def ch2_offset_v(self):
        return float(self.native.ch2.offset)

    @read("ch2_phase", unit="deg", description="Phase")
    def ch2_phase(self):
        return float(self.native.ch2.phase)

    @read("ch2_output", type="boolean", description="Output")
    def ch2_output(self):
        return bool(self.native.ch2.output_enabled)

    @read("ch2_load", type="string", enum=LOADS, description="Load")
    def ch2_load(self):
        return str(self.native.ch2.load)

    @read("ch2_duty", unit="%", description="Duty")
    def ch2_duty(self):
        return float(self.native.ch2.duty_cycle)

    @read("ch2_sym", unit="%", description="Sym")
    def ch2_sym(self):
        return float(self.native.ch2.ramp_symmetry)

    @read("last_error", type="string", description="Error queue")
    def last_error(self):
        return str(self.native.error)

    # -- writes: channel 1 --------------------------------------------------------------------------------------
    @write("ch1_shape", type="string", description="Shape", limit=_SHAPE)
    def set_ch1_shape(self, value):
        self.native.ch1.shape = str(value)
        return str(self.native.ch1.shape)

    @write("ch1_freq", unit="Hz", description="Freq", limit=_FREQUENCY)
    def set_ch1_freq(self, value):
        self.native.ch1.frequency = float(value)
        return float(self.native.ch1.frequency)

    @write("ch1_vpp", unit="V", description="Vpp", limit=_AMPLITUDE)
    def set_ch1_vpp(self, value):
        self.native.ch1.amplitude = float(value)
        return float(self.native.ch1.amplitude)

    @write("ch1_phase", unit="deg", description="Phase", limit=_PHASE)
    def set_ch1_phase(self, value):
        self.native.ch1.phase = float(value)
        return float(self.native.ch1.phase)

    @write("ch1_output", type="boolean", description="Output")
    def set_ch1_output(self, value):
        self.native.ch1.output_enabled = bool(value)
        return bool(self.native.ch1.output_enabled)

    @write("ch1_load", type="string", description="Load", limit=_LOAD)
    def set_ch1_load(self, value):
        self.native.ch1.load = str(value)
        return str(self.native.ch1.load)

    @write("ch1_duty", unit="%", description="Duty", limit=_DUTY_CYCLE)
    def set_ch1_duty(self, value):
        self.native.ch1.duty_cycle = float(value)
        return float(self.native.ch1.duty_cycle)

    @write("ch1_sym", unit="%", description="Sym", limit=_RAMP_SYMMETRY)
    def set_ch1_sym(self, value):
        self.native.ch1.ramp_symmetry = float(value)
        return float(self.native.ch1.ramp_symmetry)

    # -- writes: channel 2 --------------------------------------------------------------------------------------
    @write("ch2_shape", type="string", description="Shape", limit=_SHAPE)
    def set_ch2_shape(self, value):
        self.native.ch2.shape = str(value)
        return str(self.native.ch2.shape)

    @write("ch2_freq", unit="Hz", description="Freq", limit=_FREQUENCY)
    def set_ch2_freq(self, value):
        self.native.ch2.frequency = float(value)
        return float(self.native.ch2.frequency)

    @write("ch2_vpp", unit="V", description="Vpp", limit=_AMPLITUDE)
    def set_ch2_vpp(self, value):
        self.native.ch2.amplitude = float(value)
        return float(self.native.ch2.amplitude)

    @write("ch2_phase", unit="deg", description="Phase", limit=_PHASE)
    def set_ch2_phase(self, value):
        self.native.ch2.phase = float(value)
        return float(self.native.ch2.phase)

    @write("ch2_output", type="boolean", description="Output")
    def set_ch2_output(self, value):
        self.native.ch2.output_enabled = bool(value)
        return bool(self.native.ch2.output_enabled)

    @write("ch2_load", type="string", description="Load", limit=_LOAD)
    def set_ch2_load(self, value):
        self.native.ch2.load = str(value)
        return str(self.native.ch2.load)

    @write("ch2_duty", unit="%", description="Duty", limit=_DUTY_CYCLE)
    def set_ch2_duty(self, value):
        self.native.ch2.duty_cycle = float(value)
        return float(self.native.ch2.duty_cycle)

    @write("ch2_sym", unit="%", description="Sym", limit=_RAMP_SYMMETRY)
    def set_ch2_sym(self, value):
        self.native.ch2.ramp_symmetry = float(value)
        return float(self.native.ch2.ramp_symmetry)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.ilovebacteria.set_offset.v1",
            description="Set the DC offset of one channel",
            input={
                "channel": Field("integer", unit="1", description="Channel number (1 or 2)", limit=_CHANNEL),
                "offset_v": Field("number", unit="V", description="DC offset",
                                  limit=Limit.operator_required(_OFFSET_REASON)),
            },
            output={"offset_v": Field("number", unit="V", description="Applied DC offset")})
    def set_offset(self, channel, offset_v):
        if int(channel) == 1:
            self.native.ch1.offset = float(offset_v)
            return {"offset_v": float(self.native.ch1.offset)}
        if int(channel) == 2:
            self.native.ch2.offset = float(offset_v)
            return {"offset_v": float(self.native.ch2.offset)}
        raise ValueError(f"channel must be 1 or 2, got {channel!r}")

    @action(name="x-cap.ilovebacteria.sync_phase.v1",
            description="Synchronize the phase of both channels",
            output={"synchronized": Field("boolean", description="True once the native command returned")})
    def sync_phase(self):
        self.native.sync_phase()
        return {"synchronized": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="output_enabled", latency_ms=5000)
    def stop_outputs(self):
        """Attempt both OFF writes, then require both upstream output queries to report False.

        The 5 s budget is a package policy, not a device guarantee. Upstream paces
        every write (including queries) by 0.5 s; a slow VISA link may still time out.
        """
        channels = (("ch1", self.native.ch1), ("ch2", self.native.ch2))
        failures = []
        for name, channel in channels:
            try:
                channel.output_enabled = False
            except Exception as exc:
                failures.append(f"{name} OFF write failed: {exc}")
        for name, channel in channels:
            try:
                if channel.output_enabled is not False:
                    failures.append(f"{name} did not confirm output off")
            except Exception as exc:
                failures.append(f"{name} output readback failed: {exc}")
        if failures:
            raise DriverFailed("MHS.DEVICE.FAULTED", "; ".join(failures))
