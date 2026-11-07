OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.bcda-aps/apstools

Every fact cites the pinned clone at commit `6250dbaa2f0413611fab56d6956c523d9fe2d293`. `upstream_code` refs name
`path/in/clone:LINE`, or a bounded range where the statement spans adjacent lines. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

Tags: `ophyd`, `epics`, `bluesky`, `storage-ring`, `machine-status`, `read-only`.

## Facts

| fact | source | ref |
|---|---|---|
| ApsMachineParametersDevice is an ophyd Device of common operational parameters of the APS. | upstream_code | apstools/devices/aps_machine.py:38-40 |
| The module imports Component, Device and EpicsSignalRO from ophyd. | upstream_code | apstools/devices/aps_machine.py:13-15 |
| `current` is a Component of EpicsSignalRO on PV S-DCCT:CurrentM. | upstream_code | apstools/devices/aps_machine.py:69 |
| `machine_status` is a Component of EpicsSignalRO on PV S:DesiredMode with string=True; a recorded session lists its enum strings State Unknown, USER OPERATIONS, Bm Ln Studies, INJ Studies, ASD Studies, NO BEAM and MAINTENANCE. | upstream_code | apstools/devices/aps_machine.py:72-81 |
| `operating_mode` is a Component of EpicsSignalRO on PV S:ActualMode with string=True; a recorded session lists its enum strings State Unknown, NO BEAM, Injecting, Stored Beam, Delivered Beam and MAINTENANCE. | upstream_code | apstools/devices/aps_machine.py:82-90 |
| `shutter_status` is a Component of EpicsSignalRO on PV XFD:ShutterPermit with string=True. | upstream_code | apstools/devices/aps_machine.py:94 |
| `shutters_open`, `fill_number` and `orbit_correction` are Components of EpicsSignalRO on PVs NoOfShuttersOpenA, S:FillNumber and S:OrbitCorrection:CC. | upstream_code | apstools/devices/aps_machine.py:95-97 |
| `aps_cycle` is a Component of ApsCycleDM. | upstream_code | apstools/devices/aps_machine.py:71 |
| `operator_messages` is a Component of ApsOperatorMessagesDevice. | upstream_code | apstools/devices/aps_machine.py:103 |
| ApsOperatorMessagesDevice is a Device of eight EpicsSignalRO string Components on PVs OPS:message1 to OPS:message8. | upstream_code | apstools/devices/aps_machine.py:20-35 |
| `inUserOperations` returns whether `machine_status.get()` is 1, USER OPERATIONS, 2 or Bm Ln Studies. | upstream_code | apstools/devices/aps_machine.py:105-129 |
| ApsCycleDM is a SynSignalRO that gets the APS cycle name from a local file. | upstream_code | apstools/devices/aps_cycle.py:141-143 |

## Scope

The package serves the seven EpicsSignalRO Components of `ApsMachineParametersDevice`, each as one read-only field
bound in `signal_bindings` with the profile `classic_epics_ro_v1`. Gate G7 proves every binding against its exact
Component assignment in the pinned source: the Component import, the EpicsSignalRO import, the literal PV suffix and
keywords, the class body and every method of the class (no receiver or Signal escapes, no reflection). Every read is
`Signal.get(use_monitor=False)`, a fresh Channel Access read; nothing reads a monitor cache.

A device needs at least one capability, and no catalogue read class fits a facility status monitor
(`cap.sensing.read.v1` reads the fields a caller names, and one native call cannot serve that; the measure classes
need a stated unit). The package therefore binds the observational extension `x-cap.bcda-aps.ring_current.v1`: it
calls the same proven `current.get` with `use_monitor=False` and returns the value. `RESULT.json` requests the id.

Not served, with the reason in the source:

- `aps_cycle` (aps_machine.py:71): an ApsCycleDM soft signal computed from a local schedule file, not an
  EpicsSignalRO Component; the source proof refuses it.
- `operator_messages` (aps_machine.py:103): a sub-Device of eight string PVs; nested Components are outside the
  proven profile.
- `inUserOperations` (aps_machine.py:105-129): a property that calls `machine_status.get()` without
  `use_monitor=False`, so it can return a monitored value; the agent can derive the same answer from the fresh
  `machine_status` read.

Units: no line of the clone states the engineering unit of any PV. The numeric fields carry no unit; the IOC's EGU
field is the unit at a deployment, and the agent must not assume one. The PV names are absolute (the Device has no
prefix), so they resolve only where the APS IOCs serve them.

## Safety

The device is data only: the package reads PVs and never writes to an IOC, so its risk is R0 (the card's floor) and it
declares no native stop. An e-stop latches the endpoint in software: the extension capability is refused until an
operator reset, while `mhs.resource.read` stays available. No physical stop is claimed, because there is nothing to
stop.

## Hardware backend

`native.py` imports `apstools.devices.aps_machine` only when an operator loads the hardware backend. That import runs
the package initializer `apstools/devices/__init__.py`, which imports every device module, and `aps_cycle.py` reads its
local schedule file at import. `connect` builds the Device under an operator-given name and waits for the seven bound
Signals to connect, one after another, each for at most `connection_timeout_s` (at most 60 s): the first Signal that
does not connect within it raises, and `connect` can take up to seven times that bound (420 s at the maximum) when each
Signal connects just within it. Constructing the Device also creates the `aps_cycle`
soft signal and the eight `operator_messages` string channels (OPS:message1 to OPS:message8), which the package
neither reads nor waits for. It was never run: the package has never connected to an IOC.

## Licence

The card and `driver.lock.json` record BSD-3-Clause, the registry's reading of the clone's `LICENSE.txt`, but the
clone declares `license = "LicenseRef-ANL-Open-Source-License"` (pyproject.toml:24) and `LICENSE.txt` is UChicago
Argonne's own open-source licence with an acknowledgment clause. A registry override therefore makes the card say
`publish_review: required`: publication of this package needs the owner's licence decision.

## Exemplar notes

This is the structural exemplar of the Ophyd family. It shows a complete get-only declaration, the source-shaped fake
(one stand-in per bound Component, implementing only `get(use_monitor=...)`), the observational extension pattern for
a read-only device and the facts a reviewer needs. It does not demonstrate a writable binding, a Status-returning set,
a native stop or `unit_bindings`; the [Ophyd driver guide](../../../sdk/docs/ophyd-driver.md) specifies those.
