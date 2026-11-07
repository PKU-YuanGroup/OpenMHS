"""Siglent SDS2000X Plus oscilloscope through the pinned lxkang00/oscilloscope-mcp server.

The upstream is a single-file MCP server that wraps one raw SCPI socket in
``OscilloscopeConnection`` and publishes 34 tools from a ``TOOLS`` list.  Its tools are
dispatched by a generic ``call_tool`` (server.py:1327-1352), not registered as separate
``@<receiver>.tool()`` functions, so the finite McpClientDriver source proof cannot
describe this server.  This package therefore uses a direct Driver over the upstream
connection class, ``server:OscilloscopeConnection`` (server.py:99-225), and sends the
same SCPI commands that the pinned handlers send.

The fake backend is a local SCPI emulator.  It is not a recording and it is not the
upstream simulator: every number in fake.py is placeholder test data.  The hardware
factory in native.py refuses before importing the clone or opening a socket.  The raw
``send_command`` escape, the waveform array and the screenshot file are not bound.
"""
from __future__ import annotations

import re

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

OWNER = "lxkang00"
SOURCE = "server.py"
ANALOG_SOURCES = ["C1", "C2", "C3", "C4", "MATH", "F1", "F2", "F3", "F4"]
TRIGGER_SOURCES = (["C1", "C2", "C3", "C4", "EXT", "EXT/5", "LINE"]
                   + ["D" + str(index) for index in range(16)])
MEASUREMENTS = [
    "VPP", "VMAX", "VMIN", "VAMP", "VTOP", "VBASe", "VAVG", "VRMS",
    "OVSN", "FPREshoot", "PER", "FREQ", "RTIM", "FTIM",
    "PWIDth", "NWIDth", "DUTY", "NDUTY", "PDUTY",
    "WIDth", "RISE", "FALL", "DELay", "PHASe", "ALL",
    "AMP", "BASE", "CMEAN", "CRMS",
    "CYCLE_MEAN", "CYCLE_RMS", "CYCLE_STDDEV",
    "DELTA_DELAY", "DELTA_TCCJITTER", "DELTA_TCNJITTER",
    "DELTA_TIEJITTER", "DELTA_TPERIODJITTER",
    "DELTA_TSKEW", "DELTA_TTRIGLEVEL",
    "FOV", "FPOV", "HPO", "IREC", "ISEC",
    "LOW", "MAX", "MEAN", "MIN", "NCYC",
    "NOV", "NPO", "NSEC", "OVR", "PHA",
    "PKPK", "PPUL", "PREC", "PWID", "RPRE", "STDDEV",
]


def xcap(name):
    return "x-cap." + OWNER + "." + name + ".v1"


def operator_limit(field):
    """A numeric input the pinned tool schema does not bound; the site supplies one."""
    return Limit.operator_required(
        "The pinned tool schema states no finite range for " + field + "; the operator supplies it in site-limits.json.")


def text(description, **kwargs):
    return Field("string", description=description, **kwargs)


def number(description, unit="1", **kwargs):
    return Field("number", unit=unit, required=False, limit=operator_limit(description), description=description,
                 **kwargs)


def integer(description, unit="1", **kwargs):
    return Field("integer", unit=unit, required=False, limit=operator_limit(description), description=description,
                 **kwargs)


def choice(values, description, **kwargs):
    return Field("string", enum=values, description=description, **kwargs)


def reply_field():
    return Field("string", description="Complete text reply of the corresponding pinned handler.")


def out_text(description):
    return Field("string", description=description)


