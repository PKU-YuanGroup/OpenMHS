"""OpenMHS driver for gh.vcjdeboer/odyssey-app-hap: the LI-COR Odyssey Classic 9120 infrared imager.

A direct ``Driver`` over the card's transport entry class
``plr_v4.odyssey.connection:OdysseyDriver`` (connection.py:223).  The upstream class speaks the instrument's
embedded Apache/mod_perl CGI interface over HTTP Basic Auth: configure.pl (connection.py:360), command.pl
(connection.py:487-525), the status page (connection.py:544-566), the status-page Stop (connection.py:568-578), the
server-rendered JPEG preview (connection.py:659-687) and the instrument information page (connection.py:723-728).

The card names the PyLabRobot helper.  The repository vendors a PyLabRobot-adjacent prototype, but the Odyssey
front end is not a PyLabRobot ``LiquidHandler`` and this device is a scanner/imager, so the helper cannot express it
(the helper's own guide sends other PyLabRobot machines to a direct Driver).  This package is therefore a direct
Driver; RESULT.json records the card deviation.

Covered:
* writes through ``cap.device.configure.v1``: scan name, group, resolution, quality, both intensity values, both
  channel enables, origin, width, height and focus, sent together to configure.pl and then followed by the full
  seven-step initializing.pl poll (connection.py:360-485);
* reads: state, progress, time remaining, current user, lid status, instrument information and the configuration
  the driver will send;
* ``x-cap.vcjdeboer.odyssey_control_scan.v1``: start, pause, stop and cancel through command.pl
  (connection.py:487-525);
* ``cap.sensing.image.v1``: the instrument-rendered JPEG preview of the configured scan as a bounded local artifact;
* ``x-cap.vcjdeboer.odyssey_safe_stop.v1`` and ``@estop``: the status-page Stop command (connection.py:568-578).

The raw TIFF channels (connection.py:601-657) and the imaging progress page (connection.py:580-597) are not
covered; RESULT.json says so.  The upstream simulator exists (simulated.py:56-154) but this package does not import
or run anything from the read-only clone, so it uses its own package fake.

Every Fact and Limit cites a line of the clone at the pinned commit
4dffe3a3ed0b32153c50b398ccac3fc7d30db7d1.  The package is model-authored and unreviewed; it was checked on the fake
backend only and no hardware or upstream simulator run is claimed.
"""

from __future__ import annotations

from mhs.artifacts import publisher_from_context
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

CONNECTION = "plr_v4/odyssey/connection.py"
DEVICE_CARD = "plr_v4/odyssey/device_card.py"
STATUS_BACKEND = "plr_v4/odyssey/status_backend.py"
SCAN_BACKEND = "plr_v4/odyssey/scan_backend.py"

#: Model review: the status-page states that confirm a stop, the set the upstream's own stop_and_save waits for after
#: a Stop (scan_backend.py:105-117).  Any other state, including the parser's "Unknown", is not a confirmed stop.
_STOPPED_STATES = frozenset({"idle", "stopped"})

#: JPEG start-of-frame markers that carry the frame height and width.
_SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})

#: The next configuration the driver will send.  These are the upstream ScanParameters defaults
#: (connection.py:113-127), not device measurements and not limits.
_DEFAULTS = {
    "name": "scan",
    "group": "odyssey",
    "resolution": "169",
    "quality": "medium",
    "intensity_700": 5.0,
    "intensity_800": 5.0,
    "channel_700": True,
    "channel_800": True,
    "origin_x": 0,
    "origin_y": 0,
    "width": 10,
    "height": 10,
    "focus": 0.0,
}


def _intensity_text(value: float) -> str:
    """Render a numeric intensity as the configure.pl form value the upstream expects (a string)."""
    value = float(value)
    return str(int(value)) if value.is_integer() else str(value)


