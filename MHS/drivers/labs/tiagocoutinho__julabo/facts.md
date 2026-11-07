# Facts and tags for gh.tiagocoutinho/julabo

Every fact cites its source at commit `650da2138459d93e3bfdb8db17ce0bd161c6a9a7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| bath_temperature reads IN_PV_00, external_temperature IN_PV_02, and set_point_1 reads IN_SP_00 and writes OUT_SP_00 | upstream_code | julabo/device.py:128-132 |
| The tango server publishes the bath temperature and the external PT100 temperature in degC | upstream_code | julabo/tango/server/device.py:85-98 |
| Set point 1 is the working temperature set point of channel 1, published in degC | upstream_code | julabo/tango/server/device.py:105-108 |
| A set point is written with two decimals ('{:.2f}') | upstream_code | julabo/device.py:48 |
| start() writes OUT_MODE_05 1 and stop() writes OUT_MODE_05 0 | upstream_code | julabo/device.py:118-122 |
| The protocol idles the line 250 ms after a command and 10 ms after a query | upstream_code | julabo/protocol.py:30-33 |
| The tango server maps status codes 0 and 2 to STANDBY, 1 and 3 to RUNNING and a code below 0 to ALARM | upstream_code | julabo/tango/server/device.py:42-47 |
| The active set point channel is 1 to 3 | upstream_code | julabo/tango/server/device.py:150 |

Limits: set point 1 is `Limit.operator_required`. No text file of the clone states a temperature range (the manuals
under `docs/` are PDFs and cannot be cited by line), so the site supplies the range of its unit
(`site-limits.example.json` shows the overlay).

Safety: the e-stop and the safe-state action `x-cap.tiagocoutinho.stop_circulation.v1` both call the native `stop()`
(`OUT_MODE_05 0`). No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set;
the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: circulator, temperature-control, bath, asyncio
