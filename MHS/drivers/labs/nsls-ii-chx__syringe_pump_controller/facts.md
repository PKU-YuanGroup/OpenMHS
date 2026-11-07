# Facts and limits: NSLS-II CHX syringe-pump controller

The upstream `gh.nsls-ii-chx/syringe_pump_controller` at
`cbda9ca1c20127a220eb91a61b6420a366ae5cf8` is one Python 2 module, `pump_controler.py`. It contains one device
class, `pump` (`pump_controler.py:10`), which opens a pyserial link in its constructor
(`pump_controler.py:11-12`) and writes CR-terminated text commands. The class is the card's entry symbol. This
package is a direct Driver over the upstream class: `native.py` is an independent Python 3 port of the wire
protocol, and the fake implements the same method names. No upstream code is imported, installed or run.

The card names `family=serial` and `helper=SerialDriver`. The commands are assembled at run time from a pump
address and a keyword (`<address>DIR<INF|WDR>`, `<address>RAT<rate><unit>`, `<address>VOL <volume>`), so a
command table cannot reproduce the lines the device receives; adding a space to make a token visible to G7 would
change the wire syntax. The package is therefore a direct Driver, and `RESULT.json` records the deviation.

## Tags

`syringe pump`, `serial`, `nsls-ii`, `chx`, `fluid`

## Facts

| Fact | Source | Reference |
|---|---|---|
| The project is a Python program that controls a syringe pump system developed at CHX. | vendor_doc | `README.md:2` |
| The controller is one class, `pump`, which opens the serial port in its constructor. | upstream_code | `pump_controler.py:10-12` |
| The constructor defaults to port COM10, 19200 baud and a one-second timeout. | upstream_code | `pump_controler.py:11` |
| A command is the text plus a carriage return (0x0D) written to the serial port. | upstream_code | `pump_controler.py:14-16` |
| Pump discovery writes `<address>ADR` for each address in `range(tot_range)` and keeps the addresses that answer. | upstream_code | `pump_controler.py:18-27` |
| The direction query is `<address>DIR`; a `WDR` reply means withdraw. | upstream_code | `pump_controler.py:29-37` |
| `set_direction` writes `<address>DIR<INF\|WDR>`, where `INF` is in and `WDR` is withdraw. | upstream_code | `pump_controler.py:39-48` |
| `set_rate` first writes `<address>DIR<INF\|WDR>`, chosen by the sign of the flow rate. | upstream_code | `pump_controler.py:50-58` |
| `set_rate` then writes `<address>RAT<the first five characters of the absolute rate><unit>`, and its default unit token is `UM*`. | upstream_code | `pump_controler.py:50-61` |
| `set_diameter` writes `<address>DIA<diameter>` and `get_diameter` writes `<address>DIA` and returns `reply[4:-1]`; the clone states no unit for this value. | upstream_code | `pump_controler.py:66-81` |
| `set_volume` writes `<address>VOL <volume>` with a space after `VOL` and ignores its unit argument. | upstream_code | `pump_controler.py:83-91` |
| `get_volume` writes `<address>VOL`, parses the value from `reply[4:-3]` and the unit from `reply[-3:-1]`. | upstream_code | `pump_controler.py:94-103` |
| `get_dispense` writes `<address>DIS` and parses the INF value from `reply[5:10]`, the WDR value from `reply[11:16]` and the unit from `reply[-3:-1]`. | upstream_code | `pump_controler.py:105-117` |
| `reset_dispense` writes `<address>CLD <direction>` with a space after `CLD`. | upstream_code | `pump_controler.py:120-125` |
| `get_rate` queries `<address>DIR` and `<address>RAT`; a WDR direction gives a negative sign and a UM reply unit is labelled `ul/min`. | upstream_code | `pump_controler.py:128-151` |
| `run` sends `RUN` with an optional string pump prefix; its docstring says the pump is `00` or `01`, set by setup on the controller panel. | upstream_code | `pump_controler.py:155-161` |
| `stop` sends `STP` with an optional string pump prefix; the same docstring applies. | upstream_code | `pump_controler.py:163-169` |
| The other per-pump commands format the pump number with `%i` (an integer, no zero padding). | upstream_code | `pump_controler.py:31` |
| The module opens COM10 at import time through the module-level variable `s`. | upstream_code | `pump_controler.py:177` |
| Line 48 is a Python 2 `print` statement, so the module does not import under Python 3. | upstream_code | `pump_controler.py:48` |