class SiglentSdsMcp(Driver):
    """Direct SCPI driver for the Siglent SDS2000X Plus MCP server's own transport class."""

    device_id = "siglent_sds"
    device_kind = "instrument"
    mode, risk = "hardware", "R0"
    native = "server:OscilloscopeConnection"
    backends = {"fake": ".fake:connect", "hardware": ".native:connect"}
    vendor = "Siglent"
    model = "SDS2000X Plus series"
    display_name = "Siglent SDS2000X Plus through lxkang00/oscilloscope-mcp (SCPI transport)"
    tags = ("oscilloscope", "scpi", "siglent", "mcp-server", "fake-only")
    safe_state = ("Acquisition stopped: :STOP is sent, then :TRIGger:STATus? must read STOP; the stop does not "
                  "abort an in-flight SCPI command or any operation started before it.")
    facts = [
        Fact("The pinned server is one MCP server script that controls a Siglent SDS2000X Plus over raw TCP SCPI "
             "on port 5024.", source="upstream_code", ref=SOURCE + ":1-9"),
        Fact("SCPI_PORT is 5024.", source="upstream_code", ref=SOURCE + ":47"),
        Fact("OscilloscopeConnection is a persistent TCP socket wrapper with connect, disconnect, send, query and "
             "safe_query.", source="upstream_code", ref=SOURCE + ":99-170"),
        Fact("send() appends a newline and reads a response when the command contains a question mark.",
             source="upstream_code", ref=SOURCE + ":148-157"),
        Fact("query() appends a question mark when the command does not end with one.",
             source="upstream_code", ref=SOURCE + ":159-163"),
        Fact("measure passes ':MEASure:<item>? <source>', which ends with the source and not with a question mark, "
             "to query().", source="upstream_code", ref=SOURCE + ":844"),
        Fact("get_id queries *IDN?.", source="upstream_code", ref=SOURCE + ":651-652"),
        Fact("run and stop send :RUN and :STOP; neither queries a stopped state.",
             source="upstream_code", ref=SOURCE + ":663-670"),
        Fact("reset sends *RST and sleeps for three seconds.", source="upstream_code", ref=SOURCE + ":655-658"),
        Fact("configure_channel writes display, invert, scale, offset, coupling, bandwidth limit, probe, skew, "
             "unit and label commands under :CHANnelN:.", source="upstream_code", ref=SOURCE + ":686-716"),
        Fact("get_channel queries eight channel settings; the pinned handler swallows each query error as N/A.",
             source="upstream_code", ref=SOURCE + ":719-732"),
        Fact("configure_timebase writes :TIMebase:SCALe, :DELay and :MODE, and get_timebase queries them.",
             source="upstream_code", ref=SOURCE + ":737-749"),
        Fact("configure_trigger writes sweep and type first and then source, level, slope and coupling under the "
             "selected trigger type; holdoff is written under :TRIGger:HOLDoff.",
             source="upstream_code", ref=SOURCE + ":754-785"),
        Fact("configure_acquisition writes mode, memory depth and interpolation under :ACQuire: and average count "
             "under :ACQuire:AVERage.", source="upstream_code", ref=SOURCE + ":809-819"),
        Fact("measure sends :MEASure:<item>? <sources>, or :MEASure:ALL? for the ALL item.",
             source="upstream_code", ref=SOURCE + ":834-846"),
        Fact("get_measure_stats queries count, mean, min, max and standard deviation.",
             source="upstream_code", ref=SOURCE + ":849-857"),
        Fact("get_waveform_preamble sends :WAVeform:SOURce and queries :WAVeform:PREamble?, parsing ten "
             "comma-separated fields.", source="upstream_code", ref=SOURCE + ":867-886"),
        Fact("get_waveform_data requests ASCII data and returns only a text summary with min, max, mean and the "
             "first and last ten values; it does not return the array.",
             source="upstream_code", ref=SOURCE + ":889-941"),
        Fact("get_screenshot writes a PNG to a local file and returns only a 200-character base64 prefix.",
             source="upstream_code", ref=SOURCE + ":943-1047"),
        Fact("configure_display, configure_cursors, get_cursor_values, configure_math and configure_digital write "
             "the corresponding :DISPlay, :CURSor, :MATH and :DIGital subsystems.",
             source="upstream_code", ref=SOURCE + ":1049-1150"),
        Fact("save_setup and recall_setup validate a 1-40 character filename and send :STORe:SETup or "
             ":RECAll:SETup with the resulting path.", source="upstream_code", ref=SOURCE + ":1160-1185"),
        Fact("get_frequency_counter queries :COUNter:CURRent?, :COUNter:MODE? and :COUNter:SOURce?.",
             source="upstream_code", ref=SOURCE + ":1188-1199"),
        Fact("get_status queries acquisition state, trigger state, *OPC? and *ESR?.",
             source="upstream_code", ref=SOURCE + ":1202-1210"),
        Fact("get_next_error queries :SYSTem:ERRor?.", source="upstream_code", ref=SOURCE + ":1212-1217"),
        Fact("list_tools returns TOOLS and call_tool dispatches HANDLERS by name; the tools are not separate "
             "decorated functions.", source="upstream_code", ref=SOURCE + ":1327-1352"),
        Fact("send_command passes the caller's command string unchanged to send(), an arbitrary SCPI escape.",
             source="upstream_code", ref=SOURCE + ":647-648"),
        Fact("The socket reader returns what it has read, possibly an empty string, when the reply times out.",
             source="upstream_code", ref=SOURCE + ":185-205"),
        Fact("_sanitize_label rejects semicolons and enforces at most 20 characters.",
             source="upstream_code", ref=SOURCE + ":64-71"),
        Fact("_validate_filename accepts only 1-40 letters, digits, spaces, hyphens and underscores.",
             source="upstream_code", ref=SOURCE + ":74-83"),
        Fact("The channel input schema declares minimum 1 and maximum 4.",
             source="upstream_code", ref=SOURCE + ":295"),
        Fact("The get_channel input schema declares minimum 1 and maximum 4.",
             source="upstream_code", ref=SOURCE + ":316"),
        Fact("The display intensity input schema declares minimum 0 and maximum 100.",
             source="upstream_code", ref=SOURCE + ":482"),
    ]

    # -- read-only resource state -------------------------------------------------
    @read("identity", type="string", description="Instrument identity returned by *IDN?.")
    def identity(self):
        return self.native.query("*IDN?")

    @read("trigger_status", type="string",
          description="Trigger state returned by :TRIGger:STATus?; a native failure fails the read (no N/A "
                      "fallback), and a reply that timed out is the empty string the pinned reader returns.")
    def trigger_status(self):
        return self.native.query(":TRIGger:STATus?")

    @read("acquisition_state", type="string",
          description="Acquisition state returned by :ACQuire:STATE?; a native failure fails the read (no N/A "
                      "fallback), and a reply that timed out is the empty string the pinned reader returns.")
    def acquisition_state(self):
        return self.native.query(":ACQuire:STATE?")

    # -- helpers ------------------------------------------------------------------
    @staticmethod
    def _sanitize_label(value):
        if ";" in value:
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION", "a channel label cannot contain ';'")
        sanitized = value.replace('"', "'").replace("\n", " ").replace("\r", "")
        if len(sanitized) > 20:
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION",
                               "a channel label is limited to 20 characters by the pinned handler")
        return sanitized or "CH"

    @staticmethod
    def _validate_filename(value):
        if not re.match(r"^[A-Za-z0-9 _-]{1,40}$", value):
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION",
                               "a setup filename is limited to 1-40 letters, digits, spaces, hyphens and underscores")
        return value

    @staticmethod
    def _setup_path(location, filename):
        name = SiglentSdsMcp._validate_filename(filename)
        if not name.endswith(".xml"):
            name += ".xml"
        if location == "USB":
            return "/usb0/" + name
        return "/SDS2000X+/internal/" + name

    def _apply(self, values, mapping, prefix):
        lines = []
        for key, scpi in mapping:
            value = values.get(key)
            if value is None:
                continue
            if isinstance(value, bool):
                value = "ON" if value else "OFF"
            self.native.send(prefix + scpi + " " + str(value))
            lines.append(key + ": " + str(values[key]))
        return lines

    @staticmethod
    def _summary(heading, lines):
        return heading + "\n" + "\n".join("  - " + line for line in lines)

    # -- acquisition control ------------------------------------------------------
    @action(name=xcap("acquisition_control"),
            input={"action": choice(["run", "stop", "autoset", "force_trigger", "clear_measure_stats", "reset"],
                                    "Acquisition control to send.", required=True)},
            output={"action": out_text("Control word sent."), "reply": reply_field()},
            description="Send one acquisition control: run, stop, autoset, force trigger, clear measurement "
                        "statistics or factory reset. The driver sends the same SCPI word the pinned handler sends.")
    def acquisition_control(self, action):
        if action == "run":
            self.native.send(":RUN")
            reply = "Acquisition running"
        elif action == "stop":
            self.native.send(":STOP")
            reply = "Acquisition stopped"
        elif action == "autoset":
            self.native.send(":AUToset")
            reply = "Auto-setup complete"
        elif action == "force_trigger":
            self.native.send("*TRG")
            reply = "Trigger forced"
        elif action == "clear_measure_stats":
            self.native.send(":MEASure:STATistics:RESet")
            reply = "Measurement statistics cleared"
        elif action == "reset":
            self.native.send("*RST")
            reply = "Oscilloscope reset complete (*RST). Reconnect if needed."
        else:  # the schema enum makes this unreachable
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION", "unknown acquisition control")
        return {"action": action, "reply": reply}

    # -- channel ------------------------------------------------------------------
    @action(name=xcap("configure_channel"),
            input={
                "channel": Field("integer", unit="1", description="Channel, 1-4.",
                                 limit=Limit(1, 4, source="upstream_code", ref=SOURCE + ":295")),
                "display": Field("boolean", required=False, description="Show channel."),
                "scale": number("Scale in V/div; site bound.", "V"),
                "offset": number("Offset in V; site bound.", "V"),
                "coupling": choice(["D1M", "A1M", "D50", "GND"], "Input coupling.", required=False),
                "bandwidth_limit": choice(["OFF", "20M", "200M", "350M"], "Bandwidth limit.", required=False),
                "probe": number("Probe ratio; site bound."),
                "invert": Field("boolean", required=False, description="Invert channel."),
                "label": Field("string", max_length=20, required=False,
                               description="Label, max 20 chars."),
                "unit": choice(["V", "A"], "Channel unit.", required=False),
                "skew": number("Deskew in s; site bound.", "s"),
            },
            output={"channel": Field("integer", unit="1", description="Configured channel."),
                    "reply": reply_field()},
            examples=[{"channel": 1, "display": True}],
            description="Set analog channel settings with the pinned :CHANnelN: commands; reply is the handler summary.")
    def configure_channel(self, channel, display=None, scale=None, offset=None, coupling=None,
                          bandwidth_limit=None, probe=None, invert=None, label=None, unit=None, skew=None):
        prefix = ":CHANnel" + str(channel) + ":"
        lines = []
        if display is not None:
            value = "ON" if display else "OFF"
            self.native.send(prefix + "SWITch " + value)
            lines.append("Display: " + value)
        if invert is not None:
            value = "ON" if invert else "OFF"
            self.native.send(prefix + "INVert " + value)
            lines.append("Invert: " + value)
        lines.extend(self._apply({"scale": scale, "offset": offset, "coupling": coupling,
                                 "bandwidth_limit": bandwidth_limit, "probe": probe, "skew": skew,
                                 "unit": unit},
                                [("scale", "SCALe"), ("offset", "OFFSet"), ("coupling", "COUPling"),
                                 ("bandwidth_limit", "BWLimit"), ("probe", "PROBe"), ("skew", "SKEW"),
                                 ("unit", "UNIT")], prefix))
        if label is not None:
            safe = self._sanitize_label(label)
            self.native.send(prefix + 'LABel:TEXT "' + safe + '"')
            self.native.send(prefix + "LABel ON")
            lines.append("label: " + safe)
        return {"channel": channel, "reply": self._summary("Channel " + str(channel) + " configured:", lines)}

    @action(name=xcap("get_channel"),
            input={"channel": Field("integer", unit="1", description="Analog channel, 1 through 4.",
                                    limit=Limit(1, 4, source="upstream_code", ref=SOURCE + ":316"))},
            output={"channel": Field("integer", unit="1", description="Queried channel."),
                    "reply": reply_field()},
            description="Read the eight settings the pinned get_channel handler reads. A native failure is reported "
                        "as a failed call instead of being hidden behind the handler's N/A fallback.")
    def get_channel(self, channel):
        prefix = ":CHANnel" + str(channel) + ":"
        properties = [
            ("Display", self.native.query(prefix + "SWITch?")),
            ("Scale (V/div)", self.native.query(prefix + "SCALe?")),
            ("Offset (V)", self.native.query(prefix + "OFFSet?")),
            ("Coupling", self.native.query(prefix + "COUPling?")),
            ("BW Limit", self.native.query(prefix + "BWLimit?")),
            ("Probe", self.native.query(prefix + "PROBe?")),
            ("Invert", self.native.query(prefix + "INVert?")),
            ("Unit", self.native.query(prefix + "UNIT?")),
        ]
        reply = "Channel " + str(channel) + ":\n" + "\n".join("  " + key + ": " + value for key, value in properties)
        return {"channel": channel, "reply": reply}

    # -- timebase -----------------------------------------------------------------
    @action(name=xcap("configure_timebase"),
            input={"scale": number("Time per division in seconds; the operator supplies the range.", "s"),
                   "delay": number("Horizontal delay in seconds; the operator supplies the range.", "s"),
                   "mode": choice(["MAIN", "WINDOW", "ROLL", "XY"], "Timebase mode.", required=False)},
            output={"reply": reply_field()},
            examples=[{"mode": "MAIN"}],
            description="Set main timebase scale, delay and mode under :TIMebase:.")
    def configure_timebase(self, scale=None, delay=None, mode=None):
        lines = self._apply({"scale": scale, "delay": delay, "mode": mode},
                            [("scale", "SCALe"), ("delay", "DELay"), ("mode", "MODE")], ":TIMebase:")
        return {"reply": self._summary("Timebase configured:", lines)}

    @action(name=xcap("get_timebase"), input={}, output={"reply": reply_field()},
            description="Read timebase scale, delay and mode.")
    def get_timebase(self):
        properties = [("Scale (s/div)", self.native.query(":TIMebase:SCALe?")),
                      ("Delay (s)", self.native.query(":TIMebase:DELay?")),
                      ("Mode", self.native.query(":TIMebase:MODE?"))]
        return {"reply": "Timebase:\n" + "\n".join("  " + key + ": " + value for key, value in properties)}

    # -- trigger ------------------------------------------------------------------
    @action(name=xcap("configure_trigger"),
            input={
                "mode": choice(["AUTO", "NORMal", "SINGle", "STOP"], "Trigger sweep mode.", required=False),
                "trigger_type": choice(["EDGE", "GLIT", "INTV", "DROP", "RUNT", "WIND", "PATT", "Qualified",
                                        "NthEdge", "SETUPHOLD", "VIDeo", "SERial"],
                                       "Trigger type.", required=False),
                "source": choice(TRIGGER_SOURCES, "Trigger source.", required=False),
                "level": number("Trigger level in volts; the operator supplies the range.", "V"),
                "slope": choice(["POSitive", "NEGative", "EITHer"], "Trigger slope.", required=False),
                "coupling": choice(["DC", "AC", "HFR", "LFR"], "Trigger coupling.", required=False),
                "holdoff": number("Trigger holdoff in seconds; the operator supplies the range.", "s"),
            },
            output={"reply": reply_field()},
            examples=[{"mode": "AUTO"}],
            description="Set trigger sweep, type, source, level, slope, coupling and holdoff in the pinned order.")
    def configure_trigger(self, mode=None, trigger_type=None, source=None, level=None, slope=None,
                          coupling=None, holdoff=None):
        lines = []
        if mode is not None:
            self.native.send(":TRIGger:SWEep " + str(mode))
            lines.append("Sweep: " + str(mode))
        trigger = trigger_type if trigger_type is not None else "EDGE"
        if trigger_type is not None:
            self.native.send(":TRIGger:TYPE " + str(trigger_type))
            lines.append("Type: " + str(trigger_type))
        for key, scpi in (("source", "SOURce"), ("level", "LEVel"), ("slope", "SLOPe"),
                          ("coupling", "COUPling")):
            value = {"source": source, "level": level, "slope": slope, "coupling": coupling}[key]
            if value is not None:
                self.native.send(":TRIGger:" + trigger + ":" + scpi + " " + str(value))
                lines.append(key + ": " + str(value))
        if holdoff is not None:
            self.native.send(":TRIGger:HOLDoff " + str(holdoff))
            lines.append("Holdoff: " + str(holdoff) + " s")
        return {"reply": self._summary("Trigger configured:", lines)}

    @action(name=xcap("get_trigger"), input={}, output={"reply": reply_field()},
            description="Read the current trigger type, sweep, source, level and slope.")
    def get_trigger(self):
        trigger = self.native.query(":TRIGger:TYPE?") or "EDGE"
        properties = [("Type", trigger),
                      ("Sweep", self.native.query(":TRIGger:SWEep?")),
                      ("Source", self.native.query(":TRIGger:" + trigger + ":SOURce?")),
                      ("Level", self.native.query(":TRIGger:" + trigger + ":LEVel?")),
                      ("Slope", self.native.query(":TRIGger:" + trigger + ":SLOPe?"))]
        return {"reply": "Trigger:\n" + "\n".join("  " + key + ": " + value for key, value in properties)}

    # -- acquisition settings -----------------------------------------------------
    @action(name=xcap("configure_acquisition"),
            input={
                "mode": choice(["NORMal", "PEAK", "AVERage", "ERES"], "Acquisition mode.", required=False),
                "memory_depth": choice(["10K", "100K", "1M", "10M", "25M", "50M", "100M", "200M"],
                                       "Memory depth.", required=False),
                "interpolation": choice(["LINEAR", "SINX"], "Interpolation.", required=False),
                "average_count": integer("Average count for AVERage mode; the operator supplies the range."),
            },
            output={"reply": reply_field()},
            examples=[{"mode": "NORMal"}],
            description="Set acquisition mode, memory depth, interpolation and average count under :ACQuire:.")
    def configure_acquisition(self, mode=None, memory_depth=None, interpolation=None, average_count=None):
        lines = self._apply({"mode": mode, "memory_depth": memory_depth, "interpolation": interpolation},
                            [("mode", "MODE"), ("memory_depth", "MDEPth"),
                             ("interpolation", "INTerpolation")], ":ACQuire:")
        if average_count is not None:
            self.native.send(":ACQuire:AVERage " + str(average_count))
            lines.append("average_count: " + str(average_count))
        return {"reply": self._summary("Acquisition configured:", lines)}

    @action(name=xcap("get_acquisition"), input={}, output={"reply": reply_field()},
            description="Read acquisition mode, memory depth, sample rate and interpolation.")
    def get_acquisition(self):
        properties = [("Mode", self.native.query(":ACQuire:MODE?")),
                      ("Memory Depth", self.native.query(":ACQuire:MDEPth?")),
                      ("Sample Rate", self.native.query(":ACQuire:SRATe?")),
                      ("Interpolation", self.native.query(":ACQuire:INTerpolation?"))]
        return {"reply": "Acquisition:\n" + "\n".join("  " + key + ": " + value for key, value in properties)}

    # -- measurement --------------------------------------------------------------
    @action(name=xcap("measure"),
            input={
                "measurement": choice(MEASUREMENTS, "Automatic measurement item.", required=True),
                "source1": choice(ANALOG_SOURCES, "Primary source; defaults to C1.", required=False),
                "source2": choice(ANALOG_SOURCES, "Secondary source for delay and phase items.", required=False),
            },
            output={"measurement": out_text("Measurement item sent."),
                    "source": out_text("Source expression sent."),
                    "value": Field("number", nullable=True,
                                   description="Parsed numeric value, or null when the reply is not numeric."),
                    "reply": reply_field()},
            description="Select and read one automatic measurement item. The reply is the pinned handler's text; "
                        "the numeric value is parsed from the same reply and is null when it is not a number.")
    def measure(self, measurement, source1=None, source2=None):
        primary = source1 if source1 is not None else "C1"
        if measurement == "ALL":
            result = self.native.query(":MEASure:ALL? " + primary)
            return {"measurement": measurement, "source": primary, "value": None,
                    "reply": "All measurements for " + primary + ":\n" + result}
        source = primary + "," + source2 if source2 is not None else primary
        raw = self.native.query(":MEASure:" + measurement + "? " + source)
        try:
            value = float(raw.strip())
        except ValueError:
            value = None
        return {"measurement": measurement, "source": source, "value": value,
                "reply": measurement + "(" + source + ") = " + raw}

    @action(name=xcap("get_measure_stats"), input={},
            output={"reply": reply_field()},
            description="Read count, mean, minimum, maximum and standard deviation of the measurement statistics.")
    def get_measure_stats(self):
        properties = [("Count", self.native.query(":MEASure:STATistics:COUNt?")),
                      ("Mean", self.native.query(":MEASure:STATistics:MEAN?")),
                      ("Min", self.native.query(":MEASure:STATistics:MIN?")),
                      ("Max", self.native.query(":MEASure:STATistics:MAX?")),
                      ("StdDev", self.native.query(":MEASure:STATistics:STDD?"))]
        return {"reply": "Measurement Statistics:\n" + "\n".join("  " + key + ": " + value
                                                                 for key, value in properties)}

    # -- waveform metadata --------------------------------------------------------
    @action(name=xcap("get_waveform_preamble"),
            input={"source": choice(ANALOG_SOURCES, "Waveform source.", required=True)},
            output={"source": out_text("Waveform source."),
                    "reply": reply_field(),
                    "parsed": Field("boolean", description="True when ten preamble fields were parsed."),
                    "format": text("Preamble format field.", required=False),
                    "type": text("Preamble type field.", required=False),
                    "points": Field("integer", unit="1", required=False, description="Preamble point count."),
                    "count": Field("integer", unit="1", required=False, description="Preamble returned count."),
                    "x_increment_s": Field("number", unit="s", required=False,
                                           description="Horizontal increment."),
                    "x_origin_s": Field("number", unit="s", required=False, description="Horizontal origin."),
                    "x_reference": Field("integer", unit="1", required=False,
                                         description="Horizontal reference index."),
                    "y_increment_v": Field("number", unit="V", required=False,
                                           description="Vertical increment."),
                    "y_origin_v": Field("number", unit="V", required=False, description="Vertical origin."),
                    "y_reference": Field("integer", unit="1", required=False,
                                         description="Vertical reference index.")},
            description="Read and parse the ten-field waveform preamble. The waveform sample array is not carried "
                        "by this binding.")
    def get_waveform_preamble(self, source):
        self.native.send(":WAVeform:SOURce " + source)
        preamble = self.native.query(":WAVeform:PREamble?").strip()
        parts = preamble.split(",")
        if len(parts) < 10:
            return {"source": source, "reply": "Raw preamble: " + preamble, "parsed": False}
        try:
            result = {"source": source,
                      "reply": "Waveform Preamble for " + source + ":\n"
                               + "  Format: " + parts[0] + "\n"
                               + "  Type: " + parts[1] + "\n"
                               + "  Points: " + parts[2] + "\n"
                               + "  Count: " + parts[3] + "\n"
                               + "  X Increment: " + parts[4] + " s\n"
                               + "  X Origin: " + parts[5] + " s\n"
                               + "  X Reference: " + parts[6] + "\n"
                               + "  Y Increment: " + parts[7] + " V\n"
                               + "  Y Origin: " + parts[8] + " V\n"
                               + "  Y Reference: " + parts[9],
                      "parsed": True, "format": parts[0], "type": parts[1],
                      "points": int(float(parts[2])), "count": int(float(parts[3])),
                      "x_increment_s": float(parts[4]), "x_origin_s": float(parts[5]),
                      "x_reference": int(float(parts[6])), "y_increment_v": float(parts[7]),
                      "y_origin_v": float(parts[8]), "y_reference": int(float(parts[9]))}
        except ValueError:
            return {"source": source, "reply": "Raw preamble: " + preamble, "parsed": False}
        return result

    # -- display and analysis -----------------------------------------------------
    @action(name=xcap("configure_display"),
            input={"grid": choice(["FULL", "HALF", "OFF"], "Display grid.", required=False),
                   "persistence": choice(["OFF", "0.5", "1", "5", "10", "INF"],
                                         "Persistence: off, seconds or infinite.", required=False),
                   "intensity": Field("integer", unit="1", required=False,
                                      limit=Limit(0, 100, source="upstream_code", ref=SOURCE + ":482"),
                                      description="Display brightness, 0 through 100."),
                   "grid_style": choice(["LINE", "DOT"], "Grid style.", required=False),
                   "axis_mode": choice(["FULL", "MINImum"], "Axis mode.", required=False)},
            output={"reply": reply_field()},
            examples=[{"grid": "FULL"}],
            description="Set display grid, persistence, intensity, grid style and axis mode.")
    def configure_display(self, grid=None, persistence=None, intensity=None, grid_style=None, axis_mode=None):
        lines = self._apply({"grid": grid, "persistence": persistence, "intensity": intensity,
                             "grid_style": grid_style},
                            [("grid", "GRIDstyle"), ("persistence", "PERSistence"),
                             ("intensity", "INTensity"), ("grid_style", "GRATicule")], ":DISPlay:")
        if axis_mode is not None:
            self.native.send(":DISPlay:AXIS:MODE " + str(axis_mode))
            lines.append("axis_mode: " + str(axis_mode))
        return {"reply": self._summary("Display configured:", lines)}

    @action(name=xcap("configure_cursors"),
            input={"mode": choice(["OFF", "MANual", "TRACk", "MEASure"], "Cursor mode.", required=False),
                   "source1": choice(ANALOG_SOURCES, "Primary cursor source.", required=False),
                   "source2": choice(ANALOG_SOURCES, "Secondary cursor source.", required=False),
                   "cursor_type": choice(["X", "Y", "XY"], "Manual cursor type.", required=False)},
            output={"reply": reply_field()},
            examples=[{"mode": "MANual"}],
            description="Set cursor mode, sources and manual cursor type.")
    def configure_cursors(self, mode=None, source1=None, source2=None, cursor_type=None):
        lines = self._apply({"mode": mode, "source1": source1, "source2": source2,
                             "cursor_type": cursor_type},
                            [("mode", "MODE"), ("source1", "SOURce1"), ("source2", "SOURce2"),
                             ("cursor_type", "TYPE")], ":CURSor:")
        return {"reply": self._summary("Cursors configured:", lines)}

    @action(name=xcap("get_cursor_values"), input={}, output={"reply": reply_field()},
            description="Read cursor mode and, when cursors are on, delta X and delta Y.")
    def get_cursor_values(self):
        mode = self.native.query(":CURSor:MODE?")
        if mode.strip().upper() == "OFF":
            return {"reply": "Cursors are OFF"}
        delta_x = self.native.query(":CURSor:XDELta?")
        delta_y = self.native.query(":CURSor:YDELta?")
        return {"reply": "Cursor Values (Mode: " + mode + "):\n  Delta X: " + delta_x
                         + "\n  Delta Y: " + delta_y}

    @action(name=xcap("configure_math"),
            input={"display": Field("boolean", required=False, description="Show or hide the math trace."),
                   "function": choice(["ADD", "SUB", "MULT", "DIV", "FFT", "DIFF", "INTG", "SQRT", "AVG",
                                       "ERES", "ABSS"], "Math function.", required=False),
                   "source1": choice(ANALOG_SOURCES, "First operand.", required=False),
                   "source2": choice(ANALOG_SOURCES, "Second operand for two-operand functions.", required=False),
                   "scale": number("Math vertical scale; the operator supplies the range.", "V"),
                   "offset": number("Math vertical offset; the operator supplies the range.", "V"),
                   "fft_window": choice(["RECT", "BLAC", "HANN", "HAMM", "FLAT", "KAIS"], "FFT window.",
                                        required=False),
                   "fft_scale": choice(["VRMS", "DBVRMS", "DBM"], "FFT scale.", required=False)},
            output={"reply": reply_field()},
            examples=[{"display": True}],
            description="Set math display, function, sources, scale, offset and FFT options.")
    def configure_math(self, display=None, function=None, source1=None, source2=None, scale=None,
                       offset=None, fft_window=None, fft_scale=None):
        lines = []
        if display is not None:
            value = "ON" if display else "OFF"
            self.native.send(":MATH:SWITch " + value)
            lines.append("display: " + str(display))
        lines.extend(self._apply({"function": function, "source1": source1, "source2": source2,
                                  "scale": scale, "offset": offset},
                                 [("function", "FUNCtion"), ("source1", "SOURce1"), ("source2", "SOURce2"),
                                  ("scale", "SCALe"), ("offset", "OFFSet")], ":MATH:"))
        if fft_window is not None:
            self.native.send(":MATH:FFT:WINDow " + str(fft_window))
            lines.append("fft_window: " + str(fft_window))
        if fft_scale is not None:
            self.native.send(":MATH:FFT:SCALe " + str(fft_scale))
            lines.append("fft_scale: " + str(fft_scale))
        return {"reply": self._summary("Math configured:", lines)}

    @action(name=xcap("configure_digital"),
            input={"display": Field("boolean", required=False, description="Show or hide the digital bus."),
                   "position": integer("Vertical screen position; the operator supplies the range."),
                   "height": integer("Digital channel display height; the operator supplies the range."),
                   "label": Field("string", max_length=20, required=False,
                                  description="Digital line to label, for example D0."),
                   "label_text": Field("string", max_length=20, required=False,
                                       description="Label text, at most 20 characters."),
                   "threshold": number("Logic threshold in volts; the operator supplies the range.", "V"),
                   "threshold_line": text("Digital line for the threshold, for example D0.", required=False)},
            output={"reply": reply_field()},
            examples=[{"display": True}],
            description="Set digital-bus display, position, height, label and threshold on MSO models.")
    def configure_digital(self, display=None, position=None, height=None, label=None, label_text=None,
                          threshold=None, threshold_line=None):
        lines = []
        if display is not None:
            value = "ON" if display else "OFF"
            self.native.send(":DIGital:DISPlay " + value)
            lines.append("display: " + str(display))
        if position is not None:
            self.native.send(":DIGital:POSition " + str(position))
            lines.append("position: " + str(position))
        if height is not None:
            self.native.send(":DIGital:HEIGht " + str(height))
            lines.append("height: " + str(height))
        if label is not None and label_text is not None:
            safe_label = self._sanitize_label(label)
            safe_text = self._sanitize_label(label_text)
            self.native.send(":DIGital:LABel " + safe_label + ',"' + safe_text + '"')
            lines.append("label " + safe_label + ": " + safe_text)
        if threshold is not None and threshold_line is not None:
            self.native.send(":DIGital:THReshold " + str(threshold_line) + "," + str(threshold))
            lines.append("threshold " + str(threshold_line) + ": " + str(threshold) + "V")
        return {"reply": self._summary("Digital channels configured:", lines)}

    # -- setup storage ------------------------------------------------------------
    @action(name=xcap("save_setup"),
            input={"location": choice(["INTERNAL", "USB"], "Storage location; defaults to INTERNAL.",
                                      required=False),
                   "filename": Field("string", max_length=40, required=False,
                                     pattern=r"^[A-Za-z0-9 _-]{1,40}$",
                                     description="Setup filename without a path; defaults to SETUP.")},
            output={"location": out_text("Storage location."), "path": out_text("SCPI path written."),
                    "reply": reply_field()},
            description="Save the current setup to internal memory or USB with the pinned filename validation.")
    def save_setup(self, location=None, filename=None):
        where = location if location is not None else "INTERNAL"
        path = self._setup_path(where, filename if filename is not None else "SETUP")
        self.native.send(':STORe:SETup "' + path + '"')
        return {"location": where, "path": path, "reply": "Setup saved to " + path}

    @action(name=xcap("recall_setup"),
            input={"location": choice(["INTERNAL", "USB"], "Storage location; defaults to INTERNAL.",
                                      required=False),
                   "filename": Field("string", max_length=40, required=False,
                                     pattern=r"^[A-Za-z0-9 _-]{1,40}$",
                                     description="Setup filename without a path; defaults to SETUP.")},
            output={"location": out_text("Storage location."), "path": out_text("SCPI path recalled."),
                    "reply": reply_field()},
            description="Recall a saved setup from internal memory or USB with the pinned filename validation.")
    def recall_setup(self, location=None, filename=None):
        where = location if location is not None else "INTERNAL"
        path = self._setup_path(where, filename if filename is not None else "SETUP")
        self.native.send(':RECAll:SETup "' + path + '"')
        return {"location": where, "path": path, "reply": "Setup recalled from " + path}

    # -- counter, status and errors ----------------------------------------------
    @action(name=xcap("get_frequency_counter"), input={},
            output={"mode": out_text("Counter mode."), "source": out_text("Counter source."),
                    "frequency_hz": Field("number", unit="Hz", nullable=True,
                                          description="Parsed frequency, or null when the reply is not numeric."),
                    "reply": reply_field()},
            description="Read the hardware frequency counter mode, source and current frequency.")
    def get_frequency_counter(self):
        frequency = self.native.query(":COUNter:CURRent?")
        mode = self.native.query(":COUNter:MODE?")
        source = self.native.query(":COUNter:SOURce?")
        try:
            value = float(frequency.strip())
        except ValueError:
            value = None
        return {"mode": mode, "source": source, "frequency_hz": value,
                "reply": "Frequency Counter:\n  Mode: " + mode + "\n  Source: " + source
                         + "\n  Frequency: " + frequency + " Hz"}

    @action(name=xcap("get_status"), input={}, output={"reply": reply_field()},
            description="Read acquisition state, trigger state, operation complete and event status register.")
    def get_status(self):
        properties = [("Acquisition State", self.native.query(":ACQuire:STATE?")),
                      ("Trigger State", self.native.query(":TRIGger:STATus?")),
                      ("Operation Complete", self.native.query("*OPC?")),
                      ("Event Status Register", self.native.query("*ESR?"))]
        return {"reply": "Oscilloscope Status:\n" + "\n".join("  " + key + ": " + value
                                                              for key, value in properties)}

    @action(name=xcap("get_next_error"), input={}, output={"reply": reply_field()},
            description="Read and clear the next device error-queue entry.")
    def get_next_error(self):
        error = self.native.query(":SYSTem:ERRor?")
        return {"reply": "Error: " + error}

    # -- stop path ----------------------------------------------------------------
    @estop
    def stop_acquisition(self, reason=None):
        """Send :STOP and require a fresh trigger status of STOP; no other work is aborted."""
        self.native.send(":STOP")
        status = self.native.query(":TRIGger:STATus?").strip().upper()
        if status != "STOP":
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               ":STOP was sent but the fresh trigger status is " + repr(status),
                               native_code=status)
