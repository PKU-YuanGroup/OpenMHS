# Facts and tags for gh.alexshkarin/pylablib-v0

Every fact cites its source at commit `1c3c59d4bcbea4a16eee916033972ee13a7d1af6`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package is a direct Driver over `AWG33220A`, not a ScpiDriver as the card proposes: the upstream class scales the
amplitude between zero-to-peak volts and Vpp, parses the frequency reply as a value with a unit, and selects degrees
before reading the phase.  A command table cannot reproduce those transforms, so the driver calls the upstream methods
and the wire syntax remains exactly the class's own.  RESULT.json records this as a deviation from the card.

| fact | source | ref |
|---|---|---|
| AWG33220A covers the Agilent 33220A and partially compatible generators such as the Agilent 33500 and the Rigol D1000 | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:14-18 |
| set_amplitude writes twice the requested value in Vpp and get_amplitude halves the Vpp reply | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:100-107 |
| get_output and set_output use the boolean SCPI command :OUTPUT | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:42-48 |
| The frequency is written and read in Hz with :FREQUENCY | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:145-152 |
| get_phase selects degrees with :UNIT:ANGLE DEG before reading :PHASE? | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:153-156 |
| The duty cycle is in percent and applies only to the square function | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:163-176 |
| The function values are sine, square, ramp, pulse, noise, prbs, DC, user and arb | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:29 |
| The burst mode is trig or gate | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:34 |
| set_output(False) turns the generator output off | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:45-48 |

Limits:

| parameter | kind | limit | source | ref |
|---|---|---|---|---|
| amplitude (V) | number | operator_required | operator | none: no text in the clone states a range |
| frequency (Hz) | number | operator_required | operator | none: no text in the clone states a range |
| offset (V) | number | operator_required | operator | none: no text in the clone states a range |
| phase (deg) | number | operator_required | operator | none: no text in the clone states a range |
| duty_cycle (%) | number | operator_required | operator | none: no text in the clone states a range |
| function | string | one of sine, square, ramp, pulse, noise, prbs, DC, user, arb | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:29 |
| burst_mode | string | one of trig, gate | upstream_code | pylablib/aux_libs/devices/AgilentElectronics.py:34 |

No text file of the clone states an amplitude, frequency, offset, phase or duty-cycle range for the 33220A or its
compatible models, so those bounds are `Limit.operator_required`.  Until the operator writes a `site-limits.json`,
every call that sets one of them is refused `MHS.SAFETY.LIMITS_UNSET`.  The package's `site-limits.example.json` is an
example bench policy, not a device rating, and shows the overlay format.

Safety: the e-stop and the safe-state action both call `set_output(False)`, which turns the one actuated output off
(`AgilentElectronics.py:45-48`).  The package is R1 hardware, so no independent physical e-stop reference is required
and none is claimed.  The hardware backend has never been run; the package is model-authored and unreviewed.

Tags: awg, waveform generator, signal generator, agilent, 33220a, scpi
