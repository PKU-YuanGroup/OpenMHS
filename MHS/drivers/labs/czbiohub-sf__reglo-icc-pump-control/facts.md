# Facts and tags for gh.czbiohub-sf/reglo-icc-pump-control

Every fact cites its source at commit `af0f8648a56512cad67af26068830e65754ead5e`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.py) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package controls a Masterflex Ismatec Reglo ICC digital peristaltic pump over its USB interface; the RS-232 interface is untested | vendor_doc | README.md:2 |
| The package needs Python >= 3.6 and pyserial >= 3.5 | vendor_doc | README.md:14-16 |
| A command is written as ASCII text followed by a carriage return | upstream_code | reglo_icc_pump/_driver.py:263 |
| A query response is read until CRLF (read_until(b'\r\n')) | upstream_code | reglo_icc_pump/_driver.py:290 |
| The initialization command is '{pump_addr}~1', which puts the pump in remote-control mode | upstream_code | reglo_icc_pump/_driver.py:95 |
| The pump reports its number of channels to '{addr}xA', its serial number to '{addr}xS' and its model, software version and head code to '{addr}#' | upstream_code | reglo_icc_pump/_driver.py:227-234 |
| get_max_flow_rate returns the maximum flow rate setting for the installed tubing in mL/minute | upstream_code | reglo_icc_pump/_driver.py:311-334 |
| set_tubing_id takes the tubing inner diameter in mm and sends it as hundredths of a millimetre in a four-digit field | upstream_code | reglo_icc_pump/_driver.py:353 |
| set_tubing_id stores the value the pump reports back in tubing_ids for that channel | upstream_code | reglo_icc_pump/_driver.py:357-359 |
| The tubing inner diameter must match one of the values listed in the pump documentation | upstream_code | reglo_icc_pump/_driver.py:341-342 |
| pump_vol takes the volume in mL and the rate in mL/minute; the direction is a PumpDirection (CW or CCW) | upstream_code | reglo_icc_pump/_driver.py:362-368 |
| dispense_vol uses the channel's configured dispense direction and aspirate_vol uses the opposite direction | upstream_code | reglo_icc_pump/_driver.py:429-451 |
| The default dispense direction is CW | upstream_code | reglo_icc_pump/_driver.py:33 |
| PumpDirection is the pump rotor rotation direction as viewed from the front: CW or CCW | upstream_code | reglo_icc_pump/types.py:70-76 |
| stop(ch_no) immediately stops the specified channel, and stop(None) stops every channel | upstream_code | reglo_icc_pump/_driver.py:454-468 |
| is_running returns True while the channel is pumping and False when it is not | upstream_code | reglo_icc_pump/_driver.py:476-477 |
| The driver stops a channel and raises StallDetectionDetected when is_running reports the channel running but its odometer has not counted up for 2 seconds | upstream_code | reglo_icc_pump/_driver.py:486-494 |
| Volumes and rates are encoded with four significant digits in type-2 format ('{mantissa}{exponent:+d}') | upstream_code | reglo_icc_pump/_driver.py:554-559 |

Limits: the tubing inner diameter, the flow rate and the volume are `Limit.operator_required`. The clone says the
tubing ID must match a value in the pump documentation but does not list the values (reglo_icc_pump/_driver.py:341-342);
the maximum flow rate is the value the pump reports for the installed tubing (reglo_icc_pump/_driver.py:311-334); the
pump checks the requested volume at run time and reports a limit in its error reply (reglo_icc_pump/_driver.py:399-409).
No text file of the clone states a static range for any of them, so the site supplies the envelope
(`site-limits.example.json` shows the overlay).

Safety: the e-stop and the safe-state action `x-cap.czbiohub-sf.stop_pump.v1` both call the native `stop()`, which
stops every channel (reglo_icc_pump/_driver.py:454-468). No line of the clone documents an independent hardware e-stop,
so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: peristaltic pump, reglo icc, ismatec, serial, fluid
