"""Hardware backend of the HXN beamline status monitor: the upstream Device over EPICS Channel Access.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that imports
ophyd and pyepics.

The upstream class lives in the IPython startup file ``startup/10-optics.py``, which is not an importable module: its
file name contains a hyphen and importing it would execute the whole beamline profile (plans, other devices and the
``beamline_status`` instance at ``startup/10-optics.py:22``).  This factory therefore ports the four literal
``Component(EpicsSignalRO, "<PV>")`` declarations of ``BeamlineStatus`` (``startup/10-optics.py:13-19``) into the
small ophyd Device below instead of importing or executing the clone.  The four PV names are identical; the class has
no methods upstream and none here.

The Components carry absolute PV names (no prefix), so they resolve only on a network where the NSLS-II IOCs serve
them.  ``connect`` waits for the four Signals the driver reads, one after another, each for at most
``connection_timeout_s`` (at most 60 s): the first Signal that does not connect within it raises, and ``connect`` can
take up to four times that bound (240 s at the maximum) when each Signal connects just within it.  Nothing here was
run: the package has never connected to an IOC.
"""


def connect(*, name="beamline_status", connection_timeout_s=5.0):
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if (isinstance(connection_timeout_s, bool) or not isinstance(connection_timeout_s, (int, float))
            or not 0 < connection_timeout_s <= 60):
        raise ValueError("connection_timeout_s must be a number of seconds in (0, 60]")

    from ophyd import Component as Cpt
    from ophyd import Device, EpicsSignalRO

    class BeamlineStatus(Device):
        # The four literal declarations of startup/10-optics.py:14-19, in the same order and with the same PVs.
        shutter_status = Cpt(EpicsSignalRO, "SR-EPS{PLC:1}Sts:MstrSh-Sts")
        beam_current = Cpt(EpicsSignalRO, "SR:C03-BI{DCCT:1}I:Real-I")
        beamline_enabled = Cpt(EpicsSignalRO, "SR:C03-EPS{PLC:1}Sts:ID_BE_Enbl-Sts")
        cryo_filling = Cpt(EpicsSignalRO, "XF:03IDA-OP{CC:1}V3_STS")

    device = BeamlineStatus(name=name)
    # The four Signals the driver reads, in turn (worst case 4 x connection_timeout_s); a missing PV raises a timeout
    # here, before any MHS command is served.
    device.shutter_status.wait_for_connection(timeout=connection_timeout_s)
    device.beam_current.wait_for_connection(timeout=connection_timeout_s)
    device.beamline_enabled.wait_for_connection(timeout=connection_timeout_s)
    device.cryo_filling.wait_for_connection(timeout=connection_timeout_s)
    return device
