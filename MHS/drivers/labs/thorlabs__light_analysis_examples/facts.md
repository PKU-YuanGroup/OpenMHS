# Facts and tags for gh.thorlabs/light_analysis_examples

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

Every fact cites its source at commit `1e7f3aa6fe29ca9739c582464bf870232232567b`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository's beam profiler examples cover the BC207VIS, BC210CV and BC210CU | vendor_doc | README.md:12 |
| TLBC2.py is the Python wrapper for the BC207 or BC210 beam profiler and loads the DLL for it | vendor_doc | Python/Thorlabs BC207 BC210 Beam Profiler/README.md:3-6 |
| The upstream class takes a resource name, an identification-query flag and a reset flag and loads TLBC2_32.dll on 32-bit or TLBC2_64.dll on 64-bit Python | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:158-181 |
| get_exposure_time returns a status code and writes exposure through a c_double output pointer | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:494-505 |
| The exposure time is in ms, and the supported range is queried from the instrument with get_exposure_time_range | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:476-514 |
| The gain is in dB, and the supported range is queried from the instrument | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:393-432 |
| The precision mode values are 0 = Fast and 1 = Precise | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:529-530 |
| The binning modes are 1, 2, 4, 8 and 16 | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:582-589 |
| The ROI is at most the full sensor size and at least 32 x 32 pixels; set_roi requires width and height multiples of 4 | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:622-660 |
| The sensor information reports pixel counts and the horizontal and vertical pixel pitch in um | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:594-608 |
| get_image requires a 2448*2048*2 byte output buffer and reports width, height and bytes per pixel (1 in fast mode, 2 in precision mode) | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1508-1517 |
| request_new_measurement reads a new image and stores the calculations internally for the get_XXXX functions | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1498-1506 |
| The scan-data structure stores fourSigmaX and fourSigmaY as standard deviations in pixels | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:97-98 |
| get_beam_width_4_sigma returns the second moment multiplied by 4 in x and y, the rotated widths, the azimuth angle and the ellipticity | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1665-1679 |
| get_centroid returns the centroid pixel position relative to the top left corner of the image | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1609-1621 |
| get_peak reports the peak intensity in digits, maximal 4096 in precision mode and 255 in fast mode | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1571-1581 |
| get_saturation reports ratios in the range 0.0 to 1.0 | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1589-1599 |
| get_power returns the total power in dBm | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1623-1628 |
| get_temperature returns the sensor temperature in Celsius degrees | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:1798-1803 |
| get_wavelength and set_wavelength operate in nm | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:906-924 |
| close closes the instrument session and the instrument must be reinitialized to use it again | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:229-239 |
| open initializes the instrument driver session: it opens a session, can query the identification, resets the instrument to a known state and sends it initialization commands | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py:201-208 |
| The sample adds the IVI Foundation VISA DLL directory before it loads the beam profiler DLL | upstream_code | Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2_sample_2D_output.py:34 |

Limits: exposure time and wavelength are `Limit.operator_required`. The clone states their units and that the
supported ranges are queried from the instrument (`get_exposure_time_range` at TLBC2.py:476-503,
`get_wavelength_range` at TLBC2.py:884-902), but no text file of the clone states a numeric range for a particular
unit; `site-limits.example.json` is an example operator overlay that fills them. Precision mode is limited to the
allowed set {0, 1} and binning to {1, 2, 4, 8, 16}, both stated by the clone at TLBC2.py:529-530 and 582-589.

Adapter: the upstream methods take ctypes output pointers and return a ViStatus code (TLBC2.py:494-505). The SDK
forbids importing ctypes from package code, so `native.py` imports the upstream module (which already imports the
ctypes names it needs), passes real pointers and fills one-element lists; `fake.py` mirrors that adapted surface.
The upstream method names and output-parameter order are preserved. This package is model-authored and unreviewed,
and the hardware path was never run.

Action and fake: the capture action retains requested exposure/ROI controls and calls `request_new_measurement`
and `get_image`. It requires an endpoint-owned command artifact publisher before native mutation and publishes
exact raw bytes; it never writes a standalone temporary file. The caller must retrieve the artifact through the
same authorized endpoint session. Width and height are actual returned dimensions. The package-specific opaque
media subtypes `application/vnd.thorlabs.tlbc2.raw8` and `application/vnd.thorlabs.tlbc2.raw16` mean one or two bytes
per pixel respectively. They do not establish byte order, calibration or PNG/JPEG display compatibility. No
bytes are truncated, converted or downsampled to fit a quota. The current SDK integration remains pending; a
quota refusal is a failed capture, never a successful local path. Full supported geometry needs a bounded
10,027,008-byte artifact allowance. The fake's 64 x 48 geometry and measurement values are placeholders, not
vendor device facts. The beam-analysis command retains all its original output fields. Its logarithmic
`total_power_dbm` field describes dBm explicitly; it no longer labels dBm as dimensionless UCUM `1`.

Safety: `close()` closes the owned instrument session (TLBC2.py:229-239); it does not certify that an external
optical source is off. All native calls are serialized. Stop immediately fences admission, refuses safe-state
acknowledgment while a native call is active, and closes the session only after that call returns. Owned teardown
also closes the SDK exactly once after active native work settles. A stuck DLL call remains unresolved; no
thread is killed and no native close races that call. The closing state is irreversible, including during a
blocked close or failed cleanup. Upstream: a closed session must be reinitialized before it is used again
(TLBC2.py:229-239), and reinitializing it with `open()` resets the instrument to a known state and sends it
initialization commands (TLBC2.py:201-208). Package policy: a reset may only re-establish communication that changes
nothing on the device (CORE-087), so this package never reopens or reinitializes the session in a reset, and the
e-stop is declared terminal (`estop_terminal`, CORE-087, SAFE-048): after an e-stop the endpoint refuses every
reset with `MHS.SAFETY.RESET_REFUSED` (`terminal_estop`,
with the declared reason) without calling the bridge, and keeps the latch. Recovery is a new endpoint with a
new session, on which an operator resets the latch it restores. The package has no `@reset` hook (the runtime
now refuses the reset itself), so a reset never runs native code and nothing reopens the session, whose closing
state is irreversible. G8's TSAFE-001 checks
the refusal and the retained latch, and the suite gives every later test a new endpoint (CON-022); no reset
success is faked. No independent physical stop is documented or claimed. The retained selected
camera/measurement scope is R1, with operator exposure and wavelength limits unchanged.

Factory ownership: the hardware factory alone imports the selected upstream module and opens the device. It
retains the Windows DLL-directory object until SDK cleanup, closes owned resources on failed discovery/open,
and permits one owned SDK lifecycle per loaded package in a process. External SDK users must not share that
process: upstream does not document `closeSDK` as safe for unrelated sessions. This software ownership rule is
not proof of physical deployment isolation. No DLL, Windows device or physical camera has been exercised.

Tags: beam-profiler, camera, thorlabs, bc207, bc210, ctypes, windows

The beam-width azimuth is preserved as the native reported number without a unit claim. TLBC2.py:1678 and scan-data field line 106 do not state its unit; degrees stated by other rotation/ellipse methods are not evidence for this field.
