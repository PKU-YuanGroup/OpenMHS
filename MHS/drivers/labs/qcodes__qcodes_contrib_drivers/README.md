# Exemplar: gh.qcodes/qcodes_contrib_drivers (a QcodesDriver)

The Thorlabs PM100D optical power meter of the QCoDeS contrib driver pack
(`qcodes_contrib_drivers.drivers.Thorlabs.PM100D:Thorlab_PM100D`) as an R1 hardware driver. The package is
model-authored (`driver.lock.json` `authored_by` kind `model`) and unreviewed (`reviewed_by` null); it has run on the
fake backend only, and its evidence is `contract_checked`, never an MHS-Device level.

## Run the gate

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/drivers/labs/qcodes__qcodes_contrib_drivers --backend fake
```

## What it demonstrates

| Pattern | Where |
|---|---|
| A config-only `QcodesDriver`: `parameters` plus one `parameter_bindings` entry per field | `driver.py` |
| A binding names a Parameter that `__init__` constructs as `self.<name> = Parameter(...)` and cites its constructor lines in `source_ref`; G7 proves it in the pinned source | `_binding()` in `driver.py` |
| Field types that follow what `Parameter.get()` returns after the upstream parsers: float, a bool from an on/off mapping, the raw string where no parser exists | `parameters` |
| A write through `cap.device.configure.v1` with `Limit.operator_required` and a narrowing site overlay | `power_range`, `site-limits.example.json` |
| A native stop the source supports: `safety_bindings.estop` with `invoke: write` and the abort command the upstream itself sends | `safety_bindings` |
| Teardown through `native_close = "close"` | `driver.py` |
| A source-shaped fake: one stand-in per bound Parameter (`get`, and `set` only where the upstream has a `set_cmd`) plus the instrument's `write` and `close`; it does not apply the upstream validators or value mapping | `fake.py` |
| A read that is not side-effect free, stated as such: every `power` read re-applies the power configuration (CONF:POW, ABOR, INIT) and aborts a measurement in progress | `parameters`, `facts.md` |
| A hardware factory that takes the VISA address from the operator and discloses what the upstream constructor sends | `native.py` |
| Every Parameter that is not served, with the source line that is the reason (`scale` without `get_parser`, a `set_cmd` without a value placeholder, dB, a `MEAS:...?` read) | `facts.md`, `RESULT.json` |

## For a new card of this family

1. Use the card's entry class. Bind only Parameters constructed explicitly in its `__init__` with an explicit
   `get_cmd` (and `set_cmd` for a write), `Parameter` imported from `qcodes.parameters`.
2. Run the gate. `QCODES_PARAMETER_SOURCE` or `QCODES_UNDECLARED_MEMBER` from G7 means the source falls outside the
   proven profile; `add_parameter`, channels and submodules are not provable today. Stop `blocked` and quote the
   finding; do not bind a different member to get past it. When another class of the repository is provable, name it
   with its `path:LINE` in the notes so a maintainer can decide on an entry-symbol override (this exemplar's card
   has one).
3. Read every Parameter's parsers, `scale` and `set_cmd` before binding it; a validator is a sourced limit only where
   it bounds the device, otherwise use `Limit.operator_required`.
4. Set `risk` from the hazard table of `MHS/spec/04-safety.md`, not from this exemplar (heating and a laser above
   class 1 are R2, high voltage R3). R1+ hardware needs a native stop the source supports.

## Files

`driver.py` (the configuration), `fake.py`, `native.py`, `facts.md`, `site-limits.example.json`, `test_driver.py` (the
gate plus seven cases), `driver.lock.json`, `reference.json` and `REFERENCE.md` (generated), `RESULT.json`,
`task.json` (the registry card).
