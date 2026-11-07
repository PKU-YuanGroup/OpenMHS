# Facts and tags for gh.itdaniher/olin-smus

Every fact cites its source at commit `3bddec37c09a408493dab0bf899080670e8807fe` from the clone root as it is. The
same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The user-facing driver object is the class smu | upstream_code | modconsmu/modconsmu.py:7 |
| The README calls the modconsmu folder an importable pure-Python driver that uses pyusb | vendor_doc | README.mkd:7 |
| The constructor finds the instrument by USB vendor id 0x6666 and product id 0x0005 | upstream_code | modconsmu/modconsmu.py:38 |
| The constructor reads the DAC, VADC, IADC and RES calibration words with four vendor control transfers and converts them into the gain and shunt values | upstream_code | modconsmu/modconsmu.py:42-56 |
| The constructor registers set(amps=0) with atexit as its safety feature | upstream_code | modconsmu/modconsmu.py:57-58 |
| update() writes the DAC target with the UPDATE vendor request, reads 12 bytes and returns the measured voltage, measured current and modVolt; its docstring says it returns actual V/I | upstream_code | modconsmu/modconsmu.py:60-80 |
| update() maps a voltage target to the 12-bit code zeroV - v/scaleFactorV and a current target to zeroI + i*10000 | upstream_code | modconsmu/modconsmu.py:62-67 |
| set(volts, amps) stores one target, switches between voltage and current driving and calls update(); it raises NotImplementedError when both are given | upstream_code | modconsmu/modconsmu.py:82-101 |
| The firmware UPDATE handler writes both DAC bytes and returns four ADC result pairs, the timer bytes and a 12-byte reply | upstream_code | modconsmu/pic/ecs.c:526-563 |
| The firmware defines the vendor requests UPDATE 1, SET_DIGOUT 2, GET_DAC_VALS 3, SET_DAC_VALS 4, GET_VADC_VALS 5, GET_IADC_VALS 7, GET_RES_VAL 9, GET_NAME 11 and SET_NAME 12 | upstream_code | modconsmu/pic/ecs.c:5-16 |
| The example charger sets a constant current with set(amps=...), switches to a constant voltage with set(volts=...), and disables charging with set(amps=0) | upstream_code | apps/charger.py:41-53 |
| The constructor's maxV=9.93 and minV=-10.45 are the ends of the voltage conversion scale and are used only to derive scaleFactorV | upstream_code | modconsmu/modconsmu.py:30-32 |

Limits: the voltage and current targets are both `Limit.operator_required`. No text of the clone states a safe output
envelope. `maxV=9.93` and `minV=-10.45` are the ends of the driver's voltage conversion scale
(modconsmu/modconsmu.py:30-32), not a device rating, and the constructor names no current range; the shunt calibration
word at modconsmu/modconsmu.py:42-56 is not a bound. Until an operator overlay supplies the envelope of the installed
unit and its load, every write of `source_voltage` or `source_current` is refused `MHS.SAFETY.LIMITS_UNSET`.
`site-limits.example.json` is an example overlay only, not a statement about any unit.

Reads: the upstream API has no separate measurement call. `update(mod=1)` writes the current target and returns
`(retVolt, retAmp, modVolt)` (modconsmu/modconsmu.py:60-80), so each measured read calls `update(0)` and repeats the
target already stored by the upstream object. The measured voltage, measured current and modVolt are read state. The
two stored targets (`v` and `i`) and the upstream `driving` attribute are exposed as `source_voltage`,
`source_current` and `source_mode`; only the target of the active mode drives the output.

Safety: the output is the hazard this driver controls. The upstream constructor registers `set(amps=0)` with atexit
as its safety feature (modconsmu/modconsmu.py:57-58), and the example charger uses `set(amps=0)` to disable charging
(apps/charger.py:52-53). The `@estop` method and the `safe_state=True` action `x-cap.itdaniher.source_off.v1` both
call that upstream path; the clone documents no independent hardware e-stop, so the package does not claim one. This
package is model-authored and unreviewed and it is R2: the loader refuses its hardware backend until a human signs
`reviewed_by`.

Tags: smu, source-measure-unit, usb, pyusb, electrical
