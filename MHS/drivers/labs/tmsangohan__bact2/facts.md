# Facts and tags for gh.tmsangohan/bact2

The selected upstream class is `bact2.ophyd.devices.raw.vacuum:VacuumSensor` at the pinned commit
`1521bf0323aa1ad77c8a00d9664e4b6746157432`. Every fact below cites `path/in/clone:LINE`; the same facts are written
into `driver.py` (`facts = [...]`), and the reference file is generated from the driver, not from this page.

Tags: `ophyd`, `epics`, `vacuum`, `pressure`, `bessy-ii`, `read-only`.

## Facts

| fact | source | ref |
|---|---|---|
| VacuumSensor is an ophyd Device | upstream_code | bact2/ophyd/devices/raw/vacuum.py:3 |
| The module imports Component, Device and EpicsSignalRO from ophyd | upstream_code | bact2/ophyd/devices/raw/vacuum.py:1 |
| pressure is a Component of EpicsSignalRO on the PV suffix :rdPress | upstream_code | bact2/ophyd/devices/raw/vacuum.py:4 |
| quality is a Component of EpicsSignalRO on the PV suffix :stMeasQuality | upstream_code | bact2/ophyd/devices/raw/vacuum.py:5 |
| VacuumSensor declares only pressure and quality Components and inherits from the imported ophyd Device; it defines no stop method | upstream_code | bact2/ophyd/devices/raw/vacuum.py:1-5 |
| The VSR straight example constructs VacuumSensor('VMC3VS2R', name='vsr_straight') | upstream_code | examples/vsr_straight.py:33 |
| The VSR straight example plots the pressure reading of the vacuum sensor | upstream_code | examples/vsr_straight.py:63 |
| The package description says it provides ophyd device drivers for BESSY II | upstream_code | setup.py:8 |

## Scope

The package serves both direct Components of the selected class as read-only state fields:

- `pressure`, bound with the get-only `classic_epics_ro_v1` profile and `Signal.get(use_monitor=False)`;
- `quality`, the same way.

Gate G7 proves each binding against its literal `Component(EpicsSignalRO, "...")` declaration in the pinned source.
Nothing is discovered at run time, no monitor cache is read, and the package never writes a PV.

The one capability is the observational extension `x-cap.tmsangohan.vacuum_reading.v1`: it calls the same proven
fresh `pressure.get` and returns the raw number. No catalogue read class fits it. `cap.measure.pressure.v1` fixes
the output unit to Pa, while no line of the clone states the engineering unit of either PV; `cap.sensing.read.v1`
expects a values object and has an input that cannot be built from the single native Signal without a fake-only
method. The package therefore uses an `x-cap` id, does not carry a unit, and requests the extension in `RESULT.json`.

Not served: nothing else from the class exists. The PV engineering unit and the meaning of the `quality` bits are
not stated anywhere in the clone, so the package publishes the raw numbers and assumes neither.

The other card entries are outside this sensor package: `PowerConverter` binds a writable `:set` setpoint and
`:rdbk` readback (`bact2/ophyd/devices/raw/power_converter.py:7-17`); `Steerer` subclasses PowerConverter and can
restore a stored setpoint (`bact2/ophyd/devices/raw/steerers.py:96-122`); `BPMStorageRing` binds statistics at
`BPMZR` and waveforms at `MDIZ2T5G` (`bact2/ophyd/devices/pp/bpm/bpm.py:245-247`). None is constructed or controlled
by this package. Their actuation hazards require a separate assessment if they are integrated later.

## Safety

The device is a sensor. It has no writable Component, no actuator and no native command in the clone, so no motion,
energisation or process can be started through this package. The card floor is R1; the driver declares R1 and the
R1 hardware requirements: a `safe_state` sentence and a native stop binding. The stop binding calls the inherited
`Device.stop`. The clone defines no stop for VacuumSensor and the external ophyd base is not part of the pinned
source, so this package does not claim that the call changes the device or that it is a physical e-stop. The runtime
latch is the protection the package can provide; the `RESULT.json` notes disclose this and the package is
model-authored and unreviewed.

## Units and limits

No line of the clone states a unit or a range for `:rdPress` or `:stMeasQuality`, and the package has no writable
input. It declares no Limit and no unit. The observed values are the IOC's raw engineering values; the IOC's EGU
field is the deployment's unit and is not assumed here.

## Hardware backend

`native.py` imports `bact2.ophyd.devices.raw.vacuum` only when an operator loads the hardware backend. `connect`
builds `VacuumSensor(prefix, name=...)` from the operator's deployment options and waits for the two bound Signals,
one after another, each for at most `connection_timeout_s` (at most 60 s). No IOC connection was made and no
hardware run was performed.

## Licence

The card and `driver.lock.json` record `NOASSERTION`, the registry's reading of the clone's licence. The clone's
`setup.py:21` declares `license = "GPL"` and its classifiers name the GNU General Public License. The package is
therefore published only under the owner's licence decision (`publish_review: required` in the card).
