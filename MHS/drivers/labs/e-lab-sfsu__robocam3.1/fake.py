"""Fake backend of the RoboCam camera driver: an in-memory stand-in for robocam.camera:Camera.

Gate G7: every public method defined here exists on ``robocam.camera:Camera``
(robocam/camera.py:112-663), and the driver reaches only the ``resolution`` attribute that the
upstream constructor sets (robocam/camera.py:114).  The fake keeps the scalar setting state that
the upstream setters push to the selected backend, so a write is observable through the matching
read.  The starting values are test data only, not facts about any camera; each is marked
``# placeholder``.  Nothing here imports or talks to the upstream package or a device.
"""


class FakeCamera:
    def __init__(self, **_options):
        self.resolution = [1280, 720]            # placeholder (test data, not a fact)
        self._exposure_us = 12000                # placeholder (test data, not a fact)
        self._gain = 80                          # placeholder (test data, not a fact)
        self._ae_enabled = False                 # placeholder (test data, not a fact)
        self._hqi = False                        # placeholder (test data, not a fact)
        self._usb_bandwidth = 90                 # placeholder (test data, not a fact)
        self._offset = 2                         # placeholder (test data, not a fact)
        self._sensor_mode_index = 1              # placeholder (test data, not a fact)
        self._stat_lock_timeout = 3              # placeholder (test data, not a fact)
        self._stat_sdk_timeout_or_error = 1      # placeholder (test data, not a fact)
        self._dropped_frames = 4                 # placeholder (test data, not a fact)
        self.running = True                      # placeholder (test data, not a fact)

    def get_exposure(self):
        return self._exposure_us

    def set_exposure(self, us):
        self._exposure_us = int(round(float(us)))

    def get_gain(self):
        return self._gain

    def set_gain(self, gain):
        self._gain = int(round(float(gain)))

    def get_ae_enabled(self):
        return self._ae_enabled

    def set_ae_enabled(self, enabled):
        self._ae_enabled = bool(enabled)

    def get_hqi(self):
        return self._hqi

    def set_hqi(self, enabled):
        self._hqi = bool(enabled)

    def get_usb_bandwidth(self):
        return self._usb_bandwidth

    def set_usb_bandwidth(self, percent):
        self._usb_bandwidth = int(round(float(percent)))

    def get_offset(self):
        return self._offset

    def set_offset(self, offset):
        self._offset = int(round(float(offset)))

    def get_sensor_mode_index(self):
        return self._sensor_mode_index

    def set_sensor_mode(self, index):
        self._sensor_mode_index = int(index)

    def get_supported_resolutions(self):
        # placeholder list (test data, not the resolution list of any camera)
        return [(640, 480), (1280, 720), (1920, 1080)]

    def get_capture_stats(self):
        return {
            "lock_timeout": self._stat_lock_timeout,
            "sdk_timeout_or_error": self._stat_sdk_timeout_or_error,
        }

    def reset_capture_stats(self):
        self._stat_lock_timeout = 0
        self._stat_sdk_timeout_or_error = 0

    def get_dropped_frames_count(self):
        return self._dropped_frames

    def stop(self):
        self.running = False
        self._dropped_frames = 0
