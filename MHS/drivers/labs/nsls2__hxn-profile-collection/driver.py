"""OpenMHS driver for the HXN beamline status monitor of gh.nsls2/hxn-profile-collection.

The selected upstream class is ``BeamlineStatus`` (``startup/10-optics.py:13``), an ophyd ``Device`` of four
read-only ``Component(EpicsSignalRO, "<PV>")`` declarations: the storage-ring master-shutter status, the storage-ring
beam current, the beamline-enabled flag and the cryogenic-cooler refill flag.  The profile instantiates it with an
empty prefix (``startup/10-optics.py:22``), so every Component carries an absolute EPICS PV name.

DEVIATION FROM THE CARD: the card proposes the ``OphydDriver`` helper, but the selected class lives in an IPython
startup script that is not an importable module (the file name contains a hyphen and importing it would execute the
whole beamline profile), and the Ophyd source proof rejects the shared module because it also uses ``EpicsSignalRO``
through ``FormattedComponent`` in an unrelated class (``startup/10-optics.py:133-134``).  This package is therefore a
direct ``Driver`` over the class, with a ``native.py`` factory that ports the four literal Component declarations
instead of importing the startup script.  The interface is unchanged: each read is the Signal's own ``get``.

* Every read calls ``EpicsSignalRO.get(use_monitor=False)``: a fresh Channel Access read, never a monitor cache.
* ``cap.sensing.read.v1`` returns the current values of the requested channels, selected by the class's ``fields``
  input.  An unknown name is refused; the driver never invents a reading.
* The device is data only (risk R0).  It declares no write, no Status-returning set and no native stop: the upstream
  class has only four read-only Signals and nothing to actuate.  An e-stop latches the endpoint in software and stops
  no physical device, and no physical stop is claimed.
* Units: no line of the clone states an engineering unit for any of the four PVs; the fields carry no unit, and the
  deployment's IOC EGU is not guessed.  The suspend thresholds in ``startup/52-suspenders.py:8-26`` are scan-plan
  configuration, not device limits, and are not exposed as a Limit.

Every Fact and every ``source_ref`` cites the clone at commit 14429cea35cf05a95f90f5c69f721f3ffc62faa7.  The package
is model-authored and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and has never
connected to an IOC.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read

#: The module of the selected upstream class, relative to the clone root.
SOURCE = "startup/10-optics.py"
#: The suspend configuration that uses the four signals, relative to the clone root.
SUSPENDERS = "startup/52-suspenders.py"

#: The four read-only channels of BeamlineStatus, in declaration order.
FIELDS = ("shutter_status", "beam_current", "beamline_enabled", "cryo_filling")


class HxnBeamlineStatus(Driver):
    device_id = "hxn-beamline-status"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    native = "pyfile:startup/10-optics.py#BeamlineStatus"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBeamlineStatus"}
    vendor = "NSLS-II"
    model = "BeamlineStatus (HXN bluesky profile)"
    display_name = "HXN beamline status (NSLS-II, read only)"
    tags = ["ophyd", "epics", "bluesky", "nsls2", "hxn", "beamline-status", "read-only"]
    safe_state = ("unchanged: the package only reads four EPICS PVs and never writes to an IOC; an e-stop engages "
                  "the endpoint's software latch and stops nothing physical")
    facts = [
        Fact("BeamlineStatus is an ophyd Device in the HXN startup profile",
             source="upstream_code", ref=f"{SOURCE}:13"),
        Fact("The file imports Device, Component as Cpt and EpicsSignalRO from ophyd",
             source="upstream_code", ref=f"{SOURCE}:4-6"),
        Fact("shutter_status is a Component of EpicsSignalRO on PV SR-EPS{PLC:1}Sts:MstrSh-Sts",
             source="upstream_code", ref=f"{SOURCE}:14"),
        Fact("beam_current is a Component of EpicsSignalRO on PV SR:C03-BI{DCCT:1}I:Real-I",
             source="upstream_code", ref=f"{SOURCE}:15"),
        Fact("beamline_enabled is a Component of EpicsSignalRO on PV SR:C03-EPS{PLC:1}Sts:ID_BE_Enbl-Sts",
             source="upstream_code", ref=f"{SOURCE}:16-17"),
        Fact("cryo_filling is a Component of EpicsSignalRO on PV XF:03IDA-OP{CC:1}V3_STS",
             source="upstream_code", ref=f"{SOURCE}:18-19"),
        Fact("The profile instantiates BeamlineStatus with an empty prefix and the name beamline_status, so the "
             "Component PV names are absolute", source="upstream_code", ref=f"{SOURCE}:22"),
        Fact("The profile uses beamline_status.beam_current in SuspendFloor, beamline_status.shutter_status in "
             "SuspendBoolLow, beamline_status.beamline_enabled in SuspendBoolLow and beamline_status.cryo_filling in "
             "SuspendBoolHigh", source="upstream_code", ref=f"{SUSPENDERS}:8-26"),
    ]

    @read("shutter_status", type="number",
          description="Storage-ring master-shutter status, a fresh read of PV "
                      "SR-EPS{PLC:1}Sts:MstrSh-Sts; the source states no unit or encoding")
    def shutter_status(self):
        return self.native.shutter_status.get(use_monitor=False)

    @read("beam_current", type="number",
          description="Storage-ring beam current, a fresh read of PV SR:C03-BI{DCCT:1}I:Real-I; the source states "
                      "no unit")
    def beam_current(self):
        return self.native.beam_current.get(use_monitor=False)

    @read("beamline_enabled", type="number",
          description="Beamline-enabled flag, a fresh read of PV SR:C03-EPS{PLC:1}Sts:ID_BE_Enbl-Sts; the source "
                      "states no encoding")
    def beamline_enabled(self):
        return self.native.beamline_enabled.get(use_monitor=False)

    @read("cryo_filling", type="number",
          description="Cryogenic-cooler refill flag, a fresh read of PV XF:03IDA-OP{CC:1}V3_STS; the source states "
                      "no encoding")
    def cryo_filling(self):
        return self.native.cryo_filling.get(use_monitor=False)

    @action(cap="cap.sensing.read.v1",
            description="Read the current values of the four HXN beamline-status channels from their EPICS PVs; "
                        "every selected value is a fresh EpicsSignalRO.get(use_monitor=False), not a monitor cache",
            input={"fields": Field(
                "array", items="string",
                description="Channel names to return: " + ", ".join(FIELDS) +
                            ". Omit the input to return every channel; an unknown name fails the call")})
    def read_channels(self, fields=None):
        if fields is None:
            wanted = list(FIELDS)
        else:
            wanted = [str(value) for value in fields]
            unknown = sorted(set(wanted) - set(FIELDS))
            if unknown:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "not a beamline-status channel: " + ", ".join(unknown))
        values = {name: getattr(self, name)() for name in wanted}
        return {"values": values}
