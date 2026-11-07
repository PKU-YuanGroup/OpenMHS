# Facts and tags for gh.vcjdeboer/odyssey-app-hap

Every fact and limit in the driver cites the pinned clone at commit
`4dffe3a3ed0b32153c50b398ccac3fc7d30db7d1`. `vendor_doc` is documentation text of the clone; `upstream_code` is
code or a comment of the clone. The reference file is generated from `driver.py`, not from this page.

## Shape

The card names the PyLabRobot helper, but the Odyssey front end is not a PyLabRobot `LiquidHandler` and the device is
a scanner/imager. The helper's own guide sends other PyLabRobot machines to a direct `Driver`, so this package is a
direct `Driver` over the card's transport entry class `plr_v4.odyssey.connection:OdysseyDriver`
(`connection.py:223`). RESULT.json records the deviation.

The hardware backend is `.native:connect`, a thin adapter in `native.py` that imports the pinned upstream transport
and converts the driver's plain configuration mapping to `ScanParameters`. The fake is `.fake:FakeOdyssey`; it never
imports or runs the clone. The upstream simulator exists (`simulated.py:1-10`, `simulated.py:56-154`) but using it
would import and run code from the read-only clone, so this package does not use it. That is a package decision, not a
device fact, which is why it is not in the Fact list below.

## Native surface

| operation | upstream method | ref |
|---|---|---|
| open HTTP session | `OdysseyDriver.setup` | `connection.py:316-345` |
| close HTTP session (not a scanner stop) | `OdysseyDriver.stop` | `connection.py:347-351` |
| configure scan | `OdysseyDriver.configure_scan` | `connection.py:360-453` |
| wait for initialization | `OdysseyDriver.wait_initialization` | `connection.py:455-485` |
| start, stop, pause, cancel | `OdysseyDriver.start_scan`, `stop_scan`, `pause_scan`, `cancel_scan` | `connection.py:487-525` |
| status read | `OdysseyDriver.get_status` | `connection.py:544-566` |
| status-page stop | `OdysseyDriver.stop_from_status` | `connection.py:568-578` |
| JPEG preview | `OdysseyDriver.get_jpeg_preview` | `connection.py:659-687` |
| raw TIFF | `OdysseyDriver.download_tiff` | `connection.py:601-657` |
| imaging progress page | `OdysseyDriver.get_scan_progress` | `connection.py:580-597` |
| instrument information | `OdysseyDriver.get_instrument_info` | `connection.py:723-728` |

## Facts

| fact | source | ref |
|---|---|---|
| The Odyssey Classic is a LI-COR model 9120 infrared imaging system operated by a FastAPI control app over the instrument's embedded HTTP CGI interface. | vendor_doc | `README.md:3-9` |
| The upstream transport is an aiohttp client with Basic Auth for an Apache/mod_perl CGI interface reverse-engineered from the browser. | upstream_code | `connection.py:3-8` |
| The scan setup form posts to /scanapp/scan/nonjava/configure.pl and scan commands go to command.pl?action=start, stop, pause or cancel. | upstream_code | `connection.py:10-16` |
| configure.pl returns a 302 redirect to the initializing.pl countdown, and configure_scan follows the redirect to start hardware initialization. | upstream_code | `connection.py:360-408` |
| The full seven-step initializing.pl countdown must be polled before start because skipping it skips motor and laser warm-up. | upstream_code | `connection.py:455-464` |
| start_scan, stop_scan, pause_scan and cancel_scan send command.pl actions; an error page or "not configured" is raised. | upstream_code | `connection.py:487-525` |
| The status page returns the scanner state, current user, percent complete, time remaining and lid status. | upstream_code | `connection.py:544-566` |
| The status parser extracts the lid status from the status page. | upstream_code | `connection.py:780-786` |
| The device card declares a lid interlock. | upstream_code | `device_card.py:47-49` |
| stop_from_status posts action=Stop to the status page, is the documented way to release a paused or stuck scanner without the scan console, and returns the response text without checking it. | upstream_code | `connection.py:568-578` |
| After command.pl stop, stop_and_save polls the status page until the state reads idle or stopped and raises when that takes longer than _STOP_IDLE_TIMEOUT_SEC. | upstream_code | `scan_backend.py:103-117` |
| _STOP_IDLE_TIMEOUT_SEC is 15.0. | upstream_code | `scan_backend.py:38` |
| OdysseyDriver.stop closes the HTTP session; it is not a scanner stop. | upstream_code | `connection.py:347-351` |
| get_jpeg_preview fetches a JPEG preview the instrument renders server-side with the requested contrast, channels and background. | upstream_code | `connection.py:659-687` |
| download_tiff downloads one raw TIFF channel (700 or 800) from /scan/image/<name>-<channel>.tif. | upstream_code | `connection.py:601-618` |
| get_scan_progress reads the imaging info panel and returns dimensions, file size and time left. | upstream_code | `connection.py:580-597` |
| get_instrument_info fetches the instrument information page (serial number, software version). | upstream_code | `connection.py:723-728` |
| The 700 nm and 800 nm channels use 685 nm and 785 nm solid-state diode lasers with 80 mW peak power. | upstream_code | `device_card.py:26-40` |
| The device card records resolutions 21, 42, 84, 169 and 337 um, quality levels lowest through highest, intensity 0.5 to 10.0 in 0.5 steps, a 25 x 25 cm scan area and a 0.0 to 4.0 mm focus offset range. | upstream_code | `device_card.py:16-24` |
| The canonical instrument states are Idle, Configured, Initializing, Scanning, Paused, Stopped, Completed and Failed, and unrecognized status text is mapped to Idle. | upstream_code | `status_backend.py:27-67` |
| The upstream ships in-memory simulated scan, image and status backends. | upstream_code | `simulated.py:1-10` |
| Credentials are read from ODYSSEY_USER and ODYSSEY_PASS. | upstream_code | `connection.py:82-83` |
| When host is None, from_env reads ODYSSEY_HOST. | upstream_code | `connection.py:281-298` |

