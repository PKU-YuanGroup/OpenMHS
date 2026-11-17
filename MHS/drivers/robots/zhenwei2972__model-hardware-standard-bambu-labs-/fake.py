"""Fake backend of the Bambu Lab driver: an in-memory stand-in for ``mhs.drivers.bambu.printer:BambuPrinter``.

Gate G7: every public member defined here is a method or property of the upstream class at the pinned commit
(``src/mhs/drivers/bambu/printer.py:61``) or of the bases it uses.  The methods keep the upstream async signatures
(``start_print(remote_path, options=None)``, ``set_temperature(nozzle=None, bed=None)``, ``set_light(on,
node="chamber_light")``, ``set_speed(level)``, ``calibrate(**kwargs)``, ``status()``, ``snapshot()``) and return the
same report-shaped dictionaries that ``BambuMqtt.publish_and_wait`` returns.

What it models: the merged MQTT state machine (idle, running, paused), the target temperatures, the speed preset,
the chamber light, the calibration bitmask and the print commands.  What it does not model: any MQTT or TLS
connection, the camera protocol, physical motion or thermal dynamics, the real 1280x720 JPEG size (it returns a 1x1
placeholder), and the printer's own report latency.  Nothing here talks to a device and nothing here is a recording.

All numbers below are placeholder test data, not facts about a printer.
"""

import base64

#: placeholder: a 1x1 JPEG, only large enough for the image plumbing; the real camera frames are 1280x720.
_TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

#: placeholder: the simulated model's bed rating; the driver's bed limit is operator-required and the real
#: BambuPrinter derives this value from its configured model (src/mhs/specs.py:107-148).
_FAKE_SPEC = type("_Spec", (), {"model": "A1 mini", "max_bed_temp_c": 80.0, "max_nozzle_temp_c": 300.0})()

_SPEED_NAMES = {1: "silent", 2: "standard", 3: "sport", 4: "ludicrous"}


class _State:
    """The subset of PrintState the driver touches."""

    def __init__(self, value):
        self.value = value

    @property
    def is_active(self):
        return self.value in ("preparing", "running", "paused")

    @property
    def accepts_new_job(self):
        return self.value in ("idle", "finished", "failed")


class DeviceBusy(Exception):
    """The upstream start/calibration preflight refuses an active device."""


class _Temperature:
    def __init__(self, current, target):
        self.current = current
        self.target = target


class _Alert:
    def __init__(self, code, severity, message=None, url=None):
        self.code = code
        self.severity = severity
        self.message = message
        self.url = url


class _Status:
    def __init__(self, **values):
        self.__dict__.update(values)


class FakeBambuPrinter:
    """An in-process A1 mini stand-in that accepts every command and changes its own state."""

    def __init__(self, **options):
        self._options = dict(options)
        self._connected = False
        self._state = "idle"
        self._job = None
        self._progress = 0
        self._layer = 0
        self._total_layers = 0
        self._remaining = 0
        self._nozzle = _Temperature(25.0, 0.0)                      # placeholder
        self._bed = _Temperature(25.0, 0.0)                         # placeholder
        self._speed_level = 2                                       # placeholder
        self._lights = {"chamber_light": "on"}                      # placeholder
        self._alerts = []
        self._commands = []
        self._camera_calls = 0
        self._stop_reply = None
        self.model_name = "A1 mini"
        _FAKE_SPEC.model = self.model_name

    # -- properties the upstream Printer base defines -------------------------------------------------------------
    @property
    def spec(self):
        return _FAKE_SPEC

    # -- lifecycle ------------------------------------------------------------------------------------------------
    async def connect(self, wait_for_status=10.0):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    # -- status ---------------------------------------------------------------------------------------------------
    async def status(self):
        state = self._state if self._connected else "offline"
        return _Status(
            state=_State(state),
            online=self._connected,
            job_name=self._job,
            progress_percent=self._progress if self._state != "idle" else None,
            current_layer=self._layer if self._state != "idle" else None,
            total_layers=self._total_layers if self._state != "idle" else None,
            remaining_minutes=self._remaining if self._state != "idle" else None,
            stage="printing" if self._state == "running" else None,
            nozzle=_Temperature(self._nozzle.current, self._nozzle.target),
            bed=_Temperature(self._bed.current, self._bed.target),
            chamber=_Temperature(25.0, None),                       # placeholder
            speed_level=_SPEED_NAMES.get(self._speed_level),
            speed_percent=100,                                      # placeholder
            lights=dict(self._lights),
            filament=[],
            alerts=list(self._alerts),
            native_state=self._state.upper(),
            sd_card=True,
        )

    # -- print job control ----------------------------------------------------------------------------------------
    async def start_print(self, remote_path, options=None):
        if not _State(self._state).accepts_new_job:
            raise DeviceBusy("stop or finish the current job before starting another")
        if any(alert.severity in ("fatal", "serious") for alert in self._alerts):
            raise DeviceBusy("clear blocking alerts before printing")
        self._state = "running"
        self._job = str(remote_path)
        self._progress = 0
        self._layer = 0
        self._total_layers = 1
        self._remaining = 1
        self._commands.append(("start_print", {"remote_path": str(remote_path)}))
        return {"acknowledged": True, "success": True, "result": "success", "file": str(remote_path)}

    async def pause_print(self):
        self._commands.append(("pause_print", {}))
        if self._state == "running":
            self._state = "paused"
        return {"acknowledged": True, "success": True, "result": "success"}

    async def resume_print(self):
        self._commands.append(("resume_print", {}))
        if self._state == "paused":
            self._state = "running"
        return {"acknowledged": True, "success": True, "result": "success"}

    async def stop_print(self):
        self._commands.append(("stop_print", {}))
        forced = self._stop_reply
        self._stop_reply = None
        if forced is not None:
            return forced
        self._state = "idle"
        self._job = None
        self._progress = 0
        self._layer = 0
        self._total_layers = 0
        self._remaining = 0
        return {"acknowledged": True, "success": True, "result": "success"}

    # -- controls -------------------------------------------------------------------------------------------------
    async def set_temperature(self, nozzle=None, bed=None):
        if nozzle is not None:
            self._nozzle.target = float(int(nozzle))
        if bed is not None:
            self._bed.target = float(int(bed))
        self._commands.append(("set_temperature", {"nozzle": nozzle, "bed": bed}))
        return {"acknowledged": True, "success": True, "result": "success"}

    async def set_light(self, on, node="chamber_light"):
        self._lights[str(node)] = "on" if on else "off"
        self._commands.append(("set_light", {"on": bool(on), "node": str(node)}))
        return {"acknowledged": True, "success": True, "result": "success"}

    async def set_speed(self, level):
        self._speed_level = int(level)
        self._commands.append(("set_speed", {"level": int(level)}))
        return {"acknowledged": True, "success": True, "result": "success"}

    async def calibrate(self, **kwargs):
        if _State(self._state).is_active:
            raise DeviceBusy("calibration needs an idle printer")
        self._commands.append(("calibrate", dict(kwargs)))
        return {"acknowledged": True, "success": True, "result": "success"}

    async def snapshot(self):
        self._camera_calls += 1
        return _TINY_JPEG


    # -- hook for test_driver.py (not a BambuPrinter member, never used by the driver) -------------------------------
    def _force_stop_reply(self, reply):
        """The next stop_print returns ``reply`` instead of the normal report; the state does not change."""
        self._stop_reply = reply
