# Facts and tags for gh.wetenschaap/pycrofluidics

Every fact cites its source at commit `319de9d08c1a5f39ddd5030c98d8c356fbfb0f9c`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| setPressure() calls OB1_Set_Press and getPressure() calls OB1_Get_Press; both convert through the calibration array | upstream_code | pycrofluidics/elveob.py:180-215 |
| The pressure set point is in mbar | vendor_doc | readme.md:27 |
| The recorded pressure columns are in mbar | upstream_code | pycrofluidics/protocols.py:167 |
| getFlowUniversal() returns the flow sensor readout in uL/min | upstream_code | pycrofluidics/elveob.py:479-480 |
| getSensorData() returns the sensor reading in its native units, probably uL/min | upstream_code | pycrofluidics/elveob.py:282-284 |
| A channel number is 1 to 4 | upstream_code | pycrofluidics/elveob.py:464-470 |
| startRemote() starts the background control loop and sets insideRemote | upstream_code | pycrofluidics/elveob.py:305-314 |
| stopRemote() stops the background control loop and clears insideRemote | upstream_code | pycrofluidics/elveob.py:316-327 |
| remoteGetData() returns the pressure and sensor reading inside the remote loop | upstream_code | pycrofluidics/elveob.py:329-352 |
| setPressure() and getPressure() refuse while the remote loop is running | upstream_code | pycrofluidics/elveob.py:193-210 |
| getSensorData() refuses while the remote loop is running | upstream_code | pycrofluidics/elveob.py:296-297 |
| The pressure range depends on the installed regulator type; printRegulatorTypes() lists the regulator options, including non-installed 0 | upstream_code | pycrofluidics/elveob.py:543-553 |
| The constructor default deviceRegulators is [0, 0, 0, 0] | upstream_code | pycrofluidics/elveob.py:34-37 |
| loadCallibration() loads the pressure calibration array into self.calib | upstream_code | pycrofluidics/elveob.py:118-139 |
| close() stops a running remote loop and then calls OB1_Destructor | upstream_code | pycrofluidics/elveob.py:93-104 |
| The module controls the Elveflow OB1 pressure controller, tested on Mk4 | vendor_doc | readme.md:9 |

Limits: the pressure writes (`pressure_1` to `pressure_4`) are `Limit.operator_required`: the clone lists the
regulator options but no text file states the range of a configured unit. The site supplies each channel's range in
`site-limits.json` (`site-limits.example.json` shows the overlay). The channel selector of the two read actions is
bounded 1 to 4 by `upstream_code` at `pycrofluidics/elveob.py:468-469`.

Safety: the e-stop and the safe-state action `x-cap.wetenschaap.stop_remote.v1` stop the remote control loop (when it
runs) and command all four pressure channels to 0 mbar. No line of the clone documents an independent hardware
e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: pressure-controller, microfluidics, elveflow, ob1, flow-sensor
