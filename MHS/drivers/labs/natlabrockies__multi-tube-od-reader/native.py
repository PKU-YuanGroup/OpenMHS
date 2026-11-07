"""Hardware backend: opens one Multi-Tube-OD-Reader through the upstream Device class and its LabJack U3.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, but its risk is R1: the loader refuses the hardware backend of an unreviewed model-written package
only at R2 and R3, so this module is an operator decision, not a protection this package provides.  The acceptance
gate runs the fake backend and never imports this module, the clone or LabJackPython.

The upstream tree is not an installable package (no setup.py or pyproject.toml); its modules are imported from
``<local_path>/my_app`` as the app does.  ``Device.connect()`` opens u3.U3 by serial number
(my_app/classes/device.py:112-120).  The measurement in timecourse.py:70-83 first sets DAC0 to 5 V and DAC1 to
2.6 V (my_app/timecourse.py:11-16), samples the analog inputs and then returns both DACs to 0; this factory wraps
the handle so that the DAC power sequence runs when the driver reads an input and is undone when the handle is
closed.  The serial number and the device name are operator inputs; the clone states no default for either.
"""


def connect(local_path, sn, name, **options):
    """Open one reader by LabJack serial number and return its Device object.

    ``local_path`` is the clone root (the directory containing ``my_app``), ``sn`` is the LabJack U3 serial number
    and ``name`` the firmware name the Device object carries.  Other options are ignored.
    """
    import sys
    from pathlib import Path

    import u3

    app_path = str((Path(local_path) / "my_app").resolve())
    if app_path not in sys.path:
        sys.path.insert(0, app_path)

    from classes.device import Device
    from timecourse import DAC_0_1_voltages

    class _PoweredHandle:
        """The u3.U3 handle with the DAC power sequence of timecourse.py:70-83 around a read."""

        def __init__(self, handle):
            self._handle = handle
            self._powered = False

        def configIO(self, **kwargs):
            return self._handle.configIO(**kwargs)

        def getAIN(self, posChannel, negChannel=31, longSettle=False, quickSample=False):
            if not self._powered:
                for dac, volts in enumerate(DAC_0_1_voltages):
                    self._handle.getFeedback(
                        u3.DAC8(Dac=dac, Value=self._handle.voltageToDACBits(volts, dacNumber=dac)))
                self._powered = True
            return self._handle.getAIN(posChannel, negChannel=negChannel, longSettle=longSettle,
                                       quickSample=quickSample)

        def getTemperature(self):
            return self._handle.getTemperature()

        def close(self):
            if self._powered:
                for dac in range(len(DAC_0_1_voltages)):
                    self._handle.getFeedback(u3.DAC8(Dac=dac, Value=0))
                self._powered = False
            self._handle.close()

    class _Reader(Device):
        """The upstream Device with its connection wrapped for this driver's read/close sequence."""

        def connect(self):
            return _PoweredHandle(super().connect())

    return _Reader(name, str(sn))
