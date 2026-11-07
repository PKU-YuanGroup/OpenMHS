"""Fake backend of the Andor SDK3 camera driver: an in-memory stand-in for ``AndorCamera``.

Gate G7: every public method defined here exists on
``pymodaq_plugins_andor.hardware.andor_sdk3.api:AndorCamera`` (the methods come from ``AndorBase`` and
``AndorCamera`` in that file), and the attributes the driver reaches are the SDK3 attribute objects the
upstream ``__init__`` creates (``SensorWidth``, ``AOIWidth``, ``ExposureTime``, ``SensorTemperature``,
``SensorCooling``, ``TemperatureStatus``, ``TemperatureControl``, ``FrameRate``, ``ActualExposureTime``,
``Overlap``, ``CameraAcquiring``, ``AcquisitionStop``).  The values are test data only: every one is
marked ``# placeholder`` and no Fact, Limit or reference value is copied from them.  The values never
move by themselves except when a setter is called, so two reads of the state give the same state.
Nothing here talks to a device or to the vendor SDK.
"""


class _FakeValue:
    """The subset of an SDK3 attribute (ATInt/ATFloat/ATBool/ATString) the fake needs."""

    def __init__(self, value):
        self._value = value

    def getValue(self):
        return self._value

    def setValue(self, value):
        self._value = value


class _FakeEnum:
    """The subset of an SDK3 ATEnum the driver reads: the current symbol."""

    def __init__(self, value):
        self._value = value

    def getString(self):
        return self._value

    def setString(self, value):
        self._value = value


class _FakeCommand:
    """The subset of an SDK3 ATCommand the fake needs: calling it clears a boolean target."""

    def __init__(self, target):
        self._target = target

    def __call__(self):
        self._target.setValue(False)


class FakeAndorCamera:
    def __init__(self, **_options):
        self.SensorWidth = _FakeValue(1024)          # placeholder
        self.SensorHeight = _FakeValue(1024)         # placeholder
        self.AOIWidth = _FakeValue(1024)             # placeholder
        self.AOIHeight = _FakeValue(1024)            # placeholder
        self.SerialNumber = _FakeValue("SIM-0000")   # placeholder
        self.ExposureTime = _FakeValue(0.01)         # placeholder: 10 ms in seconds
        self.ActualExposureTime = _FakeValue(0.01)   # placeholder
        self.SensorTemperature = _FakeValue(-40.0)   # placeholder
        self.SensorCooling = _FakeValue(True)        # placeholder
        self.TemperatureStatus = _FakeEnum("idle")   # placeholder
        self.TemperatureControl = _FakeEnum("-40.00")  # placeholder
        self.FrameRate = _FakeValue(10.0)            # placeholder
        self.Overlap = _FakeValue(False)             # placeholder
        self.CameraAcquiring = _FakeValue(False)     # placeholder
        self.AcquisitionStop = _FakeCommand(self.CameraAcquiring)

    def GetCCDWidth(self):
        return self.SensorWidth.getValue()

    def GetCCDHeight(self):
        return self.SensorHeight.getValue()

    def GetPicWidth(self):
        return self.AOIWidth.getValue()

    def GetPicHeight(self):
        return self.AOIHeight.getValue()

    def GetSerialNumber(self):
        return self.SerialNumber.getValue()

    def SetIntegTime(self, iTime):
        # same conversion as the upstream method (api.py:125-128): milliseconds to seconds
        self.ExposureTime.setValue(iTime * 1e-3)

    def GetIntegTime(self):
        # same conversion as the upstream method (api.py:130-132): seconds to milliseconds
        return self.ExposureTime.getValue() * 1000

    def GetFPS(self):
        return self.FrameRate.getValue()

    def StopAq(self):
        # same guard as the upstream method (api.py:161-163)
        if self.CameraAcquiring.getValue():
            self.AcquisitionStop()
