"""OpenMHS driver for gh.maxiv-kitscontrols/sardana-albaem: the ALBA EM2 four-channel electrometer.

A direct Driver (decorated methods) over the upstream device class ``sardana_albaem.ctrl.em2:Em2``.  Em2 is the
SCPI client of the electrometer: it creates a TCP control socket (sardana_albaem/ctrl/em2.py:128-132), opens it with
``Em2.open()`` (sardana_albaem/ctrl/em2.py:170-171), exposes the acquisition and trigger settings as properties, and
reaches each channel through ``CHANxx:*`` commands (sardana_albaem/ctrl/em2.py:51-82).  The driver calls the same
public ``command`` method the upstream Channel class uses (sardana_albaem/ctrl/em2.py:181-185), so a per-channel
write is a real native call and the gate records it.

Reads: identification, acquisition state, acquisition mode, integration time, number of points, points ready,
trigger mode/input/polarity/precision/delay, the timestamp flag, and the instant current, range and inversion of each
of the four channels.  Writes: the acquisition and trigger settings and the integration time (bounded by the upstream
controller's 0.1 to 2621.0 ms constants); the per-channel range and inversion are set by the
``x-cap.maxiv-kitscontrols.configure_channel.v1`` action, whose inputs keep the same bounds.  The number of points and
the trigger delay have no bound in the clone, so they are ``Limit.operator_required``.

Capabilities: ``cap.measure.current.v1`` measures the instant current of one channel; ``cap.device.configure.v1``
is generated from the writable state fields.  Four extension actions configure one channel, start an acquisition,
send a software trigger and stop an acquisition; the stop is also the safe-state action and the ``@estop`` path is
the upstream ``Em2.stop_acquisition()`` (ACQU:STOP True, sardana_albaem/ctrl/em2.py:294-297).

Every Fact cites a line of the clone at the pinned commit 99e701a5101781fbd7855a03b5ec3a755e8c6d46.  This package
is model-authored and unreviewed; the hardware backend was never opened and the fake is an in-memory object.  The
buffered acquisition arrays (``Em2.read`` / ACQU:MEAS? and the ZMQ stream) are not exposed: the instant per-channel
current and the scalar acquisition controls are.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream module of the native class, relative to the clone root.
MODULE = "sardana_albaem/ctrl/em2.py"
#: The amplifier ranges named by the upstream macro (sardana_albaem/macro/albaEmUtils.py:10).
RANGES = ("1mA", "100uA", "10uA", "1uA", "100nA", "10nA", "1nA", "100pA")
#: The channel numbers of the upstream client (sardana_albaem/ctrl/em2.py:35-36).
CHANNELS = ("1", "2", "3", "4")

_RANGE_LIMIT = Limit(
    allowed=list(RANGES), source="upstream_code", ref="sardana_albaem/macro/albaEmUtils.py:10",
    reason="the em_range macro lists the amplifier ranges as 1mA, 100uA, 10uA, 1uA, 100nA, 10nA, 1nA and 100pA")
_CHANNEL_LIMIT = Limit(
    allowed=list(CHANNELS), source="upstream_code", ref=f"{MODULE}:35-36",
    reason="CHANNEL_MIN is 1 and CHANNEL_MAX is 4; the client builds one Channel object per channel")


class Albaem2(Driver):
    device_id = "albaem2"
    device_kind = "instrument.dmm"
    mode = "hardware"
    risk = "R1"
    native = "sardana_albaem.ctrl.em2:Em2"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeEm2"}
    vendor, model = "MAX IV Laboratory", "AlbaEM2 four-channel electrometer"
    display_name = "ALBA EM2 four-channel electrometer"
    tags = ["electrometer", "current", "four-channel", "scpi", "alba"]
    facts = [
        Fact("em2.py is the ALBA EM2 client", source="upstream_code", ref=f"{MODULE}:1-2"),
        Fact("SCPI_CONTROL_PORT is 5025 and ZMQ_STREAMING_PORT is 22003", source="upstream_code",
             ref=f"{MODULE}:30-31"),
        Fact("Em2 creates a SCPI TCP socket to (host, port) and a ZMQ stream receiver", source="upstream_code",
             ref=f"{MODULE}:128-132"),
        Fact("The electrometer channels are numbered 1 to 4", source="upstream_code", ref=f"{MODULE}:35-36"),
        Fact("Channel.current reads CHANxx:INSC? and converts the reply to float", source="upstream_code",
             ref=f"{MODULE}:68-70"),
        Fact("Channel.range reads and writes CHANxx:CABO:RANGE", source="upstream_code", ref=f"{MODULE}:51-57"),
        Fact("Channel.inversion reads CHANxx:CABO:INVE?, returns True only for 'On', and the setter writes 'On' or "
             "'Off'", source="upstream_code", ref=f"{MODULE}:59-66"),
        Fact("The amplifier range list runs from 1 mA to 100 pA", source="upstream_code",
             ref="sardana_albaem/macro/albaEmUtils.py:10"),
        Fact("MINIMUM_INTEGRATION_TIME_MS is 0.1 and MAXIMUM_INTEGRATION_TIME_WITHOUT_OVERFLOW_MS is 2621.0",
             source="upstream_code", ref="sardana_albaem/ctrl/Albaem2OneDCtrl.py:17-20"),
        Fact("LoadOne refuses an integration time below 0.1 ms or above 2621.0 ms", source="upstream_code",
             ref="sardana_albaem/ctrl/Albaem2OneDCtrl.py:192-203"),
        Fact("Em2.acquisition_time is in seconds on the client and is sent to the device in milliseconds",
             source="upstream_code", ref=f"{MODULE}:204-210"),
        Fact("Em2.idn queries *idn?", source="upstream_code", ref=f"{MODULE}:187-189"),
        Fact("Em2.acquisition_state queries ACQU:STAT? and returns the suffix after STATE_", source="upstream_code",
             ref=f"{MODULE}:200-202"),
        Fact("Em2.nb_points queries ACQU:NTRIG? and writes ACQU:NTRIG <value>", source="upstream_code",
             ref=f"{MODULE}:212-218"),
        Fact("Em2.nb_points_ready returns the number of received streaming points or queries ACQU:NDAT?",
             source="upstream_code", ref=f"{MODULE}:220-228"),
        Fact("Em2.trigger_mode, trigger_input, trigger_polarity, trigger_precision and trigger_delay read and write "
             "the TRIG:* settings; the delay is in seconds on the client and milliseconds on the wire",
             source="upstream_code", ref=f"{MODULE}:230-268"),
        Fact("Em2.software_trigger sends TRIG:SWSE True", source="upstream_code", ref=f"{MODULE}:270-271"),
        Fact("Em2.start_acquisition sends ACQU:START, appending SWTRIG when soft_trigger is true",
             source="upstream_code", ref=f"{MODULE}:289-292"),
        Fact("Em2.stop_acquisition sends ACQU:STOP True and stops the ZMQ receiver", source="upstream_code",
             ref=f"{MODULE}:294-297"),
        Fact("Em2.timestamp_data reads TMST? and writes TMST True/False", source="upstream_code",
             ref=f"{MODULE}:281-287"),
        Fact("The alternate controller names the acquisition modes CHARGE, CURRENT and STREAMING",
             source="upstream_code", ref="sardana_albaem/ctrl/Albaem2CoTiCtrl.py:63-69"),
        Fact("The manual test names the trigger modes SOFTWARE, HARDWARE, GATE, AUTOTRIGGER and HW_AUTOTRIGGER",
             source="upstream_code", ref="sardana_albaem/ctrl/manual_test_em2.py:113-116"),
    ]
    safe_state = "acquisition stopped (ACQU:STOP True); the electrometer records no new points"

    # -- state reads -------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Identification string of the electrometer (*idn?)")
    def identity(self):
        return self.native.idn

    @read("acquisition_state", type="string",
          description="Acquisition state reported by ACQU:STAT? (for example ON, RUNNING, ACQUIRING, DONE or FAULT)")
    def acquisition_state(self):
        return self.native.acquisition_state

    @read("nb_points_ready", type="integer", unit="1",
          description="Number of acquisition points the electrometer has ready")
    def nb_points_ready(self):
        return int(self.native.nb_points_ready)

    @read("current_ch1", unit="A", description="Instant current of channel 1")
    def current_ch1(self):
        return float(self.native.command("CHAN01:INSC?"))

    @read("current_ch2", unit="A", description="Instant current of channel 2")
    def current_ch2(self):
        return float(self.native.command("CHAN02:INSC?"))

    @read("current_ch3", unit="A", description="Instant current of channel 3")
    def current_ch3(self):
        return float(self.native.command("CHAN03:INSC?"))

    @read("current_ch4", unit="A", description="Instant current of channel 4")
    def current_ch4(self):
        return float(self.native.command("CHAN04:INSC?"))

    # -- acquisition settings ----------------------------------------------------------------------------------
    @read("acquisition_mode", type="string",
          description="Acquisition mode (the clone names CHARGE, CURRENT and STREAMING)")
    def acquisition_mode(self):
        return self.native.acquisition_mode

    @write("acquisition_mode", type="string", description="Acquisition mode (CHARGE, CURRENT or STREAMING)")
    def set_acquisition_mode(self, value):
        self.native.acquisition_mode = value

    @read("integration_time", unit="ms", native_unit="s",
          description="Integration time of one acquisition point")
    def integration_time(self):
        return self.native.acquisition_time

    @write("integration_time", unit="ms", native_unit="s", description="Integration time of one point",
           limit=Limit(min=0.1, max=2621.0, unit="ms", source="upstream_code",
                       ref="sardana_albaem/ctrl/Albaem2OneDCtrl.py:17-20",
                       reason="the upstream controller refuses an integration time below 0.1 ms or above 2621.0 ms "
                              "without overflow"))
    def set_integration_time(self, value):
        self.native.acquisition_time = value

    @read("nb_points", type="integer", unit="1", description="Number of acquisition points (triggers) to record")
    def nb_points(self):
        return int(self.native.nb_points)

    @write("nb_points", type="integer", unit="1", description="Number of points to record",
           limit=Limit.operator_required(
               "no text file of the clone states the maximum number of triggers the electrometer accepts; the site "
               "supplies the bound for its unit"))
    def set_nb_points(self, value):
        self.native.nb_points = value

    # -- trigger settings --------------------------------------------------------------------------------------
    @read("trigger_mode", type="string",
          description="Trigger mode (the manual test names SOFTWARE, HARDWARE, GATE, AUTOTRIGGER and HW_AUTOTRIGGER)")
    def trigger_mode(self):
        return self.native.trigger_mode

    @write("trigger_mode", type="string", description="Trigger mode")
    def set_trigger_mode(self, value):
        self.native.trigger_mode = value

    @read("trigger_input", type="string", description="External trigger input selected by TRIG:INPU?")
    def trigger_input(self):
        return self.native.trigger_input

    @write("trigger_input", type="string", description="External trigger input")
    def set_trigger_input(self, value):
        self.native.trigger_input = value

    @read("trigger_polarity", type="string", description="Trigger polarity selected by TRIG:POLA?")
    def trigger_polarity(self):
        return self.native.trigger_polarity

    @write("trigger_polarity", type="string", description="Trigger polarity")
    def set_trigger_polarity(self, value):
        self.native.trigger_polarity = value

    @read("trigger_precision", type="boolean", description="True when the precision trigger mode is enabled")
    def trigger_precision(self):
        return bool(self.native.trigger_precision)

    @write("trigger_precision", type="boolean", description="Precision trigger enabled")
    def set_trigger_precision(self, value):
        self.native.trigger_precision = bool(value)

    @read("trigger_delay", unit="ms", native_unit="s", description="Delay between the trigger and the acquisition")
    def trigger_delay(self):
        return self.native.trigger_delay

    @write("trigger_delay", unit="ms", native_unit="s", description="Trigger delay",
           limit=Limit.operator_required(
               "no text file of the clone states the trigger delay range of the electrometer; the site supplies the "
               "bound for its unit"))
    def set_trigger_delay(self, value):
        self.native.trigger_delay = value

    @read("timestamp_data", type="boolean", description="True when acquisition points carry timestamps")
    def timestamp_data(self):
        return bool(self.native.timestamp_data)

    @write("timestamp_data", type="boolean", description="Timestamps on acquisition points")
    def set_timestamp_data(self, value):
        self.native.timestamp_data = bool(value)

    # -- per-channel range and inversion ------------------------------------------------------------------------
    @read("range_ch1", type="string", description="Amplifier range of channel 1")
    def range_ch1(self):
        return self.native.command("CHAN01:CABO:RANGE?")

    @read("range_ch2", type="string", description="Amplifier range of channel 2")
    def range_ch2(self):
        return self.native.command("CHAN02:CABO:RANGE?")

    @read("range_ch3", type="string", description="Amplifier range of channel 3")
    def range_ch3(self):
        return self.native.command("CHAN03:CABO:RANGE?")

    @read("range_ch4", type="string", description="Amplifier range of channel 4")
    def range_ch4(self):
        return self.native.command("CHAN04:CABO:RANGE?")

    @read("inversion_ch1", type="boolean", description="Digital inversion of channel 1")
    def inversion_ch1(self):
        return self.native.command("CHAN01:CABO:INVE?") == "On"

    @read("inversion_ch2", type="boolean", description="Digital inversion of channel 2")
    def inversion_ch2(self):
        return self.native.command("CHAN02:CABO:INVE?") == "On"

    @read("inversion_ch3", type="boolean", description="Digital inversion of channel 3")
    def inversion_ch3(self):
        return self.native.command("CHAN03:CABO:INVE?") == "On"

    @read("inversion_ch4", type="boolean", description="Digital inversion of channel 4")
    def inversion_ch4(self):
        return self.native.command("CHAN04:CABO:INVE?") == "On"

    # -- capabilities ------------------------------------------------------------------------------------------
    @action(cap="cap.measure.current.v1", description="Measure the instant current of one electrometer channel",
            input={"channel": Field("string", description="Channel number, 1 to 4",
                                    limit=_CHANNEL_LIMIT)})
    def measure_current(self, channel="1"):
        try:
            index = int(channel)
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {channel!r} is not one of {list(CHANNELS)}") from exc
        return {"current": float(self.native.command(f"CHAN{index:02d}:INSC?"))}

    @action(name="x-cap.maxiv-kitscontrols.configure_channel.v1",
            description="Read or set the amplifier range and digital inversion of one channel",
            input={"channel": Field("string", description="Channel number, 1 to 4",
                                    limit=_CHANNEL_LIMIT),
                   "amplifier_range": Field("string", description="Amplifier range",
                                            limit=_RANGE_LIMIT),
                   "inversion": Field("boolean", description="Digital inversion")},
            output={"channel": Field("string", description="Channel number"),
                    "amplifier_range": Field("string", description="Amplifier range after the call"),
                    "inversion": Field("boolean", description="Digital inversion after the call")})
    def configure_channel(self, channel="1", amplifier_range=None, inversion=None):
        try:
            index = int(channel)
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"channel {channel!r} is not one of {list(CHANNELS)}") from exc
        if amplifier_range is not None:
            self.native.command(f"CHAN{index:02d}:CABO:RANGE {amplifier_range}")
        if inversion is not None:
            self.native.command(f"CHAN{index:02d}:CABO:INVE {'On' if inversion else 'Off'}")
        return {"channel": str(index),
                "amplifier_range": self.native.command(f"CHAN{index:02d}:CABO:RANGE?"),
                "inversion": self.native.command(f"CHAN{index:02d}:CABO:INVE?") == "On"}

    @action(name="x-cap.maxiv-kitscontrols.start_acquisition.v1",
            description="Start an acquisition with the current settings",
            input={"soft_trigger": Field("boolean",
                                         description="True to send a software trigger with the start command")},
            output={"acquisition_state": Field("string",
                                               description="Acquisition state reported after the start"),
                    "soft_trigger": Field("boolean",
                                          description="The software trigger flag sent with the start command")})
    def start_acquisition(self, soft_trigger=True):
        flag = bool(soft_trigger)
        self.native.start_acquisition(soft_trigger=flag)
        return {"acquisition_state": self.native.acquisition_state, "soft_trigger": flag}

    @action(name="x-cap.maxiv-kitscontrols.software_trigger.v1",
            description="Send a software trigger to the electrometer",
            output={"acquisition_state": Field("string",
                                               description="Acquisition state reported after the trigger")})
    def software_trigger(self):
        self.native.software_trigger()
        return {"acquisition_state": self.native.acquisition_state}

    @action(name="x-cap.maxiv-kitscontrols.stop_acquisition.v1", safe_state=True,
            description="Stop the acquisition and the streaming receiver (the native stop, the safe state)",
            output={"acquisition_state": Field("string",
                                               description="Acquisition state reported after the stop")})
    def stop_acquisition(self):
        self.native.stop_acquisition()
        return {"acquisition_state": self.native.acquisition_state}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends ACQU:STOP True."""
        self.native.stop_acquisition()