## Limits

No text file of the clone states a numeric range for the flow rate, the dispense volume, the run duration or the
syringe diameter. The catalogue pump class's `10000 uL/s` maximum is a class default, not a bound of this
device. Every numeric write and action input is therefore `Limit.operator_required`; until the site supplies a
bound in `site-limits.json`, the runtime refuses the call with `MHS.SAFETY.LIMITS_UNSET`.

| Input | Unit | Why the operator supplies it |
|---|---|---|
| state `flow_rate` | `uL/min` | `set_rate` writes the rate and the `UM*` unit token; the clone states no range. A negative value selects WDR. |
| state `volume` | `uL` | `set_volume` writes the value; the clone states no usable volume range or maximum. |
| `cap.actuation.pump.v1.flow_rate` | `uL/s` | No flow-rate range is stated in the clone. |
| `cap.actuation.pump.v1.volume` | `uL` | The clone has no volumetric run; it only runs until stopped. |
| `cap.actuation.pump.v1.duration_s` | `s` | The clone has no timed run; it only runs until stopped. |

The syringe diameter (`DIA`) is not exposed: the clone names the command but states no unit for the value, and
this driver does not invent one.

`site-limits.example.json` supplies an example overlay; it narrows the catalogue field and fills the
operator-required fields. It is an example, not a claim about an instrument.

## Units

* `flow_rate`: `uL/min`, the unit the clone labels a `UM` reply (`pump_controler.py:149-150`). Negative means
  WDR. The action's `flow_rate` is in `uL/s`; the driver multiplies by 60 before it writes the rate.
* `volume`: `uL`, from the `UL` default of the clone's `set_volume` signature (`pump_controler.py:83`) and the
  unit the `VOL` reply carries (`pump_controler.py:102`).
* `dispensed_volume`: `uL`; the driver asks for the INF field and requires the reply's unit to be `UL`. If the
  pump reports another unit, the read raises a precondition failure instead of guessing.

## Safety

The pump dispenses liquid, so the device is at least R2 (`MHS/spec/04-safety.md`) even though the card's floor
is R0. No text file of the clone documents an independent hardware e-stop, so the independent stop is the
`safe_state=True` action `x-cap.nsls-ii-chx.stop_pump.v1`, which writes the broadcast `STP`; the `@estop` writes
the same command without waiting for a reply. The safe state is every pump stopped. This package is
model-authored and unreviewed; `driver.lock.json` has `reviewed_by: null`, no hardware backend was run, and no
human reviewed or tested anything.

## Fake

`fake.py` is a stateful in-memory stand-in for the upstream `pump` class. It implements only the upstream method
names this driver uses. Its start values, address and replies are canned test data marked `# placeholder`; they
are not facts, limits or references, and they are not a recording of an instrument. The reply layout is chosen so
that the clone's own slices (`reply[4:7]`, `reply[4:-3]`, `reply[-3:-1]`, `reply[5:10]`, `reply[11:16]`) yield
the modelled values.

## Gate note

The clone is Python 2, and gate G7 resolves the native class with a Python 3 `ast` parser
(`MHS/sdk/src/mhs/driver/upstream.py:315-322`). It reports `pump_controler.py cannot be parsed` for the card's
only entry class, and the clone is read-only, so the package cannot pass G7. `RESULT.json` records
`PLATFORM_UNSUPPORTED`; the rest of the package is written so that only that gate fails.
