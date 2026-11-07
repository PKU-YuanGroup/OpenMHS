"""OpenMHS driver for gh.bcda-aps/apstools: the APS storage-ring machine parameters, read only.

The OphydDriver exemplar.  A config-only ``OphydDriver`` over the classic Ophyd Device
``apstools.devices.aps_machine:ApsMachineParametersDevice`` (apstools/devices/aps_machine.py:38), which reads common
operational parameters of the Advanced Photon Source storage ring from EPICS PVs.

* Every field is one explicit ``signal_bindings`` entry: a direct ``Component(EpicsSignalRO, "<PV>")`` declaration of
  the selected class, cited at its exact line (``source_ref``).  Gate G7 proves each declaration in the pinned source
  with the get-only profile ``classic_epics_ro_v1``; nothing is discovered at run time.
* Every read calls ``Signal.get(use_monitor=False)``: a fresh Channel Access read, never a monitor cache.
* The device is data only (risk R0).  It declares no write, no Status-returning set and no native stop: the Device has
  nothing to actuate.  Its one capability is the observational extension ``x-cap.bcda-aps.ring_current.v1``, which
  reads the ring current through the same proven ``current.get``.
* Not exposed: the ``aps_cycle`` Component (``ApsCycleDM``, a soft signal computed from a local schedule file) and the
  ``operator_messages`` Component (a sub-Device of eight string PVs).  Neither is a direct EpicsSignalRO declaration
  of the selected class, so both are outside the proven profile.  The ``inUserOperations`` property is not exposed
  either: its ``machine_status.get()`` call does not force a fresh read (aps_machine.py:126).
* Units: the source states no engineering unit for any PV.  The numeric fields carry no unit; the IOC's EGU field is
  the deployment's unit, and the agent must not assume one.

Every Fact and every ``source_ref`` cites the clone at the pinned commit 6250dbaa2f0413611fab56d6956c523d9fe2d293.  The
package is model-authored and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and has
never connected to an IOC.
"""

from mhs.driver import Action, Fact, Field, OphydDriver

#: The module of the selected upstream class, relative to the clone root.
SOURCE = "apstools/devices/aps_machine.py"
#: The observational extension capability (the device has no catalogue read class: see RESULT.json).
RING_CURRENT = "x-cap.bcda-aps.ring_current.v1"


def _read_only(signal: str, line: int) -> dict:
    """One get-only binding: the EpicsSignalRO Component ``signal`` declared at ``SOURCE:line``."""
    return {"signal": signal, "get": True, "set": False, "profile": "classic_epics_ro_v1",
            "get_kwargs": {"use_monitor": False}, "timeout_ms": 2000, "source_ref": f"{SOURCE}:{line}"}


