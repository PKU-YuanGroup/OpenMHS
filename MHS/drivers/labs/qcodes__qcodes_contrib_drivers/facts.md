OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.qcodes/qcodes_contrib_drivers

Every fact cites the pinned clone at commit `187164d608ed3a281fccdf3f68693d29b2d46a62`. `upstream_code` refs name
`path/in/clone:LINE`, or a bounded range where the statement spans adjacent lines; `PM100D.py` below is
`src/qcodes_contrib_drivers/drivers/Thorlabs/PM100D.py`. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

Tags: `qcodes`, `visa`, `scpi`, `optical-power-meter`, `photodiode`.

## Facts

| fact | source | ref |
|---|---|---|
| Thorlab_PM100D is a QCoDeS VisaInstrument that represents a Thorlab PM100D optical powermeter, status beta-version. | upstream_code | PM100D.py:20-24 |
| The constructor takes a VISA resource address, terminator default '\n' and timeout default 20. | upstream_code | PM100D.py:32-39 |
| The module imports Parameter from qcodes.parameters and VisaInstrument from qcodes.instrument. | upstream_code | PM100D.py:13-14 |
| `power` is a Parameter with unit W whose get_cmd is self._get_power. | upstream_code | PM100D.py:61-68 |
| `_get_power()` calls `_set_conf_power()`, writes MEAS:POW, sleeps .2 and returns float of the FETC? reply. | upstream_code | PM100D.py:172-179 |
| `_set_conf_power()` writes CONF:POW, asks ABOR;:STAT:OPER? and writes INIT. | upstream_code | PM100D.py:164-170 |
| `power_range` has unit W, get_cmd SENS:POW:RANG:UPP?, set_cmd SENS:POW:RANG:UPP {}, float parsers and the unbounded validator Numbers(). | upstream_code | PM100D.py:82-92 |
| `auto_range` has get_cmd SENS:POW:RANG:AUTO?, set_cmd SENS:POW:RANG:AUTO {} and an on/off mapping to '1' and '0'. | upstream_code | PM100D.py:94-102 |
| `attenuation` has unit dB, get_cmd CORR?, set_cmd CORR {} and validator Numbers(-60, 60). | upstream_code | PM100D.py:70-80 |
| `averaging` has get_cmd AVER? and set_cmd AVER, which has no value placeholder. | upstream_code | PM100D.py:41-48 |
| `zero_value` has unit W and get_cmd CORR:COLL:ZERO:MAGN?. | upstream_code | PM100D.py:133-140 |
| `current_range` has unit A and get_cmd SENS:CURR:RANG:UPP?. | upstream_code | PM100D.py:123-131 |
| `wavelength` has unit m, get_cmd SENS:CORR:WAV?, scale=1e9, validator Numbers(185e-9, 25e-6) and no get_parser. | upstream_code | PM100D.py:50-59 |
| `beam_diameter` has unit m, get_cmd CORR:BEAM?, scale=1e3 and no get_parser. | upstream_code | PM100D.py:142-151 |
| `frequency` and `current` get MEAS:FREQ? and MEAS:CURR?. | upstream_code | PM100D.py:104-121 |
| The constructor applies the transition filter (512, 0), calls averaging(300), applies the power configuration and calls connect_message(). | upstream_code | PM100D.py:153-157 |
| `_set_transition_filter()` writes STAT:OPER:PTR and STAT:OPER:NTR and sleeps .2, 5 and .2. | upstream_code | PM100D.py:181-189 |
| `_check_error()` asks SYST:ERR? and raises RuntimeError unless the reply starts with +0. | upstream_code | PM100D.py:159-162 |

## Scope

The card is the whole `qcodes_contrib_drivers` driver pack; this package serves one instrument of it, the Thorlabs
PM100D power meter console, whose class constructs every Parameter explicitly as `self.<name> = Parameter(...,
instrument=self)`. Most other classes of the pack create their Parameters with `add_parameter`, which the QcodesDriver
source proof does not cover; the card's entry symbol was set to this class by a registry override for that reason.

Served, each as one `parameter_bindings` entry that gate G7 proves against its exact constructor lines:

