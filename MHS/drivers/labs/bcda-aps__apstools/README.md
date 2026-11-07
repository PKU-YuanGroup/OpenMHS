OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Exemplar: gh.bcda-aps/apstools (a read-only OphydDriver)

The APS storage-ring machine parameters, read through the classic Ophyd Device
`apstools.devices.aps_machine:ApsMachineParametersDevice`, as an R0 hardware driver. The package is model-authored
(`driver.lock.json` `authored_by` kind `model`) and unreviewed (`reviewed_by` null); it has run on the fake backend
only, and its evidence is `contract_checked`, never an MHS-Device level.

## Run the gate

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/drivers/labs/bcda-aps__apstools --backend fake
```

## What it demonstrates

| Pattern | Where |
|---|---|
| A config-only `OphydDriver`: `parameters` plus one `signal_bindings` entry per field, no decorated methods | `driver.py` |
| A binding names a direct `Component(...)` attribute of the card's entry class and cites its exact line in `source_ref`; G7 proves it in the pinned source | `_read_only()` in `driver.py` |
| The get-only profile `classic_epics_ro_v1` for `Component(EpicsSignalRO, ...)`, with `get_kwargs` `{"use_monitor": False}` (a fresh read) | `driver.py` |
| A read-only device still needs a capability: an observational `x-cap` read (`commands` plus `actions`) whose native is a bound `<signal>.get` | `x-cap.bcda-aps.ring_current.v1` |
| No unit where the source states none; strings where the Component reads with `string=True` | `parameters` |
| A source-shaped fake: one stand-in per bound Component, implementing only `get(use_monitor=...)` and recording its argument | `fake.py` |
| A hardware factory that builds the upstream Device and waits, with a bound, for the bound Signals only | `native.py` |
| Components and properties the profile cannot serve, each named with its reason | `facts.md`, `RESULT.json` |

## What it does not demonstrate

A writable binding (`classic_epics_v1`, `set: True`, a write that waits for the Signal's Status), limits on a write, a
native stop for R1+ hardware (`safety_bindings.estop` with source evidence) and `unit_bindings` for an operator-given
EPICS unit. The [Ophyd driver guide](../../../sdk/docs/ophyd-driver.md) specifies them, and the
[family page](../../../registry/families/bluesky-ophyd.md) maps Ophyd constructs to OpenMHS targets.

## For a new card of this family

1. Use the card's entry class. Bind only direct `Component(EpicsSignal | EpicsSignalRO | Signal, "literal")`
   declarations of that class; cite each at its line.
2. Run the gate. `OPHYD_COMPONENT_SOURCE`, `OPHYD_IDENTITY_UNRESOLVED` or `OPHYD_UNPROVEN_MEMBER` from G7 means the
   source falls outside the proven profile (nested Devices, `FormattedComponent`, custom Signal classes, reflection,
   ophyd-async): stop `blocked` and quote the finding; do not bind a different member to get past it. When another
   class of the repository is provable, name it with its `path:LINE` in the notes so a maintainer can decide on an
   entry-symbol override (this exemplar's card has one).
3. Set `risk` from the hazard table of `MHS/spec/04-safety.md`, not from this exemplar: anything that moves, opens
   a shutter or writes to an IOC is not R0, and R1+ hardware needs a native stop the source supports.

## Files

`driver.py` (the configuration), `fake.py`, `native.py`, `facts.md`, `test_driver.py` (the gate plus six cases),
`driver.lock.json`, `reference.json` and `REFERENCE.md` (generated), `RESULT.json`, `task.json` (the registry card).
