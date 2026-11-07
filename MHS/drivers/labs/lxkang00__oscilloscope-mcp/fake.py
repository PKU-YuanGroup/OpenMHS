"""Local SCPI emulator for the pinned oscilloscope-mcp server.

This is an analytic protocol fake, not a recording and not the upstream simulator. It
speaks only the public methods of ``server:OscilloscopeConnection``: ``connected``,
``host``, ``connect``, ``disconnect``, ``send``, ``query`` and ``safe_query``. Every
state value below is placeholder test data, not a Siglent measurement, range or
calibration value.

The emulator answers the exact command strings the driver composes from the pinned
handlers. Unknown commands raise, so a new command cannot silently pass with a made-up
reply. A failed reply can be injected through the ``stuck`` test hook: when true,
``:STOP`` leaves the trigger status at RUN.
"""
from __future__ import annotations

import re
import threading


class FakeOscilloscope:
    """One controlled SCPI endpoint with the upstream connection class's public surface."""

    def __init__(self, **_options):
        self._lock = threading.RLock()
        self._connected = True
        self._host = "fake-scope"
        self._port = 5024  # placeholder (transport test data, not a device bound)
        self._timeout = 10.0  # placeholder (transport test data, not a device bound)
        self._idn = "Siglent Technologies,SDS2000X Plus,FAKE000000,0.0.0"  # placeholder identity
        self.calls = []
        self.stuck = False
        self._reset_state()

    @property
    def connected(self):
        return self._connected

    @property
    def host(self):
        return self._host

    def connect(self, host, port=5024, timeout=10.0):
        with self._lock:
            self._host = host
            self._port = port
            self._timeout = timeout
            self._connected = True
            return "Connected to " + str(host) + ":" + str(port)

    def disconnect(self):
        with self._lock:
            if not self._connected:
                return "Not connected"
            self._connected = False
            return "Disconnected"

    def send(self, command):
        with self._lock:
            if not self._connected:
                raise RuntimeError("Not connected to oscilloscope.")
            cmd = command.strip()
            self.calls.append(cmd)
            if "?" in cmd:
                return self._answer(cmd)
            self._write(cmd)
            return ""

    def query(self, command):
        if not command.strip().endswith("?"):
            command = command.strip() + "?"
        return self.send(command)

    def safe_query(self, command, fallback="N/A"):
        try:
            return self.query(command).strip()
        except Exception:
            return fallback

    # -- state -------------------------------------------------------------------
    def _reset_state(self):
        self._channels = {
            number: {
                "display": "ON" if number == 1 else "OFF",  # placeholder
                "scale": "1.0E+00",  # placeholder
                "offset": "0.0E+00",  # placeholder
                "coupling": "D1M",  # placeholder
                "bw": "OFF",  # placeholder
                "probe": "1",  # placeholder
                "invert": "OFF",  # placeholder
                "unit": "V",  # placeholder
                "label": "CH",  # placeholder
            } for number in range(1, 5)
        }
        self._timebase = {"scale": "1.0E-03", "delay": "0.0E+00", "mode": "MAIN"}  # placeholder
        self._trigger = {"type": "EDGE", "sweep": "AUTO", "source": "C1", "level": "0.0E+00",
                         "slope": "POSitive", "coupling": "DC", "holdoff": "0.0E+00"}  # placeholder
        self._acquisition = {"mode": "NORMal", "depth": "10K", "interpolation": "LINEAR",
                             "average": "4", "srate": "1.000000E+06"}  # placeholder
        self._display = {"grid": "FULL", "persistence": "OFF", "intensity": "50",
                         "style": "LINE", "axis": "FULL"}  # placeholder
        self._cursor = {"mode": "OFF", "source1": "C1", "source2": "C2", "type": "X",
                        "xdelta": "1.0E-03", "ydelta": "2.0E-01"}  # placeholder
        self._math = {"display": "OFF", "function": "ADD", "source1": "C1", "source2": "C2",
                      "scale": "1.0E+00", "offset": "0.0E+00", "window": "HANN",
                      "fft_scale": "VRMS"}  # placeholder
        self._digital = {"display": "OFF", "position": "0", "height": "20", "label": "D0",
                         "label_text": "D0", "threshold": "1.5", "threshold_line": "D0"}  # placeholder
        self._statistics = {"count": "10", "mean": "1.234000E+00", "min": "1.000000E+00",
                            "max": "1.500000E+00", "stddev": "5.000000E-02"}  # placeholder
        self._measurement = "1.234000E+00"  # placeholder
        self._preamble = "0,0,1000,1000,1.000000E-06,-5.000000E-04,0,1.000000E-02,-1.000000E+00,128"  # placeholder
        self._counter = {"current": "1.000000E+03", "mode": "FREQ", "source": "C1"}  # placeholder
        self._error = '0,"No error"'  # placeholder
        self._waveform_source = "C1"
        self._waveform_format = "ASCII"
        self._last_setup_path = ""
        self._trigger_status = "STOP"
        self._acquisition_state = "0"

    # -- writes ------------------------------------------------------------------
    def _write(self, cmd):
        lower = cmd.lower()
        if lower == "*rst":
            self._reset_state()
            return
        if lower == "*trg":
            self._trigger_status = "TRIGGERED"
            return
        if lower == ":run":
            self._acquisition_state = "1"
            self._trigger_status = "RUN"
            return
        if lower == ":stop":
            if not self.stuck:
                self._acquisition_state = "0"
                self._trigger_status = "STOP"
            return
        if lower == ":autoset":
            self._acquisition_state = "1"
            self._trigger_status = "AUTO"
            return
        if lower == ":measure:statistics:reset":
            self._statistics = {key: "0" for key in self._statistics}  # placeholder reset
            return
        match = re.match(r"^:channel(\d+):(.+)$", lower)
        if match:
            channel = int(match.group(1))
            suffix = match.group(2)
            value = cmd.split(" ", 1)[1] if " " in cmd else ""
            if channel not in self._channels:
                raise RuntimeError("channel outside the fake's four channels: " + cmd)
            channel_state = self._channels[channel]
            if suffix.startswith("switch"):
                channel_state["display"] = value
            elif suffix.startswith("invert"):
                channel_state["invert"] = value
            elif suffix.startswith("scale"):
                channel_state["scale"] = value
            elif suffix.startswith("offset"):
                channel_state["offset"] = value
            elif suffix.startswith("coupling"):
                channel_state["coupling"] = value
            elif suffix.startswith("bwlimit"):
                channel_state["bw"] = value
            elif suffix.startswith("probe"):
                channel_state["probe"] = value
            elif suffix.startswith("skew"):
                channel_state["skew"] = value
            elif suffix.startswith("unit"):
                channel_state["unit"] = value
            elif suffix.startswith("label:text"):
                channel_state["label"] = value.strip('"')
            elif suffix.startswith("label"):
                pass
            else:
                raise RuntimeError("unsupported fake channel command: " + cmd)
            return
        if lower.startswith(":timebase:"):
            key, _, value = cmd.partition(" ")
            field = key.lower().split(":", 2)[2]
            if field not in self._timebase:
                raise RuntimeError("unsupported fake timebase command: " + cmd)
            self._timebase[field] = value
            return
        if lower.startswith(":trigger:"):
            key, _, value = cmd.partition(" ")
            parts = key.lower().split(":")
            if len(parts) == 3 and parts[2] in ("sweep", "type", "holdoff"):
                self._trigger[parts[2]] = value
                return
            if len(parts) == 4 and parts[2] == self._trigger["type"].lower() \
                    and parts[3] in ("source", "level", "slope", "coupling"):
                self._trigger[parts[3]] = value
                return
            raise RuntimeError("unsupported fake trigger command: " + cmd)
        if lower.startswith(":acquire:"):
            key, _, value = cmd.partition(" ")
            field = key.lower().split(":", 2)[2]
            names = {"mode": "mode", "mdepth": "depth", "interpolation": "interpolation",
                     "average": "average"}
            if field not in names:
                raise RuntimeError("unsupported fake acquisition command: " + cmd)
            self._acquisition[names[field]] = value
            return
        if lower.startswith(":display:"):
            key, _, value = cmd.partition(" ")
            field = key.lower().split(":", 2)[2]
            names = {"gridstyle": "grid", "persistence": "persistence", "intensity": "intensity",
                     "graticule": "style", "axis:mode": "axis"}
            if field not in names:
                raise RuntimeError("unsupported fake display command: " + cmd)
            self._display[names[field]] = value
            return
        if lower.startswith(":cursor:"):
            key, _, value = cmd.partition(" ")
            field = key.lower().split(":", 2)[2]
            names = {"mode": "mode", "source1": "source1", "source2": "source2", "type": "type"}
            if field not in names:
                raise RuntimeError("unsupported fake cursor command: " + cmd)
            self._cursor[names[field]] = value
            return
        if lower.startswith(":math:"):
            key, _, value = cmd.partition(" ")
            field = key.lower().split(":", 2)[2]
            names = {"switch": "display", "function": "function", "source1": "source1",
                     "source2": "source2", "scale": "scale", "offset": "offset",
                     "fft:window": "window", "fft:scale": "fft_scale"}
            if field not in names:
                raise RuntimeError("unsupported fake math command: " + cmd)
            self._math[names[field]] = value
            return
        if lower.startswith(":digital:"):
            key, _, value = cmd.partition(" ")
            field = key.lower().split(":", 2)[2]
            if field == "label":
                line, _, label = value.partition(",")
                self._digital["label"] = line
                self._digital["label_text"] = label.strip('"')
            elif field == "threshold":
                line, _, threshold = value.partition(",")
                self._digital["threshold_line"] = line
                self._digital["threshold"] = threshold
            elif field in ("display", "position", "height"):
                self._digital[field] = value
            else:
                raise RuntimeError("unsupported fake digital command: " + cmd)
            return
        if lower.startswith(":store:setup"):
            self._last_setup_path = cmd.partition(" ")[2].strip('"')
            return
        if lower.startswith(":recall:setup"):
            self._last_setup_path = cmd.partition(" ")[2].strip('"')
            return
        if lower.startswith(":waveform:source"):
            self._waveform_source = cmd.partition(" ")[2]
            return
        if lower.startswith(":waveform:format"):
            self._waveform_format = cmd.partition(" ")[2]
            return
        raise RuntimeError("unsupported fake write command: " + cmd)

    # -- reads -------------------------------------------------------------------
    def _answer(self, cmd):
        head = cmd.split(" ", 1)[0].lower()
        lower = head
        if lower == "*idn?":
            return self._idn
        if lower == "*opc?":
            return "1"
        if lower == "*esr?":
            return "0"
        if lower == ":trigger:status?":
            return self._trigger_status
        if lower == ":acquire:state?":
            return self._acquisition_state
        match = re.match(r"^:channel(\d+):(.+)\?$", lower)
        if match:
            channel = int(match.group(1))
            field = match.group(2)
            if channel not in self._channels:
                raise RuntimeError("channel outside the fake's four channels: " + cmd)
            names = {"switch": "display", "scale": "scale", "offset": "offset", "coupling": "coupling",
                     "bwlimit": "bw", "probe": "probe", "invert": "invert", "unit": "unit"}
            if field not in names:
                raise RuntimeError("unsupported fake channel query: " + cmd)
            return self._channels[channel][names[field]]
        match = re.match(r"^:timebase:(scale|delay|mode)\?$", lower)
        if match:
            return self._timebase[match.group(1)]
        if lower == ":trigger:type?":
            return self._trigger["type"]
        if lower == ":trigger:sweep?":
            return self._trigger["sweep"]
        if lower == ":trigger:holdoff?":
            return self._trigger["holdoff"]
        match = re.match(r"^:trigger:[a-z]+:(source|level|slope|coupling)\?$", lower)
        if match:
            return self._trigger[match.group(1)]
        match = re.match(r"^:acquire:(mode|mdepth|srate|interpolation|average)\?$", lower)
        if match:
            names = {"mode": "mode", "mdepth": "depth", "srate": "srate",
                     "interpolation": "interpolation", "average": "average"}
            return self._acquisition[names[match.group(1)]]
        match = re.match(r"^:measure:statistics:(count|mean|min|max|stdd)\?$", lower)
        if match:
            names = {"count": "count", "mean": "mean", "min": "min", "max": "max", "stdd": "stddev"}
            return self._statistics[names[match.group(1)]]
        if lower.startswith(":measure:all?"):
            return "VPP=" + self._measurement + ",FREQ=1.000000E+03"  # placeholder
        if re.match(r"^:measure:[a-z_]+\?$", lower):
            return self._measurement
        if lower == ":waveform:preamble?":
            return self._preamble
        match = re.match(r"^:cursor:(mode|xdelta|ydelta)\?$", lower)
        if match:
            return self._cursor[match.group(1)]
        match = re.match(r"^:counter:(current|mode|source)\?$", lower)
        if match:
            return self._counter[match.group(1)]
        if lower == ":system:error?":
            return self._error
        raise RuntimeError("unsupported fake query command: " + cmd)


def connect(**options):
    return FakeOscilloscope(**options)