def _jpeg_size(data: bytes) -> tuple[int, int]:
    """Return the frame width and height from a JPEG start-of-frame segment.

    This reads the marker segments only; it does not decode pixels, infer colour or validate entropy data.
    """
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise DriverFailed("MHS.DEVICE.FAULTED", "the instrument preview is not a JPEG stream")
    index = 2
    while index + 3 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker == 0xD9 or marker == 0xDA:       # EOI or start of scan: no frame header follows
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in _SOF_MARKERS:
            if length < 7:
                break
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            if width < 1 or height < 1:
                break
            return width, height
        index += length
    raise DriverFailed("MHS.DEVICE.FAULTED", "the instrument preview has no usable JPEG frame header")


class OdysseyClassic(Driver):
    """LI-COR Odyssey Classic 9120 infrared imager, driven over its HTTP CGI interface."""

    device_id = "odyssey-classic"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R2"
    native = "plr_v4.odyssey.connection:OdysseyDriver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOdyssey"}
    vendor, model = "LI-COR Biosciences", "Odyssey Classic 9120"
    display_name = "LI-COR Odyssey Classic 9120 infrared imager (CGI over HTTP)"
    tags = ["scanner", "infrared", "fluorescence", "western-blot", "li-cor", "odyssey", "http", "cgi"]
    safe_state = (
        "the status-page Stop command is sent (POST bounded to two seconds) and the stop holds only when a fresh "
        "status read then reports Idle or Stopped, the states the upstream's stop_and_save waits for; that wait may "
        "last up to 15 s upstream, so an attempt can be reported unreached and is retried; any other state, a timeout "
        "or an error is a failed safe state; lid, lasers and queued firmware work are not confirmed"
    )
    facts = [
        Fact("The Odyssey Classic is a LI-COR model 9120 infrared imaging system operated by a FastAPI control "
             "app over the instrument's embedded HTTP CGI interface", source="vendor_doc", ref="README.md:3-9"),
        Fact("The upstream transport is an aiohttp client with Basic Auth for an Apache/mod_perl CGI interface "
             "reverse-engineered from the browser", source="upstream_code", ref=CONNECTION + ":3-8"),
        Fact("The scan setup form posts to /scanapp/scan/nonjava/configure.pl and scan commands go to "
             "command.pl?action=start|stop|pause|cancel", source="upstream_code", ref=CONNECTION + ":10-16"),
        Fact("configure.pl returns a 302 redirect to the initializing.pl countdown, and configure_scan follows "
             "the redirect to start hardware initialization", source="upstream_code", ref=CONNECTION + ":360-408"),
        Fact("The full seven-step initializing.pl countdown must be polled before start because skipping it skips "
             "motor and laser warm-up", source="upstream_code", ref=CONNECTION + ":455-464"),
        Fact("start_scan, stop_scan, pause_scan and cancel_scan send command.pl actions start, stop, pause and "
             "cancel; an error page or 'not configured' is raised", source="upstream_code",
             ref=CONNECTION + ":487-525"),
        Fact("The status page returns the scanner state, current user, percent complete, time remaining and lid "
             "status", source="upstream_code", ref=CONNECTION + ":544-566"),
        Fact("The status parser extracts the lid status from the status page", source="upstream_code",
             ref=CONNECTION + ":780-786"),
        Fact("The device card declares a lid interlock", source="upstream_code", ref=DEVICE_CARD + ":47-49"),
        Fact("stop_from_status posts action=Stop to the status page, is the documented way to release a paused "
             "or stuck scanner without the scan console, and returns the response text without checking it",
             source="upstream_code", ref=CONNECTION + ":568-578"),
        Fact("After command.pl stop, stop_and_save polls the status page until the state reads idle or stopped and "
             "raises when that takes longer than _STOP_IDLE_TIMEOUT_SEC", source="upstream_code",
             ref=SCAN_BACKEND + ":103-117"),
        Fact("_STOP_IDLE_TIMEOUT_SEC is 15.0", source="upstream_code", ref=SCAN_BACKEND + ":38"),
        Fact("OdysseyDriver.stop closes the HTTP session; it is not a scanner stop", source="upstream_code",
             ref=CONNECTION + ":347-351"),
        Fact("get_jpeg_preview fetches a JPEG preview the instrument renders server-side with the requested "
             "contrast, channels and background", source="upstream_code", ref=CONNECTION + ":659-687"),
        Fact("download_tiff downloads one raw TIFF channel (700 or 800) from /scan/image/<name>-<channel>.tif",
             source="upstream_code", ref=CONNECTION + ":601-618"),
        Fact("get_scan_progress reads the imaging info panel and returns dimensions, file size and time left",
             source="upstream_code", ref=CONNECTION + ":580-597"),
        Fact("get_instrument_info fetches the instrument information page (serial number, software version)",
             source="upstream_code", ref=CONNECTION + ":723-728"),
        Fact("The device card records 700 nm and 800 nm solid-state diode lasers with 80 mW peak power each",
             source="upstream_code", ref=DEVICE_CARD + ":26-40"),
        Fact("The device card records scan resolutions 21, 42, 84, 169 and 337 um, quality levels lowest through "
             "highest, an intensity range of 0.5 to 10.0 in 0.5 steps, a 25 x 25 cm scan area and a focus offset "
             "range of 0.0 to 4.0 mm", source="upstream_code", ref=DEVICE_CARD + ":16-24"),
        Fact("The canonical instrument states are Idle, Configured, Initializing, Scanning, Paused, Stopped, "
             "Completed and Failed, and unrecognized status text is mapped to Idle", source="upstream_code",
             ref=STATUS_BACKEND + ":27-67"),
        Fact("The upstream ships in-memory simulated scan, image and status backends", source="upstream_code",
             ref="plr_v4/odyssey/simulated.py:1-10"),
        Fact("Credentials are read from ODYSSEY_USER and ODYSSEY_PASS", source="upstream_code",
             ref=CONNECTION + ":82-83"),
        Fact("When host is None, from_env reads ODYSSEY_HOST", source="upstream_code", ref=CONNECTION + ":281-298"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._config = dict(_DEFAULTS)

    # -- lifecycle -------------------------------------------------------------------------------------------
    async def setup(self):
        """Open the upstream HTTP session (connection.py:316-345)."""
        if not getattr(self, "_config", None):
            self._config = dict(_DEFAULTS)
        await self.native.setup()

    async def teardown(self):
        """Close the upstream HTTP session (connection.py:347-351); this is not a scanner stop."""
        await self.native.stop()

    # -- configuration ---------------------------------------------------------------------------------------
    async def _apply(self, **changes):
        candidate = dict(self._config)
        candidate.update(changes)
        payload = {
            "name": str(candidate["name"]),
            "group": str(candidate["group"]),
            "resolution": str(candidate["resolution"]),
            "quality": str(candidate["quality"]),
            "intensity_700": _intensity_text(candidate["intensity_700"]),
            "intensity_800": _intensity_text(candidate["intensity_800"]),
            "channel_700": bool(candidate["channel_700"]),
            "channel_800": bool(candidate["channel_800"]),
            "origin_x": int(candidate["origin_x"]),
            "origin_y": int(candidate["origin_y"]),
            "width": int(candidate["width"]),
            "height": int(candidate["height"]),
            "focus": float(candidate["focus"]),
        }
        await self.native.configure_scan(payload)
        self.check_cancelled()
        await self.native.wait_initialization(payload["name"], payload["group"])
        self.check_cancelled()
        self._config = candidate

    @write("scan_name", type=Field("string",
                                   pattern=r'^[^;/?:@=&<>"#%{}|^~\[\]]+$',
                                   description="Scan name"),
           description="Scan name")
    async def set_scan_name(self, value):
        await self._apply(name=str(value))
        return str(value)

    @write("scan_group", type="string", description="Scan group")
    async def set_scan_group(self, value):
        await self._apply(group=str(value))
        return str(value)

    @write("resolution", type="string",
           limit=Limit(allowed=["21", "42", "84", "169", "337", "preview"], source="upstream_code",
                       ref=CONNECTION + ":96"),
           description="Resolution in um or preview")
    async def set_resolution(self, value):
        await self._apply(resolution=str(value))
        return str(value)

    @write("quality", type="string",
           limit=Limit(allowed=["lowest", "low", "medium", "high", "highest"], source="upstream_code",
                       ref=CONNECTION + ":97"),
           description="Quality level")
    async def set_quality(self, value):
        await self._apply(quality=str(value))
        return str(value)

    @write("intensity_700", unit="1",
           limit=Limit(min=0.5, max=10.0, source="upstream_code", ref=DEVICE_CARD + ":19"),
           description="700 nm intensity")
    async def set_intensity_700(self, value):
        await self._apply(intensity_700=float(value))
        return float(value)

    @write("intensity_800", unit="1",
           limit=Limit(min=0.5, max=10.0, source="upstream_code", ref=DEVICE_CARD + ":19"),
           description="800 nm intensity")
    async def set_intensity_800(self, value):
        await self._apply(intensity_800=float(value))
        return float(value)

    @write("channel_700", type="boolean", description="Enable 700 nm channel")
    async def set_channel_700(self, value):
        await self._apply(channel_700=bool(value))
        return bool(value)

    @write("channel_800", type="boolean", description="Enable 800 nm channel")
    async def set_channel_800(self, value):
        await self._apply(channel_800=bool(value))
        return bool(value)

    @write("origin_x_cm", type="integer", unit="cm",
           limit=Limit(min=0, max=25, source="upstream_code", ref=CONNECTION + ":103"),
           description="Origin X in cm")
    async def set_origin_x_cm(self, value):
        await self._apply(origin_x=int(value))
        return int(value)

    @write("origin_y_cm", type="integer", unit="cm",
           limit=Limit(min=0, max=25, source="upstream_code", ref=CONNECTION + ":104"),
           description="Origin Y in cm")
    async def set_origin_y_cm(self, value):
        await self._apply(origin_y=int(value))
        return int(value)

    @write("width_cm", type="integer", unit="cm",
           limit=Limit.operator_required(
               "the clone states only origin_x + width <= 25 cm (connection.py:105) and gives no minimum width or "
               "site-specific maximum; the operator supplies the usable range"),
           description="Width in cm")
    async def set_width_cm(self, value):
        await self._apply(width=int(value))
        return int(value)

    @write("height_cm", type="integer", unit="cm",
           limit=Limit.operator_required(
               "the clone states only origin_y + height <= 25 cm (connection.py:106) and gives no minimum height or "
               "site-specific maximum; the operator supplies the usable range"),
           description="Height in cm")
    async def set_height_cm(self, value):
        await self._apply(height=int(value))
        return int(value)

    @write("focus_offset_mm", unit="mm",
           limit=Limit(min=0.0, max=4.0, source="upstream_code", ref=CONNECTION + ":107"),
           description="Focus offset in mm")
    async def set_focus_offset_mm(self, value):
        await self._apply(focus=float(value))
        return float(value)

    # -- state reads -----------------------------------------------------------------------------------------
    @read("scan_name", type="string", description="Scan name the driver will send to configure.pl")
    async def scan_name(self):
        return str(self._config["name"])

    @read("scan_group", type="string", description="Scan group the driver will send to configure.pl")
    async def scan_group(self):
        return str(self._config["group"])

    @read("resolution", type="string", description="Configured scan resolution")
    async def resolution(self):
        return str(self._config["resolution"])

    @read("quality", type="string", description="Configured scan quality")
    async def quality(self):
        return str(self._config["quality"])

    @read("intensity_700", unit="1", description="Configured 700 nm channel intensity")
    async def intensity_700(self):
        return float(self._config["intensity_700"])

    @read("intensity_800", unit="1", description="Configured 800 nm channel intensity")
    async def intensity_800(self):
        return float(self._config["intensity_800"])

    @read("channel_700", type="boolean", description="Whether the 700 nm channel is enabled")
    async def channel_700(self):
        return bool(self._config["channel_700"])

    @read("channel_800", type="boolean", description="Whether the 800 nm channel is enabled")
    async def channel_800(self):
        return bool(self._config["channel_800"])

    @read("origin_x_cm", type="integer", unit="cm", description="Configured scan origin X in cm")
    async def origin_x_cm(self):
        return int(self._config["origin_x"])

    @read("origin_y_cm", type="integer", unit="cm", description="Configured scan origin Y in cm")
    async def origin_y_cm(self):
        return int(self._config["origin_y"])

    @read("width_cm", type="integer", unit="cm", description="Configured scan width in cm")
    async def width_cm(self):
        return int(self._config["width"])

    @read("height_cm", type="integer", unit="cm", description="Configured scan height in cm")
    async def height_cm(self):
        return int(self._config["height"])

    @read("focus_offset_mm", unit="mm", description="Configured focus offset in mm")
    async def focus_offset_mm(self):
        return float(self._config["focus"])

    @read("state", type="string", description="Scanner state reported by the status page")
    async def state(self):
        status = await self.native.get_status()
        return str(status.get("state", ""))

    @read("progress_percent", unit="%",
          description="Percent complete reported by the status page; 0.0 when the page shows no number")
    async def progress_percent(self):
        status = await self.native.get_status()
        raw = str(status.get("progress", "")).strip().rstrip("%").strip()
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    @read("time_remaining", type="string", description="Time remaining reported by the status page")
    async def time_remaining(self):
        status = await self.native.get_status()
        return str(status.get("time_remaining", ""))

    @read("current_user", type="string", description="Current user reported by the status page")
    async def current_user(self):
        status = await self.native.get_status()
        return str(status.get("current_user", ""))

    @read("lid_open", type="boolean", description="Whether the status page reports the lid open")
    async def lid_open(self):
        status = await self.native.get_status()
        return str(status.get("lid_status", "closed")).strip().lower() != "closed"

    @read("instrument_info", type="string", description="Instrument information page text")
    async def instrument_info(self):
        return str(await self.native.get_instrument_info())

    # -- scan control ----------------------------------------------------------------------------------------
    @action(name="x-cap.vcjdeboer.odyssey_control_scan.v1", risk="R2",
            description="Start, pause, stop or cancel the configured scan through command.pl",
            input={
                "command": Field("string", description="Scan command to send to command.pl",
                                 limit=Limit(allowed=["start", "pause", "stop", "cancel"], source="upstream_code",
                                             ref=CONNECTION + ":13")),
            },
            output={"state": Field("string", description="Scanner state after the command")})
    async def control_scan(self, command):
        if command == "start":
            await self.native.start_scan()
        elif command == "pause":
            await self.native.pause_scan()
        elif command == "stop":
            await self.native.stop_scan()
        elif command == "cancel":
            await self.native.cancel_scan()
        else:  # the input schema refuses this before the method; keep the method honest if called directly
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "command must be start, pause, stop or cancel")
        self.check_cancelled()
        status = await self.native.get_status()
        return {"state": str(status.get("state", ""))}

    async def _stop_and_confirm(self):
        """Send the status-page Stop, then require a fresh status read of Idle or Stopped (model review).

        stop_from_status returns the response text unchecked (connection.py:568-578), so a returned POST proves
        nothing; the upstream's own stop_and_save confirms a stop by the status page (scan_backend.py:103-117).
        """
        await self.native.stop_from_status()
        status = await self.native.get_status()
        state = str(status.get("state", "")).strip()
        if state.lower() not in _STOPPED_STATES:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"after the status-page Stop the status page reports {state!r}, not Idle or Stopped")
        return state

    @action(name="x-cap.vcjdeboer.odyssey_safe_stop.v1", safe_state=True, risk="R2",
            description="Send the status-page Stop and confirm the status page then reports Idle or Stopped",
            output={"stopped": Field("boolean", description="True once the status page reported Idle or Stopped"),
                    "state": Field("string", description="Scanner state read after the Stop")})
    async def safe_stop(self):
        state = await self._stop_and_confirm()
        return {"stopped": True, "state": state}

    @estop(native="stop_from_status")
    async def stop(self):
        """The native stop path: the status-page Stop (connection.py:568-578), confirmed by a fresh status read."""
        await self._stop_and_confirm()

    # -- image capture ---------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1", risk="R1",
            description="Fetch the instrument-rendered JPEG preview of the configured scan as a bounded artifact",
            input={
                "camera": Field("string", description="Channel selector: 700, 800 or both; the preview is "
                                                      "rendered for the named channel or both channels"),
                "format": Field("string", description="Only jpeg is available from this preview endpoint",
                                limit=Limit(allowed=["jpeg"], source="upstream_code", ref=CONNECTION + ":668")),
                "width": Field("integer", unit="1",
                               description="Requested preview width; it must equal the instrument-rendered width",
                               limit=Limit.operator_required(
                                   "the instrument renders the preview at its own width; no text of the clone "
                                   "states a usable request range and the driver accepts only the actual width, so "
                                   "the operator supplies the bound")),
                "height": Field("integer", unit="1",
                                description="Requested preview height; it must equal the instrument-rendered height",
                                limit=Limit.operator_required(
                                    "the instrument renders the preview at its own height; no text of the clone "
                                    "states a usable request range and the driver accepts only the actual height, "
                                    "so the operator supplies the bound")),
                "exposure_ms": Field("number", unit="ms",
                                     description="Only 0 (no exposure override) is accepted; the preview endpoint "
                                                 "has no exposure control",
                                     limit=Limit.operator_required(
                                         "the JPEG preview endpoint has no exposure parameter; no text of the "
                                         "clone states a requestable exposure range, the driver accepts only 0 as "
                                         "no override, and the operator supplies the bound")),
            })
    async def capture(self, camera=None, exposure_ms=None, format=None, width=None, height=None):
        if format not in (None, "jpeg"):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "the preview endpoint returns JPEG; format must be jpeg or omitted")
        if exposure_ms not in (None, 0, 0.0):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "the preview endpoint has no exposure control; omit exposure_ms or send 0")
        if camera in (None, "", "both"):
            channels = "700 800"
        elif str(camera) in ("700", "800"):
            channels = str(camera)
        else:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "camera must be 700, 800 or both for this two-channel imager")
        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "image capture requires an endpoint-owned artifact store")
        data = await self.native.get_jpeg_preview(
            str(self._config["group"]), str(self._config["name"]), channels=channels
        )
        self.check_cancelled()
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the instrument returned no JPEG preview")
        image = bytes(data)
        actual_width, actual_height = _jpeg_size(image)
        if width is not None and int(width) != actual_width:
            raise DriverFailed(
                "MHS.CAPABILITY.INPUT_INVALID",
                f"the instrument rendered a {actual_width} pixel wide preview, not the requested {width}",
            )
        if height is not None and int(height) != actual_height:
            raise DriverFailed(
                "MHS.CAPABILITY.INPUT_INVALID",
                f"the instrument rendered a {actual_height} pixel high preview, not the requested {height}",
            )
        if len(image) > publisher.max_bytes:
            raise DriverFailed(
                "MHS.DEVICE.NOT_READY",
                f"the JPEG preview is {len(image)} bytes, above the artifact store bound {publisher.max_bytes}",
            )
        publisher.preflight(len(image))
        descriptor = publisher.publish(image, "image/jpeg")
        return {
            "image_ref": descriptor["uri"],
            "width": actual_width,
            "height": actual_height,
            "media_type": "image/jpeg",
        }
