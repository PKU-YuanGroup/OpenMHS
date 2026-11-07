# Facts and tags for gh.rk-exxec/pymupump

Every fact cites its source at commit `2de8fb492bbf11b44ad30f571ebb5e64239c6176`: `vendor_doc` (a text file of the
clone, README.md) or `upstream_code` (`pymupump/pymupump.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| pymupump controls a Harvard Apparatus Microliter OEM syringe pump | vendor_doc | README.md:2 |
| A Chain is created on a serial port and a Microliter is created on that chain | vendor_doc | README.md:16-17 |
| A second pump on the same port is selected by its address | vendor_doc | README.md:18-20 |
| The syringe diameter is in mm and the README states the range 0.1 - 4.61 mm | vendor_doc | README.md:22 |
| The flow rate is set in uL/min | vendor_doc | README.md:23 |
| The infuse or withdraw target volume is in uL | vendor_doc | README.md:25 |
| The README example runs infuse or withdraw, optionally waits for the target volume, and stops the pump | vendor_doc | README.md:27-33 |
| Chain opens a serial line with two stop bits, no parity and a 2 s timeout | upstream_code | pymupump/pymupump.py:51 |
| The pump address is formatted as two zero-padded digits | upstream_code | pymupump/pymupump.py:69 |
| A command is written as the pump address, the command text and a carriage return | upstream_code | pymupump/pymupump.py:107 |
| The constructor queries VER, reads 17 bytes and checks the two characters before the last against the address | upstream_code | pymupump/pymupump.py:83-88 |
| diameter, flowrate and targetvolume start as None | upstream_code | pymupump/pymupump.py:70-72 |
| The clone states the syringe diameter range as 0.1-4.61 mm and says the pump ignores precision beyond two decimal places | upstream_code | pymupump/pymupump.py:166-169 |
| setdiameter rounds to three decimal places and rejects a diameter above 4.61 or below 0.1 mm | upstream_code | pymupump/pymupump.py:171-173 |
| setdiameter sends MMD and checks the set value with DIA | upstream_code | pymupump/pymupump.py:179-187 |
| setflowrate takes microlitres per minute | upstream_code | pymupump/pymupump.py:202 |
| The clone says the accepted flow rate depends on the syringe diameter and the pump reports an out-of-range rate | upstream_code | pymupump/pymupump.py:204-207 |
| setflowrate sends ULM and ULMW and checks the values with RAT and RATW | upstream_code | pymupump/pymupump.py:216-235 |
| An out-of-range flow rate is reported as OOR | upstream_code | pymupump/pymupump.py:244-245 |
| infuse sends RUN and requires the forward-running '>' status character | upstream_code | pymupump/pymupump.py:253-255 |
| withdraw sends RUNW and requires the backward-running '<' status character | upstream_code | pymupump/pymupump.py:262-264 |
| stop sends STP without waiting for a reply and requires one of ':*IWDT' | upstream_code | pymupump/pymupump.py:273-275 |
| settargetvolume clears the four target settings with CLT, CLTW, CLV and CLVW, then sends ULT and ULTW | upstream_code | pymupump/pymupump.py:280-286 |
| settargetvolume stores the target volume in microlitres | upstream_code | pymupump/pymupump.py:278-292 |
| waituntiltarget polls VOL while the reply carries '<' or '>' | upstream_code | pymupump/pymupump.py:302-319 |

Limits: the syringe diameter is bounded by the clone at 0.1 to 4.61 mm (`pymupump/pymupump.py:167`). The flow rate and
the target volume are `Limit.operator_required`: the clone says the accepted flow rate depends on the syringe diameter
(`pymupump/pymupump.py:204-206`) and states no target-volume range. The site supplies both ranges
(`site-limits.example.json` shows the overlay); until it does, every write and the pump action are refused
`MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop and the safe-state action `x-cap.rk-exxec.stop_pump.v1` both call the native `stop()`, which sends
STP (`pymupump/pymupump.py:273-275`). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.  The pump
action calls `waituntiltarget`, whose polling loop has no bound of its own (`pymupump/pymupump.py:310-319`); the
hardware backend is refused until a human reviews this package, and the reviewer must decide whether the pump's own
target stop is sufficient for the installation.

Tags: syringe pump, harvard apparatus, microliter oem, serial, infuse, withdraw, pymupump
