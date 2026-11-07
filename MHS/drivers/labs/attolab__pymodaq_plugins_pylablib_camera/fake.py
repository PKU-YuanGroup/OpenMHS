"""Fake backend of the pylablib camera driver: an in-memory stand-in for the upstream Thorlabs viewer class.

Gate G7: every public method and property defined here exists on
``pymodaq_plugins_pylablib_camera.daq_viewer_plugins.plugins_2D.daq_2Dviewer_ThorlabsPLL:DAQ_2DViewer_ThorlabsPLL``
or on its base ``DAQ_2DViewer_GenericPylablibCamera`` in the clone: the ``exposure`` property
(daq_2Dviewer_GenericPylablibCamera.py:114-122), ``update_rois`` (:229-244), ``stop`` (:326-330) and ``close``
(:315-321), plus the ``camera_list`` class attribute of the Thorlabs viewer
(daq_2Dviewer_ThorlabsPLL.py:17).  The driver also reaches ``controller`` (:43) and that object stands in for the
pylablib camera the clone calls: get_roi, set_roi, get_detector_size, get_device_info, get_exposure, set_exposure,
stop_acquisition, clear_acquisition, setup_acquisition and close.

Every value below is test data, not a fact about any camera, and every one is marked ``# placeholder``.  The state
changes only through the methods above, so reading it twice gives the same values.  Nothing here imports the
upstream package or talks to a device.
"""


class _FakeCameraController:
    """The pylablib camera controller stand-in (the object the upstream viewer keeps in self.controller)."""

    def __init__(self):
        self._hstart = 0              # placeholder (test data, not the ROI of any camera)
        self._hend = 640              # placeholder (test data, not the ROI of any camera)
        self._vstart = 0              # placeholder (test data, not the ROI of any camera)
        self._vend = 480              # placeholder (test data, not the ROI of any camera)
        self._hbin = 1                # placeholder (test data, not the binning of any camera)
        self._vbin = 1                # placeholder (test data, not the binning of any camera)
        self._exposure = 0.01         # placeholder (test data, not the exposure of any camera)
        self._acquiring = False
        self._closed = False

    def get_roi(self):
        return (self._hstart, self._hend, self._vstart, self._vend, self._hbin, self._vbin)

    def set_roi(self, hstart, hend, vstart, vend, hbin, vbin):
        hstart, hend = int(hstart), int(hend)
        vstart, vend = int(vstart), int(vend)
        hbin, vbin = int(hbin), int(vbin)
        if hend <= hstart or vend <= vstart:
            raise ValueError("the ROI must have a positive width and height")
        if hbin < 1 or vbin < 1:
            raise ValueError("the binning factors must be at least 1")
        self._hstart, self._hend = hstart, hend
        self._vstart, self._vend = vstart, vend
        self._hbin, self._vbin = hbin, vbin

    def get_detector_size(self):
        return (1280, 1024)           # placeholder (test data, not the sensor of any camera)

    def get_device_info(self):
        return ("Thorlabs", "fake-thorlabs-camera", "")   # placeholder (test data, not the information of any camera)

    def get_exposure(self):
        return self._exposure

    def set_exposure(self, value):
        value = float(value)
        if value <= 0:
            raise ValueError("the exposure must be positive")
        self._exposure = value

    def stop_acquisition(self):
        self._acquiring = False

    def clear_acquisition(self):
        self._acquiring = False

    def setup_acquisition(self):
        self._acquiring = True

    def close(self):
        self._acquiring = False
        self._closed = True


class FakeThorlabsCamera:
    """The upstream viewer's camera-facing surface, backed by an in-memory controller."""

    camera_list = ["fake-thorlabs-serial"]   # placeholder (test data, not a serial number of any camera)

    def __init__(self, **_options):
        self.controller = _FakeCameraController()

    @property
    def exposure(self):
        return self.controller.get_exposure()

    @exposure.setter
    def exposure(self, value):
        self.controller.set_exposure(float(value))

    def update_rois(self, new_roi):
        new_x, new_width, new_xbinning, new_y, new_height, new_ybinning = new_roi
        if tuple(new_roi) != self.controller.get_roi():
            self.controller.set_roi(hstart=new_x, hend=new_x + new_width, vstart=new_y,
                                    vend=new_y + new_height, hbin=new_xbinning, vbin=new_ybinning)
            self.controller.clear_acquisition()
            self.controller.setup_acquisition()

    def stop(self):
        self.controller.stop_acquisition()
        self.controller.clear_acquisition()

    def close(self):
        self.controller.close()
