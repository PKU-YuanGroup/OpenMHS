"""OpenMHS driver for gh.kitour/rigol-mho98-mcp: a RIGOL MHO98 oscilloscope over SCPI.

The card proposes the ScpiDriver family, but the pinned upstream is a PyVISA session object
(``rigol_mcp.mho98.session:Session``) whose waveform path also reads IEEE-488.2 definite-length
binary blocks and whose commands are assembled from parts (``:CURsor:MANual:CAX <seconds>``).
A command table cannot express the binary read, so this package is a direct Driver over the
upstream session class (DEVIATION FROM THE CARD); the fake implements only the public surface of
``Session`` and the driver sends the same SCPI text the pinned feature modules send.

* reads: identity, session health, the first queued SCPI error, the main timebase, the CH1
  vertical settings, and the current waveform transfer selector;
* writes: the main timebase scale/offset, the CH1 scale/offset, the waveform source/mode/format;
* actions: acquire the current waveform (the primary output), read and set the manual cursors,
  and run/stop the acquisition, with the stop also declared as the safe-state action;
* the e-stop writes ``:STOP``, the acquisition stop the upstream acquisition module sends.

The waveform arrays are carried by the extension action ``x-cap.kitour.acquire_waveform.v1``
because no catalogue class binds the ``instrument`` resource kind for a waveform array.  Every
Limit and Fact cites a line of the clone at commit 22fc52291dee96b01e75c0e6549c3175d1d5ec35.
This package is model-authored and unreviewed; it is checked on the fake backend only and no
hardware run is claimed.
"""

from __future__ import annotations

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SESSION = "src/rigol_mcp/mho98/session.py"
WAVEFORM = "src/rigol_mcp/mho98/waveform.py"
CURSOR = "src/rigol_mcp/mho98/cursor.py"
TIMEBASE = "src/rigol_mcp/mho98/timebase.py"
CHANNEL = "src/rigol_mcp/mho98/channel.py"
ACQUIRE = "src/rigol_mcp/mho98/acquire.py"
REFERENCE = "src/rigol_mcp/mho98/reference.py"
SEARCH = "src/rigol_mcp/mho98/search.py"
README = "README_MHO98.md"
SCOPE = "src/rigol_mcp/scope.py"

INLINE_MAX_POINTS = 100000  # upstream waveform.py:25; a transfer ceiling, not an instrument range

#: Waveform sources the pinned selector accepts (waveform.py:19).
SOURCES = ("CHAN1", "CHAN2", "CHAN3", "CHAN4", "MATH1", "MATH2", "MATH3", "MATH4")
#: Waveform modes the pinned selector accepts (waveform.py:20).
MODES = ("NORM", "MAX", "RAW")
#: Waveform formats this driver can carry; WORD needs caller-declared encoding (waveform.py:21, 115-185).
FORMATS = ("ASC", "BYTE")

#: The numeric settings below are validated only as finite (and positive for a scale) by the clone;
#: the clone states no instrument range.  The operator supplies the range at deployment.
_NOT_STATED = ("the clone validates only that the value is finite (and positive for a scale) but states no "
               "instrument range (timebase.py:175, channel.py:177-183, cursor.py:298); the site supplies the bound")


def _number(text: str, field: str) -> float:
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        raise DriverFailed("MHS.DEVICE.FAULTED", f"MHO98 returned a non-numeric {field}: {text!r}") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise DriverFailed("MHS.DEVICE.FAULTED", f"MHO98 returned a non-finite {field}: {text!r}")
    return value


def _integer(text: str, field: str) -> int:
    value = _number(text, field)
    if not value.is_integer():
        raise DriverFailed("MHS.DEVICE.FAULTED", f"MHO98 returned a non-integer {field}: {text!r}")
    return int(value)


def _token(value: str, allowed: tuple[str, ...], field: str) -> str:
    token = str(value).strip().upper()
    if field in ("waveform source", "cursor source"):
        token = token.replace(" ", "")
        if token.startswith("CHANNEL"):
            token = "CHAN" + token[7:]
        elif token.startswith("CH") and not token.startswith("CHAN"):
            token = "CHAN" + token[2:]
    elif field == "waveform mode":
        token = {"NORMAL": "NORM", "MAXIMUM": "MAX"}.get(token, token)
    elif field == "waveform format" and token == "ASCII":
        token = "ASC"
    if token not in allowed:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"MHO98 returned an unknown {field}: {value!r}")
    return token


