# Facts and tags for gh.kyleellefsen/light_sheet_controller

This package drives `light_sheet_controller:LightSheetDriver`
(`light_sheet_controller.py:118`) at commit `69ce700174c9498f7ad27925b751ed47e45ce3b3`. The class generates the
piezo scan, camera TTL, dither and laser TTL waveforms on two NI USB-6001 boards. It is a Qt widget and a
desktop application, not a vendor SDK client. The package is model-authored and unreviewed
(`driver.lock.json` `reviewed_by` is null), so it runs only on the fake backend; the loader refuses its R2
hardware backend until a human signs the lock.

The same facts are in `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The controller expects two NI USB-6001 boards as Dev1 and Dev2 and warns that it continues in test mode when either board is absent or is another product type | upstream_code | light_sheet_controller.py:46-57 |
| createTask builds two analog-output tasks: Dev1/ao0 is the piezo channel, Dev1/ao1 the camera TTL, Dev2/ao0 the dither and Dev2/ao1 the laser TTL, each configured from -10.0 to 10.0 V | upstream_code | light_sheet_controller.py:133-144 |
| createTask starts both analog-output tasks and sets stopped to False | upstream_code | light_sheet_controller.py:145-148 |
| startstop from the stopped state recalculates and restarts both tasks; from the running state it stops both tasks, returns the dither to zero and sets stopped to True | upstream_code | light_sheet_controller.py:159-173 |
| refresh recalculates the waveform, stops both tasks, configures continuous sampling and restarts both tasks while the controller is not stopped | upstream_code | light_sheet_controller.py:175-188 |
| gotozero writes a finite zero waveform to the piezo and camera TTL channels, sleeps 0.2 s, stops the task, returns the dither to zero and sets stopped to True | upstream_code | light_sheet_controller.py:204-218 |
| gotoend drives the piezo to maximum_displacement * mV_per_pixel / 1000 V, sleeps 0.2 s, stops the task, returns the dither to zero and sets stopped to True | upstream_code | light_sheet_controller.py:220-235 |
| gotobluelaser sets the blue_laser_on setting to True and gotoyellowlaser sets it to False | upstream_code | light_sheet_controller.py:237-265 |
| calc_ttl writes 6 V on the laser TTL when alternate_lasers is set (in one segment) or when blue_laser_on is true (the whole array), and zeros otherwise | upstream_code | calc_waveforms.py:140-150 |
| The generated piezo waveform is clamped to -10.0 to 10.0 V and the code asserts the clamp | upstream_code | calc_waveforms.py:80-87 |
| The settings are mV_per_pixel in mV/pixel, maximum_displacement and offset in pixels, nSteps as a count, step_duration and flyback_duration in ms, total_cycle_period in s and dither_amp in mV | upstream_code | light_sheet_controller.py:388-395 |
| start_light_sheet_controller builds a Qt application, checks the NI devices and constructs MainGui | upstream_code | light_sheet_controller.py:539-544 |
| calc_waveforms imports numpy, scipy.ndimage and QtWidgets from qtpy | upstream_code | calc_waveforms.py:1-3 |
| The controller module imports numpy, PyDAQmx, qtpy and pyqtgraph | upstream_code | light_sheet_controller.py:15-29 |
| calcPiezoWaveform applies scipy.ndimage.filters.gaussian_filter1d with sigma 3 | upstream_code | calc_waveforms.py:75-76 |
| Settings loads ~/.lightsheet/config.p with pickle and uses defaults only after an IOError | upstream_code | light_sheet_controller.py:73-92 |
| dither_gotozero computes calc_ttl, stops task two, writes with timeout -1, briefly starts it and stops it again | upstream_code | light_sheet_controller.py:190-202 |

## Reads

The driver publishes the controller's own attributes: `stopped`, `blue_laser_on`, `alternate_lasers`,
`triangle_scan`, `sample_rate`, `samples_per_period` and the eight waveform settings (`n_steps`,
`step_duration`, `flyback_duration`, `total_cycle_period`, `dither_amp`, `offset`, `maximum_displacement`,
`mv_per_pixel`). These are configuration and task state, not measurements: the clone exposes no readback of
the analog output voltage, the actual piezo position or the emitted laser power.

## Limits

Every numeric setting write is `Limit.operator_required`, because no text of the clone states a safe range for
the installed piezo, objective, camera or sample. The GUI does construct sliders with ranges
(`light_sheet_controller.py:376-383`), but a slider range is a bound of the desktop application's controls, not
a statement that the range is safe for a particular instrument, and the constructor defaults are likewise
configuration values (`light_sheet_controller.py:75-92`). Every write is therefore refused
`MHS.SAFETY.LIMITS_UNSET` until the operator's `site-limits.json` supplies a range. `site-limits.example.json`
is an example only; its numbers are the upstream sliders' ranges and are not device facts. The generated piezo
waveform is clamped to +/-10 V by `calc_waveforms.py:80-87`, but that clamp is an output limit, not a safe
motion or illumination limit.

The two boolean settings (`triangle_scan`, `alternate_lasers`) have no numeric bound; the
`x-cap.kyleellefsen.set_scan_mode.v1` action sets them. `blue_laser_on` is read-only; it is changed only by the
laser-selection action and by the stop path.

A settings write while the scan is running calls the upstream `refresh()`, which stops both tasks, rewrites the
waveform and restarts them (`light_sheet_controller.py:175-188`); that is a brief interruption of the output, not
a safe stop. While the scan is stopped the write only recalculates the arrays with `calculate()` and the new
settings take effect on the next `startstop()` (`light_sheet_controller.py:159-168`).

## Stop, e-stop and safe state

There is no upstream `stop()` method. `startstop()` toggles the running state
(`light_sheet_controller.py:159-173`), and `gotozero()` requests finite zero piezo and camera waveforms
before calling `dither_gotozero()` (`204-218`). The latter builds its TTL from `calc_ttl` (`190-202`).
Clearing `alternate_lasers` and `blue_laser_on` makes that TTL zero (`calc_waveforms.py:140-150`), but zero
TTL is also the path used by `gotoyellowlaser` (`light_sheet_controller.py:261-281`). Neither laser-off nor
emission confirmation is shown by these sources. A cached `stopped=True` flag does not establish either.

`x-cap.kyleellefsen.stop_scan.v1` is an ordinary zeroing action and has no `safe_state=True` designation.
The `@estop` hook attempts that zeroing and then raises `MHS.SAFETY.SAFE_STATE_UNREACHED`; the endpoint
keeps the latch held. The source provides no independent physical stop to satisfy SAFE-045 at R2. This is
an expected blocked gate, not accepted safety evidence. Recovery needs an external verified stop path.

Construction starts both continuous tasks immediately from the settings loaded by `Settings()`
(`light_sheet_controller.py:73-92,120-147`), before an endpoint envelope can apply. The factory's later
`gotozero()` neither prevents that initial output nor clears the saved laser flags. DAQ writes in the zeroing
path use timeout -1 (`190-218`), and `calc_ttl` calls the piezo calculation whose clamps can open modal warning
dialogs (`calc_waveforms.py:80-87,140-142`). Therefore the short sleeps do not bound this stop's duration.
The fake models no construction transient, DAQ blocking or laser emission. No upstream code was run.

## Fake fidelity

`fake.py` is an in-memory F0 stand-in, not a recording and not the upstream simulator (the clone has neither).
It implements only methods and attributes that exist on `LightSheetDriver` in the pinned source. Its starting
numbers are placeholders, marked `# placeholder`; they are not copied into a Fact or a Limit. It models the
start/stop toggle, the stop and end paths, the two laser-selection methods and the settings dictionary; it
models no DAQ timing, no finite-sample waveform, no Qt event loop and no physical output. `test_driver.py`
exercises the adapter through the stock server; fake evidence is `contract_checked`, never an MHS-Device level
and never a hardware run.

