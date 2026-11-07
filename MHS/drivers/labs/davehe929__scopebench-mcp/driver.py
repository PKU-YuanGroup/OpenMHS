"""OpenMHS driver for gh.davehe929/scopebench-mcp: a RIGOL DHO800/DHO900 SCPI oscilloscope (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands are the raw SCPI commands of the
upstream package (``src/scopebench_mcp/drivers/rigol_dho.py``); the package opens the instrument through its own
transport classes (``src/scopebench_mcp/transports/tcp.py`` and ``visa.py``), which this driver does not import:
the bridge opens the instrument itself (``host``/``port`` or a VISA resource, options of the hardware backend), so
only the commands are shared.

* reads: the acquisition state and the CH1 settings, and instrument-side scalar measurements of CH1 (frequency,
  period, Vpp, Vrms and mean voltage);
* writes: the CH1 coupling (AC/DC/GND) and, bounded by the operating site, the CH1 vertical scale and offset, the
  edge-trigger level and the timebase scale and offset.  The clone states no range for the numeric settings: it says
  the valid ranges depend on the active volts/div setting, the main timebase and the RUN/STOP state, so they are
  ``Limit.operator_required`` and ``site-limits.example.json`` shows the overlay;
* one action, ``x-cap.davehe929.scope_measure.v1``, reads one instrument-side measurement of one analog channel;
* the e-stop writes ``:STOP``: the scope stops acquiring, and this driver sets no instrument output.

The waveform, screenshot and statistics arrays are not carried by this driver (see RESULT.json).  Every Limit and
Fact cites a line of the clone at the pinned commit (3f0abc87a2839e816744a7d867c1ef06ed721f7a).  This package is
model-authored and unreviewed, and its wire syntax has not been tried on an instrument (README.md).
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

UPSTREAM_FILE = "src/scopebench_mcp/drivers/rigol_dho.py"

#: The measurement names of the clone's table (rigol_dho.py:519-536) and the SCPI item each one selects.
MEASUREMENT_ITEMS = {
    "frequency": "FREQuency",
    "freq": "FREQuency",
    "period": "PERiod",
    "vpp": "VPP",
    "vmax": "VMAX",
    "max": "VMAX",
    "vmin": "VMIN",
    "min": "VMIN",
    "mean": "VAVG",
    "average": "VAVG",
    "rms": "VRMS",
    "duty": "PDUTy",
    "positive_duty": "PDUTy",
    "negative_duty": "NDUTy",
    "rise_time": "RTIMe",
    "fall_time": "FTIMe",
}

#: The coupling tokens of the clone's map (rigol_dho.py:1149-1154).
COUPLINGS = ["AC", "DC", "GND"]


class RigolDho(ScpiDriver):
    device_id = "dho804d"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "scopebench_mcp.transports.tcp:TCPTransport"
    backends = {"fake": ".fake:FakeDhoTransport"}
    vendor, model = "RIGOL Technologies", "DHO800/DHO900 series oscilloscope"
    display_name = "RIGOL DHO800/DHO900 oscilloscope"
    tags = ["oscilloscope", "rigol", "dho800", "dho804d", "scpi"]
    #: The clone's raw TCP transport defaults to port 5555 and the LAN row of the compatibility matrix uses it.
    port = 5555
    #: The identity of the verified unit (README.md:185); the serial and firmware vary per instrument.
    idn = {"expect": "^RIGOL TECHNOLOGIES,DHO"}
    #: The clone reads the instrument error queue after a configuration write (rigol_dho.py:62-75).
    error_query = ":SYSTem:ERRor?"

    facts = [
        Fact("The project targets the RIGOL DHO800/DHO900 SCPI oscilloscope family and was verified on a DHO804D",
             source="vendor_doc", ref="README.md:15-17"),
        Fact("The DHO804D identity reply is 'RIGOL TECHNOLOGIES,DHO804D,<serial>,<firmware>'",
             source="vendor_doc", ref="README.md:185"),
        Fact("Raw LAN SCPI is reachable on port 5555; port 5025 did not accept connections on the tested DHO804D",
             source="vendor_doc", ref="docs/compatibility_matrix.md:6"),
        Fact("The instrument is identified with *IDN?", source="upstream_code", ref=f"{UPSTREAM_FILE}:36-37"),
        Fact("The error queue is read with ':SYSTem:ERRor?'; a reply that starts with 0 or '+0', or contains "
             "'No error', means no error", source="upstream_code", ref=f"{UPSTREAM_FILE}:62-75"),
        Fact("The acquisition state is queried with ':TRIGger:STATus?'", source="upstream_code", ref=f"{UPSTREAM_FILE}:20"),
        Fact("An analog channel's display, scale and offset are read with ':CHANnel<n>:DISPlay?', "
             "':CHANnel<n>:SCALe?' and ':CHANnel<n>:OFFSet?', and the coupling with "
             "':CHANnel<n>:COUPling?'",
             source="upstream_code", ref=f"{UPSTREAM_FILE}:40-51"),
        Fact("The timebase scale and offset are read with ':TIMebase:MAIN:SCALe?' and ':TIMebase:MAIN:OFFSet?'",
             source="upstream_code", ref=f"{UPSTREAM_FILE}:25-26"),
        Fact("The edge-trigger level is read with ':TRIGger:EDGE:LEVel?'", source="upstream_code",
             ref=f"{UPSTREAM_FILE}:24"),
        Fact("Channel settings are written as ':CHANnel<n>:COUPling <value>', ':CHANnel<n>:SCALe <value>' and "
             "':CHANnel<n>:OFFSet <value>'", source="upstream_code", ref=f"{UPSTREAM_FILE}:118-131"),
        Fact("The timebase is written as ':TIMebase:MAIN:SCALe <value>' and ':TIMebase:MAIN:OFFSet <value>'",
             source="upstream_code", ref=f"{UPSTREAM_FILE}:143-150"),
        Fact("The edge-trigger level is written as ':TRIGger:EDGE:LEVel <value>'", source="upstream_code",
             ref=f"{UPSTREAM_FILE}:174-186"),
        Fact("The coupling accepts AC, DC and GND (the map also accepts the alias GROUND)", source="upstream_code",
             ref=f"{UPSTREAM_FILE}:1149-1154"),
        Fact("The acquisition is controlled with ':RUN', ':STOP' and ':SINGle'", source="upstream_code",
             ref=f"{UPSTREAM_FILE}:1193-1199"),
        Fact("A measurement is queried with ':MEASure:ITEM? <item>,CHANnel<n>'", source="upstream_code",
             ref=f"{UPSTREAM_FILE}:596"),
        Fact("The measurement names select the SCPI items FREQuency, PERiod, VPP, VMAX, VMIN, VAVG, VRMS, PDUTy, "
             "NDUTy, RTIMe and FTIMe", source="upstream_code", ref=f"{UPSTREAM_FILE}:519-536"),
        Fact("The analog channels are numbered 1 to 4", source="upstream_code", ref=f"{UPSTREAM_FILE}:1240-1241"),
        Fact("Valid vertical and horizontal offset ranges depend on the active volts/div setting, the main timebase "
             "and the RUN/STOP state, so they must not be hard-coded", source="vendor_doc",
             ref="docs/development_plan.md:148-151"),
        Fact("The device readback is authoritative because valid ranges depend on scale and acquisition state",
             source="vendor_doc", ref="README.md:294-296"),
        Fact("The clone's raw TCP transport defaults to port 5555", source="upstream_code",
             ref="src/scopebench_mcp/transports/tcp.py:18"),
    ]

    safe_state = "acquisition stopped (:STOP); this driver sets no instrument output"

    parameters = {
        "trigger_status": Field("string",
                                description="Acquisition state reported by ':TRIGger:STATus?' (for example RUN or "
                                            "STOP)"),
        "channel_coupling": Field("string", writable=True,
                                  description="CH1 coupling: AC, DC or GND",
                                  limit=Limit(allowed=COUPLINGS, source="upstream_code",
                                              ref=f"{UPSTREAM_FILE}:1149-1154")),
        "channel_scale": Field("number", unit="V", writable=True,
                               description="CH1 vertical scale in volts per division",
                               limit=Limit.operator_required(
                                   "no text of the clone states the volts/div range of the instrument; "
                                   "docs/development_plan.md:148-150 says the vertical limits depend on the active "
                                   "volts/div setting, so the operating site sets the range of its unit")),
        "channel_offset": Field("number", unit="V", writable=True,
                                description="CH1 vertical offset",
                                limit=Limit.operator_required(
                                    "no text of the clone states a vertical offset range; "
                                    "docs/development_plan.md:148-150 says it depends on the active volts/div "
                                    "setting, so the operating site sets the range of its unit")),
        "trigger_level": Field("number", unit="V", writable=True,
                               description="Edge-trigger level of the trigger channel",
                               limit=Limit.operator_required(
                                   "no text of the clone states a trigger level range; "
                                   "docs/development_plan.md:148-151 and README.md:294-296 say valid ranges depend "
                                   "on scale and acquisition state, so the operating site sets the range of its "
                                   "unit")),
        "timebase_scale": Field("number", unit="s", writable=True,
                                description="Main timebase scale in seconds per division",
                                limit=Limit.operator_required(
                                    "no text of the clone states the seconds/div range; "
                                    "docs/development_plan.md:148-150 says the horizontal limits depend on the main "
                                    "timebase and RUN/STOP state, so the operating site sets the range of its unit")),
        "timebase_offset": Field("number", unit="s", writable=True,
                                 description="Main timebase offset",
                                 limit=Limit.operator_required(
                                     "no text of the clone states a horizontal offset range; "
                                     "docs/development_plan.md:148-150 says it depends on the main timebase and "
                                     "RUN/STOP state, so the operating site sets the range of its unit")),
        "frequency": Field("number", unit="Hz",
                           description="Instrument-side frequency measurement of CH1"),
        "period": Field("number", unit="s",
                        description="Instrument-side period measurement of CH1"),
        "vpp": Field("number", unit="V",
                     description="Instrument-side peak-to-peak voltage measurement of CH1"),
        "vrms": Field("number", unit="V",
                      description="Instrument-side RMS voltage measurement of CH1"),
        "mean": Field("number", unit="V",
                      description="Instrument-side mean voltage measurement of CH1"),
    }

    reads = {
        "trigger_status": {"query": ":TRIGger:STATus?", "parse": {"kind": "str"}},
        "channel_coupling": {"query": ":CHANnel1:COUPling?", "parse": {"kind": "str"}},
        "channel_scale": {"query": ":CHANnel1:SCALe?", "parse": {"kind": "float"}},
        "channel_offset": {"query": ":CHANnel1:OFFSet?", "parse": {"kind": "float"}},
        "trigger_level": {"query": ":TRIGger:EDGE:LEVel?", "parse": {"kind": "float"}},
        "timebase_scale": {"query": ":TIMebase:MAIN:SCALe?", "parse": {"kind": "float"}},
        "timebase_offset": {"query": ":TIMebase:MAIN:OFFSet?", "parse": {"kind": "float"}},
        "frequency": {"query": ":MEASure:ITEM? FREQuency,CHANnel1", "parse": {"kind": "float"}},
        "period": {"query": ":MEASure:ITEM? PERiod,CHANnel1", "parse": {"kind": "float"}},
        "vpp": {"query": ":MEASure:ITEM? VPP,CHANnel1", "parse": {"kind": "float"}},
        "vrms": {"query": ":MEASure:ITEM? VRMS,CHANnel1", "parse": {"kind": "float"}},
        "mean": {"query": ":MEASure:ITEM? VAVG,CHANnel1", "parse": {"kind": "float"}},
    }

    writes = {
        "channel_coupling": {"write": ":CHANnel1:COUPling {value}", "type": "string"},
        "channel_scale": {"write": ":CHANnel1:SCALe {value:g}", "type": "number"},
        "channel_offset": {"write": ":CHANnel1:OFFSet {value:g}", "type": "number"},
        "trigger_level": {"write": ":TRIGger:EDGE:LEVel {value:g}", "type": "number"},
        "timebase_scale": {"write": ":TIMebase:MAIN:SCALe {value:g}", "type": "number"},
        "timebase_offset": {"write": ":TIMebase:MAIN:OFFSet {value:g}", "type": "number"},
    }

    commands = {
        "x-cap.davehe929.scope_measure.v1": {
            "query": ":MEASure:ITEM? {measurement},CHANnel{channel}",
            "args": {
                "measurement": {"from": "input.measurement", "type": "string", "enum_map": MEASUREMENT_ITEMS},
                "channel": {"from": "input.channel", "type": "integer"},
            },
            "parse": {"kind": "float"},
            "result": {"map": {"value": "output.$"}},
            "description": "Read one instrument-side measurement of one analog channel",
        },
    }

    actions = {
        "x-cap.davehe929.scope_measure.v1": Action(
            name="measure",
            description="Read one instrument-side scalar measurement of one analog channel",
            input={
                "channel": Field("integer", unit="1",
                                 description="Analog channel number (1 to 4)",
                                 limit=Limit(min=1, max=4, source="upstream_code",
                                             ref=f"{UPSTREAM_FILE}:1240-1241")),
                "measurement": Field("string",
                                     description="Measurement name from the clone's table (frequency, period, vpp, "
                                                 "vmax, vmin, mean, rms, duty, positive_duty, negative_duty, "
                                                 "rise_time, fall_time and their short aliases)",
                                     limit=Limit(allowed=sorted(MEASUREMENT_ITEMS), source="upstream_code",
                                                 ref=f"{UPSTREAM_FILE}:519-536")),
            },
            output={
                "value": Field("number",
                               description="Measured value in the unit of the selected item (Hz, s, V or a ratio)"),
            },
        ),
    }

    safety_bindings = {"estop": {"write": ":STOP", "description": "stop the acquisition"}}