class ApsMachineParameters(OphydDriver):
    device_id = "aps-machine-parameters"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    native = "apstools.devices.aps_machine:ApsMachineParametersDevice"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeApsMachineParametersDevice"}
    model = "ApsMachineParametersDevice (apstools)"
    display_name = "APS storage-ring machine parameters (apstools, read only)"
    tags = ["ophyd", "epics", "bluesky", "storage-ring", "machine-status", "read-only"]
    safe_state = ("unchanged: the package only reads PVs and never writes to the IOC; an e-stop latches the endpoint "
                  "against further commands and stops nothing physical")

    parameters = {
        "current": Field("number", description="Storage-ring current, a fresh read of PV S-DCCT:CurrentM (the IOC's "
                                               "engineering unit; the source states none)"),
        "machine_status": Field("string", description="Fresh string read of PV S:DesiredMode; the source states no "
                                                      "meaning beyond the PV name"),
        "operating_mode": Field("string", description="Fresh string read of PV S:ActualMode; the source states no "
                                                      "meaning beyond the PV name"),
        "shutter_status": Field("string", description="Fresh string read of PV XFD:ShutterPermit; the source states "
                                                      "no meaning beyond the PV name"),
        "shutters_open": Field("number", description="Fresh read of PV NoOfShuttersOpenA (attribute shutters_open)"),
        "fill_number": Field("number", description="Fresh read of PV S:FillNumber"),
        "orbit_correction": Field("number", description="Fresh read of PV S:OrbitCorrection:CC; the source states no "
                                                        "unit or meaning"),
    }
    signal_bindings = {
        "current": _read_only("current", 69),
        "machine_status": _read_only("machine_status", 72),
        "operating_mode": _read_only("operating_mode", 82),
        "shutter_status": _read_only("shutter_status", 94),
        "shutters_open": _read_only("shutters_open", 95),
        "fill_number": _read_only("fill_number", 96),
        "orbit_correction": _read_only("orbit_correction", 97),
    }
    commands = {
        RING_CURRENT: {"native": "current.get", "invoke": "call", "args": {"use_monitor": {"value": False}},
                       "result": {"map": {"current": "output.$"}}, "concurrency": "shared", "timeout_ms": 2000},
    }
    actions = {
        RING_CURRENT: Action(
            name="read_ring_current", verb="read",
            description="Read the storage-ring current fresh from PV S-DCCT:CurrentM (EpicsSignalRO get, "
                        "use_monitor=False); no input, no effect",
            output={"current": Field("number", description="Storage-ring current in the IOC's engineering unit")}),
    }
    facts = [
        Fact("ApsMachineParametersDevice is an ophyd Device of common operational parameters of the APS",
             source="upstream_code", ref=f"{SOURCE}:38-40"),
        Fact("The module imports Component, Device and EpicsSignalRO from ophyd", source="upstream_code",
             ref=f"{SOURCE}:13-15"),
        Fact("current is a Component of EpicsSignalRO on PV S-DCCT:CurrentM", source="upstream_code",
             ref=f"{SOURCE}:69"),
        Fact("machine_status is a Component of EpicsSignalRO on PV S:DesiredMode with string=True; a recorded session "
             "lists its enum strings State Unknown, USER OPERATIONS, Bm Ln Studies, INJ Studies, ASD Studies, "
             "NO BEAM and MAINTENANCE", source="upstream_code", ref=f"{SOURCE}:72-81"),
        Fact("operating_mode is a Component of EpicsSignalRO on PV S:ActualMode with string=True; a recorded session "
             "lists its enum strings State Unknown, NO BEAM, Injecting, Stored Beam, Delivered Beam and MAINTENANCE",
             source="upstream_code", ref=f"{SOURCE}:82-90"),
        Fact("shutter_status is a Component of EpicsSignalRO on PV XFD:ShutterPermit with string=True",
             source="upstream_code", ref=f"{SOURCE}:94"),
        Fact("shutters_open, fill_number and orbit_correction are Components of EpicsSignalRO on PVs "
             "NoOfShuttersOpenA, S:FillNumber and S:OrbitCorrection:CC", source="upstream_code",
             ref=f"{SOURCE}:95-97"),
        Fact("aps_cycle is a Component of ApsCycleDM", source="upstream_code", ref=f"{SOURCE}:71"),
        Fact("operator_messages is a Component of ApsOperatorMessagesDevice", source="upstream_code",
             ref=f"{SOURCE}:103"),
        Fact("ApsOperatorMessagesDevice is a Device of eight EpicsSignalRO string Components on PVs OPS:message1 to "
             "OPS:message8", source="upstream_code", ref=f"{SOURCE}:20-35"),
        Fact("inUserOperations returns whether machine_status.get() is 1, USER OPERATIONS, 2 or Bm Ln Studies",
             source="upstream_code", ref=f"{SOURCE}:105-129"),
        Fact("ApsCycleDM is a SynSignalRO that gets the APS cycle name from a local file", source="upstream_code",
             ref="apstools/devices/aps_cycle.py:141-143"),
    ]
