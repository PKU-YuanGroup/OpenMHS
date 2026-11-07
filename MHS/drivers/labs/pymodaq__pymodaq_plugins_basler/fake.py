"""Fake backend of the Basler driver: an in-memory stand-in for
pymodaq_plugins_basler.hardware.basler:BaslerCamera.

Gate G7: every public method defined here exists on BaslerCamera (src/pymodaq_plugins_basler/hardware/basler.py),
and the attributes the driver reaches (``camera`` and ``model_name``) are set by the upstream __init__
(hardware/basler.py:53-60, 86-89).  The fake mirrors the upstream methods the driver calls: get_roi, set_roi,
get_detector_size, check_attribute_names, setup_acquisition, start_grabbing, stop_grabbing and close.  The camera
node object carries only the pylon nodes the driver and the upstream class touch.

The starting values are test data only, not facts about any camera; each is marked ``# placeholder``.  The state
changes only through the methods above, so reading it twice gives the same values.  Nothing here imports the
upstream package or talks to a device.
"""


class _FakeNode:
    """One pylon node: GetValue and SetValue plus the increment the upstream set_roi reads."""

    def __init__(self, value, inc=1):
        self._value = value
        self.Inc = inc                    # placeholder (test data, not the increment of any camera)

    def GetValue(self):
        return self._value

    def SetValue(self, value):
        self._value = value


class _FakePylonCamera:
    """The pylon.InstantCamera stand-in the upstream class wraps."""

    def __init__(self):
        # placeholder values (test data, not the values or the size of any camera)
        self.OffsetX = _FakeNode(0)
        self.Width = _FakeNode(1280)
        self.OffsetY = _FakeNode(0)
        self.Height = _FakeNode(960)
        self.BinningHorizontal = _FakeNode(1)
        self.BinningVertical = _FakeNode(1)
        self.SensorWidth = _FakeNode(1280)
        self.SensorHeight = _FakeNode(960)
        self.ExposureTime = _FakeNode(10000.0)
        self.Gain = _FakeNode(1.0)
        self.AcquisitionFrameRate = _FakeNode(15.0)
        self.PixelFormat = _FakeNode("Mono12")
        self._grabbing = False

    def IsGrabbing(self):
        return self._grabbing


class FakeBaslerCamera:
    def __init__(self, **_options):
        self.camera = _FakePylonCamera()
        self.model_name = "acA1920-40gm"  # placeholder (test data, not the model of any camera)
        self.attributes = []              # placeholder (test data, not a camera configuration)
        self.attribute_names = []         # placeholder (test data, not a camera configuration)
        self.device_info = None
        self._acquisition_ready = False
        self._closed = False

    def get_roi(self):
        x0 = self.camera.OffsetX.GetValue()
        width = self.camera.Width.GetValue()
        y0 = self.camera.OffsetY.GetValue()
        height = self.camera.Height.GetValue()
        xbin = self.camera.BinningHorizontal.GetValue()
        ybin = self.camera.BinningVertical.GetValue()
        return x0, x0 + width, y0, y0 + height, xbin, ybin

    def set_roi(self, hstart, hend, vstart, vend, hbin, vbin):
        m_width = self.camera.SensorWidth.GetValue()
        m_height = self.camera.SensorHeight.GetValue()
        inc = self.camera.Width.Inc
        hstart = max(0, min(int(hstart), m_width)) // inc * inc
        vstart = max(0, min(int(vstart), m_height)) // inc * inc
        self.camera.OffsetX.SetValue(0)
        self.camera.Width.SetValue((max(0, min(int(hend), m_width)) - hstart) // inc * inc)
        self.camera.OffsetX.SetValue(hstart)
        self.camera.OffsetY.SetValue(0)
        self.camera.Height.SetValue((max(0, min(int(vend), m_height)) - vstart) // inc * inc)
        self.camera.OffsetY.SetValue(vstart)
        self.camera.BinningHorizontal.SetValue(int(hbin))
        self.camera.BinningVertical.SetValue(int(vbin))

    def get_detector_size(self):
        return self.camera.SensorWidth.GetValue(), self.camera.SensorHeight.GetValue()

    def check_attribute_names(self):
        return "ExposureTime", "Gain", False

    def setup_acquisition(self):
        self._acquisition_ready = True

    def start_grabbing(self, frame_rate):
        if frame_rate is not None:
            self.camera.AcquisitionFrameRate.SetValue(frame_rate)
        self.camera._grabbing = True

    def stop_grabbing(self):
        self.camera._grabbing = False
        return ""

    def close(self):
        self.camera._grabbing = False
        self._closed = True
