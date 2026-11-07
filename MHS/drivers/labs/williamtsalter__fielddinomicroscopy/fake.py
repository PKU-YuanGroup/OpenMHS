"""Fake backend of the Dino-Lite driver: an in-memory stand-in for dnx64:DNX64.

Gate G7: every public method defined here is a method of ``dnx64.DNX64`` in the clone (dnx64.py:41-467), and the
driver calls no other native attribute.  DNX64 is a ctypes wrapper around the proprietary Windows DNX64.dll; the
clone ships no simulator for it and no recording, so this is an in-memory stand-in, not a recording of a session.
The wrapper has no getter for the LED or FLC state (dnx64.py lists only SetLEDState and SetFLCLevel), so those
actions return what they applied rather than reading it back.  Every starting value below is placeholder test data,
never a Fact, a Limit or a reference; nothing here talks to a device.
"""


class FakeDNX64:
    """A fresh in-memory Dino-Lite control object per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self._device_name = "Dino-Lite AM7515 (fake)"     # placeholder
        self._device_id = "FAKE-0000"                     # placeholder
        self._exposure_value = 10                         # placeholder
        self._ae_target = 18                              # placeholder
        self._auto_exposure = False                       # placeholder
        self._led_state = 1                               # placeholder
        self._flc_level = 3                               # placeholder

    def Init(self):
        return True

    def GetVideoDeviceName(self, device_index):
        return self._device_name

    def GetDeviceID(self, device_index):
        return self._device_id

    def GetExposureValue(self, device_index):
        return self._exposure_value

    def SetExposureValue(self, device_index, exposure_value):
        self._exposure_value = int(exposure_value)

    def GetAETarget(self, device_index):
        return self._ae_target

    def SetAETarget(self, device_index, ae_target):
        self._ae_target = int(ae_target)

    def GetAutoExposure(self, device_index):
        return self._auto_exposure

    def SetAutoExposure(self, device_index, ae_state):
        self._auto_exposure = bool(ae_state)

    def SetLEDState(self, device_index, led_state):
        self._led_state = int(led_state)

    def SetFLCLevel(self, device_index, flc_level):
        self._flc_level = int(flc_level)
