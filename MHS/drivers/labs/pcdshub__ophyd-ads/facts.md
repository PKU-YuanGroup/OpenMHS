# Facts and tags for gh.pcdshub/ophyd-ads

Every fact cites the pinned clone at commit `2029e0bebee6148aba47e5947467574337fea61a` as
`upstream_code` (or `vendor_doc` for README.rst) with `path/in/clone:LINE` (or a bounded adjacent range).  The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

Tags: `ophyd`, `ads`, `beckhoff`, `twincat`, `nc-axis`, `telemetry`, `read-only`.

## Facts

| fact | source | ref |
|---|---|---|
| `NcAxis` is an ophyd `Device` whose fields are `Component(AdsSignal, ...)` declarations. | upstream_code | ophyd_ads/devices.py:7-18 |
| The README describes ophyd-ads as ophyd integration with Beckhoff TwinCAT 3 via pyads. | vendor_doc | README.rst:12 |
| `act_acc`, `act_pos`, `act_pos_modulo`, `act_torque`, `act_velo`, `axis_state`, `cmd_no`, `control_d_word`, `couple_state`, `ctrl_output` and `drive_output` are `Component(AdsSignal, ...)` declarations of `NcAxis`. | upstream_code | ophyd_ads/devices.py:8-18 |
| `set_acc`, `set_pos`, `set_pos_modulo`, `set_torque` and `set_velo` are also `Component(AdsSignal, ...)` declarations of `NcAxis`; this read-only package does not bind them. | upstream_code | ophyd_ads/devices.py:25-29 |
| `AdsSignal` is a `Signal` subclass. | upstream_code | ophyd_ads/signal.py:32 |
| `AdsSignal.get` reads the `Symbol` value over ADS and updates the `Signal` value and timestamp. | upstream_code | ophyd_ads/signal.py:72-78 |
| `AdsSignal.put` writes the value through the `Symbol` over ADS. | upstream_code | ophyd_ads/signal.py:80-83 |
| `AdsSignal` parses an ADS address from `read_pv` and requires an IP address. | upstream_code | ophyd_ads/signal.py:40-60 |
| `AdsSignal` obtains its `Symbol` from `Plc.get_symbol` with the `_SignalSymbol` class. | upstream_code | ophyd_ads/signal.py:62-64 |
| `Symbol.read` reads the symbol by name with the ADS data type. | upstream_code | ophyd_ads/ads.py:206-210 |
| `Plc.get_symbol` caches a `Symbol` by symbol name, poll rate and class, and opens the ADS connection when it is closed. | upstream_code | ophyd_ads/ads.py:340-348 |
| `Plc.stop` sets `running` to `False` and queues a no-op. | upstream_code | ophyd_ads/ads.py:298-300 |
| The `Plc` connection thread loops while `running` and closes the ADS connection when it exits. | upstream_code | ophyd_ads/ads.py:324-333 |
| `Plc.stop_polling` removes a registered poll call from the poll thread. | upstream_code | ophyd_ads/ads.py:282-287 |

## Scope and deviation from the card

The card proposes `OphydDriver` with `ophyd_ads.devices:NcAxis` as the entry class.  The family helper proves direct
classic `Component(EpicsSignal | EpicsSignalRO | Signal, "literal")` declarations; `NcAxis` uses
`Component(AdsSignal, ...)`, and `AdsSignal` is a custom `Signal` subclass (ophyd_ads/signal.py:32), so the Ophyd
source proof cannot bind it.  This package is a direct `Driver` over the same entry class, with a `native.py`
factory.  `native` remains one of the card's entry symbols (`ophyd_ads.devices:NcAxis`, devices.py:7), so gate G7
checks the fake against the upstream class.

Served: the eleven telemetry channels the card names, each as one read-only field (`@read`) and as one member of the
`cap.sensing.read.v1` action.  Each read is a fresh `AdsSignal.get` (signal.py:72-78) and therefore a fresh
`Symbol.read` (ads.py:206-210), not a monitor cache; the optional `fields` input selects a subset.  A name outside the
eleven channels contributes no value, so the catalogue class example `fields: ["temperature"]` completes with an
empty `values` object rather than a fabricated reading; the package never invents a channel the clone does not have.

NOT COVERED: the five `set_*` Components (`set_acc`, `set_pos`, `set_pos_modulo`, `set_torque`, `set_velo`;
devices.py:25-29), which would write a motion setpoint through `AdsSignal.put` (signal.py:80-83); the six other
telemetry Components (`err_state`, `homing_state`, `override_v`, `pos_diff`, `pos_diff_couple`, `state_d_word`;
devices.py:19, 21-24, 30); the commented-out `from_plc`/`to_plc` declarations (devices.py:20, 31); and the
subscription path (`AdsSignal.subscribe`, signal.py:91-100).  The package exposes no write and no subscription.

Units: no line of the clone states an engineering unit, scale or axis meaning for these symbols.  The fields
therefore carry no unit, and a deployment's TwinCAT symbol configuration supplies the actual meaning.

## Safety

The device is data only as integrated: the package reads ADS symbols and never writes a setpoint, so its risk is R0
(the card's floor) and it declares no native stop.  A TwinCAT NC axis can move when a caller writes a `set_*` symbol
(devices.py:25-29, signal.py:80-83), but this package does not expose that path.  `Plc.stop` is not an axis stop: it
stops the Python client's queue thread and closes the ADS connection (ads.py:298-300, 324-333), and it sends no stop
command to the PLC; no clone text supports an axis stop.  An MHS e-stop engages the endpoint's software latch and
stops nothing physical; it is not claimed as a hardware e-stop.

## Hardware backend

`native.py` imports `ophyd_ads.devices` only when an operator loads the hardware backend.  Its `connect` builds
`NcAxis(prefix=<deployment ADS address>, name=<operator name>)`, where the prefix is
`ads://<host>[:<port>][/@<poll_rate>]/<symbol-prefix>` and `AdsSignal` parses the resulting per-Component address
(signal.py:40-63).  `NcAxis` declares 22 Components, including the setpoints this package never reads or writes;
ophyd constructs a Component when the Device is built or the attribute is first used, and each constructed
`AdsSignal` registers a `Symbol` with the process-wide `Plc` cache and opens the ADS connection if it is closed
(signal.py:62-64, ads.py:340-348).  The factory performs no read, write, subscription or stop; a missing PLC or
symbol may surface while the Device is built or on the first driver read.  It has never been run; no ADS library,
PLC or hardware was imported or attached here.

## Fidelity

The fake is a source-shaped stand-in, not a recording of ADS traffic: one stored value and a call counter per served
`Component`, and every value is a placeholder (`# placeholder` in `fake.py`).  It models no ADS connection, symbol
type resolution, PLC cycle, axis state machine or timing.  The gate evidence is `contract_checked`; it is not an
MHS-Device level and does not establish a real PLC or hardware run.

## Licence

The card and `driver.lock.json` record BSD-3-Clause.  The clone's `LICENSE` is the three-clause BSD text of the
Board of Trustees of the Leland Stanford Junior University, and `setup.py:48` declares `license='BSD'`.

## Authorship

The package was written by a model (`driver.lock.json` `authored_by` kind `model`, model id
`deepseek-v4.1-flash:1017`) and `reviewed_by` is null.  No human reviewed or tested it, and no hardware run is
claimed.