## Limits

| parameter | bound | source | ref | note |
|---|---|---|---|---|
| `resolution` | one of 21, 42, 84, 169, 337 or preview | upstream_code | `connection.py:96` | the line lists the values |
| `quality` | one of lowest, low, medium, high, highest | upstream_code | `connection.py:97` | the line lists the values |
| `intensity_700`, `intensity_800` | 0.5 to 10.0 | upstream_code | `device_card.py:19` | the 0.5 step on the next line is a setting step, not a numeric bound; the driver does not round |
| `origin_x_cm`, `origin_y_cm` | 0 to 25 cm | upstream_code | `connection.py:103`, `connection.py:104` | the docstring states 0-25 |
| `focus_offset_mm` | 0.0 to 4.0 mm | upstream_code | `connection.py:107` | the docstring states 0.0-4.0 |
| `width_cm` | operator_required | operator | `connection.py:105` (in the reason) | only origin_x + width <= 25 cm is stated; no minimum or site maximum is given |
| `height_cm` | operator_required | operator | `connection.py:106` (in the reason) | only origin_y + height <= 25 cm is stated; no minimum or site maximum is given |
| image `width`, `height` | operator_required | operator | the reason in `driver.py` | the preview is rendered at the instrument's size; the driver accepts only the actual size |
| image `exposure_ms` | operator_required | operator | the reason in `driver.py` | the preview endpoint has no exposure control; the driver accepts only 0 |
| image `format` | jpeg | upstream_code | `connection.py:668` | the upstream method fetches a JPEG preview |

`site-limits.example.json` is an example operator overlay for the operator-required ranges. It is not a fact about
any installed unit.

## Stop, safety and coverage

The e-stop method calls `OdysseyDriver.stop_from_status` and so does the `safe_state=True` extension action
`x-cap.vcjdeboer.odyssey_safe_stop.v1`. `native.py` bounds that status-page POST to two seconds and reports a timeout
as a failed safe state; it never claims the scanner stopped when the POST did not return. Model review (2026-11-05):
`stop_from_status` returns the response text unchecked, so a returned POST (even an error page) proved nothing; both
stop paths now read the status page afterwards and fail `MHS.SAFETY.SAFE_STATE_UNREACHED` unless it reports Idle or
Stopped, the states the upstream's own `stop_and_save` waits for (`scan_backend.py:103-117`, up to 15 s). A first
attempt can therefore be reported unreached while the instrument settles; the server retries the stop. This is a vendor HTTP
command, not a certified emergency stop, and the clone documents no independent hardware e-stop. The runtime software
latch is not a substitute for the instrument's own protective systems. The driver only reads the status-page lid
state; it does not claim an independent hardware interlock.

The driver does not expose raw TIFF download, the imaging progress page, the scan log, group/preset listing, the
administrator shutdown, or the upstream simulator. The JPEG preview is the covered image path; it is the
instrument-rendered preview, not the 16-bit raw TIFF. `cap.sensing.image.v1` publishes the preview bytes as an
`image/jpeg` artifact and reports the frame size parsed from the JPEG start-of-frame segment. The driver does not
decode pixels, infer colour, or provide the two raw channels.

The fake is an in-memory stand-in with canned progress, a placeholder 8 x 6 JPEG, and no TIFF data. It accepts scan
commands without enforcing the instrument's configure-before-start rule. No hardware run and no upstream simulator
run is claimed; the package was checked on the fake backend only.
