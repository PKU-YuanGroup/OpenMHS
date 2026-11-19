"""OpenMHS driver for gh.tmsangohan/bact2: one BESSY II vacuum sensor, read only.

The selected upstream class is ``bact2.ophyd.devices.raw.vacuum:VacuumSensor`` (vacuum.py:3), a classic Ophyd
``Device`` whose two Components are direct ``Component(EpicsSignalRO, "<suffix>")`` declarations:

* ``pressure`` on the device prefix plus ``:rdPress`` (vacuum.py:4);
* ``quality`` on the device prefix plus ``:stMeasQuality`` (vacuum.py:5).

The config-only ``OphydDriver`` binds both Components explicitly, with the get-only ``classic_epics_ro_v1`` profile
and ``Signal.get(use_monitor=False)``, so every state read is a fresh Channel Access read and not the monitor cache.
The source proof of G7 accepts the class because its only base is the unshadowed ``Device`` import from ``ophyd``
(vacuum.py:1, :3); the Components are literal EpicsSignalRO declarations with literal suffixes.

The device is a sensor: it has no writable Component and no method in the clone that actuates anything.  Its one
capability is therefore an observational extension, ``x-cap.tmsangohan.vacuum_reading.v1``, which performs the same
proven fresh ``pressure.get`` and returns the raw number.  No catalogue read class fits it: ``cap.measure.pressure.v1``
fixes the output unit to Pa, while no line of the clone states the engineering unit of either PV.  The package asks
for an extension in RESULT.json and publishes the value without a unit.

The e-stop binding calls the inherited ``Device.stop``.  The clone's whole VacuumSensor class is vacuum.py:3-5 and
defines no stop; ophyd's base method is outside the pinned clone, so the package does not claim that it changes the
sensor or that it is a physical stop.  The runtime latch is the protection this package can actually provide.

Every Fact cites the clone at the pinned commit 1521bf0323aa1ad77c8a00d9664e4b6746157432.  The package is
model-authored and unreviewed (``reviewed_by`` is null); the gate checks the fake backend only, and this package has
never connected to an IOC or to the device.
"""

from mhs.driver import Action, Fact, Field, OphydDriver

#: The selected class, its Components and the base import are all in this file of the clone.
SOURCE = "bact2/ophyd/devices/raw/vacuum.py"
#: The observational capability: its id is an extension because no catalogue class fits an unstated pressure unit.
VACUUM_READING = "x-cap.tmsangohan.vacuum_reading.v1"


def _read_only(signal: str, line: int) -> dict:
    """The get-only classic Ophyd binding of the Component ``signal`` declared at ``SOURCE:line``."""
    return {"signal": signal, "get": True, "set": False, "profile": "classic_epics_ro_v1",
            "get_kwargs": {"use_monitor": False}, "timeout_ms": 2000,
            "source_ref": f"{SOURCE}:{line}"}


class Bact2VacuumSensor(OphydDriver):
    device_id = "bact2-vacuum-sensor"
    device_kind = "sensor.pressure"
    mode = "hardware"
    risk = "R1"
    native = "bact2.ophyd.devices.raw.vacuum:VacuumSensor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeVacuumSensor"}
    model = "VacuumSensor (bact2)"
    display_name = "BESSY II vacuum sensor (bact2, read only)"
    tags = ["ophyd", "epics", "vacuum", "pressure", "bessy-ii", "read-only"]
    safe_state = ("unchanged: the sensor only reads PVs; the e-stop latches the endpoint and calls the inherited "
                  "ophyd Device.stop, which the clone does not define and this package does not claim changes the "
                  "device")

    parameters = {
        "pressure": Field("number", description="Fresh read of the raw pressure PV suffix :rdPress (the IOC's "
                                                "engineering unit; no line of the clone states it)"),
        "quality": Field("number", description="Fresh read of the measurement-quality PV suffix :stMeasQuality "
                                               "(the source states no meaning or unit beyond the PV suffix)"),
    }
    signal_bindings = {
        "pressure": _read_only("pressure", 4),
        "quality": _read_only("quality", 5),
    }
    commands = {
        VACUUM_READING: {
            "native": "pressure.get", "invoke": "call",
            "args": {"use_monitor": {"value": False}},
            "result": {"map": {"pressure": "output.$"}},
            "concurrency": "shared", "timeout_ms": 2000,
        },
    }
    actions = {
        VACUUM_READING: Action(
            name="read_pressure", verb="read",
            description="Read the raw pressure PV suffix :rdPress fresh (EpicsSignalRO get, use_monitor=False); "
                        "no input, no effect",
            output={"pressure": Field("number", description="Raw pressure value in the IOC's engineering unit; the "
                                                           "clone states no unit")}),
    }
    safety_bindings = {
        "estop": {"native": "stop", "invoke": "call", "timeout_ms": 2000,
                  "description": "the inherited ophyd Device.stop; the sensor has no actuator, so the runtime latch "
                                 "is the protection and no physical stop is claimed"},
    }
    facts = [
        Fact("VacuumSensor is an ophyd Device", source="upstream_code", ref=f"{SOURCE}:3"),
        Fact("The module imports Component, Device and EpicsSignalRO from ophyd", source="upstream_code",
             ref=f"{SOURCE}:1"),
        Fact("pressure is a Component of EpicsSignalRO on the PV suffix :rdPress", source="upstream_code",
             ref=f"{SOURCE}:4"),
        Fact("quality is a Component of EpicsSignalRO on the PV suffix :stMeasQuality", source="upstream_code",
             ref=f"{SOURCE}:5"),
        Fact("VacuumSensor declares only pressure and quality Components and inherits from the imported ophyd "
             "Device; it defines no stop method", source="upstream_code", ref=f"{SOURCE}:1-5"),
        Fact("The VSR straight example constructs VacuumSensor('VMC3VS2R', name='vsr_straight')",
             source="upstream_code", ref="examples/vsr_straight.py:33"),
        Fact("The VSR straight example plots the pressure reading of the vacuum sensor", source="upstream_code",
             ref="examples/vsr_straight.py:63"),
        Fact("The package description says it provides ophyd device drivers for BESSY II", source="upstream_code",
             ref="setup.py:8"),
    ]
