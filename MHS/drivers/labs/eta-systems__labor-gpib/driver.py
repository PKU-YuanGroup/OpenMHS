"""OpenMHS driver for gh.eta-systems/labor-gpib: channel A of a Rohde & Schwarz NGMO2.

The upstream repository is a small GPIB wrapper.  The relevant entry class is
``devices.rohde_schwarz_ngmo2:device`` (src/devices/rohde_schwarz_ngmo2.py:16), which builds a ``Channel`` object for
each output (lines 24-25).  The class writes SCPI-like text through a Prologix GPIB transport
(``src/interface/prologix_gpib.py:45-99``).  This package is a direct ``Driver`` over that class, not the card's
``ScpiDriver``: the channel commands are assembled from a channel letter at run time (for example
``':SOUR:' + self.letter + ':VOLT '``, line 408), and the upstream object also owns the transport, the format and the
display, so a command table would not reproduce the interface.  The driver calls the upstream class through its
top-level ``send_command`` path (lines 193-194) and reads the device through the methods the class provides.

Covered:

* state reads: the last voltage and current set points this driver applied, the measurement interval, the averaging
  count, the output and display states, the sense function, the current range, the output format, the identity and
  the status byte;
* writes: voltage set point, current limit, measurement interval, averaging samples, output on/off, display on/off,
  sense function, current range and output data format, each bounded by the upstream code;
* ``cap.measure.voltage.v1`` and ``cap.measure.current.v1``: one measurement of channel A after selecting the
  corresponding sense function, using the same ``:MEAS:A?`` query as ``Channel.read_voltage`` / ``read_current``
  (lines 569-579);
* the e-stop and the safe-state action send ``:OUT:A OFF``.  This is the output-disable command of the clone
  (lines 394-395); no text of the clone documents a separate hardware emergency stop, so there is no
  ``estop_physical_ref`` and the safe-state action is the declared independent stop path of SAFE-045.
* the safety reset sends nothing.  ``device.reset`` (lines 85-86) calls ``rst`` (lines 81-83), which writes
  ``*RST`` and then calls ``cls``.  ``cls`` (lines 30-31) writes ``*CLS``.  The comment on line 80 does not state
  the output, so that call is the ordinary command ``x-cap.eta-systems.scpi_rst.v1`` and not a reset step (SAFE-042).

The upstream class has no query for the voltage and current set points or for the averaging count.  The driver keeps
those three values as the last values it applied; before the first write they are the binding's initial state, not a
reading of the instrument.  After ``x-cap.eta-systems.scpi_rst.v1`` they are refused until this driver writes them
again, because the clone does not state the ``*RST`` defaults.  The current limit is bounded at 5 A by the clone's
code (line 413); the comment above it says that at most 2.5 A is allowed above 5 V (line 410), and that conditional
derating is stated here rather than enforced as a second, conditional limit the runtime cannot express.

Every Fact and Limit cites a line of the clone at the pinned commit
(d5fe1b230344452bc32b756fc14567acde683c74).  The package is model-authored and unreviewed, and the acceptance gate ran
the fake backend only; nothing here ran on hardware.
"""

from decimal import Decimal

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

UPSTREAM = "src/devices/rohde_schwarz_ngmo2.py"
PROLOGIX = "src/interface/prologix_gpib.py"

#: The canonical sense names this driver accepts and the tokens the clone writes (lines 422-444).
SENSE_COMMANDS = {
    "volt": "VOLT",
    "curr": "CURR",
    "dvm": "DVM",
    "avg": "AVER",
    "peak": "PEAK",
    "min": "MIN",
    "high": "HIGH",
    "low": "LOW",
    "rms": "RMS",
}
#: Reverse map for the value returned by ``get_sense`` (line 447).
SENSE_VALUES = {command: name for name, command in SENSE_COMMANDS.items()}

#: The canonical current-range names this driver accepts and the tokens the clone writes (lines 451-463).
RANGE_COMMANDS = {"auto": "AUTO", "high": "HIGH", "medium": "MED", "low": "MIN"}
#: Reverse map for the value returned by ``get_current_range`` (line 467).  ``MIN`` is the 5 mA range.
RANGE_VALUES = {"AUTO": "auto", "HIGH": "high", "MED": "medium", "MIN": "low"}

