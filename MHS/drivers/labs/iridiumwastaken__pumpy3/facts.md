# Facts and tags for gh.iridiumwastaken/pumpy3

Every fact cites its source at commit `0819cd6f9c402ce75e12eb697672a8b3559f93c1`: `vendor_doc` (a text file of the
clone, README.md) or `upstream_code` (`pump.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| pumpy3 controls a Harvard syringe pump over an RS-232 interface and supports the PHD 2000 and the PHD Ultra | vendor_doc | README.md:3-8 |
| The supported features are set pump volume, set pump diameter, set infuse and withdraw rate, set target volumes and wait until target volume | vendor_doc | README.md:10-15 |
| The example creates Chain serial objects and pumps at addresses 0 and 2 | vendor_doc | README.md:31-39 |
| The PHD 2000 only takes notice of target volumes after it has been put into volume mode with the keypad | vendor_doc | README.md:52-53 |
| The PHD 2000 sometimes does not wait until infusion or withdrawal is finished | vendor_doc | README.md:54 |
| Chain opens the serial line with a 115200 baud default, two stop bits, no parity, eight data bits and a 2 s timeout | upstream_code | pump.py:96-104 |
| Pump2000 stores the configured pump address as a two-digit string with '{0:02.0f}' | upstream_code | pump.py:527 |
| Pump.write prefixes the stored pump address and terminates every command with a carriage return | upstream_code | pump.py:159-164 |
| Pump.setdiameter states that the syringe diameter range is 0.1-35 mm | upstream_code | pump.py:182-193 |
| Pump.setinfusionrate says the accepted flow-rate range depends on the syringe diameter and is given by the pump manual | upstream_code | pump.py:264-272 |
| Pump.settargetvolume says the accepted target-volume range depends on the syringe and is given by the pump manual | upstream_code | pump.py:351-359 |
| Pump2000 queries VER during construction, requires 'PHD' in the reply and reads the status character ':' (idle), '>' (infusing), '<' (withdrawing) or '*' (stalled) | upstream_code | pump.py:539-556 |
| Pump2000.run writes RUN and Pump2000.rev writes REV, then records the reported state | upstream_code | pump.py:576-590 |
| Pump2000.stop writes STP, reads the reply, pauses 0.1 s and raises if the state still reports infusing or withdrawing | upstream_code | pump.py:606-614 |
| Pump2000.set_rate maps m/m, u/m, m/h and u/h to MLM, ULM, MLH and ULH and writes the rate with four decimals | upstream_code | pump.py:640-656 |
| Pump2000.settargetvolume sets the target volume in mL with MLT | upstream_code | pump.py:663-667 |
| Pump2000.getdiameter queries DIA and reports the number in mm | upstream_code | pump.py:669-678 |
| Pump2000.getrate queries RAT and RNG and reports the rate and the first four characters of the RNG reply | upstream_code | pump.py:680-692 |
| Pump2000.ivolume queries VOL and reports the infused volume in mL | upstream_code | pump.py:694-703 |
| Pump2000.gettargetvolume queries TAR and reports the target volume in mL | upstream_code | pump.py:705-714 |

## Limits

The syringe diameter is bounded by the clone at 0.1 to 35 mm (`pump.py:184`).  The flow rate and the target volume are
`Limit.operator_required`: the clone says the flow-rate range depends on the syringe diameter and is given by the pump
manual (`pump.py:264-272`), and it says the target-volume range depends on the syringe (`pump.py:351-359`); neither
manual is a text file of the clone.  The site supplies both ranges (`site-limits.example.json` shows the overlay);
until it does, every write of the rate or the target volume is refused `MHS.SAFETY.LIMITS_UNSET`.

## Safety

The device is a syringe pump that dispenses liquid, so the driver is R2 (MHS/spec/04-safety.md).  The e-stop and the
safe-state action `x-cap.iridiumwastaken.stop_pump.v1` both call the native `stop()`, which sends STP and checks that
the pump left the running states (`pump.py:606-614`).  No line of the clone documents an independent hardware e-stop,
so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.  The package
is model-authored and unreviewed: `reviewed_by` is null in `driver.lock.json`, and the hardware backend was not run.

## Mock

There is no upstream simulator (`task.json` `mock_strategy.preferred` is `fake`).  `fake.py` is an in-memory stand-in
for `pump:Pump2000`; its numeric starting values and reply strings are test data marked `# placeholder`, not facts about
any pump.  It never reproduces the serial protocol and never talks to a device.

## Tags

syringe pump, harvard, phd2000, serial, infuse, withdraw, pumpy3
