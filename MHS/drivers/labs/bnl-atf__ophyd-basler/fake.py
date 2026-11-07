"""Fake backend of the Basler camera: an in-memory stand-in for BaslerCamera.

The upstream class (``ophyd_basler/basler_camera.py:21``) is an ophyd Device over pypylon.  This fake keeps the same
public attributes and only the methods the driver calls: ``stage``, ``grab_image`` and ``unstage``.  Its signals expose
only ``get`` and ``put``, the two ophyd Signal calls the driver makes.  It never imports pypylon, ophyd or the upstream
package and never opens a camera.

Every number or string below is a placeholder for the tests, not a fact about a Basler camera.  The real metadata,
image shape, pixel range and payload size are read from the pylon camera at run time in the hardware backend.
"""


class _FakeSignal:
    """The small part of an ophyd Signal the driver uses: ``get`` and ``put``."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def put(self, value):
        self._value = value
        return value


class _FakeCameraObject:
    """The pylon camera object methods the e-stop and the fake acquisition reach."""

    def __init__(self):
        self._grabbing = False
        self._open = False
        self.stop_calls = 0

    def StartGrabbingMax(self, count):
        self._grabbing = True
        return count

    def IsGrabbing(self):
        return self._grabbing

    def StopGrabbing(self):
        self._grabbing = False
        self.stop_calls += 1

    def Open(self):
        self._open = True

    def Close(self):
        self._open = False
        self._grabbing = False


class FakeBaslerCamera:
    """Source-shaped fake of ``ophyd_basler.basler_camera:BaslerCamera``."""

    def __init__(self, **_options):
        self.image = _FakeSignal("")                         # placeholder
        self.mean = _FakeSignal(0.0)                         # placeholder
        self.exposure_time = _FakeSignal(1000.0)             # placeholder (the source states the unit is ms)
        self.user_defined_name = _FakeSignal("fake-camera")  # placeholder
        self.camera_model = _FakeSignal("Emulation")         # placeholder
        self.serial_number = _FakeSignal("00000000")         # placeholder
        self.image_shape = _FakeSignal((8, 8))               # placeholder
        self.pixel_level_min = _FakeSignal(0)                # placeholder
        self.pixel_level_max = _FakeSignal(255)              # placeholder
        self.active_format = _FakeSignal("Mono8")            # placeholder
        self.payload_size = _FakeSignal(64)                  # placeholder
        self.grab_timeout = _FakeSignal(5000)                # placeholder (the source labels the unit ms)
        self.camera_object = _FakeCameraObject()
        self._staged = False

    def stage(self):
        """The driver's acquisition opens the camera through the upstream stage path."""
        self._staged = True
        self.camera_object.Open()

    def grab_image(self):
        """Return a small deterministic frame; the real shape comes from the pylon camera."""
        self.camera_object.StartGrabbingMax(1)
        height, width = self.image_shape.get()
        rows = [[(row + column) % 256 for column in range(width)] for row in range(height)]  # placeholder
        self.camera_object.StopGrabbing()
        return rows

    def unstage(self):
        """The driver's acquisition closes the camera through the upstream unstage path."""
        self.camera_object.Close()
        self._staged = False
