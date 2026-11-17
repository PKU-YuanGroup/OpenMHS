"""Fake backend of the Nuvu camera driver: an in-memory stand-in for NuvuCamUtils.

Gate G7: every public member defined here exists on the upstream class
``user_devices.NuvuCamera.Nuvu_sdk.Nuvu_cam_utils:NuvuCamUtils``: the setters, cam_start, cam_stop, cam_close,
get_image and the isrunning flag are declared in Nuvu_cam_utils.py (23-255); getAllCamInfo and camIsAcquring are
inherited from nc_camera.py:607-671 and 335-352.  The gate cannot follow the upstream's ``from ... import *`` base, so
those two names are reported as MAYBE_ABSENT warnings; both occur in the clone and this class deliberately mirrors
them.

Every value below is test data of this stand-in, not a device fact, and each is marked ``# placeholder``.  The frame
is 8 x 8 so the receipt stays small; a real camera reports its own width and height through the SDK, and the clone
queries those from the device rather than stating them (nc_camera.py:322-333).  The values never move by themselves,
so reading the state twice gives the same state.  Nothing here talks to a device: this class is a separate object and
never derives from NuvuCamUtils (G3 FAKE_IS_NATIVE).
"""

import numpy as np

#: Side of the placeholder square frame (test data, not a device fact).
FRAME_SIDE = 8  # placeholder


class FakeNuvuCamUtils:
    def __init__(self, **_options):
        self.isrunning = False                      # placeholder test data: no acquisition before cam_start
        self._closed = False
        self._num_images = 0
        self._exposure_time = 20.0                  # placeholder test data, milliseconds
        self._readout_mode = 1                      # placeholder test data, 1 = EM
        self._trigger_mode = 0                      # placeholder test data, 0 = internal
        self._shutter_mode = 1                      # placeholder test data, 1 = on
        self._em_gain = 2                           # placeholder test data, calibrated EM gain
        self._target_detector_temperature = -60.0   # placeholder test data, raw SDK units
        self._detector_temperature = -55.0          # placeholder test data, raw SDK units
        self._width = FRAME_SIDE                    # placeholder test data, pixels
        self._height = FRAME_SIDE                   # placeholder test data, pixels

    # -- configuration ---------------------------------------------------------------------------------------------
    def set_exposure_time(self, new_exposure_time):
        """Set the exposure in milliseconds (upstream nc_camera.py:219-226)."""
        self._exposure_time = float(new_exposure_time)

    def set_readout_mode(self, readoutMode):
        """Set the readout mode (upstream nc_camera.py:152-159)."""
        self._readout_mode = int(readoutMode)

    def set_trigger_mode(self, triggerMode):
        """Set the trigger mode (upstream nc_camera.py:180-192)."""
        self._trigger_mode = int(triggerMode)

    def set_shutter_mode(self, new_shutter_mode):
        """Set the shutter mode (upstream nc_camera.py:294-303)."""
        self._shutter_mode = int(new_shutter_mode)

    def set_calibrated_em_gain(self, new_em_gain):
        """Set the calibrated EM gain (upstream nc_camera.py:531-540)."""
        self._em_gain = int(new_em_gain)

    def set_target_detector_temp(self, target):
        """Set the target detector temperature (upstream nc_camera.py:464-475)."""
        self._target_detector_temperature = float(target)

    # -- acquisition -----------------------------------------------------------------------------------------------
    def cam_start(self, num_images):
        """Start a finite acquisition; the upstream wrapper refuses a second start (Nuvu_cam_utils.py:89-95)."""
        if self.isrunning:
            raise Exception("Camera already started...")
        self._num_images = int(num_images)
        self.isrunning = True

    def cam_stop(self):
        """Abort all acquisition (upstream Nuvu_cam_utils.py:97-99)."""
        self.isrunning = False

    def cam_close(self):
        """Close the camera handle (upstream Nuvu_cam_utils.py:101-102)."""
        self.isrunning = False
        self._closed = True

    def camIsAcquring(self):
        """Query the acquisition state: 1 while acquiring, 0 otherwise (upstream nc_camera.py:335-352)."""
        return 1 if self.isrunning else 0

    def get_image(self):
        """Return one placeholder uint16 frame (upstream Nuvu_cam_utils.py:202-205)."""
        row = np.arange(FRAME_SIDE, dtype=np.uint16) * 1000   # placeholder test data
        return np.tile(row, (FRAME_SIDE, 1))                  # placeholder test data, 8 x 8 uint16

    # -- snapshot --------------------------------------------------------------------------------------------------
    def getAllCamInfo(self):
        """The camera snapshot the upstream nc_camera builds (nc_camera.py:607-671); values are placeholders."""
        return {
            "nbrReadoutModes": 2,                              # placeholder test data
            "currentReadoutMode": self._readout_mode,
            "currentTriggerMode": self._trigger_mode,
            "readoutTime": 10.0,                               # placeholder test data
            "width": self._width,
            "height": self._height,
            "waitingTime": 0.0,                                # placeholder test data
            "exposureTime": self._exposure_time,
            "componentTemp": {
                "detectorTemp": self._detector_temperature,
                "controllerTemp": 20.0,                        # placeholder test data
                "powerSupplyTemp": 25.0,                       # placeholder test data
                "fpgaTemp": 30.0,                              # placeholder test data
            },
            "shutterMode": self._shutter_mode,
            "calibratedEmGain": self._em_gain,
            "calibratedEmGainMin": 1,                          # placeholder test data
            "calibratedEmGainMax": 1000,                       # placeholder test data
            "calibratedEmGainTempMin": -80.0,                  # placeholder test data
            "calibratedEmGainTempMax": -20.0,                  # placeholder test data
            "rawEmGain": 1,                                    # placeholder test data
            "rawEmGainMin": 1,                                 # placeholder test data
            "rawEmGainMax": 1000,                              # placeholder test data
            "targetDetectorTemp": self._target_detector_temperature,
            "targetDetectorTempMin": -80.0,                    # placeholder test data
            "targetDetectorTempMax": 20.0,                     # placeholder test data
        }
