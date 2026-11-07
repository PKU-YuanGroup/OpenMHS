"""Hardware backend of the APS machine-parameter monitor: the upstream ophyd Device over EPICS Channel Access.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that
imports apstools, and through it ophyd and pyepics.  Importing ``apstools.devices.aps_machine`` runs the package
initializer ``apstools/devices/__init__.py``, which imports every device module of the package, and
``apstools/devices/aps_cycle.py`` reads its local cycle schedule file at import.

The Device's Components carry absolute PV names (no prefix), so they resolve only on a network where the APS IOCs
serve those PVs.  ``connect`` waits for the seven Signals the driver reads, one after another, each for at most
``connection_timeout_s`` (at most 60 s): the first Signal that does not connect within it raises, and ``connect`` can
take up to seven times that bound (420 s at the maximum) when each Signal connects just within it.  Constructing the
Device also creates the Components the package neither reads nor waits for: ``aps_cycle`` (an ApsCycleDM soft signal
over a local schedule file, aps_machine.py:71) and the eight EpicsSignalRO string channels OPS:message1 to OPS:message8
of ``operator_messages`` (aps_machine.py:20-35, 103); what the control layer does with their connections was not
checked.  The driver never writes: OphydDriver compiles only ``get(use_monitor=False)`` for its get-only bindings.
Nothing here was run: the package has never connected to an IOC.
"""


def connect(*, name="aps", connection_timeout_s=5.0):
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if (isinstance(connection_timeout_s, bool) or not isinstance(connection_timeout_s, (int, float))
            or not 0 < connection_timeout_s <= 60):
        raise ValueError("connection_timeout_s must be a number of seconds in (0, 60]")
    from apstools.devices.aps_machine import ApsMachineParametersDevice

    device = ApsMachineParametersDevice(name=name)
    # The seven Signals the driver reads, in turn (worst case 7 x connection_timeout_s); a missing PV raises a timeout
    # here, before any MHS command is served.  aps_cycle and the eight operator_messages channels are not waited for.
    device.current.wait_for_connection(timeout=connection_timeout_s)
    device.machine_status.wait_for_connection(timeout=connection_timeout_s)
    device.operating_mode.wait_for_connection(timeout=connection_timeout_s)
    device.shutter_status.wait_for_connection(timeout=connection_timeout_s)
    device.shutters_open.wait_for_connection(timeout=connection_timeout_s)
    device.fill_number.wait_for_connection(timeout=connection_timeout_s)
    device.orbit_correction.wait_for_connection(timeout=connection_timeout_s)
    return device
