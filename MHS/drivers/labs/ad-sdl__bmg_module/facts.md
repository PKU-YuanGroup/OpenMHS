# Facts and tags for gh.ad-sdl/bmg_module

Every fact cites the pinned clone at commit `22d55c6036e91f0af8d0c398727aef226208896d`. The same facts are written
into `driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| BmgCom's constructor calls pythoncom.CoInitialize, creates the BMG_ActiveX.BMGRemoteControl COM object and opens the connection with the control name; open_connection raises when OpenConnection returns a non-zero result | upstream_code | sidecar/bmg_interface.py:18-36 |
| get_version returns the result of the COM GetVersion call; its docstring calls it the BMG instrument version | upstream_code | sidecar/bmg_interface.py:44-46 |
| The module's __main__ block connects with the control name CLARIOstar and prints get_version() as the BMG LABTECH Remote Control Version | upstream_code | sidecar/bmg_interface.py:155-157 |
| get_status and get_error return the COM GetInfo items 'Status' and 'Error' stripped, or the string 'unknown' when GetInfo returns something other than a string | upstream_code | sidecar/bmg_interface.py:48-58 |
| plate_in sends PlateIn and plate_out sends PlateOut through _exec (docstrings: close and open the plate tray), and neither checks the response | upstream_code | sidecar/bmg_interface.py:64-70 |
| set_temp documents 0.0 as off, 0.1 as monitor only, 25.0-45.0 for standard models and 10.0-60.0 for extended-temperature-range models; it raises ValueError unless the value is 0.0, 0.1 or inside the range the extended_temperature_range_model flag selects, sends the Temp command with str(temp) and raises when the ExecuteAndWait response is not 0 | upstream_code | sidecar/bmg_interface.py:72-90 |
| read_temps reads Temp1, Temp2 and Temp3 with GetInfo and divides each value by 10; its docstring gives the values in Celsius, or None per sensor when GetInfo returns no value (typical when the device has not been initialized in SMART Control or the sensor is not yet reporting), and a value float() cannot parse also gives None | upstream_code | sidecar/bmg_interface.py:92-112 |
| run_assay sends Run with the assay name, the protocol database path, the output directory, the three plate ids, the output directory again and the output file name (str(int(time.time())) + '.txt' when none is given), raises when the response is not 0 and returns the output directory joined with the file name | upstream_code | sidecar/bmg_interface.py:114-145 |
| The BmgCom class defines __init__, open_connection, close_connection, get_version, get_status, get_error, init, plate_in, plate_out, set_temp, read_temps, run_assay and _exec; init, plate_in, plate_out, set_temp and run_assay send their command through _exec, which calls ExecuteAndWait and returns its response, and the class has no stop, abort or pause method | upstream_code | sidecar/bmg_interface.py:15-152 |
| The upstream sidecar keeps BmgCom on one worker thread: the thread calls pythoncom.CoInitialize, constructs BmgCom and runs every call it takes from a queue, and on shutdown it closes the connection and calls pythoncom.CoUninitialize | upstream_code | sidecar/bmg_sidecar_server.py:31-87 |
| The sidecar README lists the endpoints /, /is_busy, /status, /error, /temps, /plate_out, /plate_in, /set_temp and /run_assay | vendor_doc | sidecar/README.md:16-28 |
| The MADSci REST node labels Temp1, Temp2 and Temp3 as the bottom heating plate, the top heating plate and the optic slide heating plate | upstream_code | src/bmg_rest_node.py:203-209 |
| The upstream README says the BMG driver can only connect to the device when run with 32-bit Python on a Windows machine | vendor_doc | README.md:15 |
| The upstream README says the model name must be entered as 'CLARIOstar' when the device is instantiated, even for a BMG VANTAstar | vendor_doc | README.md:50 |

## Scope

Served: the version, status and error strings, the three temperature sensors, the incubator set point and the
input-free heater-off action. NOT COVERED: the plate tray (`plate_in`, `plate_out`), `init` and the assay run
(`run_assay`, the reader's primary function). They are actuators, and the clone has no stop, abort or pause for any
of them: not in the BmgCom class (`sidecar/bmg_interface.py:15-152`), not among the sidecar's endpoints
(`sidecar/README.md:16-28`), and the MADSci node's actions are open, close, set_temp and run_assay
(`src/bmg_rest_node.py:215-308`). `plate_in` and `plate_out` also discard the ExecuteAndWait response
(`sidecar/bmg_interface.py:64-70`), so a refused tray command would not raise. An actuator without a source-backed stop
stays out of the package (the user's decision for this build). The repository's MADSci REST node and FastAPI sidecar
are other front ends to the same BmgCom class, not other devices.

## Limits

The incubator set point is `Limit.operator_required`. The upstream validator accepts 0.0 (off), 0.1 (monitor only),
25.0 to 45.0 Cel on a standard model and 10.0 to 60.0 Cel on an extended-temperature-range model
(`sidecar/bmg_interface.py:72-84`). Which range applies depends on the installed model and the
`extended_temperature_range_model` constructor option, so the driver does not choose one: every write is refused
`MHS.SAFETY.LIMITS_UNSET` until the site's `site-limits.json` states the range of its unit. `site-limits.example.json`
is an example overlay for a standard-range unit, not a statement about any installed device. The upstream validator
stays in force behind the overlay: a value it refuses fails the write. The safe-state action sends `set_temp(0.0)`
directly and therefore remains available without the write limit.

## Safety

The e-stop and the safe-state action `x-cap.ad-sdl.bmg_heater_off.v1` both send the native `set_temp(0.0)`, the
upstream-documented "off" value (`sidecar/bmg_interface.py:75`); a direct driver sends it twice per e-stop. The
upstream raises unless ExecuteAndWait answers 0 (`sidecar/bmg_interface.py:86-90`), so a completed stop is the
reader's acknowledgement of the off command; a refused or failed one gives `MHS.SAFETY.SAFE_STATE_UNREACHED` with the
latch held. The temperatures are not driven down, and no read of the device's set point exists: the served `setpoint`
is the last value written through the parameter, which the heater-off action and the e-stop do not change. The
fixture `fixtures/conformance.json` gives the gate a test set point (36.5 and 37.0 Cel, inside the standard validator
range), not a device fact. The upstream README documents no independent hardware e-stop, so `estop_physical_ref` is
not set; the input-free safe-state action is the SAFE-045 path. No `@reset` hook and no re-enable are declared: after a reset the heater stays off until a new set point is
written. The hardware factory keeps BmgCom on one COM thread, as the upstream sidecar does
(`sidecar/bmg_sidecar_server.py:31-87`), so the e-stop's Temp 0.0 waits for a call already running on that thread.
This package is unreviewed, so its R2 hardware backend is refused by the loader until a human sets `reviewed_by`.

Tags: microplate-reader, plate-reader, incubator, activex, windows
