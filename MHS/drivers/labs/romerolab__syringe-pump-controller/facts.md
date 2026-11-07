# Facts and limits: New Era NE-500/501 syringe pump

The upstream repository `gh.romerolab/syringe-pump-controller` at
`7c2af002a04ae3abbc7f9fba435b286e69c820fc` is a Python 2 PyQt4 GUI, not a device class. The serial protocol
is the set of module functions in `new_era.py`; `pump_control.py:14` is the only class (`PumpControl`, a
`QtGui.QWidget`) and it owns the serial link `self.ser` created at `pump_control.py:22`. This package is a
direct Driver over that link. The hardware factory opens pyserial itself because the clone cannot be
imported under Python 3; no upstream code is imported or installed by the fake backend.

## Tags

`syringe pump`, `new era`, `ne-500`, `ne-501`, `serial`, `fluid`

## Facts

| Fact | Source | Reference |
|---|---|---|
| The project is a Python GUI that operates New Era syringe pumps such as the NE-500/501. | vendor_doc | `README.md:2` |
| The upstream runs on Python 2 and requires PyQt4 and the serial module. | vendor_doc | `README.md:6` |
| The GUI opens the serial port at 19200 baud with a 0.1-second timeout. | upstream_code | `pump_control.py:22` |
| Pump discovery writes the CR-terminated query `<address>ADR` and accepts a non-empty reply. | upstream_code | `new_era.py:7-10` |
| The broadcast stop is the CR-terminated command `*STP`. | upstream_code | `new_era.py:20` |
| A rate is set by a per-pump `<address>DIR<INF\|WDR>` line followed by one `<address>RAT<value><UH\|MH>` line; several pump rates are chained with `*` and the line ends with CR. | upstream_code | `new_era.py:42-53` |
| Rates below 5000 are sent in UH; at 5000 and above the rate is divided by 1000 and sent in MH. | upstream_code | `new_era.py:48-52` |
| A rate is read by `<address>DIR` and `<address>RAT`; a WDR direction gives a negative sign and an MH reply is multiplied by 1000 to obtain UH. | upstream_code | `new_era.py:60-74` |
| The syringe diameter is written by `<address>DIA<millimetres>` and read by `<address>DIA`. | upstream_code | `new_era.py:81-94` |
| Prime sends `<address>DIRINF`, `<address>RAT10.0MH` and `<address>RUN`, each CR-terminated. | upstream_code | `new_era.py:98-112` |
| The GUI shows the current flow rate with the unit `ul/hr`. | upstream_code | `pump_control.py:131` |
| The clone lists no maximum or minimum rate, diameter, volume or duration; `set_rates` only switches the unit at 5000 UH. | upstream_code | `new_era.py:48-52` |

## Limits

No text file of the clone states a numeric range for the flow rate, the syringe diameter, the dispensed
volume or the run duration. The catalogue class's `10000 uL/s` maximum is a class default, not a bound of
this device. The driver therefore declares `Limit.operator_required` for every numeric input:

| Input | Unit | Why the operator supplies it |
|---|---|---|
| state `flow_rate` | `uL/hr` | `set_rates` only switches from UH to MH at 5000; no range is stated. |
| state `diameter` | `mm` | The GUI menu (`pump_control.py:8-11`) lists syringes, not an allowed diameter range. |
| `cap.actuation.pump.v1.flow_rate` | `uL/s` | No range is stated in the clone. |
| `cap.actuation.pump.v1.volume` | `uL` | The clone has no volumetric run; it only runs until stopped. |
| `cap.actuation.pump.v1.duration_s` | `s` | The clone has no timed run; it only runs until stopped. |

`site-limits.example.json` supplies an example site overlay. It narrows the catalogue pump class and fills
the operator-required fields; it is an example, not a claim about an instrument.

## Safety

The pump dispenses liquid, so the device is at least R2 (`MHS/spec/04-safety.md`) even though the card's
floor is R0. The independent stop is the safe-state action `x-cap.romerolab.stop_pump.v1`, which writes the
broadcast `*STP` from `new_era.py:20`; the `@estop` writes the same command without waiting for a reply.
The safe state is all pumps stopped. No hardware stop in the vendor text is claimed, and no hardware run was
made.

## Units

* `flow_rate` state: `uL/hr`, the unit the GUI displays (`pump_control.py:131`). Negative values mean WDR.
* `diameter`: `mm`, the value written into the `DIA` command.
* dispense inputs: `flow_rate` in `uL/s`, `volume` in `uL`, `duration_s` in seconds; the driver converts
  `uL/s` to `uL/hr` by multiplying by 3600 before building the `RAT` line.

## Fake

`fake.py` is a stateful pyserial-like link. It answers only the commands above, and its initial rate,
diameter, direction, address and reply text are canned test data marked `# placeholder`. It is not a
recording of an instrument run. G7 reports `write`, `readline` and `close` as `MAYBE_ABSENT` because the
upstream class's AST exposes `self.ser` but not pyserial's methods; the upstream protocol functions call
exactly those two methods (`new_era.py:8`, `new_era.py:61`).
