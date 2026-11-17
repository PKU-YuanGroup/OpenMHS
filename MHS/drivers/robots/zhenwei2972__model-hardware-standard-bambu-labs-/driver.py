"""OpenMHS driver for gh.zhenwei2972/model-hardware-standard-bambu-labs: a Bambu Lab FDM printer over LAN MQTT.

A direct Driver over the upstream async class ``mhs.drivers.bambu.printer:BambuPrinter``.  The card lists the
``PythonObjectDriver`` helper, but the upstream object is an asyncio device with a multi-step print-job, thermal and
camera interface, so this package uses the decorated ``Driver``; the deviation is recorded in RESULT.json.

* reads: the cached MQTT status (state, job progress, nozzle and bed temperatures and targets, speed preset,
  chamber light, alerts);
* writes: the nozzle target (0-300 C, the range commands.set_temperature enforces), the bed target (operator
  required: the bed rating differs per model), the four firmware speed presets and the chamber light;
* actions: start a sliced file already on the printer, pause, resume, stop, the native calibration bitmask, a JPEG
  frame from the chamber camera published as an image artifact, and the input-free safe stop;
* the best-effort e-stop sends ``print.stop`` and zero heater targets over LAN MQTT, then fails with the latch held:
  command echoes and cached status do not confirm a physical stop. The clone documents no independent physical
  e-stop. ``x-cap.zhenwei2972.safe_stop.v1`` is an ordinary request with cached read-back, not a safe-state action.

Every Fact and Limit cites the clone at commit ``e945c3ed88927760b082c3068b1233c276f17f96``.  The package is
model-authored and unreviewed: it is checked on the fake backend only, the hardware backend has never been run, and
no hardware run is claimed.
"""

import asyncio
import math

from mhs.driver import (
    Busy,
    Driver,
    DriverFailed,
    Fact,
    Field,
    Limit,
    OutcomeUnknown,
    action,
    estop,
    read,
    write,
)

SOURCE = "src/mhs/drivers/bambu"
COMMANDS = f"{SOURCE}/commands.py"
PRINTER = f"{SOURCE}/printer.py"
MQTT = f"{SOURCE}/mqtt.py"
CAMERA = f"{SOURCE}/camera.py"
SPECS = "src/mhs/specs.py"

#: The upstream command builders reject a nozzle target outside 0-300 C (commands.py:95-96).
NOZZLE_TARGET_LIMIT = Limit(
    min=0, max=300, unit="Cel", source="upstream_code", ref=f"{COMMANDS}:95-96",
    reason="commands.set_temperature rejects a nozzle target outside 0-300 C before it builds the M104 line")
#: The firmware defines exactly the four presets 1 silent, 2 standard, 3 sport and 4 ludicrous (commands.py:11).
SPEED_LEVEL_LIMIT = Limit(
    min=1, max=4, unit="1", source="upstream_code", ref=f"{COMMANDS}:11",
    reason="the firmware defines exactly four speed presets and commands.set_speed accepts only those four")
#: The bed rating is per model (A1 mini 80 C, A1/P1P/P1S 100 C, X1 Carbon 110 C; specs.py:107-148), so no single
#: static range is a source for this printer.  The operator supplies the range of the installed unit.
BED_TARGET_LIMIT = Limit.operator_required(
    "the bed rating depends on the configured model: 80 C for the A1 mini (src/mhs/specs.py:113), 100 C for the "
    "A1/P1P/P1S (src/mhs/specs.py:130,136,140) and 110 C for the X1 Carbon (src/mhs/specs.py:145); the site supplies "
    "the range of its printer")

#: A JPEG starts with SOI and has a SOFn segment carrying the frame size.
_JPEG_SOF = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
_SPEED_NAMES = {1: "silent", 2: "standard", 3: "sport", 4: "ludicrous"}