class RigolMho98(Driver):
    device_id = "rigol-mho98"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "rigol_mcp.mho98.session:Session"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSession"}
    vendor, model = "RIGOL Technologies", "MHO98"
    display_name = "RIGOL MHO98 oscilloscope"
    tags = ["oscilloscope", "rigol", "mho98", "scpi", "waveform", "instrument"]
    facts = [
        Fact("Session is an MHO98 instrument session; production sessions open it lazily on first I/O",
             source="upstream_code", ref=f"{SESSION}:75-80"),
        Fact("A Session accepts an identity only when its second comma-separated field is MHO98",
             source="upstream_code", ref=f"{SESSION}:70-72"),
        Fact("idn() sends *IDN? and refuses an identity that is not MHO98, closing the transport",
             source="upstream_code", ref=f"{SESSION}:324-338"),
        Fact("query() runs exactly the requested text query; write() sends one command without a readback",
             source="upstream_code", ref=f"{SESSION}:357-374"),
        Fact("binary_query() returns one validated IEEE-488.2 definite-length payload, and write_binary() "
             "uploads one bounded binary block", source="upstream_code", ref=f"{SESSION}:623-663"),
        Fact("is_healthy is false after a transport fault or close", source="upstream_code",
             ref=f"{SESSION}:141-144"),
        Fact("query_error() drains :SYSTem:ERRor? and returns the first non-zero response", source="upstream_code",
             ref=f"{SESSION}:342-354"),
        Fact("The waveform selector accepts CHAN1-CHAN4 and MATH1-MATH4, modes NORM/MAX/RAW and formats "
             "WORD/BYTE/ASC", source="upstream_code", ref=f"{WAVEFORM}:19-21"),
        Fact("The waveform module declares ceilings of 1000 NORM points, 500000000 memory points "
             "and 100000 inline points", source="upstream_code",
             ref=f"{WAVEFORM}:23-25"),
        Fact("get_waveform defaults to source CH1, start 1, 1000 points, mode NORM and format ASC",
             source="upstream_code", ref=f"{WAVEFORM}:445-452"),
        Fact("The waveform preamble has ten comma-separated fields and is rejected unless it has exactly ten",
             source="upstream_code", ref=f"{WAVEFORM}:187-215"),
        Fact("The waveform preamble format code must match the transfer format: BYTE 0, WORD 1, ASC 2",
             source="upstream_code", ref=f"{WAVEFORM}:217-222"),
        Fact("BYTE samples convert as (sample - yorigin - yreference) * yincrement",
             source="upstream_code", ref=f"{WAVEFORM}:249-253"),
        Fact("Waveform times are xorigin + (start - 1 + index - xreference) * xincrement",
             source="upstream_code", ref=f"{WAVEFORM}:293-297"),
        Fact("The pinned cursor state reads :CURSor:MODE? and the manual cursor A/B X screen positions with "
             ":CURSor:MANual:CAX? and :CURSor:MANual:CBX?", source="upstream_code", ref=f"{CURSOR}:147-176"),
        Fact("set_cursor sends :CURSor:MODE, :CURSor:MANual:TYPE, :CURSor:MANual:SOURce and the CAX/CBX "
             "positions for explicitly requested manual fields", source="upstream_code",
             ref=f"{CURSOR}:336-359"),
        Fact("The main timebase scale is read with :TIMebase:MAIN:SCALe? and written as :TIMebase:MAIN:SCALe",
             source="upstream_code", ref=f"{TIMEBASE}:96-212"),
        Fact("The main timebase scale must be positive; the clone states no maximum", source="upstream_code",
             ref=f"{TIMEBASE}:175"),
        Fact("CH1 scale and offset are read with :CHANnel1:SCALe? and :CHANnel1:OFFSet? and written under the "
             "same prefix", source="upstream_code", ref=f"{CHANNEL}:142-309"),
        Fact("The channel scale bound depends on the input impedance and the probe ratio, which this driver does "
             "not read, so the clone does not state one fixed range", source="upstream_code",
             ref=f"{CHANNEL}:160-175"),
        Fact("acquisition_control maps RUN to :RUN, STOP to :STOP, SINGLE to :SINGle and FORCE to :TFORce",
             source="upstream_code", ref=f"{ACQUIRE}:236-254"),
        Fact("The upstream scope stop helper writes :STOP, rejects a queued SCPI error and reads "
             ":TRIGger:STATus?", source="upstream_code", ref=f"{SCOPE}:366-371"),
        Fact("The main-offset validator treats trigger status STOP as the stopped case",
             source="upstream_code", ref=f"{TIMEBASE}:132-137"),
        Fact("Acquisition averages are 2 through 65536 and must be a power of two", source="upstream_code",
             ref=f"{ACQUIRE}:28-110"),
        Fact("Reference waveform slots are 1 through 10", source="upstream_code", ref=f"{REFERENCE}:18-64"),
        Fact("Search event requests are limited to 1000 events", source="upstream_code", ref=f"{SEARCH}:19-316"),
        Fact("The upstream README prints the MHO98 identity as RIGOL TECHNOLOGIES,MHO98,MHO9A274501253,...",
             source="vendor_doc", ref=f"{README}:220"),
    ]
    safe_state = ("acquisition reports STOP on :TRIGger:STATus? after :STOP and an empty SCPI error queue; "
                  "this is a single acquisition-state readback, and this driver sets no instrument output")

    # -- state reads ---------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identification returned by *IDN?")
    def read_identity(self):
        return self.native.idn()

    @read("healthy", type="boolean", description="True while the session is neither faulted nor closed")
    def read_healthy(self):
        return bool(self.native.is_healthy)

    @read("last_error", type="string",
          description="First non-zero entry drained from the SCPI error queue, or the empty string")
    def read_last_error(self):
        return self.native.query_error() or ""

    @read("timebase_scale_s_div", unit="s", description="Main timebase scale in seconds per division")
    def read_timebase_scale(self):
        return _number(self.native.query(":TIMebase:MAIN:SCALe?"), "timebase scale")

    @read("timebase_offset_s", unit="s", description="Main timebase offset in seconds")
    def read_timebase_offset(self):
        return _number(self.native.query(":TIMebase:MAIN:OFFSet?"), "timebase offset")

    @read("ch1_scale_v_div", unit="V", description="CH1 displayed vertical scale in volts per division")
    def read_ch1_scale(self):
        return _number(self.native.query(":CHANnel1:SCALe?"), "CH1 scale")

    @read("ch1_offset_v", unit="V", description="CH1 vertical offset in volts")
    def read_ch1_offset(self):
        return _number(self.native.query(":CHANnel1:OFFSet?"), "CH1 offset")

    @read("waveform_source", type="string", description="Waveform transfer source (:WAVeform:SOURce?)")
    def read_waveform_source(self):
        return _token(self.native.query(":WAVeform:SOURce?"), SOURCES, "waveform source")

    @read("waveform_mode", type="string", description="Waveform transfer mode (:WAVeform:MODE?)")
    def read_waveform_mode(self):
        return _token(self.native.query(":WAVeform:MODE?"), MODES, "waveform mode")

    @read("waveform_format", type="string", description="Waveform transfer format (:WAVeform:FORMat?)")
    def read_waveform_format(self):
        return _token(self.native.query(":WAVeform:FORMat?"), ("ASC", "BYTE", "WORD"), "waveform format")

    @read("waveform_points", type="integer", description="Waveform transfer point count (:WAVeform:POINts?)")
    def read_waveform_points(self):
        return _integer(self.native.query(":WAVeform:POINts?"), "waveform points")

    # -- state writes --------------------------------------------------------------------------------------
    @write("timebase_scale_s_div", unit="s", description="Main timebase scale in seconds per division",
           limit=Limit.operator_required(_NOT_STATED))
    def write_timebase_scale(self, value):
        self._write_checked(f":TIMebase:MAIN:SCALe {value:.15g}")
        return value

    @write("timebase_offset_s", unit="s", description="Main timebase offset in seconds",
           limit=Limit.operator_required(_NOT_STATED))
    def write_timebase_offset(self, value):
        self._write_checked(f":TIMebase:MAIN:OFFSet {value:.15g}")
        return value

    @write("ch1_scale_v_div", unit="V", description="CH1 displayed vertical scale in volts per division",
           limit=Limit.operator_required(
               "the clone derives the channel scale bound from the input impedance and the probe ratio "
               "(channel.py:160-175), which this driver does not read; the site supplies the range for its probe"))
    def write_ch1_scale(self, value):
        self._write_checked(f":CHANnel1:SCALe {value:.15g}")
        return value

    @write("ch1_offset_v", unit="V", description="CH1 vertical offset in volts",
           limit=Limit.operator_required(
               "the clone enforces no numeric channel offset range and leaves it to the instrument "
               "(channel.py:177-183); the site supplies the range for its probe"))
    def write_ch1_offset(self, value):
        self._write_checked(f":CHANnel1:OFFSet {value:.15g}")
        return value

    @write("waveform_source", type="string", description="Waveform transfer source",
           limit=Limit(allowed=SOURCES, source="upstream_code", ref=f"{WAVEFORM}:19"))
    def write_waveform_source(self, value):
        token = _token(value, SOURCES, "waveform source")
        self._write_checked(f":WAVeform:SOURce {token}")
        return token

    @write("waveform_mode", type="string", description="Waveform transfer mode",
           limit=Limit(allowed=MODES, source="upstream_code", ref=f"{WAVEFORM}:20"))
    def write_waveform_mode(self, value):
        token = _token(value, MODES, "waveform mode")
        self._write_checked(f":WAVeform:MODE {token}")
        return token

    @write("waveform_format", type="string", description="Waveform transfer format (ASC or BYTE here)",
           limit=Limit(allowed=FORMATS, source="upstream_code", ref=f"{WAVEFORM}:21"))
    def write_waveform_format(self, value):
        token = _token(value, FORMATS, "waveform format")
        self._write_checked(f":WAVeform:FORMat {token}")
        return token

    # -- actions -------------------------------------------------------------------------------------------
    @action(name="x-cap.kitour.acquire_waveform.v1", verb="read",
            description="Read at most 100000 ASC or BYTE samples and their time axis using the ten-field preamble. "
                        "The transfer selector is not changed; the preamble is used internally.",
            output={
                "source": Field("string", description="Waveform source reported by :WAVeform:SOURce?"),
                "format": Field("string", description="Waveform format reported by :WAVeform:FORMat?"),
                "points": Field("integer", description="Point count reported by the preamble"),
                "time": Field("array", unit="s", max_items=INLINE_MAX_POINTS, items=Field("number", unit="s"),
                              description="Time of each sample, computed from the preamble"),
                "values": Field("array", max_items=INLINE_MAX_POINTS, items=Field("number"),
                                description="Sample values in the source's amplitude unit, with the "
                                            "upstream (sample - yorigin - yreference) * yincrement conversion"),
            })
    def acquire_waveform(self):
        source = _token(self.native.query(":WAVeform:SOURce?"), SOURCES, "waveform source")
        fmt = _token(self.native.query(":WAVeform:FORMat?"), ("ASC", "BYTE", "WORD"), "waveform format")
        start = _integer(self.native.query(":WAVeform:STARt?"), "waveform start")
        if start < 1:
            raise DriverFailed("MHS.DEVICE.FAULTED", "MHO98 waveform start must be at least 1")
        preamble = self._preamble(self.native.query(":WAVeform:PREamble?"))
        expected_code = {"BYTE": 0, "WORD": 1, "ASC": 2}[fmt]
        if preamble["format_code"] != expected_code:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"MHO98 preamble reports format code {preamble['format_code']}; expected "
                               f"{expected_code} for {fmt}")
        points = preamble["points"]
        if fmt == "ASC":
            text = str(self.native.query(":WAVeform:DATA?"))
            fields = [item.strip() for item in text.split(",") if item.strip()]
            if len(fields) != points:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   f"MHO98 returned {len(fields)} ASCII samples; the preamble reports {points}")
            values = [_number(item, "waveform sample") for item in fields]
        elif fmt == "BYTE":
            payload = self.native.binary_query(":WAVeform:DATA?", max_bytes=INLINE_MAX_POINTS)
            if len(payload) != points:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   f"MHO98 returned {len(payload)} BYTE samples; the preamble reports {points}")
            values = [(sample - preamble["yorigin"] - preamble["yreference"]) * preamble["yincrement"]
                      for sample in payload]
        else:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "WORD waveform data needs caller-declared byte order and signedness, which this "
                               "driver does not carry; set :WAVeform:FORMat ASC or BYTE")
        times = [preamble["xorigin"] + (start - 1 + index - preamble["xreference"]) * preamble["xincrement"]
                 for index in range(points)]
        return {"source": source, "format": fmt, "points": points, "time": times, "values": values}

    @action(name="x-cap.kitour.read_cursor.v1", verb="read",
            description="Read the cursor mode and, in manual mode, the A/B X screen positions in seconds",
            output={
                "mode": Field("string", description="Cursor mode reported by :CURSor:MODE?"),
                "a_s": Field("number", unit="s", nullable=True, description="Manual cursor A X position"),
                "b_s": Field("number", unit="s", nullable=True, description="Manual cursor B X position"),
            })
    def read_cursor(self):
        mode = _token(self.native.query(":CURSor:MODE?"), ("OFF", "MAN", "MANUAL", "TRAC", "TRACK", "XY"),
                      "cursor mode")
        if mode in ("MAN", "MANUAL"):
            return {"mode": "MANUAL",
                    "a_s": _number(self.native.query(":CURSor:MANual:CAX?"), "cursor A"),
                    "b_s": _number(self.native.query(":CURSor:MANual:CBX?"), "cursor B")}
        return {"mode": mode, "a_s": None, "b_s": None}

    @action(name="x-cap.kitour.set_cursor.v1",
            description="Put the manual cursors in TIME mode and set the A/B X screen positions in seconds",
            input={
                "a_s": Field("number", unit="s", description="Manual cursor A X screen position",
                             limit=Limit.operator_required(_NOT_STATED)),
                "b_s": Field("number", unit="s", description="Manual cursor B X screen position",
                             limit=Limit.operator_required(_NOT_STATED)),
                "source": Field("string", required=False, enum=list(SOURCES),
                                description="Cursor source; default CHAN1"),
            },
            output={
                "mode": Field("string", description="Cursor mode after the write"),
                "a_s": Field("number", unit="s", description="Cursor A X position after the write"),
                "b_s": Field("number", unit="s", description="Cursor B X position after the write"),
            })
    def set_cursor(self, a_s, b_s, source="CHAN1"):
        token = _token(source, SOURCES, "cursor source")
        self._write_checked(":CURSor:MODE MANual")
        self._write_checked(":CURSor:MANual:TYPE TIME")
        self._write_checked(f":CURSor:MANual:SOURce {token}")
        self._write_checked(f":CURSor:MANual:CAX {a_s:.15g}")
        self._write_checked(f":CURSor:MANual:CBX {b_s:.15g}")
        return {"mode": "MANUAL", "a_s": a_s, "b_s": b_s}

    @action(name="x-cap.kitour.run_acquisition.v1", reenable=True,
            description="Start the acquisition with :RUN (the explicit re-enable after a safety reset)",
            input={},
            output={"command": Field("string", description="SCPI command sent")})
    def run_acquisition(self):
        self._write_checked(":RUN")
        return {"command": ":RUN"}

    @action(name="x-cap.kitour.stop_acquisition.v1", safe_state=True,
            description="Send :STOP, reject SCPI errors and require :TRIGger:STATus? to report STOP",
            input={},
            output={"command": Field("string", description="SCPI command sent")})
    def stop_acquisition(self):
        self._write_checked(":STOP")
        status = str(self.native.query(":TRIGger:STATus?")).strip().upper()
        if status != "STOP":
            raise DriverFailed("MHS.DEVICE.FAULTED", f"MHO98 did not confirm acquisition STOP: {status!r}")
        return {"command": ":STOP"}

    # -- helpers -------------------------------------------------------------------------------------------
    def _write_checked(self, command):
        self.native.write(command)
        error = self.native.query_error()
        if error:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"MHO98 SCPI error after {command!r}: {error}")

    @staticmethod
    def _preamble(text) -> dict:
        fields = [item.strip() for item in str(text).strip().split(",")]
        if len(fields) != 10:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"MHO98 waveform preamble must contain 10 fields, got {len(fields)}")
        try:
            format_code = int(fields[0])
            type_code = int(fields[1])
            points = int(fields[2])
            average_count = int(fields[3])
        except ValueError:
            raise DriverFailed("MHS.DEVICE.FAULTED", "MHO98 waveform preamble has a non-integer field") from None
        if points < 1 or points > INLINE_MAX_POINTS or average_count < 1:
            raise DriverFailed("MHS.DEVICE.FAULTED", "MHO98 waveform preamble has an invalid point or average count")
        numbers = [_number(item, "waveform preamble field") for item in fields[4:]]
        return {
            "raw": text,
            "format_code": format_code,
            "type_code": type_code,
            "points": points,
            "count": average_count,
            "xincrement": numbers[0],
            "xorigin": numbers[1],
            "xreference": numbers[2],
            "yincrement": numbers[3],
            "yorigin": numbers[4],
            "yreference": numbers[5],
        }

    # -- safety --------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Require acquisition-state readback; write completion alone does not confirm a stop."""
        self.stop_acquisition()

    def setup(self):
        """Validate the MHO98 identity before serving any call."""
        self.native.idn()

    def teardown(self):
        self.native.close()
