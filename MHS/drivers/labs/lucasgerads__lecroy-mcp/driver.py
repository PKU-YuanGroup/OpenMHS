"""OpenMHS driver for gh.lucasgerads/lecroy-mcp: LeCroy MAUI oscilloscopes over VISA/SCPI.

A direct Driver over the upstream high-level class ``oscilloscope:LeCroyScope``.  The card proposes a
``ScpiDriver`` (family ``scpi``, decision ``family-config``), but the upstream is an object whose every channel
command is assembled at run time from a channel number and a command word (``C1:VDIV``, ``C1:OFST``,
``C1:BWL``); a fixed command table cannot reproduce those lines and gate G7 refuses to let the wire syntax be
changed to fit one.  This package therefore uses a direct Driver with the ``native.py`` hardware factory
(DEVIATION FROM THE CARD, recorded in RESULT.json).

The served resource is analog channel 1 plus the shared timebase, the edge trigger and acquisition control:

* reads: identity, model family, channel count, bandwidth, date, acquisition status, the stopped flag, the
  channel-1 vertical scale, offset, coupling and probe attenuation, the timebase, trigger mode, trigger source
  and trigger level;
* writes: channel 1's vertical scale, offset, coupling and attenuation, the timebase, trigger mode, trigger
  source and trigger level.  The numeric writes whose range the clone and the vendor text do not state are
  ``Limit.operator_required``;
* actions: arm one acquisition, force a trigger, read one PAVA scalar measurement, and the catalogue
  ``cap.device.calibrate.v1`` binding around the native ``*CAL?`` self-calibration;
* the e-stop calls the native ``stop()``, which writes ``STOP``; the frozen acquisition is the oscilloscope's
  safe state.

NOT COVERED: the waveform array and the screenshot.  ``get_waveform``/``get_waveforms`` transfer IEEE 488.2
binary blocks as voltage and time arrays, and ``get_screenshot`` returns PNG bytes; no catalogue class carries
a trace or image array for this package, so it serves the scalar measurements and the settings of the
oscilloscope, not the samples.  The math functions, cursors, WaveSource and serial-decode paths are not exposed.
The bandwidth limit (BWL) and trigger delay (TRDL) are also not exposed: the single configure tool must stay
within the MCP projection's 2048-byte budget, and the channel, timebase and trigger controls above are the
primary ones.

Every Fact and Limit cites a line of the clone at the pinned commit (3c866b341605ca689069d729c7b918f1c725d2e6).
The vendor citations are the manual text files shipped in the clone (``resources/maui_text.txt``).  This package
is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

UPSTREAM = "oscilloscope.py"
MANUAL = "resources/maui_text.txt"

#: The one analog channel this package serves.  Every profile has at least channel 1 (oscilloscope.py:368-375).
CHANNEL = 1

#: Values the vendor manual states for the commands this driver writes.
COUPLINGS = ["A1M", "D1M", "D50", "GND"]                                      # MANUAL:4589
ATTENUATIONS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 10000]          # MANUAL:4527
TRIGGER_MODES = ["AUTO", "NORM", "SINGLE", "STOP"]                            # MANUAL:4842

#: The standard PAVA parameters the clone accepts (oscilloscope.py:170-175).
PAVA_PARAMETERS = [
    "AMPL", "AREA", "BASE", "DELAY", "DUTY", "FALL", "FREQ", "MAX", "MEAN", "MIN",
    "OVSP", "PERIOD", "PHASE", "PKPK", "RISE", "RMS", "TOP", "UNDSP", "WIDTH",
]


def _text(value):
    """A SCPI reply as text: the upstream transport may hand back bytes or str."""
    if isinstance(value, bytes):
        return value.decode("ascii", "replace").strip()
    return str(value).strip()


def _number(value):
    """A numeric SCPI reply as a float; a reply that carries no number is a device fault."""
    text = _text(value)
    try:
        return float(text)
    except ValueError as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"expected a numeric reply, got {text!r}") from exc


def _setting_text(value):
    text = _text(value)
    if not text or text == "N/A":
        raise DriverFailed("MHS.DEVICE.FAULTED", "the upstream setting query failed (N/A or empty reply)")
    return text


def _trigger_source(select):
    """The source field of a TRIG_SELECT reply (the manual's format is TRIG_SELECT <type>,SR,<source>,...)."""
    text = _text(select).replace("TRIG_SELECT", " ")
    fields = [item.strip() for item in text.split(",") if item.strip()]
    for index, item in enumerate(fields):
        if item.upper() == "SR" and index + 1 < len(fields):
            return fields[index + 1].upper()
    raise DriverFailed("MHS.DEVICE.FAULTED", f"TRIG_SELECT reply has no source field: {text!r}")


def _calibration_code(reply):
    """The diagnostic code of a *CAL? reply (MANUAL:6376-6377: 0 means the calibration was successful)."""
    text = _text(reply)
    token = text.split()[-1] if text.split() else ""
    try:
        return int(token)
    except ValueError as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"*CAL? reply has no diagnostic code: {text!r}") from exc


