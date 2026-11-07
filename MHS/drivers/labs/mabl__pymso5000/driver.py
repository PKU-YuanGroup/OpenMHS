"""OpenMHS driver for gh.mabl/pymso5000: a Rigol MSO5000-series oscilloscope over VISA SCPI.

A direct Driver over the upstream high-level ``pymso5000.scope:Scope`` class.  The card proposes a ``ScpiDriver``
(family ``scpi``, decision ``family-config``), but the upstream interface is an object with methods, not a table of
fixed command lines: every command carries a channel number and typed arguments, setters read the instrument back
and return the adjustments, and the measurement request is a typed object (``scope.py:565-603``, ``619-734``,
``738-793``).  So this package is a direct Driver over the upstream class with a ``native.py`` factory
(DEVIATION FROM THE CARD, recorded in RESULT.json).

* the served resource is analog channel 1 of the oscilloscope; its vertical settings and the shared timebase and
  acquisition settings are read and written;
* reads: identity, run state, acquisition type, average count, sample rate, memory depth, the channel-1 display,
  scale, offset, coupling, probe ratio and bandwidth limit, and the timebase mode, scale and offset;
* writes: acquisition type and memory depth, channel-1 scale and offset, and the timebase scale and offset.  The
  four vertical/timebase span and position writes are ``Limit.operator_required`` because the programming guide
  states their ranges only as a function of the probe ratio, the vertical scale, the model or the timebase mode;
* the ``x-cap.mabl.scope_channel_input.v1`` action sets the channel-1 display, coupling, probe ratio and bandwidth
  filter, which are kept out of the standard configure tool so that each MCP tool stays within its size bound;
* the measurement action runs one scalar ``MEASure:ITEM?`` query through the documented ``Scope.execute`` escape
  hatch, so waveform arrays are not carried;
* the e-stop writes STOP through the native ``Scope.stop``: the acquisition is halted and the frozen display is
  this instrument's safe state.

Every Limit and Fact cites a line of the clone at the pinned commit (48ebacc0317ada6d6f54a58ab03916c5d5a44e80).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SCOPE = "src/pymso5000/scope.py"
PARAMETERS = "src/pymso5000/parameters.py"
MEASURE = "src/pymso5000/api/measure.py"
MEASUREMENT_MODELS = "src/pymso5000/api/measurement_models.py"
GUIDE = "src/pymso5000/data/mso5000_commands.json"
CHANNEL_XML = "src/pymso5000/data/scpi_mso5000/CHANnel1.xml"

#: The analog channel this package serves; the class accepts channels 1 to 4 (parameters.py:5).
CHANNEL = 1

#: The acquisition types the upstream class accepts (parameters.py:60).
ACQUISITION_TYPES = ["NORMal", "AVERages", "PEAK", "HRESolution"]

#: The memory depths the upstream class accepts as settable spellings (parameters.py:85).
MEMORY_DEPTHS = ["AUTO", "1k", "10k", "100k", "1M", "10M", "25M", "50M", "100M", "200M"]

#: The input couplings the upstream class accepts (parameters.py:8).
COUPLINGS = ["DC", "AC", "GND"]

#: The explicit bandwidth filters the upstream class accepts (parameters.py:153-173).
BANDWIDTH_LIMITS = [
    "OFF", "20M", "25M", "50M", "70M", "100M", "150M", "200M", "250M", "300M", "350M", "500M", "600M",
    "1G", "2G", "4G", "5G", "10G", "20G",
]

#: The probe ratios the firmware definition accepts for a channel (CHANnel1.xml:827-885).
PROBE_RATIOS = [
    0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0,
    50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0, 20000.0, 50000.0,
]

#: The waveform measurement items of a single-source measurement (measurement_models.py:54-87).
MEASURE_ITEMS = [
    "VMAX", "VMIN", "VPP", "VTOP", "VBASe", "VAMP", "VAVG", "VRMS", "VUPPer", "VMID", "VLOWer", "VARiance",
    "PVRMs", "OVERshoot", "PREShoot", "MARea", "MPARea", "PERiod", "FREQuency", "RTIMe", "FTIMe", "PWIDth",
    "NWIDth", "PDUTy", "NDUTy", "TVMax", "TVMin", "PSLewrate", "NSLewrate", "PPULses", "NPULses", "PEDGes",
    "NEDGes",
]

#: The analog sources a waveform measurement can name (measurement_models.py:108-117).
MEASURE_SOURCES = ["CHANnel1", "CHANnel2", "CHANnel3", "CHANnel4"]


class MSO5000Scope(Driver):
    device_id = "mso5000"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "pymso5000.scope:Scope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScope"}
    vendor = "RIGOL Technologies"
    model = "MSO5000 series oscilloscope"
    display_name = "RIGOL MSO5000 series oscilloscope (pymso5000.Scope)"
    tags = ["oscilloscope", "scpi", "visa", "mso5000", "mso5074", "pymso5000"]
    facts = [
        Fact("The clone is a Python library and MCP server for controlling Rigol MSO5000 series oscilloscopes "
             "over VISA", source="vendor_doc", ref="README.md:3-4"),
        Fact("Scope is the high-level API and Scope.connect opens any message-based VISA resource name using "
             "the bundled SCPI definitions", source="upstream_code", ref=f"{SCOPE}:189-224"),
        Fact("info returns the *IDN? reply split into vendor, model, serial and firmware fields",
             source="upstream_code", ref=f"{SCOPE}:293-307"),
        Fact("run writes RUN, stop writes STOP and trigger_status reads TRIGger:STATus? (STOP, WAIT, TD, AUTO, "
             "RUN)", source="upstream_code", ref=f"{SCOPE}:311-329"),
        Fact("get_acquisition reads the run state and the ACQuire TYPE, AVERages, SRATe and MDEPth queries",
             source="upstream_code", ref=f"{SCOPE}:389-423"),
        Fact("set_acquisition writes ACQuire:TYPE, ACQuire:AVERages and ACQuire:MDEPth, then reads the state back",
             source="upstream_code", ref=f"{SCOPE}:477-489"),
        Fact("set_acquisition refuses acquisition writes while the acquisition is stopped, because the "
             "instrument would accept and ignore them", source="upstream_code", ref=f"{SCOPE}:524-542"),
        Fact("The acquisition types are NORMal, AVERages, PEAK and HRESolution",
             source="upstream_code", ref=f"{PARAMETERS}:60"),
        Fact("The average count is a power of two from 2 to 65536",
             source="upstream_code", ref=f"{PARAMETERS}:63-65"),
        Fact("The settable memory depths are AUTO, 1k, 10k, 100k, 1M, 10M, 25M, 50M, 100M and 200M",
             source="upstream_code", ref=f"{PARAMETERS}:85"),
        Fact("get_channel reads DISPlay, SCALe, OFFSet, UNITs, COUPling, PROBe and BWLimit of one analog channel",
             source="upstream_code", ref=f"{SCOPE}:565-603"),
        Fact("set_channel writes the channel settings and returns the read-back state with the requested values "
             "it disagrees with", source="upstream_code", ref=f"{SCOPE}:693-734"),
        Fact("The channel input couplings are DC, AC and GND", source="upstream_code", ref=f"{PARAMETERS}:8"),
        Fact("The explicit bandwidth filters are OFF, 20M to 600M, and 1G to 20G",
             source="upstream_code", ref=f"{PARAMETERS}:153-173"),
        Fact("The channel probe ratios accepted by the firmware definition run from 0.0001 to 50000",
             source="upstream_code", ref=f"{CHANNEL_XML}:827-885"),
        Fact("get_timebase reads TIMebase:MODE?, TIMebase:MAIN:SCALe? and TIMebase:MAIN:OFFSet?",
             source="upstream_code", ref=f"{SCOPE}:738-746"),
        Fact("set_timebase writes TIMebase:MAIN:SCALe and TIMebase:MAIN:OFFSet and returns the read-back "
             "adjustments", source="upstream_code", ref=f"{SCOPE}:783-792"),
        Fact("Scope.execute validates a command and its arguments and returns the parsed reply of a query",
             source="upstream_code", ref=f"{SCOPE}:932-946"),
        Fact("MEASure:ITEM? is the immediate measurement query of one item and source; each query also "
             "registers the item on the ten-slot measurement list", source="upstream_code",
             ref=f"{MEASURE}:811-820"),
        Fact("The single-source waveform measurement items run from VMAX to NEDGes",
             source="upstream_code", ref=f"{MEASUREMENT_MODELS}:54-87"),
        Fact("The programming guide gives the channel scale range as 500 uV/div to 10 V/div for a 1X probe",
             source="vendor_doc", ref=f"{GUIDE}:3627"),
        Fact("The programming guide gives the channel scale range as 10 mV/div to 100 V/div for a 10X probe",
             source="vendor_doc", ref=f"{GUIDE}:9692"),
        Fact("The programming guide gives the channel offset range in three vertical-scale bands, from +/-1 V "
             "to +/-100 V", source="vendor_doc", ref=f"{GUIDE}:3546"),
        Fact("The programming guide gives the main timebase scale in YT mode per model, from 1 ns to 1000 s "
             "for the MSO5354 and 5 ns to 1000 s for the MSO5072/MSO5074",
             source="vendor_doc", ref=f"{GUIDE}:13005"),
        Fact("The programming guide leaves the timebase offset range to remarks that depend on the timebase "
             "mode and the operating status", source="vendor_doc", ref=f"{GUIDE}:12968"),
    ]
    safe_state = "acquisition stopped (STOP); the frozen display is left as it is"

    def setup(self):
        """Require a four-field *IDN? reply before the driver serves the instrument (scope.py:296-299)."""
        identity = self.native.info().idn
        if len([item for item in identity.split(",") if item.strip()]) != 4:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"expected the four-field Rigol *IDN? reply, got {identity!r}")

    def teardown(self):
        self.native.close()

    # -- reads -------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Identity string of the oscilloscope (the *IDN? reply)")
    def identity(self):
        return self.native.info().idn

    @read("trigger_status", type="string",
          description="Acquisition run state: STOP, WAIT, TD, AUTO or RUN")
    def trigger_status(self):
        return self.native.trigger_status()

    @read("acquisition_type", type="string",
          description="How the scope builds each displayed sample: NORMal, AVERages, PEAK or HRESolution")
    def acquisition_type(self):
        return self.native.get_acquisition().acquisition_type

    @read("average_count", type="integer",
          description="Number of acquisitions averaged in AVERages mode (a power of two from 2 to 65536)")
    def average_count(self):
        return self.native.get_acquisition().averages

    @read("sample_rate", unit="Hz", description="Sample rate of the acquisition in samples per second")
    def sample_rate(self):
        return self.native.get_acquisition().sample_rate_sa_s

    @read("memory_depth_points", type="integer",
          description="Acquisition memory depth in points as the instrument reports it")
    def memory_depth_points(self):
        return self.native.get_acquisition().memory_depth_points

    @read("channel1_enabled", type="boolean", description="True while analog channel 1 is displayed")
    def channel1_enabled(self):
        return self.native.get_channel(CHANNEL).enabled

    @read("channel1_scale_per_div", unit="V",
          description="Vertical scale of channel 1 in volts per division (the value is V/div)")
    def channel1_scale_per_div(self):
        return self.native.get_channel(CHANNEL).scale_per_div

    @read("channel1_offset", unit="V", description="Vertical offset of channel 1 in volts")
    def channel1_offset(self):
        return self.native.get_channel(CHANNEL).offset

    @read("channel1_coupling", type="string", description="Input coupling of channel 1: DC, AC or GND")
    def channel1_coupling(self):
        return self.native.get_channel(CHANNEL).coupling

    @read("channel1_probe_ratio", unit="1", description="Probe attenuation factor of channel 1")
    def channel1_probe_ratio(self):
        return self.native.get_channel(CHANNEL).probe_ratio

    @read("channel1_bandwidth_limit", type="string",
          description="Bandwidth filter of channel 1: OFF, 20M to 600M, or 1G to 20G")
    def channel1_bandwidth_limit(self):
        return self.native.get_channel(CHANNEL).bandwidth_limit

    @read("timebase_mode", type="string", description="Horizontal timebase mode as the instrument reports it")
    def timebase_mode(self):
        return self.native.get_timebase().mode

    @read("timebase_scale_s_per_div", unit="s",
          description="Horizontal scale in seconds per division (the value is s/div)")
    def timebase_scale_s_per_div(self):
        return self.native.get_timebase().scale_s_per_div

    @read("timebase_offset_s", unit="s", description="Horizontal position offset in seconds")
    def timebase_offset_s(self):
        return self.native.get_timebase().offset_s

    # -- writes ------------------------------------------------------------------------------------------------
    @write("acquisition_type", type="string",
           description="Sample construction mode",
           limit=Limit(allowed=ACQUISITION_TYPES, source="upstream_code", ref=f"{PARAMETERS}:60",
                       reason="setter domain"))
    def set_acquisition_type(self, value):
        state = self.native.set_acquisition(acquisition_type=value)
        return state.acquisition_type

    @write("memory_depth", type="string",
           description="Memory depth spelling",
           limit=Limit(allowed=MEMORY_DEPTHS, source="upstream_code", ref=f"{PARAMETERS}:85",
                       reason="setter domain; the query reports points"))
    def set_memory_depth(self, value):
        self.native.set_acquisition(memory_depth=value)
        return value

    @write("channel1_scale_per_div", unit="V",
           description="Channel 1 vertical scale (V/div)",
           limit=Limit.operator_required(
               "range depends on probe ratio (mso5000_commands.json:3627, 9692)"))
    def set_channel1_scale_per_div(self, value):
        outcome = self.native.set_channel(CHANNEL, scale_per_div=value)
        self._require_applied(outcome, "scale_per_div", value)
        return outcome.state.scale_per_div

    @write("channel1_offset", unit="V", description="Channel 1 vertical offset",
           limit=Limit.operator_required(
               "range depends on vertical scale (mso5000_commands.json:3546)"))
    def set_channel1_offset(self, value):
        outcome = self.native.set_channel(CHANNEL, offset=value)
        self._require_applied(outcome, "offset", value)
        return outcome.state.offset

    @write("timebase_scale_s_per_div", unit="s",
           description="Timebase scale (s/div)",
           limit=Limit.operator_required(
               "range depends on model and mode (mso5000_commands.json:13005)"))
    def set_timebase_scale_s_per_div(self, value):
        outcome = self.native.set_timebase(scale_s_per_div=value)
        self._require_applied(outcome, "scale_s_per_div", value)
        return outcome.state.scale_s_per_div

    @write("timebase_offset_s", unit="s", description="Timebase position offset",
           limit=Limit.operator_required(
               "range depends on mode and status (mso5000_commands.json:12968)"))
    def set_timebase_offset_s(self, value):
        outcome = self.native.set_timebase(offset_s=value)
        self._require_applied(outcome, "offset_s", value)
        return outcome.state.offset_s

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.mabl.scope_run.v1", description="Start continuous acquisition (the native RUN command)",
            output={"trigger_status": Field("string", description="Run state read back after RUN")})
    def run(self):
        self.native.run()
        return {"trigger_status": self.native.trigger_status()}

    @action(name="x-cap.mabl.scope_measure.v1",
            description="Read one scalar automatic measurement item from one analog channel",
            input={
                "item": Field("string", description="Measurement item, for example VPP, FREQuency or PDUTy",
                              enum=MEASURE_ITEMS),
                "source": Field("string", description="Analog channel the measurement reads",
                                enum=MEASURE_SOURCES),
            },
            output={"value": Field("number", description="Measured value in the instrument's unit for the item")})
    def measure(self, item="VPP", source="CHANnel1"):
        raw = self.native.execute("MEASure:ITEM?", [item, source])
        if raw is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the scope returned no {item} measurement for {source}")
        return {"value": float(raw)}

    @action(name="x-cap.mabl.scope_channel_input.v1",
            description="Set the analog channel 1 display and input conditioning",
            input={
                "channel1_enabled": Field("boolean", description="Display channel 1"),
                "channel1_coupling": Field("string", description="Channel 1 input coupling: DC, AC or GND",
                                           limit=Limit(allowed=COUPLINGS, source="upstream_code",
                                                       ref=f"{PARAMETERS}:8", reason="setter domain")),
                "channel1_probe_ratio": Field("number", unit="1",
                                              description="Channel 1 probe attenuation factor",
                                              limit=Limit(allowed=PROBE_RATIOS, source="upstream_code",
                                                          ref=f"{CHANNEL_XML}:827-885",
                                                          reason="firmware input enum")),
                "channel1_bandwidth_limit": Field("string", description="Channel 1 bandwidth filter",
                                                  limit=Limit(allowed=BANDWIDTH_LIMITS,
                                                              source="upstream_code",
                                                              ref=f"{PARAMETERS}:153-173",
                                                              reason="setter domain; ON is not explicit")),
            },
            output={
                "channel1_enabled": Field("boolean", description="Channel 1 display state after the write"),
                "channel1_coupling": Field("string", description="Channel 1 coupling after the write"),
                "channel1_probe_ratio": Field("number", unit="1",
                                              description="Channel 1 probe ratio after the write"),
                "channel1_bandwidth_limit": Field("string", description="Channel 1 bandwidth filter after the write"),
            })
    def configure_channel_input(self, channel1_enabled=None, channel1_coupling=None,
                                channel1_probe_ratio=None, channel1_bandwidth_limit=None):
        updates = {}
        if channel1_enabled is not None:
            updates["enabled"] = bool(channel1_enabled)
        if channel1_coupling is not None:
            updates["coupling"] = channel1_coupling
        if channel1_probe_ratio is not None:
            updates["probe_ratio"] = channel1_probe_ratio
        if channel1_bandwidth_limit is not None:
            updates["bandwidth_limit"] = channel1_bandwidth_limit
        outcome = self.native.set_channel(CHANNEL, **updates)
        for name, value in updates.items():
            self._require_applied(outcome, name, value)
        state = outcome.state
        return {
            "channel1_enabled": state.enabled,
            "channel1_coupling": state.coupling,
            "channel1_probe_ratio": state.probe_ratio,
            "channel1_bandwidth_limit": state.bandwidth_limit,
        }

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Halt the acquisition (native STOP): the frozen display is the safe state of this instrument."""
        self.native.stop()

    # -- helpers ------------------------------------------------------------------------------------------------
    @staticmethod
    def _require_applied(outcome, name, requested):
        """Refuse a write the instrument did not apply instead of reporting a silent clamp as success."""
        for adjustment in outcome.adjustments:
            if adjustment.field == name:
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    f"the scope did not apply {name}={requested!r}: it reports {adjustment.actual!r}")
