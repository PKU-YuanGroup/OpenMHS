OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.nsls2/hxn-profile-collection

Every fact cites the pinned clone at commit `14429cea35cf05a95f90f5c69f721f3ffc62faa7` with `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

Tags: `ophyd`, `epics`, `bluesky`, `nsls2`, `hxn`, `beamline-status`, `read-only`.

## Facts

| fact | source | ref |
|---|---|---|
| BeamlineStatus is an ophyd Device in the HXN startup profile. | upstream_code | startup/10-optics.py:13 |
| The file imports Device, Component as Cpt and EpicsSignalRO from ophyd. | upstream_code | startup/10-optics.py:4-6 |
| `shutter_status` is a Component of EpicsSignalRO on PV SR-EPS{PLC:1}Sts:MstrSh-Sts. | upstream_code | startup/10-optics.py:14 |
| `beam_current` is a Component of EpicsSignalRO on PV SR:C03-BI{DCCT:1}I:Real-I. | upstream_code | startup/10-optics.py:15 |
| `beamline_enabled` is a Component of EpicsSignalRO on PV SR:C03-EPS{PLC:1}Sts:ID_BE_Enbl-Sts. | upstream_code | startup/10-optics.py:16-17 |
| `cryo_filling` is a Component of EpicsSignalRO on PV XF:03IDA-OP{CC:1}V3_STS. | upstream_code | startup/10-optics.py:18-19 |
| The profile instantiates BeamlineStatus with an empty prefix and the name `beamline_status`, so the Component PV names are absolute. | upstream_code | startup/10-optics.py:22 |
| The profile uses `beamline_status.beam_current` in SuspendFloor, `beamline_status.shutter_status` in SuspendBoolLow, `beamline_status.beamline_enabled` in SuspendBoolLow and `beamline_status.cryo_filling` in SuspendBoolHigh. | upstream_code | startup/52-suspenders.py:8-26 |

## Scope

The package serves the four EpicsSignalRO Components of `BeamlineStatus` (startup/10-optics.py:13-19). Each field is
one read method that calls the Signal's own `get(use_monitor=False)`: a fresh Channel Access read, never a monitor
cache. The class has no methods, no writable Signal and no stop method; the package therefore exposes no write and no
native stop.

The selected class is defined inside an IPython startup script. The file name contains a hyphen, and importing the
file would run the whole beamline profile; the package never imports or executes the clone. `native.py` ports the four
literal Component declarations (the same PV names, in the same order) into a small ophyd Device and waits for the four
Signals when an operator loads the hardware backend. The package is model-authored and unreviewed (`reviewed_by` is
null) and has run on the fake backend only.

The repository is a beamline profile collection, not a package of device classes. `BeamlineStatus` is the one
self-contained, method-free `Device` whose Components are the classic read-only Signal type supported by the clone.
The profile's motion, shutter, detector, plan and pseudo-positioner classes are outside this package: they are not
served, and no control of them is claimed. The card's `entry_symbols` list is empty and `mock_strategy` points at the
startup scripts; the detector and plan modules are not importable without EPICS, `hxntools` and the rest of the
profile.

## Units

No line of the clone states an engineering unit for any of the four PVs. The fields carry no unit; the IOC's EGU is
the deployment's unit and must not be guessed. The suspend thresholds at `startup/52-suspenders.py:8-26` (150.0 and
240.0 in SuspendFloor, with no unit on the lines) are scan-plan configuration, not limits of the device; they are not
exposed as a `Limit` and no `site-limits.example.json` is needed.

## Safety

The device is data only: the package reads four PVs and never writes to an IOC, so its risk is R0 (the card's floor)
and it declares no native stop. An e-stop latches the endpoint in software: `cap.sensing.read.v1` is refused until an
operator reset, while `mhs.resource.read` stays available. No physical stop is claimed, because there is nothing to
stop.

## Hardware backend

`native.py` imports `ophyd` only when an operator loads the hardware backend. It builds the ported `BeamlineStatus`,
waits for the four Signals to connect, one after another, each for at most `connection_timeout_s` (at most 60 s), and
returns the Device. The first Signal that does not connect within its bound raises, before any MHS command is served.
It was never run: the package has never connected to an IOC.