## Deployment assumptions and gaps

* The clone has no setup.py and the card's install block is empty; `native.py` accepts `clone_root` and inserts
  it on `sys.path`. PyDAQmx, qtpy, pyqtgraph, numpy and scipy must be installed by the deployment. The
  upstream clone was never imported or installed by this package.
* NI MAX must expose the two USB-6001 boards as Dev1 and Dev2 (`light_sheet_controller.py:7,46-57`).
* The driver exposes the DAQ waveform controller only. The camera TTL is an output; no camera image, no
  camera settings and no camera status are captured. The laser TTL is an output; no laser power, wavelength,
  class, shutter or emission sensor is read. The piezo is open-loop; no position sensor is read.
* The upstream GUI remains the only documented way to visualise waveforms and to select the saved settings
  (`light_sheet_controller.py:518-537`); the driver does not reproduce the GUI.
* The 0.2 s and 0.02 s sleeps (`light_sheet_controller.py:201,215,232`) do not bound the DAQ calls or modal
  dialogs. The runtime can report a failed stop while a native call is still running.
* Importing the upstream module changes the process working directory (`light_sheet_controller.py:14-19`),
  and `Settings()` deserializes a local pickle (`73-77`). Qt widget construction also depends on the deployment's
  application and thread ownership. These production lifecycle hazards remain unresolved in this blocked package.

Tags: light-sheet, piezo, ni-daqmx, usb-6001, laser-ttl, waveform
