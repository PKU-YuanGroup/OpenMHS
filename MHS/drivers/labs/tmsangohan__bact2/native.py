"""Hardware backend of the bact2 vacuum sensor: the upstream ophyd Device over EPICS Channel Access.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that imports
bact2, and through it ophyd and pyepics.  The upstream example passes a BESSY II device name as the ophyd prefix
(examples/vsr_straight.py:33); the prefix is a deployment option, not a fact of this package, because the same
VacuumSensor class serves every vacuum gauge whose IOC exposes the two suffixes ``:rdPress`` and ``:stMeasQuality``.

``connect`` waits for the two Signals the driver reads, one after another, each for at most ``connection_timeout_s``
(at most 60 s): the first Signal that does not connect within it raises, and ``connect`` can take up to twice that
bound (120 s at the maximum) when each Signal connects just within it.  The e-stop binding calls the inherited
``Device.stop``; the clone defines no stop for VacuumSensor, so what that base method does on this device was not
checked here.  The e-stop latch in the runtime is software-only, and no physical stop is claimed.

Nothing here was run: the package has never connected to an IOC or a vacuum gauge.
"""


def connect(*, prefix, name="vacuum_sensor", connection_timeout_s=5.0):
    if not isinstance(prefix, str) or not prefix.strip():
        raise ValueError("prefix must be the non-empty ophyd prefix of the vacuum sensor's two PVs")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if (isinstance(connection_timeout_s, bool) or not isinstance(connection_timeout_s, (int, float))
            or not 0 < connection_timeout_s <= 60):
        raise ValueError("connection_timeout_s must be a number of seconds in (0, 60]")
    from bact2.ophyd.devices.raw.vacuum import VacuumSensor

    device = VacuumSensor(prefix, name=name)
    # The two Signals the driver reads, in turn (worst case 2 x connection_timeout_s); a missing PV raises a timeout
    # here, before any MHS command is served.
    device.pressure.wait_for_connection(timeout=connection_timeout_s)
    device.quality.wait_for_connection(timeout=connection_timeout_s)
    return device
