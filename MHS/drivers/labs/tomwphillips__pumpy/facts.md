# Facts and tags for gh.tomwphillips/pumpy

Every fact cites its source at commit `3e49d71a73d23ea6f16082109bd4fac90a69119b`: `vendor_doc` (a text file of the
clone, such as README.md) or `upstream_code` (`pumpy.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| pumpy controls a Harvard syringe pump or a Mighty Mini piston pump over an RS-232 interface | vendor_doc | README.md:3 |
| The supported Harvard pumps are Pump 11, Pump 11 Plus and PHD2000 | vendor_doc | README.md:15-17 |
| The supported features for the Harvard pumps are infuse, withdraw, set diameter, set flow rate, set target volume and wait until target volume | vendor_doc | README.md:22-28 |
| A pump is created on a Chain and the PHD2000 is created with an address | vendor_doc | README.md:52-63 |
| The example flow rate is in uL/min and the example target volume is in uL | vendor_doc | README.md:56-57 |
| PHD2000 requires withdraw, stop, infuse rather than withdraw, infuse | vendor_doc | README.md:80 |
| PHD2000 only takes notice of target volumes when it has been put into volume mode using the keypad | vendor_doc | README.md:81 |
| Chain opens a serial line with two stop bits, no parity and a 2 s timeout | upstream_code | pumpy.py:33 |
| A command is written as the pump address, the command text and a carriage return | upstream_code | pumpy.py:82-83 |
| Pump.__init__ stores the name, the serial chain, the two-digit address and the diameter, flow rate and target volume (initially None), then queries VER to check the pump and its address | upstream_code | pumpy.py:48-74 |
| setdiameter states that the Pump 11 syringe diameter range is 0.1-35 mm and the pump truncates precision beyond two decimal places | upstream_code | pumpy.py:93-98 |
| setdiameter sends MMD with the diameter and checks it with DIA | upstream_code | pumpy.py:120-141 |
| setflowrate takes microlitres per minute and says the range depends on the syringe diameter and is given by the Pump 11 manual | upstream_code | pumpy.py:143-151 |
| setflowrate sends ULM with the flow rate and checks it with RAT | upstream_code | pumpy.py:163-184 |
| infuse sends RUN and checks for the forward-running status character | upstream_code | pumpy.py:186-197 |
| withdraw sends REV and checks for the backward-running status character | upstream_code | pumpy.py:199-214 |
| Pump.stop sends STP and expects the stopped status character | upstream_code | pumpy.py:216-224 |
| Pump.settargetvolume takes microlitres, sends MLT and stores the target volume | upstream_code | pumpy.py:226-239 |
| PHD2000 overrides stop, sends STP and expects the '*' status character | upstream_code | pumpy.py:278-286 |
| PHD2000.settargetvolume takes microlitres, converts them to millilitres, sends MLT and stores the value back in microlitres | upstream_code | pumpy.py:288-308 |
| waituntiltarget polls VOL until the pump stops or two consecutive replies are equal | upstream_code | pumpy.py:241-269 |

Limits: the syringe diameter is bounded by the clone at 0.1 to 35 mm (`pumpy.py:96`). The flow rate and the target
volume are `Limit.operator_required`: the clone says the flow-rate range depends on the syringe diameter and is given
by the Pump 11 manual (`pumpy.py:150-151`), and it states no target-volume range. The site supplies both ranges
(`site-limits.example.json` shows the overlay); until it does, every write and the pump action are refused
`MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop and the safe-state action `x-cap.tomwphillips.stop_pump.v1` both call the native `stop()`, which
sends STP (`pumpy.py:278-286`). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: syringe pump, harvard, phd2000, serial, infuse, withdraw, pumpy