#: The canonical output-format names this driver accepts and the tokens the clone writes (lines 214-225).
FORMAT_COMMANDS = {"ascii": "ASCii", "long": "LONG", "short": "SREal", "double": "DREal"}
#: Reverse map for the value returned by ``get_output_format`` (line 228).
FORMAT_VALUES = {"ASC": "ascii", "ASCii": "ascii", "LONG": "long", "SRE": "short", "SREAL": "short",
                 "DRE": "double", "DREAL": "double"}


class Ngmo2(Driver):
    device_id = "ngmo2"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R2"
    native = "devices.rohde_schwarz_ngmo2:device"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNgmo2"}
    vendor = "Rohde & Schwarz"
    model = "NGMO2 dual-channel analyzer/power supply"
    display_name = "Rohde & Schwarz NGMO2 channel A"
    tags = ["power supply", "source measure unit", "ngmo2", "gpib", "prologix", "channel a"]
    facts = [
        Fact("The NGMO2 is a dual-channel analyzer/power supply", source="vendor_doc", ref="README.md:84"),
        Fact("device builds channel_a, channel_b, display, format and status objects in its constructor",
             source="upstream_code", ref=f"{UPSTREAM}:16-27"),
        Fact("send_command writes one command to the bus for the device address", source="upstream_code",
             ref=f"{UPSTREAM}:193-194"),
        Fact("Channel.voltage accepts 0 to 15 V and rounds to 1 mV", source="upstream_code",
             ref=f"{UPSTREAM}:402-408"),
        Fact("Channel.current accepts 0 to 5 A and rounds to 1 mA; the comment says at most 2.5 A above 5 V",
             source="upstream_code", ref=f"{UPSTREAM}:410-417"),
        Fact("Channel.measure_interval accepts 0.00001 to 1.0 s in 10 us steps", source="upstream_code",
             ref=f"{UPSTREAM}:481-487"),
        Fact("Channel.set_averaging_samples accepts 1 to 10 samples", source="upstream_code",
             ref=f"{UPSTREAM}:495-506"),
        Fact("Channel.on and Channel.off send :OUT:A ON and :OUT:A OFF", source="upstream_code",
             ref=f"{UPSTREAM}:391-395"),
        Fact("Channel.is_on queries :OUTP:A:STAT?", source="upstream_code", ref=f"{UPSTREAM}:397-400"),
        Fact("Channel.sense maps sense names to :SENS:A:FUNC", source="upstream_code",
             ref=f"{UPSTREAM}:422-444"),
        Fact("Channel.get_sense queries :SENS:A:FUNC?", source="upstream_code", ref=f"{UPSTREAM}:446-448"),
        Fact("Channel.current_range maps range names to :SENS:A:CURR:RANG:UPP", source="upstream_code",
             ref=f"{UPSTREAM}:451-463"),
        Fact("Channel.get_current_range queries :SENS:A:CURR:DC:RANG:UPP?", source="upstream_code",
             ref=f"{UPSTREAM}:466-468"),
        Fact("Channel.get_interval queries :SENS:A:MEAS:INT? and returns a float", source="upstream_code",
             ref=f"{UPSTREAM}:490-493"),
        Fact("Channel.read_voltage selects the volt function, sends :MEAS:A? and reads until LF",
             source="upstream_code", ref=f"{UPSTREAM}:569-573"),
        Fact("Channel.read_current selects the current function, sends :MEAS:A? and reads until LF",
             source="upstream_code", ref=f"{UPSTREAM}:575-579"),
        Fact("device.set_output_format maps ascii, long, short and double to :FORMat:DATA", source="upstream_code",
             ref=f"{UPSTREAM}:214-225"),
        Fact("device.get_output_format queries :FORMat:DATA?", source="upstream_code", ref=f"{UPSTREAM}:227-229"),
        Fact("Display.enable writes :DISP:ENAB ON or OFF", source="upstream_code", ref=f"{UPSTREAM}:246-252"),
        Fact("Display.enabled queries :DISP:ENAB? and returns a boolean", source="upstream_code",
             ref=f"{UPSTREAM}:255-264"),
        Fact("device.get_idn sends *IDN? and its comment shows the reply format", source="upstream_code",
             ref=f"{UPSTREAM}:188-191"),
        Fact("device.get_status sends *STB?", source="upstream_code", ref=f"{UPSTREAM}:201-203"),
        Fact("device.arm sends *ARM", source="upstream_code", ref=f"{UPSTREAM}:124-126"),
        Fact("device.reset sends *RST and then *CLS", source="upstream_code", ref=f"{UPSTREAM}:80-89"),
        Fact("The comment on device.rst says it returns the power supply to the *RST default conditions",
             source="upstream_code", ref=f"{UPSTREAM}:80"),
        Fact("The Prologix adapter accepts GPIB addresses 0 to 30", source="upstream_code",
             ref=f"{PROLOGIX}:35-43"),
        Fact("The Prologix request writes the query and then ++read 10", source="upstream_code",
             ref=f"{PROLOGIX}:85-99"),
        Fact("Display.set_channel builds a command but the TODO on line 281 shows it is never sent",
             source="upstream_code", ref=f"{UPSTREAM}:266-281"),
        Fact("Channel.get_impedance queries the bandwidth command instead of an impedance query",
             source="upstream_code", ref=f"{UPSTREAM}:553-555"),
    ]
    safe_state = "channel A output off (:OUT:A OFF) and no further actuation sent by this binding"

    def setup(self):
        """Initial binding state for the three values the upstream class has no query for.

        The initial values are this binding's starting state, not a measurement of the instrument.
        ``None`` means ``x-cap.eta-systems.scpi_rst.v1`` has run and the clone states no default number.
        """
        self._voltage_setpoint = 0.0
        self._current_limit = 0.0
        self._averaging_samples = 1

    def _known_applied(self, attr, initial, label):
        """Return a cached set point, or refuse it after ``*RST`` (SAFE-042).

        The comment on ``device.rst`` (line 80) says the supply returns to the ``*RST`` default conditions and
        states no voltage, current or averaging.  Reporting the last applied number, or zero, would claim a
        value the clone does not show.
        """
        value = getattr(self, attr, initial)
        if value is None:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"{label} is unknown after *RST. The comment on device.rst says the supply returns to the "
                "*RST default conditions (src/devices/rohde_schwarz_ngmo2.py:80) and states no number. "
                "Write it again.")
        return value

    def _measure_channel_a(self):
        """Send ``:MEAS:A?`` and read the reply (Channel.read_voltage, line 571-572)."""
        self.native.send_command(":MEAS:A?")
        return float(self.native.bus.read_until_char(self.native.address, "10"))

    # -- state reads ----------------------------------------------------------------------------------------------
    @read("voltage_setpoint", unit="V",
          description="Last voltage set point this driver applied; the upstream class has no voltage query. "
                      "Refused after x-cap.eta-systems.scpi_rst.v1 until written again: the clone states no "
                      "*RST default voltage")
    def voltage_setpoint(self):
        return float(self._known_applied("_voltage_setpoint", 0.0, "voltage_setpoint"))

    @read("current_limit", unit="A",
          description="Last current limit this driver applied; the upstream class has no current query. "
                      "Refused after x-cap.eta-systems.scpi_rst.v1 until written again: the clone states no "
                      "*RST default current")
    def current_limit(self):
        return float(self._known_applied("_current_limit", 0.0, "current_limit"))

    @read("measurement_interval", unit="s",
          description="Measurement interval returned by :SENS:A:MEAS:INT?")
    def measurement_interval(self):
        return float(self.native.channel_a.get_interval())

    @read("averaging_samples", type="integer", unit="1",
          description="Last averaging count this driver applied; the upstream class has no averaging query. "
                      "Refused after x-cap.eta-systems.scpi_rst.v1 until written again: the clone states no "
                      "*RST default count")
    def averaging_samples(self):
        return int(self._known_applied("_averaging_samples", 1, "averaging_samples"))

    @read("output_enabled", type="boolean", description="True while :OUTP:A:STAT? reports ON")
    def output_enabled(self):
        value = str(self.native.channel_a.is_on()).strip().upper()
        return value in ("ON", "1")

    @read("sense_function", type="string",
          description="Selected sense function from :SENS:A:FUNC?")
    def sense_function(self):
        value = str(self.native.channel_a.get_sense()).strip().upper()
        return SENSE_VALUES.get(value, value.lower())

    @read("current_range", type="string",
          description="Selected current measurement range from :SENS:A:CURR:DC:RANG:UPP?")
    def current_range(self):
        value = str(self.native.channel_a.get_current_range()).strip().upper()
        return RANGE_VALUES.get(value, value.lower())

    @read("output_format", type="string",
          description="Output data format from :FORMat:DATA?")
    def output_format(self):
        value = str(self.native.get_output_format()).strip().upper()
        return FORMAT_VALUES.get(value, value.lower())

    @read("display_enabled", type="boolean", description="True while :DISP:ENAB? reports ON")
    def display_enabled(self):
        return bool(self.native.display.enabled())

    @read("identity", type="string", description="Instrument identity returned by *IDN?")
    def identity(self):
        return str(self.native.get_idn()).strip()

    @read("status_byte", type="integer", description="Status byte returned by *STB?")
    def status_byte(self):
        return int(str(self.native.get_status()).strip())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("voltage_setpoint", unit="V",
           description="Channel A voltage set point",
           limit=Limit(min=0, max=15, source="upstream_code", ref=f"{UPSTREAM}:405",
                       reason="Channel.voltage checks 0 <= voltage <= 15"))
    def set_voltage_setpoint(self, value):
        applied = round(float(value), 3)
        self.native.send_command(f":SOUR:A:VOLT {applied}")
        self._voltage_setpoint = applied
        return applied

    @write("current_limit", unit="A",
           description="Channel A current limit",
           limit=Limit(min=0, max=5, source="upstream_code", ref=f"{UPSTREAM}:413",
                       reason="Channel.current checks 0 <= current <= 5; the comment on line 410 also states a "
                              "2.5 A maximum above 5 V"))
    def set_current_limit(self, value):
        applied = round(float(value), 3)
        self.native.send_command(":SOUR:A:CURR:LIM " + ("%.2E" % Decimal(applied)))
        self._current_limit = applied
        return applied

    @write("measurement_interval", unit="s",
           description="Measurement interval",
           limit=Limit(min=0.00001, max=1.0, source="upstream_code", ref=f"{UPSTREAM}:482",
                       reason="Channel.measure_interval checks 0.00001 <= interval <= 1.0"))
    def set_measurement_interval(self, value):
        applied = round(float(value), 5)
        self.native.send_command(":SENS:A:MEAS:INT " + ("%.2E" % Decimal(applied)))
        return applied

    @write("averaging_samples", type="integer", unit="1",
           description="Averaging count",
           limit=Limit(min=1, max=10, source="upstream_code", ref=f"{UPSTREAM}:504",
                       reason="Channel.set_averaging_samples checks 1 <= count <= 10"))
    def set_averaging_samples(self, value):
        applied = int(value)
        self.native.send_command(f":SENS:A:MEAS:AVER:COUN {applied}")
        self._averaging_samples = applied
        return applied

    @write("output_enabled", type="boolean",
           description="Channel A output on or off")
    def set_output_enabled(self, value):
        self.native.send_command(":OUT:A ON" if value else ":OUT:A OFF")
        return bool(value)

    @write("display_enabled", type="boolean",
           description="Display on or off")
    def set_display_enabled(self, value):
        self.native.send_command(":DISP:ENAB ON" if value else ":DISP:ENAB OFF")
        return bool(value)

    @write("sense_function", type="string",
           description="Sense function",
           limit=Limit(allowed=list(SENSE_COMMANDS), source="upstream_code", ref=f"{UPSTREAM}:424-441",
                       reason="Channel.sense accepts these function names"))
    def set_sense_function(self, value):
        name = str(value).strip().lower()
        self.native.send_command(f":SENS:A:FUNC {SENSE_COMMANDS[name]}")
        return name

    @write("current_range", type="string",
           description="Current range",
           limit=Limit(allowed=list(RANGE_COMMANDS), source="upstream_code", ref=f"{UPSTREAM}:454-461",
                       reason="Channel.current_range accepts these range names"))
    def set_current_range(self, value):
        name = str(value).strip().lower()
        self.native.send_command(f":SENS:A:CURR:RANG:UPP:{RANGE_COMMANDS[name]}")
        return name

    @write("output_format", type="string",
           description="Output format",
           limit=Limit(allowed=list(FORMAT_COMMANDS), source="upstream_code", ref=f"{UPSTREAM}:216-223",
                       reason="device.set_output_format accepts these format names"))
    def set_output_format(self, value):
        name = str(value).strip().lower()
        self.native.set_output_format(name)
        return name

    # -- capabilities ---------------------------------------------------------------------------------------------
    def _bound_channel(self, channel):
        """Accept only a name of channel A; channel B is not bound by this package."""
        if channel is None:
            return
        text = str(channel).strip().lower()
        if text in ("a", "1", "ch1", "channel_a", "channel a"):
            return
        raise DriverFailed(
            "MHS.DEVICE.PRECONDITION_UNMET",
            f"channel {channel!r} is not the channel A binding; only channel A is bound")

    @action(cap="cap.measure.voltage.v1",
            description="Select the volt function and read one channel A measurement (:MEAS:A?)",
            input={
                "channel": Field("string", max_length=64,
                                 description="Channel name; only channel A is bound"),
                "dc": Field("boolean", description="True for the DC reading this binding supports"),
                "range_v": Field("number", unit="V", description="Requested voltage range",
                                 limit=Limit(min=0, max=15, source="upstream_code", ref=f"{UPSTREAM}:405",
                                             reason="Channel.voltage accepts 0 to 15 V")),
            })
    def measure_voltage(self, channel=None, dc=True, range_v=None):
        self._bound_channel(channel)
        if not dc:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "the clone's :MEAS:A? returns a DC reading; an RMS query is not available")
        self.native.send_command(":SENS:A:FUNC VOLT")
        output = {"voltage": self._measure_channel_a()}
        if range_v is not None:
            output["range_v"] = float(range_v)
        return output

    @action(cap="cap.measure.current.v1",
            description="Select the current function and read one channel A measurement (:MEAS:A?)",
            input={
                "channel": Field("string", max_length=64,
                                 description="Channel name; only channel A is bound"),
                "range_a": Field("number", unit="A", description="Requested current range",
                                 limit=Limit(min=0, max=5, source="upstream_code", ref=f"{UPSTREAM}:413",
                                             reason="Channel.current accepts 0 to 5 A")),
            })
    def measure_current(self, channel=None, range_a=None):
        self._bound_channel(channel)
        self.native.send_command(":SENS:A:FUNC CURR")
        output = {"current": self._measure_channel_a()}
        if range_a is not None:
            output["range_a"] = float(range_a)
        return output

    @action(name="x-cap.eta-systems.output_off.v1", safe_state=True,
            description="Send :OUT:A OFF: the safe state, with no input and no read-back wait",
            output={"output_enabled": Field("boolean",
                                            description="False: the :OUT:A OFF stop command was sent")})
    def output_off(self):
        self.native.send_command(":OUT:A OFF")
        return {"output_enabled": False}

    @action(name="x-cap.eta-systems.scpi_rst.v1",
            description="Call device.reset (src/devices/rohde_schwarz_ngmo2.py:85-86). rst writes *RST "
                        "(lines 81-83) and cls writes *CLS (lines 30-31). The comment on rst says this returns the "
                        "supply to the *RST default conditions and does not state the output, the voltage, the "
                        "current or the averaging. An ordinary command: the safety reset does not call it, and it "
                        "is not a re-enable or a safe-state action. The three cached set points are refused before "
                        "device.reset is called, including when that call raises, until this driver writes them. "
                        "The operator confirms the instrument, including whether an output is enabled.",
            output={"command_sent": Field(
                "boolean",
                description="True after device.reset returned. Not a reading of the output or the set points.")})
    def scpi_rst(self):
        """The upstream ``device.reset`` (*RST then *CLS). Not the safety reset (SAFE-042).

        Clear the three caches before the call. ``reset`` writes ``*RST`` and then ``*CLS``, and a failure
        on the later write must not leave the old set points readable. The exception still propagates.
        """
        self._voltage_setpoint = None
        self._current_limit = None
        self._averaging_samples = None
        self.native.reset()
        return {"command_sent": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="send_command")
    def stop(self):
        """The native stop: send the clone's channel A output-off command (line 395). It does not send *RST."""
        self.native.send_command(":OUT:A OFF")