class LecroyScope(Driver):
    device_id = "lecroy-scope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "oscilloscope:LeCroyScope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLeCroyScope"}
    vendor = "Teledyne LeCroy"
    model = "MAUI oscilloscopes (WaveSurfer, HDO, MDA, WavePro, WaveRunner, SDA)"
    display_name = "LeCroy MAUI oscilloscope (LeCroyScope)"
    tags = ["oscilloscope", "lecroy", "maui", "scpi", "visa", "waveform", "measurement"]
    facts = [
        Fact("LeCroyScope is a VISA/SCPI interface for LeCroy oscilloscopes running MAUI firmware",
             source="upstream_code", ref=f"{UPSTREAM}:198-200"),
        Fact("Connection is lazy: __init__ stores the VISA resource string and connect() opens "
             "pyvisa.ResourceManager('@py') and the resource, sets a 10 s timeout and newline terminators, then "
             "queries *IDN?", source="upstream_code", ref=f"{UPSTREAM}:209-237"),
        Fact("The model is the second comma-separated field of the *IDN? reply", source="upstream_code",
             ref=f"{UPSTREAM}:263-273"),
        Fact("The model profile registry covers WaveSurfer, HDO, MDA, WavePro, WaveRunner and SDA families with 4 "
             "or 8 analog channels", source="upstream_code", ref=f"{UPSTREAM}:53-156"),
        Fact("get_capabilities returns the profile's channel count, bandwidth, ADC bits, coupling and "
             "bandwidth-limit values and math-channel count", source="upstream_code", ref=f"{UPSTREAM}:275-294"),
        Fact("get_channel_info queries <channel>:VDIV?, <channel>:OFST?, <channel>:CPL? (or COUP?), BWL?, "
             "<channel>:TRA? and, when the profile supports them, INVS? and UNIT?", source="upstream_code",
             ref=f"{UPSTREAM}:440-460"),
        Fact("set_vdiv writes <channel>:VDIV and set_offset writes <channel>:OFST", source="upstream_code",
             ref=f"{UPSTREAM}:462-466"),
        Fact("set_coupling and set_bwlimit validate the value against the detected profile before writing "
             "<channel>:CPL or <channel>:BWL", source="upstream_code", ref=f"{UPSTREAM}:468-488"),
        Fact("set_attenuation writes <channel>:ATTN", source="upstream_code", ref=f"{UPSTREAM}:498-499"),
        Fact("get_timebase_info queries TDIV?, TRDL? and MSIZ?", source="upstream_code",
             ref=f"{UPSTREAM}:513-521"),
        Fact("set_tdiv writes TDIV and set_trigger_delay writes TRDL", source="upstream_code",
             ref=f"{UPSTREAM}:523-527"),
        Fact("get_trigger_info queries TRIG_MODE?, TRIG_SELECT? and <channel>:TRIG_LEVEL? for every profile "
             "channel", source="upstream_code", ref=f"{UPSTREAM}:536-548"),
        Fact("set_trigger_mode validates against VALID_TRIG_MODES, set_trigger_source writes TRIG_SELECT "
             "EDGE,SR,...,SL,...,HT,OFF and set_trigger_level writes <channel>:TRIG_LEVEL", source="upstream_code",
             ref=f"{UPSTREAM}:550-565"),
        Fact("force_trigger writes FRTR, arm writes ARM and stop writes STOP", source="upstream_code",
             ref=f"{UPSTREAM}:567-578"),
        Fact("is_stopped queries TRMD? and reports True when the reply contains STOP", source="upstream_code",
             ref=f"{UPSTREAM}:580-583"),
        Fact("measure queries <channel>:PAVA? <parameter>; if the reply contains ',IV' it writes "
             "PACU 1,<parameter>,<channel> and queries again", source="upstream_code", ref=f"{UPSTREAM}:628-640"),
        Fact("calibrate queries *CAL? and returns the stripped reply", source="upstream_code",
             ref=f"{UPSTREAM}:421-422"),
        Fact("disconnect attempts to close the VISA instrument and resource manager, suppresses close errors, "
             "then clears the stored connections", source="upstream_code",
             ref=f"{UPSTREAM}:239-251"),
        Fact("get_date queries DATE?", source="upstream_code", ref=f"{UPSTREAM}:427-428"),
        Fact("COMM_HEADER defaults to SHORT; OFF omits response headers and suppresses units",
             source="vendor_doc", ref=f"{MANUAL}:5063-5075"),
        Fact("The manual states the attenuation factors {1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 10000}",
             source="vendor_doc", ref=f"{MANUAL}:4527"),
        Fact("The manual states the coupling values {A1M, D1M, D50, GND}", source="vendor_doc",
             ref=f"{MANUAL}:4589"),
        Fact("The manual states the bandwidth-limit values {OFF, 20MHZ, 200MHZ, 500MHZ, 1GHZ, 2GHZ, 3GHZ, "
             "4GHZ, 6GHZ}", source="vendor_doc", ref=f"{MANUAL}:4544"),
        Fact("The manual states the trigger modes {AUTO, NORM, SINGLE, STOP}", source="vendor_doc",
             ref=f"{MANUAL}:4842"),
        Fact("The manual refers the timebase range to the product datasheet and gives no numeric TDIV bound",
             source="vendor_doc", ref=f"{MANUAL}:4744"),
        Fact("The manual says the offset range depends on the fixed sensitivity and refers to the product "
             "datasheet", source="vendor_doc", ref=f"{MANUAL}:4660"),
        Fact("The manual says an out-of-range trigger level is adjusted to the closest legal value and gives no "
             "numeric bound", source="vendor_doc", ref=f"{MANUAL}:4818"),
        Fact("The manual gives the trigger delay range as 0 to -10,000 times Time/div for negative delay and 0 "
             "to +10 times Time/div for positive delay", source="vendor_doc", ref=f"{MANUAL}:4792"),
        Fact("The manual says the trigger sources available depend on the oscilloscope model", source="vendor_doc",
             ref=f"{MANUAL}:4884"),
        Fact("The manual lists the trigger source mnemonics C1...Cn, LINE, EX, EX5, EX10 and ETM10",
             source="vendor_doc", ref=f"{MANUAL}:4914-4920"),
        Fact("The manual says *CAL? returns a diagnostic code where 0 means calibration successful and the "
             "example reply for no failure is '*CAL 0'", source="vendor_doc", ref=f"{MANUAL}:6376-6381"),
        Fact("The manual gives the PAVA response format <parameter>,<value>,<state>", source="vendor_doc",
             ref=f"{MANUAL}:5617"),
        Fact("The manual says MEMORY_SIZE accepts a numeric size or the listed forms and the oscilloscope adapts "
             "to the closest valid memory size", source="vendor_doc", ref=f"{MANUAL}:4643-4646"),
    ]
    safe_state = ("acquisition STOP sent and TRMD? read back as stopped; no external circuit or WaveSource "
                  "generator is stopped, and another client or the front panel can resume acquisition")

    def setup(self):
        # The manual's COMM_HEADER OFF suppresses both headers and units. The upstream query() passes
        # replies through unchanged, so the numeric reads require this explicit session configuration.
        self.native.write("CHDR OFF")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (*IDN?)")
    def identity(self):
        return _text(self.native.identify())

    @read("family", type="string", description="Model family from the detected profile")
    def family(self):
        return _text(self.native.get_capabilities()["family"])

    @read("channels", type="integer", unit="1", description="Analog input channels in the detected profile")
    def channels(self):
        return int(self.native.get_capabilities()["channels"])

    @read("bandwidth_mhz", unit="MHz", description="Analog bandwidth in MHz from the detected profile")
    def bandwidth_mhz(self):
        return float(self.native.get_capabilities()["bandwidth_mhz"])

    @read("date", type="string", description="Scope date and time (DATE?)")
    def date(self):
        return _text(self.native.get_date())

    @read("acquisition_status", type="string", description="Trigger mode and INR status (TRMD? and INR?)")
    def acquisition_status(self):
        return _text(self.native.get_acquisition_status())

    @read("stopped", type="boolean", description="True when headerless TRMD? reports exactly STOP")
    def stopped(self):
        mode = _setting_text(self.native.query("TRMD?")).upper()
        if mode not in TRIGGER_MODES:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"unexpected trigger-mode reply: {mode!r}")
        return mode == "STOP"

    @read("vdiv", unit="V", description="Channel 1 V/div")
    def vdiv(self):
        return _number(self.native.get_channel_info(CHANNEL)["vdiv"])

    @read("offset", unit="V", description="Channel 1 offset, V")
    def offset(self):
        return _number(self.native.get_channel_info(CHANNEL)["offset"])

    @read("coupling", type="string", description="Channel 1 coupling")
    def coupling(self):
        return _setting_text(self.native.get_channel_info(CHANNEL)["coupling"])

    @read("attenuation", unit="1", description="Probe attenuation")
    def attenuation(self):
        return _number(self.native.query("C1:ATTN?"))

    @read("tdiv", unit="s", description="Timebase, s/div")
    def tdiv(self):
        return _number(self.native.get_timebase_info()["tdiv"])

    @read("trigger_mode", type="string", description="Trigger mode (TRIG_MODE?)")
    def trigger_mode(self):
        return _setting_text(self.native.get_trigger_info()["mode"])

    @read("trigger_source", type="string", description="Edge-trigger source parsed from TRIG_SELECT?")
    def trigger_source(self):
        return _trigger_source(self.native.get_trigger_info()["select"])

    @read("trigger_level", unit="V", description="Channel 1 edge-trigger level in volts")
    def trigger_level(self):
        return _number(self.native.get_trigger_info()["c1_trig_level"])

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("vdiv", unit="V", description="Channel 1 V/div",
           limit=Limit.operator_required(
               "the manual refers the valid VOLT_DIV range to the product datasheet "
               "(resources/maui_text.txt:4985) and the clone states no range (oscilloscope.py:462-463); the "
               "operator must supply the scale envelope of the fitted probe"))
    def set_vdiv(self, value):
        self.native.set_vdiv(CHANNEL, float(value))
        return _number(self.native.get_channel_info(CHANNEL)["vdiv"])

    @write("offset", unit="V", description="Channel 1 offset, V",
           limit=Limit.operator_required(
               "the manual says the maximum offset depends on the fixed sensitivity "
               "(resources/maui_text.txt:4660) and the clone states no range; the operator must supply the "
               "offset window of this bench"))
    def set_offset(self, value):
        self.native.set_offset(CHANNEL, float(value))
        return _number(self.native.get_channel_info(CHANNEL)["offset"])

    @write("coupling", type="string", description="Channel 1 coupling",
           limit=Limit(allowed=COUPLINGS, source="vendor_doc", ref=f"{MANUAL}:4589"))
    def set_coupling(self, value):
        self.native.set_coupling(CHANNEL, str(value))
        return _setting_text(self.native.get_channel_info(CHANNEL)["coupling"])

    @write("attenuation", unit="1", description="Probe attenuation",
           limit=Limit(allowed=ATTENUATIONS, source="vendor_doc", ref=f"{MANUAL}:4527"))
    def set_attenuation(self, value):
        self.native.set_attenuation(CHANNEL, float(value))
        return _number(self.native.query("C1:ATTN?"))

    @write("tdiv", unit="s", description="Timebase, s/div",
           limit=Limit.operator_required(
               "the manual refers the timebase specifications to the product datasheet "
               "(resources/maui_text.txt:4744) and the clone states no range (oscilloscope.py:523-524); the "
               "operator must supply the timebase window of this bench"))
    def set_tdiv(self, value):
        self.native.set_tdiv(float(value))
        return _number(self.native.get_timebase_info()["tdiv"])

    @write("trigger_mode", type="string", description="Trigger mode",
           limit=Limit(allowed=TRIGGER_MODES, source="vendor_doc", ref=f"{MANUAL}:4842"))
    def set_trigger_mode(self, value):
        self.native.set_trigger_mode(str(value))
        return _setting_text(self.native.get_trigger_info()["mode"])

    @write("trigger_source", type="string", description="Trigger source",
           limit=Limit.operator_required(
               "the manual says the trigger sources available depend on the oscilloscope model "
               "(resources/maui_text.txt:4884) and lists C1...Cn, LINE, EX, EX5, EX10 and ETM10 "
               "(resources/maui_text.txt:4914-4920); the operator must name the sources fitted to this model"))
    def set_trigger_source(self, value):
        self.native.set_trigger_source(str(value))
        return _trigger_source(self.native.get_trigger_info()["select"])

    @write("trigger_level", unit="V", description="Trigger level, V",
           limit=Limit.operator_required(
               "the manual says an out-of-range trigger level is adjusted to the closest legal value "
               "(resources/maui_text.txt:4818) and states no numeric bound; the level range depends on the "
               "trigger source, so the operator must supply the window"))
    def set_trigger_level(self, value):
        self.native.set_trigger_level(CHANNEL, float(value))
        return _number(self.native.get_trigger_info()["c1_trig_level"])

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.lucasgerads.arm.v1", description="Arm the scope for one acquisition (ARM)",
            output={"armed": Field("boolean", description="True once the native ARM write returned")})
    def arm(self):
        self.native.arm()
        return {"armed": True}

    @action(name="x-cap.lucasgerads.force_trigger.v1",
            description="Force one acquisition (FRTR)",
            output={"forced": Field("boolean", description="True once the native FRTR write returned")})
    def force_trigger(self):
        self.native.force_trigger()
        return {"forced": True}

    @action(name="x-cap.lucasgerads.measure.v1",
            description="Read one PAVA scalar measurement from channel 1",
            input={"parameter": Field("string", description="PAVA measurement parameter",
                                      enum=PAVA_PARAMETERS)},
            output={"parameter": Field("string", description="The requested PAVA parameter"),
                    "reply": Field("string",
                                   description="The native PAVA reply in <parameter>,<value>,<state> form")})
    def measure(self, parameter):
        reply = _text(self.native.measure(CHANNEL, parameter))
        return {"parameter": parameter, "reply": reply}

    @action(cap="cap.device.calibrate.v1",
            description="Run the scope's internal self-calibration (*CAL?) and report its diagnostic code",
            input={"standard_ref": Field("string", max_length=512,
                                         description="Reference standard name required by the class; the "
                                                     "native *CAL? takes no reference"),
                   "targets": Field("array", max_items=64,
                                    description="Calibration targets required by the class; the native *CAL? "
                                                "calibrates the scope as a whole",
                                    items=Field("string", max_length=64, description="Target name")),
                   "notes": Field("string", max_length=1000,
                                  description="Free-text notes for the receipt; not sent to the scope")})
    def calibrate(self, standard_ref=None, targets=None, notes=None):
        reply = _text(self.native.calibrate())
        code = _calibration_code(reply)
        if code != 0:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"scope calibration failed with diagnostic {code}: {reply}")
        return {"calibrated": True, "calibration_ref": reply}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the upstream stop() writes STOP."""
        self.native.stop()
        if self.stopped() is not True:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the scope does not report STOP after the native stop")

    def teardown(self):
        self.native.disconnect()
