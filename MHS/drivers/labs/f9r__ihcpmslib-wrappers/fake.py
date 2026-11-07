"""Fake backend of the SCILA driver: an in-memory stand-in for ihcWrappers.scila:ScilaWrapper.

Gate G7: every public method defined here is an attribute of ``ihcWrappers.scila:ScilaWrapper`` at the pinned
commit (``src/ihcWrappers/scila.py:36-321``; GetStatus, GetDeviceIdentification, Abort and Dispose are inherited
from ``src/ihcWrappers/device.py:30-128``).  Nothing here derives from the upstream class, imports it, or talks to a
device.  The wrapper's methods are synchronous and return a response wrapper; the small helper objects below stand in
for the wrapper's response and status objects.

The upstream repository has no simulator and no recording, and the vendor assembly is not available here, so this is
an in-memory fake.  Every value below is placeholder test data, not a fact about a device and not a recording; the
values never move by themselves, so two reads return the same state.
"""


class _Data:
    """The payload object a wrapper's ``ResponseData`` exposes."""

    def __init__(self, **values):
        self.__dict__.update(values)


class _ReturnValue:
    """Stand-in for ``SiLAReturnValueWrapper``: ReturnCode 1 is the success code the app asserts."""

    def __init__(self, code=1, message=""):
        self.ReturnCode = code
        self.Message = message
        self.DeviceClass = 0
        self.Duration = "00:00:00"


class _Response:
    """Stand-in for a ``ResponseValueWrapper``-derived object."""

    def __init__(self, **data):
        self.Success = True
        self.Message = ""
        self.Aborted = False
        self.RequestId = 0
        self.CommandId = ""
        self.ExpectedDuration = "00:00:00"
        self.ResponseDuration = "00:00:00"
        self.SynchronousDuration = "00:00:00"
        self.ReturnValue = _ReturnValue()
        self.ResponseData = _Data(**data)


class FakeScila:
    def __init__(self, **_options):
        self._device_name = "SCILA fake"          # placeholder
        self._firmware = "FAKE-0.0"               # placeholder
        self._manufacturer = "INHECO"             # placeholder
        self._serial = "FAKE-0000"                # placeholder
        self._state = "Idle"                      # placeholder
        self._locked = False                      # placeholder
        self._current = 37.0                      # placeholder
        self._target = 37.0                       # placeholder
        self._control = True                      # placeholder
        self._auto_boost = False                  # placeholder
        self._boost_state = "Idle"                # placeholder
        self._co2_flow_status = "Off"             # placeholder
        self._liquid_level = "OK"                 # placeholder
        self._drawers = ("Closed", "Closed", "Closed", "Closed")       # placeholder
        self._valves = ("Closed", "Open", "Closed")                   # placeholder
        self._aborted = False
        self._disposed = False

    def GetDeviceIdentification(self):
        return _ReturnValue(), _Data(
            DeviceName=self._device_name,
            DeviceFirmwareVersion=self._firmware,
            DeviceManufacturer=self._manufacturer,
            DeviceSerialNumber=self._serial,
        )

    def GetStatus(self):
        return _ReturnValue(), _Data(State=self._state, Locked=self._locked)

    def GetTemperature(self):
        return _Response(CurrentTemperature=self._current, TargetTemperature=self._target,
                         TemperatureControl=self._control)

    def GetAutoBoostCo2(self):
        return _Response(AutoBoostCO2=self._auto_boost, BoostState=self._boost_state)

    def GetCo2FlowStatus(self):
        return _Response(CO2FlowStatus=self._co2_flow_status)

    def GetDoorStatus(self):
        return _Response(Drawer1=self._drawers[0], Drawer2=self._drawers[1],
                         Drawer3=self._drawers[2], Drawer4=self._drawers[3])

    def GetLiquidLevel(self):
        return _Response(LiquidLevel=self._liquid_level)

    def GetValveStatus(self):
        return _Response(Gas_Boost=self._valves[0], Gas_Normal=self._valves[1], H2O=self._valves[2])

    def SetAutoBoostCo2(self, autoBoostCo2):
        self._auto_boost = bool(autoBoostCo2)
        self._boost_state = "Boost" if self._auto_boost else "Idle"
        return _Response()

    def SetCo2NormalFlow(self, co2NormalFlow):
        self._co2_flow_status = "Normal" if bool(co2NormalFlow) else "Off"
        return _Response()

    def SetTemperature(self, targetTemperature, temperatureControl):
        if targetTemperature is not None:
            self._target = float(targetTemperature)
        if temperatureControl is not None:
            self._control = bool(temperatureControl)
        return _Response()

    def Abort(self):
        self._aborted = True
        return _Response()

    def Dispose(self):
        self._disposed = True
