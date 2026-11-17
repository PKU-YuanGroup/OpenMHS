# Facts and limits for gh.cnpem/sophys-common

Selected entry symbol: `sophys.common.devices.compacteras:CompactERAS`
(`src/sophys/common/devices/compacteras.py:49`) at the pinned commit
`8bcf1e54511791b0f20ce1dc4d15a8cd6cc47eff`.  The repository is a multi-device pack of Bluesky/Ophyd
classes; this package drives the CompactERAS Soft IOC electrometer because it is a concrete device with
four measurable channels.  The other card entry symbols exist in the same clone
(`src/sophys/common/devices/motor.py:30`, `src/sophys/common/devices/aravis.py:51`,
`src/sophys/common/devices/pimega.py:222`, `src/sophys/common/devices/mobipix.py:85`) but are separate
devices, and one package serves one device.

## Facts

| fact | source | ref |
|---|---|---|
| CompactERAS is an ophyd Device documented as a CompactERAS Soft IOC; the class docstring names the channels through the CH{0..4} attributes and the class declares the CH1 to CH4 Channel components | upstream_code | src/sophys/common/devices/compacteras.py:49-69 |
| Channel.voltage is an EpicsSignalRO Component on the Voltage suffix and Channel.current is an EpicsSignalRO Component on the Current suffix | upstream_code | src/sophys/common/devices/compacteras.py:16-21 |
| CompactERAS.CH1 to CH4 are Channel Components with the CH1: to CH4: suffixes | upstream_code | src/sophys/common/devices/compacteras.py:66-69 |
| version reads the Version PV and supported_devices reads the DevicesUsed PV, both as string signals | upstream_code | src/sophys/common/devices/compacteras.py:56-61 |
| sampling_rate reads the SamplingRate PV and acquisition_bandwidth reads the AcquisitionBandwidth PV | upstream_code | src/sophys/common/devices/compacteras.py:58-59 |
| verifyVersion reads version.get() and returns False when the read raises ConnectionTimeoutError | upstream_code | src/sophys/common/devices/compacteras.py:102-115 |
| getSupportedDevices splits the supported_devices reply on single spaces | upstream_code | src/sophys/common/devices/compacteras.py:144-146 |

## Limits

This package declares no MHS `Limit`.  The four channel names are the components the upstream class
defines (`src/sophys/common/devices/compacteras.py:66-69`); the driver enforces them as a device
precondition (`MHS.DEVICE.PRECONDITION_UNMET`) before any read, not as a safety envelope.  There is no
numeric set point, range or timeout to bound: the package binds no write and no actuation.

The voltage and current values are read-only measurements, so their units come from the measurement
class (`V` and `A`), not from a device bound.

## Safety

The clone declares no stop, abort, disable or acquisition command on CompactERAS
(`src/sophys/common/devices/compacteras.py:49-146`).  The driver therefore has no `@estop` native call and
claims none: it is an R0 read-only data integration.  The endpoint's software e-stop latch changes nothing
on the device, and `safe_state` says so.  No hardware e-stop is cited and none is claimed.

## Fake and fidelity

`fake.py` is an in-memory stand-in, not a recording and not an upstream simulator: the clone ships no
simulator or mock for CompactERAS.  It preserves the upstream surface the driver uses: the `CH1` to
`CH4` Channel components with their `voltage` and `current` read-only signals, the `version` and
`supported_devices` signals, and the public `verifyVersion` and `getSupportedDevices` methods.  Every
number and reply in it is marked `# placeholder`; none is a Fact, a Limit or a citation.  The values
never move by themselves.

## Not covered

- The hardware backend (`native.py`) was never imported or run, and no EPICS Soft IOC was contacted.
- The writable upstream members are not exposed: `Channel.measurement_type`, the offsets and scale
  factors, the `Scale` calibration settings and `CompactERAS.verifyVersion` as a command.  The clone
  states no range or safe value for them, so this package does not invent a write envelope.
- The upstream `verifyVersion` logs a warning for an incompatible version but still returns `True` after
  the version read succeeds (`src/sophys/common/devices/compacteras.py:117-142`). The fake preserves that
  behaviour. It is not bound as an MHS interlock.
