"""Fake backend of the Fisba ReadyBeam driver: an in-memory stand-in for FisbaReadyBeam:FisbaReadyBeam.

Gate G7: every public method defined here is a method of the upstream class (FisbaReadyBeam/__init__.py:60-256),
and the driver touches nothing else.  The class keeps the three channel powers and answers the status and type
reads from fixed values; a brightness write is visible to the next state read through the driver's own record.

The values are test data, not facts: they are marked ``# placeholder`` and are not a recording of an instrument —
the clone has no simulator and no hardware was available.  Nothing here talks to a device.
"""

STATUS_READY = 1    # placeholder: the device_status dictionary names 1 'Ready' (FisbaReadyBeam/__init__.py:24)
TYPE_FRAME = "=0001171"    # placeholder: a response frame of parameter 100 (device type), a stand-in for RGB-1171


class FakeFisbaReadyBeam:
    def __init__(self, **_options):
        self._status = STATUS_READY                                     # placeholder
        self._brightness = [0.0, 0.0, 0.0]                              # placeholder
        self.closed = False

    def get_device_status(self):
        return self._status

    def get_device_type(self):
        return TYPE_FRAME

    def set_brightness(self, power=[10., 0., 10.]):
        self._brightness = [float(item) for item in power]
        return None

    def close(self):
        self.closed = True
