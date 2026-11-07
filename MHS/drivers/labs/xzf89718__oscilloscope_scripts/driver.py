"""OpenMHS driver for gh.xzf89718/oscilloscope_scripts: a Tektronix TBS2000B over pyvisa.

A direct ``Driver`` over the upstream class
``Tektronix_TBS2000B_control.oscilloscope_control:Oscilloscope``.  The card guessed a ``ScpiDriver`` because the
upstream sends SCPI text, but each ``Measure*`` method writes a source command, writes a measurement-type command and
then queries ``:MEASUrement:IMMed:VALue?`` (oscilloscope_control.py:106-134).  A ``ScpiDriver`` read is one query and
cannot express that two-write-then-query sequence without merging the lines, so the driver calls the upstream methods
themselves; the hardware backend opens the same class.

* reads: the selected channel and the instrument's own immediate frequency, amplitude and high-level measurements;
* one write: the measurement channel (CH1 to CH4, the only values ``SetChannel`` accepts);
* the e-stop closes the pyvisa session with the upstream ``Close`` (oscilloscope_control.py:178-180).  This is a
  measurement-only instrument: the driver actuates nothing, and the safe state is a closed session.

The waveform array ``Sampling`` returns is **NOT COVERED**: the standard has no waveform-array contract yet, and the
clone's comment names 1 to 2500 samples as a full waveform (oscilloscope_control.py:56-58).  ``MeasureLow`` is also
not exposed because the clone's implementation formats a stray ``}`` and iterates the characters of its channel
argument (oscilloscope_control.py:136-144).

Every Fact cites a line of the clone at the pinned commit 105e6021650f5b4f6557e733451612e4696a860d.  This package is
model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

UPSTREAM = "Tektronix_TBS2000B_control/oscilloscope_control.py"

#: The channels SetChannel accepts, in the order of its branches (oscilloscope_control.py:156-167).
CHANNELS = ["CH1", "CH2", "CH3", "CH4"]


class Oscilloscope(Driver):
    device_id = "tbs2000b"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "Tektronix_TBS2000B_control.oscilloscope_control:Oscilloscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOscilloscope"}
    vendor, model = "Tektronix", "TBS2000B"
    display_name = "Tektronix TBS2000B oscilloscope"
    tags = ["oscilloscope", "tektronix", "tbs2000b", "scpi", "measurement"]
    facts = [
        Fact("The supported instrument is the Tektronix TBS2000B", source="vendor_doc", ref="README.md:3"),
        Fact("The upstream connects over pyvisa to a VISA resource and writes '*cls' and 'header OFF' on connect",
             source="upstream_code", ref=f"{UPSTREAM}:22-37"),
        Fact("SetChannel accepts CH1, CH2, CH3 and CH4 and raises for any other value",
             source="upstream_code", ref=f"{UPSTREAM}:146-172"),
        Fact("The measure methods take comma-separated channels and default to CH1",
             source="upstream_code", ref=f"{UPSTREAM}:106-136"),
        Fact("MeasureFreq sends the immediate source and the FREQuency type and then queries "
             ":MEASUrement:IMMed:VALue?", source="upstream_code", ref=f"{UPSTREAM}:106-114"),
        Fact("MeasureAmpl sends the immediate source and the AMPlitude type and then queries "
             ":MEASUrement:IMMed:VALue?", source="upstream_code", ref=f"{UPSTREAM}:116-124"),
        Fact("MeasureHigh sends the immediate source and the HIGH type and then queries "
             ":MEASUrement:IMMed:VALue?", source="upstream_code", ref=f"{UPSTREAM}:126-134"),
        Fact("MeasureLow formats a stray '}' and iterates the characters of its channel argument, unlike the other "
             "measure methods", source="upstream_code", ref=f"{UPSTREAM}:136-144"),
        Fact("For the TBS2000B, 1 to 2500 is a full waveform in the clone's waveform comment",
             source="upstream_code", ref=f"{UPSTREAM}:56-58"),
        Fact("The vertical waveform scale is in volts: ymult is 'volts / level' and yzero is a reference voltage",
             source="upstream_code", ref=f"{UPSTREAM}:78-81"),
        Fact("Close closes the pyvisa resource and the resource manager",
             source="upstream_code", ref=f"{UPSTREAM}:178-180"),
    ]
    safe_state = ("pyvisa session closed by the upstream Close(); the measurement-only scope receives no further "
                  "commands")

    def setup(self):
        """Start on CH1, the default channel of the upstream measure methods (oscilloscope_control.py:106)."""
        self._channel = "CH1"
        self._session_closed = False

    @read("channel", type="string", description="Channel used by the measurement reads (CH1 to CH4)")
    def channel(self):
        return self._channel

    @read("frequency", unit="Hz", description="Immediate frequency measurement on the selected channel")
    def frequency(self):
        return float(self._measure(self.native.MeasureFreq))

    @read("amplitude", unit="V", description="Immediate amplitude measurement on the selected channel")
    def amplitude(self):
        return float(self._measure(self.native.MeasureAmpl))

    @read("high", unit="V", description="Immediate high-level measurement on the selected channel")
    def high(self):
        return float(self._measure(self.native.MeasureHigh))

    @write("channel", type="string", description="Select the channel (CH1 to CH4) used by the measurement reads",
           limit=Limit(allowed=CHANNELS, source="upstream_code", ref=f"{UPSTREAM}:156-167",
                       reason="SetChannel sets CH1, CH2, CH3 and CH4 and raises for any other value"))
    def set_channel(self, value):
        self.native.SetChannel(value)
        self._channel = value

    def _measure(self, method):
        """Call one upstream measure method and take its reply for the selected channel."""
        reply = method(self._channel)
        return reply[self._channel]

    @estop
    def stop(self):
        """The upstream Close: no output is driven, and the session is no longer open to commands."""
        self._close_session()

    def teardown(self):
        self._close_session()

    def _close_session(self):
        if not self._session_closed:
            self._session_closed = True
            self.native.Close()