def _jpeg_size(data):
    """Return (width, height) from a JPEG's SOFn segment, or raise when the bytes are not a complete JPEG."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 4 or not data.startswith(b"\xff\xd8"):
        raise DriverFailed("MHS.DEVICE.FAULTED", "the chamber camera did not return a JPEG (missing SOI)")
    if not data.endswith(b"\xff\xd9"):
        raise DriverFailed("MHS.DEVICE.FAULTED", "the chamber camera returned a truncated JPEG (missing EOI)")
    index = 2
    limit = len(data)
    while index + 4 <= limit:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            index += 1 if marker == 0xFF else 2
            continue
        length = int.from_bytes(data[index + 2:index + 4], "big")
        if length < 2 or index + 2 + length > limit:
            break
        if marker in _JPEG_SOF and index + 9 <= limit:
            height = int.from_bytes(data[index + 5:index + 7], "big")
            width = int.from_bytes(data[index + 7:index + 9], "big")
            if width < 1 or height < 1:
                break
            return width, height
        index += 2 + length
    raise DriverFailed("MHS.DEVICE.FAULTED", "the chamber camera returned a JPEG without a frame size")


def _check_ack(result, what):
    """Translate one publish_and_wait receipt (mqtt.py:171-202): a missing report is an unknown outcome."""
    if not isinstance(result, dict):
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned {type(result).__name__}, not a report dict")
    if not result.get("acknowledged"):
        hint = result.get("hint") or "no report echoed the sequence id"
        raise OutcomeUnknown(f"{what}: the printer did not acknowledge the command ({hint})")
    if not result.get("success"):
        reason = result.get("reason") or result.get("result") or "the report did not report success"
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what}: {reason}")
    return result


def _temperature(value):
    """Unknown temperatures stay unknown instead of becoming a zero-temperature reading."""
    if value is None:
        raise DriverFailed("MHS.DEVICE.NOT_READY", "the printer has not reported this temperature")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DriverFailed("MHS.CAPABILITY.OUTPUT_INVALID", "the printer reported an invalid temperature")
    return float(value)


class BambuLabPrinter(Driver):
    """A Bambu Lab A1 mini / A1 / P1P / P1S / X1 Carbon / X1E reached over the LAN."""

    device_id = "bambu-printer"
    device_kind = "process.controller"
    mode = "hardware"
    risk = "R2"
    native = "mhs.drivers.bambu.printer:BambuPrinter"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBambuPrinter"}
    vendor, model = "Bambu Lab", "A1 mini / A1 / P1P / P1S / X1 Carbon / X1E"
    display_name = "Bambu Lab LAN printer (mhs.drivers.bambu.printer:BambuPrinter)"
    tags = ["3d printer", "fdm", "bambu lab", "lan mqtt", "print job", "camera", "asyncio"]
    extra_resources = {
        "camera": {"kind": "sensor.camera", "title": "Chamber camera (TCP 6000 JPEG frames)"},
    }
    facts = [
        Fact("BambuPrinter builds one BambuMqtt, one BambuFiles and one BambuCamera from the configured host, "
             "serial and access code", source="upstream_code", ref=f"{PRINTER}:66-92"),
        Fact("The MQTT transport defines device/<serial>/request and device/<serial>/report topic names",
             source="upstream_code", ref=f"{MQTT}:54-55"),
        Fact("The MQTT client uses username bblp and the printer access code", source="upstream_code",
             ref=f"{MQTT}:78"),
        Fact("publish_and_wait publishes and waits up to 6 s for a report with the same sequence_id; a missing "
             "acknowledgement is returned as acknowledged false rather than raised",
             source="upstream_code", ref=f"{MQTT}:171-202"),
        Fact("pause, resume and stop are print commands carrying an empty param",
             source="upstream_code", ref=f"{COMMANDS}:52-61"),
        Fact("start_print refuses unless the printer accepts a new job and reports no fatal or serious alert, then "
             "publishes project_file and waits for its report", source="upstream_code", ref=f"{PRINTER}:176-205"),
        Fact("project_file needs a .3mf, .gcode or .gcode.3mf path and a plate index of at least 1",
             source="upstream_code", ref=f"{COMMANDS}:182-184"),
        Fact("set_temperature rejects a nozzle target outside 0-300 C and a bed target outside 0-120 C",
             source="upstream_code", ref=f"{COMMANDS}:95-101"),
        Fact("Temperatures are sent as M104 and M140 gcode because the firmware has no dedicated JSON temperature "
             "command", source="upstream_code", ref=f"{COMMANDS}:91-101"),
        Fact("The firmware speed presets are 1 silent, 2 standard, 3 sport and 4 ludicrous",
             source="upstream_code", ref=f"{COMMANDS}:11"),
        Fact("set_light sends ledctrl for the chamber_light or work_light node with led_mode on or off",
             source="upstream_code", ref=f"{COMMANDS}:107-120"),
        Fact("calibrate refuses an active printer, calls commands.calibration with its keyword arguments and "
             "publishes the result", source="upstream_code", ref=f"{PRINTER}:247-252"),
        Fact("The printer module declares _MIN_PUSHALL_INTERVAL=300.0 and _STALE_AFTER=90.0",
             source="upstream_code", ref=f"{PRINTER}:55-58"),
        Fact("status refreshes stale telemetry with force=True, waits 1 s and returns the merged cached status",
             source="upstream_code", ref=f"{PRINTER}:153-160"),
        Fact("_refresh skips requests within the minimum interval only when force is false",
             source="upstream_code", ref=f"{PRINTER}:126-134"),
        Fact("The A1/P1 chamber camera streams 1280x720 JPEG frames at roughly 1 fps over a TLS socket",
             source="upstream_code", ref=f"{CAMERA}:1-5"),
        Fact("The camera declares a 16-byte header size and an 8 MiB maximum frame size",
             source="upstream_code", ref=f"{CAMERA}:29-30"),
        Fact("The printer moves fast and reaches 220 C or more: it can burn, pinch and start a fire if left "
             "unattended with a fault", source="upstream_code", ref="src/mhs/printer.py:53-54"),
        Fact("The bed rating depends on the model: 80 C for the A1 mini, 100 C for the A1/P1P/P1S and 110 C for the "
             "X1 Carbon", source="upstream_code", ref=f"{SPECS}:107-148"),
        Fact("Firmware 01.05 and newer on the A1 series silently ignores start, stop and heat commands unless "
             "Developer Mode is enabled", source="vendor_doc", ref="README.md:235-236"),
        Fact("The README safety model puts start_print, upload_and_print, stop_print and send_gcode behind a "
             "confirmation gate", source="vendor_doc", ref="README.md:359-361"),
        Fact("A stopped Bambu print job cannot be resumed", source="vendor_doc", ref="docs/MHS_ALIGNMENT.md:81"),
    ]
    safe_state = ("no safe state is confirmed: the e-stop requests print.stop and zero nozzle/bed targets, then "
                  "fails SAFE_STATE_UNREACHED with the latch held; MQTT echoes and merged cached fields prove "
                  "neither physical standstill nor heater shutdown, and a hot printer remains hot")
    #: The native stop's publish_and_wait default is 6 s (mqtt.py:171), so the runtime's stop budget must cover it.
    estop_timeout_ms = 8000

    # -- lifecycle ------------------------------------------------------------------------------------------------
    async def setup(self):
        await self.native.connect()

    async def teardown(self):
        await self.native.disconnect()

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("state", type="string",
          description="Lifecycle state: offline, idle, preparing, running, paused, finished, failed or unknown")
    async def get_state(self):
        return (await self.native.status()).state.value

    @read("online", type="boolean", description="True while the MQTT link is up and telemetry is not stale")
    async def get_online(self):
        return bool((await self.native.status()).online)

    @read("job_name", type="string", description="Name of the loaded or printing job, empty when there is none")
    async def get_job_name(self):
        return str((await self.native.status()).job_name or "")

    @read("progress_percent", type=Field("integer", nullable=True),
          description="Completion of the running job, omitted when unreported")
    async def get_progress_percent(self):
        return (await self.native.status()).progress_percent

    @read("current_layer", type=Field("integer", nullable=True),
          description="Layer currently being printed, omitted when unreported")
    async def get_current_layer(self):
        return (await self.native.status()).current_layer

    @read("total_layers", type=Field("integer", nullable=True),
          description="Total layers of the running job, omitted when unreported")
    async def get_total_layers(self):
        return (await self.native.status()).total_layers

    @read("remaining_minutes", type=Field("integer", nullable=True),
          description="The printer's estimate of minutes left, omitted when unreported")
    async def get_remaining_minutes(self):
        return (await self.native.status()).remaining_minutes

    @read("nozzle_temperature", unit="Cel", description="Measured hotend temperature")
    async def get_nozzle_temperature(self):
        return _temperature((await self.native.status()).nozzle.current)

    @read("nozzle_target_temperature", unit="Cel", description="Hotend target temperature")
    async def get_nozzle_target_temperature(self):
        return _temperature((await self.native.status()).nozzle.target)

    @read("bed_temperature", unit="Cel", description="Measured heated-bed temperature")
    async def get_bed_temperature(self):
        return _temperature((await self.native.status()).bed.current)

    @read("bed_target_temperature", unit="Cel", description="Heated-bed target temperature")
    async def get_bed_target_temperature(self):
        return _temperature((await self.native.status()).bed.target)

    @read("print_speed_level", type="integer", unit="1",
          description="Speed preset: 1 silent, 2 standard, 3 sport, 4 ludicrous; fails while unknown")
    async def get_print_speed_level(self):
        name = (await self.native.status()).speed_level
        for level, label in _SPEED_NAMES.items():
            if name == label:
                return level
        raise DriverFailed("MHS.DEVICE.NOT_READY", "the printer has not reported a known speed preset")

    @read("chamber_light", type="boolean", description="True when the chamber LED is on")
    async def get_chamber_light(self):
        value = (await self.native.status()).lights.get("chamber_light")
        if value not in ("on", "off"):
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the printer has not reported the chamber light")
        return value == "on"

    @read("alerts", type="array",
          items=Field("object", description="One health-management or print error code", properties={
              "code": Field("string", description="Firmware alert code"),
              "severity": Field("string", description="Severity reported by the clone's decoder"),
              "message": Field("string", description="Decoded message", nullable=True),
              "url": Field("string", description="Documentation link", nullable=True),
          }),
          description="Active fault codes the printer reports")
    async def get_alerts(self):
        return [
            {"code": str(alert.code), "severity": str(alert.severity),
             "message": alert.message, "url": alert.url}
            for alert in (await self.native.status()).alerts
        ]

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("nozzle_target_temperature", unit="Cel", limit=NOZZLE_TARGET_LIMIT,
           description="Set the hotend target with M104; the native command truncates fractional Celsius")
    async def set_nozzle_target_temperature(self, value):
        result = await self._native("set_temperature", self.native.set_temperature(nozzle=float(value)))
        _check_ack(result, "set_temperature")
        return float(int(value))

    @write("bed_target_temperature", unit="Cel", limit=BED_TARGET_LIMIT,
           description="Set the heated-bed target temperature with M140; the site supplies the model's bed range")
    async def set_bed_target_temperature(self, value):
        spec = self.native.spec
        if float(value) > float(spec.max_bed_temp_c):
            raise DriverFailed(
                "MHS.SAFETY.ENVELOPE_VIOLATION",
                f"the configured {spec.model} bed is rated to {spec.max_bed_temp_c:g} C, not {value!r} C")
        result = await self._native("set_temperature", self.native.set_temperature(bed=float(value)))
        _check_ack(result, "set_temperature")
        return float(int(value))

    @write("print_speed_level", type="integer", unit="1", limit=SPEED_LEVEL_LIMIT,
           description="Select the firmware speed preset with print_speed")
    async def set_print_speed_level(self, value):
        result = await self._native("set_speed", self.native.set_speed(int(value)))
        _check_ack(result, "set_speed")
        return int(value)

    @write("chamber_light", type="boolean", description="Turn the chamber LED on or off with ledctrl")
    async def set_chamber_light(self, value):
        result = await self._native("set_light", self.native.set_light(bool(value)))
        _check_ack(result, "set_light")
        return bool(value)

    # -- print job control ----------------------------------------------------------------------------------------
    @action(name="x-cap.zhenwei2972.start_print.v1",
            description="Start a sliced .3mf or .gcode file already on the printer with the native project_file "
                        "command; the printer must be idle and report no fatal or serious alert",
            input={"remote_path": Field("string", max_length=1024,
                                        description="Path of the sliced file on the printer, such as cache/a.3mf")},
            output={"accepted": Field("boolean", description="True when the printer acknowledged the command"),
                    "file": Field("string", description="The file the command was sent for"),
                    "result": Field("string", description="The report's result word")})
    async def start_print(self, remote_path):
        result = await self._native("start_print", self.native.start_print(str(remote_path)))
        _check_ack(result, "start_print")
        return {"accepted": True, "file": str(result.get("file", remote_path)),
                "result": str(result.get("result", ""))}

    @action(name="x-cap.zhenwei2972.pause_print.v1",
            description="Pause the running print with the native print.pause command",
            input={},
            output={"accepted": Field("boolean", description="True when the printer acknowledged the command"),
                    "result": Field("string", description="The report's result word")})
    async def pause_print(self):
        result = await self._native("pause_print", self.native.pause_print())
        _check_ack(result, "pause_print")
        return {"accepted": True, "result": str(result.get("result", ""))}

    @action(name="x-cap.zhenwei2972.resume_print.v1",
            description="Resume a paused print with the native print.resume command",
            input={},
            output={"accepted": Field("boolean", description="True when the printer acknowledged the command"),
                    "result": Field("string", description="The report's result word")})
    async def resume_print(self):
        result = await self._native("resume_print", self.native.resume_print())
        _check_ack(result, "resume_print")
        return {"accepted": True, "result": str(result.get("result", ""))}

    @action(name="x-cap.zhenwei2972.stop_print.v1",
            description="Stop the print with the native print.stop command; a stopped job cannot be resumed",
            input={},
            output={"accepted": Field("boolean", description="True when the printer acknowledged the command"),
                    "result": Field("string", description="The report's result word")})
    async def stop_print(self):
        result = await self._native("stop_print", self.native.stop_print())
        _check_ack(result, "stop_print")
        return {"accepted": True, "result": str(result.get("result", ""))}

    @action(name="x-cap.zhenwei2972.calibrate_printer.v1",
            description="Run the native calibration bitmask; the printer must be idle",
            input={
                "bed_level": Field("boolean", description="Run auto bed levelling"),
                "vibration": Field("boolean", description="Run vibration compensation calibration"),
                "motor_noise": Field("boolean", description="Run motor-noise calibration"),
                "lidar": Field("boolean", description="Run the lidar calibration on models that have one"),
            },
            output={"accepted": Field("boolean", description="True when the printer acknowledged the command"),
                    "options": Field("object", description="The routines the command selected", properties={
                        "bed_level": Field("boolean", description="Auto bed levelling selected"),
                        "vibration": Field("boolean", description="Vibration compensation selected"),
                        "motor_noise": Field("boolean", description="Motor-noise calibration selected"),
                        "lidar": Field("boolean", description="Lidar calibration selected"),
                    })})
    async def calibrate_printer(self, bed_level=True, vibration=True, motor_noise=False, lidar=False):
        if not any((bed_level, vibration, motor_noise, lidar)):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "select at least one calibration routine")
        result = await self._native("calibrate", self.native.calibrate(
            bed_level=bool(bed_level), vibration=bool(vibration), motor_noise=bool(motor_noise), lidar=bool(lidar)))
        _check_ack(result, "calibrate")
        return {"accepted": True, "options": {"bed_level": bool(bed_level), "vibration": bool(vibration),
                                              "motor_noise": bool(motor_noise), "lidar": bool(lidar)}}

    # -- camera ---------------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1", resource="camera",
            description="Capture one JPEG frame from the chamber camera and publish it as an image artifact",
            input={"camera": Field("string",
                                   description="Camera selector; this package serves the one chamber camera")})
    async def capture(self, camera=None):
        from mhs.artifacts import publisher_from_context

        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "capture requires an endpoint-owned artifact store")
        data = await self._native("snapshot", self.native.snapshot())
        self.check_cancelled()
        if not isinstance(data, (bytes, bytearray)):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"BambuPrinter.snapshot returned {type(data).__name__}, not JPEG bytes")
        data = bytes(data)
        width, height = _jpeg_size(data)
        if len(data) > publisher.max_bytes:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the captured JPEG is {len(data)} bytes, above the endpoint artifact bound of "
                               f"{publisher.max_bytes} bytes")
        descriptor = publisher.publish(data, "image/jpeg")
        return {"image_ref": descriptor["uri"], "width": width, "height": height, "media_type": "image/jpeg"}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.zhenwei2972.safe_stop.v1",
            description="Request print.stop and zero heater targets, then check cached fields; this ordinary "
                        "request does not confirm physical stopping or heater shutdown",
            input={},
            output={"stop_acknowledged": Field("boolean",
                                               description="True when the printer acknowledged print.stop"),
                    "heater_targets_zero": Field("boolean", description="Both cached target temperatures are 0"),
                    "job_state": Field("string", description="Cached printer state after the request"),
                    "nozzle_target_c": Field("number", unit="Cel", description="Cached nozzle target"),
                    "bed_target_c": Field("number", unit="Cel", description="Cached bed target")})
    async def safe_stop(self):
        result = await self._native("stop_print", self.native.stop_print())
        _check_ack(result, "stop_print")
        result = await self._native("set_temperature", self.native.set_temperature(nozzle=0, bed=0))
        _check_ack(result, "set_temperature")
        status = await self.native.status()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 2.5
        while status.state.is_active and loop.time() < deadline:
            await asyncio.sleep(0.25)
            status = await self.native.status()
        if not status.online or status.state.value not in ("idle", "finished", "failed"):
            raise DriverFailed(
                "MHS.SAFETY.SAFE_STATE_UNREACHED",
                f"the printer still reports {status.state.value} after print.stop and the heater-off command")
        nozzle_target = _temperature(status.nozzle.target)
        bed_target = _temperature(status.bed.target)
        if nozzle_target != 0.0 or bed_target != 0.0:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "cached heater targets are not both zero")
        return {"stop_acknowledged": True, "heater_targets_zero": True,
                "job_state": status.state.value, "nozzle_target_c": nozzle_target, "bed_target_c": bed_target}

    @estop(native="stop_print", latency_ms=6500)
    async def stop(self):
        """Send both best-effort requests promptly, then fail because neither confirms a physical safe state."""
        results = await asyncio.gather(
            self._native("stop_print", self.native.stop_print()),
            self._native("set_temperature", self.native.set_temperature(nozzle=0, bed=0)),
        )
        _check_ack(results[0], "stop_print")
        _check_ack(results[1], "set_temperature")
        raise DriverFailed("MHS.DEVICE.NOT_READY", "MQTT echoes and cached status do not confirm a physical stop")

    # -- helpers --------------------------------------------------------------------------------------------------
    async def _native(self, what, awaitable):
        """Await one native call and translate the clone's own error classes without hiding a failure."""
        try:
            return await awaitable
        except (Busy, DriverFailed, OutcomeUnknown):
            raise
        except Exception as exc:  # noqa: BLE001 - translated below and re-raised when unknown
            name = type(exc).__name__
            message = f"{what}: {name}: {exc}"
            if name == "DeviceBusy":
                raise Busy(message) from exc
            if name in ("ConnectionFailed", "TimeoutExceeded"):
                raise OutcomeUnknown(message) from exc
            if name == "CommandRejected":
                raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", message) from exc
            raise
