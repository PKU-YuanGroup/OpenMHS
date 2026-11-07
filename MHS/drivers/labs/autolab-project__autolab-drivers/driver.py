"""OpenMHS driver for gh.autolab-project/autolab-drivers: an Anritsu MS2830A spectrum analyzer over VISA.

A direct Driver (decorated methods) over the upstream connection class
anritsu_MS2830A.anritsu_MS2830A:Driver_VISA (anritsu_MS2830A/anritsu_MS2830A.py:138).  The class opens a pyvisa
resource itself and talks SCPI through it (anritsu_MS2830A/anritsu_MS2830A.py:138-153); its base Driver class holds
the identification, marker-power and timeout methods, and its Frequency module holds the sweep-window settings
(anritsu_MS2830A/anritsu_MS2830A.py:19-24 and 158-240).

* reads: the *IDN? identification, the three marker powers in dBm, the sweep window (start, stop, span and center in
  GHz; the center step in Hz, as the driver model declares it), the sweep-point count, and the pyvisa controller
  timeout in seconds;
* writes: the same sweep settings, the point count and the timeout.  No text file of the clone states a range for
  any of them: the manuals of the supported models are PDFs under anritsu_MS2830A/, and the code only gives the
  pyvisa constructor's own 3000 ms timeout default (anritsu_MS2830A/anritsu_MS2830A.py:144).  Every numeric write is
  therefore ``Limit.operator_required``: it is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range
  of its analyser (``site-limits.example.json`` shows the overlay);
* the native stop is ``INIT:CONT OFF`` through the upstream ``write`` (the first command of the upstream
  ``single_sweep``, anritsu_MS2830A/anritsu_MS2830A.py:52-59): it stops a repeating sweep.

What this package does not expose: the trace itself.  ``frequency_array`` and ``power_array`` build a DataFrame from
the whole trace (``TRAC? TRAC1``, anritsu_MS2830A/anritsu_MS2830A.py:74-92); this package carries the scalar marker
powers and the sweep settings, and reports no measurement-array value.

Every Fact cites a line of the clone at the pinned commit (4b44dfba7444d1e8e8b5fd895fa304fa550ce882).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on an analyser.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

#: The upstream module that holds Driver_VISA, the base Driver and the Frequency module.
MS2830A = "anritsu_MS2830A/anritsu_MS2830A.py"

#: Why the four sweep-window settings need the site's range (see site-limits.example.json).
FREQUENCY_REASON = (
    "no line of the clone states the frequency range of an MS2830A: the class exposes the sweep window in GHz but "
    "gives no band, and the manuals under anritsu_MS2830A/ are PDFs; the site states the range of its analyser")
#: Why the center-frequency step needs the site's range.
STEP_REASON = (
    "no line of the clone states a range for the center-frequency step: the setter writes the bare value in the "
    "instrument's default unit (anritsu_MS2830A/anritsu_MS2830A.py:182-187); the site states the step range it uses")
#: Why the sweep-point count needs the site's range.
POINTS_REASON = (
    "no line of the clone states a sweep-point range or a default for the analyser: the model only declares the "
    "count as an int (anritsu_MS2830A/anritsu_MS2830A.py:238-240); the site states the count its sweeps need")
#: Why the timeout needs the site's range.
TIMEOUT_REASON = (
    "the 3000 ms timeout in Driver_VISA.__init__ is the pyvisa controller default, not a bound of the analyser "
    "(anritsu_MS2830A/anritsu_MS2830A.py:144); the site states the timeout its measurements need")


class AnritsuMS2830A(Driver):
    device_id = "anritsu-ms2830a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "anritsu_MS2830A.anritsu_MS2830A:Driver_VISA"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMS2830A"}
    vendor, model = "Anritsu", "MS2830A spectrum analyzer"
    display_name = "Anritsu MS2830A spectrum analyzer (autolab Driver_VISA)"
    tags = ["spectrum-analyzer", "esa", "scpi", "visa", "rf"]
    facts = [
        Fact("Driver_VISA is the pyvisa connection class: it opens the VISA resource named by address, stores it in "
             "self.controller and sets the controller timeout to 3000 ms", source="upstream_code",
             ref=f"{MS2830A}:138-146"),
        Fact("The driver forces the SCPI language, selects spectrum mode and sets the ASCII trace format, then "
             "builds the Frequency module", source="upstream_code", ref=f"{MS2830A}:19-24"),
        Fact("get_id queries *IDN? and returns the answer", source="upstream_code", ref=f"{MS2830A}:31-32"),
        Fact("get_power_marker queries CALC:MARK<n>:Y? as a float; get_power_marker_1, _2 and _3 select marker 1, "
             "2 and 3", source="upstream_code", ref=f"{MS2830A}:35-46"),
        Fact("The driver model publishes power1, power2 and power3 in dBm", source="upstream_code",
             ref=f"{MS2830A}:102-112"),
        Fact("get_timeout and set_timeout read and write the pyvisa controller timeout", source="upstream_code",
             ref=f"{MS2830A}:62-67"),
        Fact("The driver model publishes timeout in seconds", source="upstream_code", ref=f"{MS2830A}:131-133"),
        Fact("get_frequency_start queries FREQ:STARt? and returns GHz (multiplied by 1e-9); set_frequency_start "
             "writes FREQ:STAR <value>GHZ", source="upstream_code", ref=f"{MS2830A}:166-171"),
        Fact("get_frequency_stop queries FREQ:STOP? and returns GHz; set_frequency_stop writes FREQ:STOP "
             "<value>GHZ", source="upstream_code", ref=f"{MS2830A}:174-179"),
        Fact("get_frequency_step queries FREQ:CENT:STEP? and set_frequency_step writes the bare value without a unit "
             "suffix or conversion", source="upstream_code", ref=f"{MS2830A}:182-187"),
        Fact("The driver model declares step with unit Hz and its help text says GHz, so the raw query value is "
             "published as Hz", source="upstream_code", ref=f"{MS2830A}:226-228"),
        Fact("get_frequency_span queries FREQ:SPAN? and returns GHz; set_frequency_span writes FREQ:SPAN "
             "<value>GHZ", source="upstream_code", ref=f"{MS2830A}:190-195"),
        Fact("get_frequency_center queries FREQ:CENT? and returns GHz; set_frequency_center writes FREQ:CENT "
             "<value>GHZ and then waits for *OPC?", source="upstream_code", ref=f"{MS2830A}:198-204"),
        Fact("get_points queries :SENS:SWEep:POINts? and set_points writes SENS:SWEep:POINts with a whole number",
             source="upstream_code", ref=f"{MS2830A}:207-212"),
        Fact("The driver model declares points as an int", source="upstream_code", ref=f"{MS2830A}:238-240"),
        Fact("repeat_sweep writes INIT:CONT ON; single_sweep writes INIT:CONT OFF, then INIT:MODE:SING and *OPC?",
             source="upstream_code", ref=f"{MS2830A}:49-59"),
        Fact("The trace is built from frequency_array (start, stop and points) and power_array (TRAC? TRAC1) as a "
             "DataFrame with frequency(GHz) and power columns", source="upstream_code", ref=f"{MS2830A}:74-92"),
    ]
    safe_state = "repeating sweep off (INIT:CONT OFF): the analyser takes no new automatic sweep"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identification", type="string", description="Identification string returned by *IDN?")
    def identification(self):
        return str(self.native.get_id())

    @read("power_marker_1", unit="dBm", description="Power at marker 1")
    def power_marker_1(self):
        return float(self.native.get_power_marker_1())

    @read("power_marker_2", unit="dBm", description="Power at marker 2")
    def power_marker_2(self):
        return float(self.native.get_power_marker_2())

    @read("power_marker_3", unit="dBm", description="Power at marker 3")
    def power_marker_3(self):
        return float(self.native.get_power_marker_3())

    @read("frequency_start", unit="GHz", description="Start frequency of the sweep window")
    def frequency_start(self):
        return float(self.native.frequency.get_frequency_start())

    @read("frequency_stop", unit="GHz", description="Stop frequency of the sweep window")
    def frequency_stop(self):
        return float(self.native.frequency.get_frequency_stop())

    @read("frequency_span", unit="GHz", description="Span of the sweep window")
    def frequency_span(self):
        return float(self.native.frequency.get_frequency_span())

    @read("frequency_center", unit="GHz", description="Center frequency of the sweep window")
    def frequency_center(self):
        return float(self.native.frequency.get_frequency_center())

    @read("frequency_step", unit="Hz", description="Center-frequency step, published in Hz as the driver model says")
    def frequency_step(self):
        return float(self.native.frequency.get_frequency_step())

    @read("sweep_points", type="integer", unit="1", description="Number of points of a sweep")
    def sweep_points(self):
        return int(self.native.frequency.get_points())

    @read("timeout", unit="s", description="Timeout of the pyvisa controller")
    def timeout(self):
        return float(self.native.get_timeout())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("frequency_start", unit="GHz", description="Start frequency of the sweep window",
           limit=Limit.operator_required(FREQUENCY_REASON))
    def set_frequency_start(self, value):
        self.native.frequency.set_frequency_start(value)
        return float(self.native.frequency.get_frequency_start())

    @write("frequency_stop", unit="GHz", description="Stop frequency of the sweep window",
           limit=Limit.operator_required(FREQUENCY_REASON))
    def set_frequency_stop(self, value):
        self.native.frequency.set_frequency_stop(value)
        return float(self.native.frequency.get_frequency_stop())

    @write("frequency_span", unit="GHz", description="Span of the sweep window",
           limit=Limit.operator_required(FREQUENCY_REASON))
    def set_frequency_span(self, value):
        self.native.frequency.set_frequency_span(value)
        return float(self.native.frequency.get_frequency_span())

    @write("frequency_center", unit="GHz", description="Center frequency of the sweep window",
           limit=Limit.operator_required(FREQUENCY_REASON))
    def set_frequency_center(self, value):
        self.native.frequency.set_frequency_center(value)
        return float(self.native.frequency.get_frequency_center())

    @write("frequency_step", unit="Hz", description="Center-frequency step, written in Hz",
           limit=Limit.operator_required(STEP_REASON))
    def set_frequency_step(self, value):
        self.native.frequency.set_frequency_step(value)
        return float(self.native.frequency.get_frequency_step())

    @write("sweep_points", type="integer", unit="1", description="Number of points of a sweep",
           limit=Limit.operator_required(POINTS_REASON))
    def set_sweep_points(self, value):
        self.native.frequency.set_points(value)
        return int(self.native.frequency.get_points())

    @write("timeout", unit="s", description="Timeout of the pyvisa controller",
           limit=Limit.operator_required(TIMEOUT_REASON))
    def set_timeout(self, value):
        self.native.set_timeout(value)
        return float(self.native.get_timeout())

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="write")
    def stop(self):
        """The native stop: the runtime latches first, then sends INIT:CONT OFF through the upstream write."""
        self.native.write("INIT:CONT OFF")