| field | access | unit | note |
|---|---|---|---|
| `power` | read | W | every read re-applies power mode and aborts a running measurement: CONF:POW, ABOR, INIT, MEAS:POW, 0.2 s, FETC? |
| `power_range` | read, write | W | `Limit.operator_required`: no source states the ranges, which depend on the sensor head |
| `auto_range` | read, write | (boolean) | the on/off mapping returns and accepts a bool |
| `attenuation` | read | none | the upstream unit is dB, which is not an OpenMHS unit |
| `averaging` | read | (string) | the raw `AVER?` reply: the upstream declares no parser |
| `zero_value` | read | W | |
| `current_range` | read | A | |

Writes go through `cap.device.configure.v1` and call `Parameter.set(value)`, awaited as a whole. The upstream sends a
write without reading the SCPI error queue (`_check_error()` exists but no Parameter calls it), so a setting the meter
or the sensor head rejects shows only as the unchanged value of the fresh read that follows every command.

NOT COVERED, each for a reason in the source:

- `wavelength` (PM100D.py:50-59) and `beam_diameter` (PM100D.py:142-151) declare `scale` but no `get_parser`, so the
  QCoDeS get divides the raw reply string by the scale and fails; neither their reads nor their writes (whose readback
  would fail) are served.
- `averaging` writes: `set_cmd='AVER'` carries no value placeholder (PM100D.py:45), so a set would not transmit the
  value; the constructor's `averaging(300)` call has the same effect.
- `attenuation` writes: dB is not an OpenMHS unit, and a configure input needs a unit.
- `current` and `frequency` (PM100D.py:104-121): `MEAS:CURR?` and `MEAS:FREQ?` are SCPI measure queries that would
  switch the meter out of the power mode every served field assumes, until the next power read re-applies it
  (PM100D.py:164-179). The served power read is not side-effect free either: it aborts a measurement in progress and
  re-applies the power configuration on every read.

## Safety

The PM100D is a passive detector console: this package drives no output, light source or motion. Its writes change
only the range selection of the meter, so its risk is R1, the card's floor (a configuration write). The native stop is
`write("ABOR")`, the SCPI abort command that `_set_conf_power()` sends, as the first command of `ABOR;:STAT:OPER?`,
before it re-initializes a measurement (PM100D.py:164-170). It is sent as a plain write so that no reply on the shared
VISA session can be taken for the reply of a power read that may be running; such a read can then fail. The stop is
not synchronised with that read either: when ABOR lands between the read's own ABOR and INIT, the read re-arms a
measurement (INIT, MEAS:POW) after the stop (PM100D.py:167-176). For a passive detector this drives nothing. An e-stop
latches the endpoint: writes are refused until an operator reset; reads stay available.

## Fake fidelity

`fake.py` stores any value a write sends. The upstream validators (`auto_range`: `vals.Ints(0, 1)` with an on/off
`val_mapping`; `power_range`: `vals.Numbers()`), the `val_mapping` and the `set_parser` (PM100D.py:82-102) are not
exercised. In the QCoDeS source of the separate clone `labs/microsoft/qcodes` (pinned commit
09ec44d9fa7f993dcd20b5a6f4e65afff03d9239), `Ints.validate` accepts any `int` instance, a Python bool included
(src/qcodes/validators/validators.py:334, 367-374), and `set_wrapper` validates the value before mapping it
(src/qcodes/parameters/parameter_base.py:1016, 1031-1033); which QCoDeS version a deployment installs is not known. A
first supervised run must write `auto_range` both ways and read it back.

## Hardware backend

`native.py` imports the upstream class only when an operator loads the hardware backend, with the VISA resource
address as an explicit option. The upstream constructor talks to the meter before it returns: it opens the session,
writes STAT:OPER:PTR 512 and STAT:OPER:NTR 0 with about 5.4 s of sleeps, sends `AVER`, applies the power configuration
and asks the identity (PM100D.py:38-157, 164-189). `native_close = "close"` closes the QCoDeS instrument at teardown.
Nothing was run: the package has never opened a VISA session.

## Exemplar notes

This is the structural exemplar of the QCoDeS family. It shows explicit `parameter_bindings`, a writable Field with
`Limit.operator_required` and a site overlay example, types that follow the upstream parsers, a native stop that the
source supports, the source-shaped fake and a reason in the source for every Parameter that is not served.
