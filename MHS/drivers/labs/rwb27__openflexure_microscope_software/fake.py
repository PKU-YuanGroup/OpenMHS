"""Fake backend of the OpenFlexure Microscope package: an in-memory stand-in for microscope:Microscope.

Gate G7: every public member defined here is a member of ``openflexure_microscope.microscope:Microscope`` at the
pinned commit 991e1b72b94d796a05caf4c896c0b001ea5a2c97, with the upstream parameter names and defaults.  The camera
and the stage behind it are plain model objects: the upstream class only ever reaches them as ``self.camera`` and
``self.stage`` and the gate checks this class, not its stand-ins.

What it does not do: no picamera, no images, no timing.  A zoom change keeps the field-of-view centre exactly as the
upstream setter does (microscope.py:227-243) and the autofocus scan is instantaneous, with a sharpness curve that is
merely test data.  ``close()`` marks the model shut down, which is what the driver's e-stop reaches.  Nothing here
talks to a device.
"""

# placeholder: the camera's initial field of view (x, y, width, height of the sensor region)
_START_FOV = (0.0, 0.0, 1.0, 1.0)
# placeholder: an initial resolution, shutter speed and white-balance mode; a camera reports its own
_START_RESOLUTION = (640, 480)
_START_SHUTTER_US = 10000
_START_AWB_MODE = "auto"
# placeholder: the sharpness curve of the model, 1/(1 + (z/100)^2)
_SHARPNESS_SCALE = 100.0


class _FakeCamera:
    """The picamera attributes settings_dict and zoom read (never checked by the gate)."""

    def __init__(self):
        self.zoom = _START_FOV
        self.resolution = _START_RESOLUTION
        self.shutter_speed = _START_SHUTTER_US
        self.awb_mode = _START_AWB_MODE
        self.closed = False

    def close(self):
        self.closed = True


class _FakeStage:
    """A stage with a z position in its own unit (microsteps) and a close method."""

    def __init__(self):
        self.position = [0.0, 0.0, 0.0]                     # placeholder: x, y, z in microsteps
        self.backlash = [0.0, 0.0, 0.0]
        self.closed = False

    def close(self):
        self.closed = True


class FakeMicroscope:
    """A stand-in for the Microscope object: camera, stage and the scan the driver runs."""

    def __init__(self, camera=None, stage=None):
        self.camera = camera if camera is not None else _FakeCamera()
        self.stage = stage if stage is not None else _FakeStage()
        self._commands = []                                  # the name of every native call received
        self._closed = False

    # -- the members of Microscope the driver may touch ---------------------------------------------------------
    def close(self):
        self._commands.append("close")
        self.camera.close()
        self.stage.close()
        self._closed = True

    def settings_dict(self):
        self._commands.append("settings_dict")
        return {"resolution": tuple(self.camera.resolution),
                "shutter_speed": self.camera.shutter_speed,
                "awb_mode": self.camera.awb_mode}

    def autofocus(self, dz, settle=0.5, metric_fn=None):
        """Score every z position of the scan and end at the sharpest one, as microscope.py:148-170 describes."""
        self._commands.append("autofocus")
        start = float(self.stage.position[2])
        positions = []
        sharpnesses = []
        for offset in dz:
            position = start + float(offset)
            self.stage.position = [0.0, 0.0, position]
            positions.append(position)
            sharpnesses.append(1.0 / (1.0 + (position / _SHARPNESS_SCALE) ** 2))   # placeholder: test data
        best = max(range(len(sharpnesses)), key=lambda index: sharpnesses[index])
        self.stage.position = [0.0, 0.0, positions[best]]
        return positions, sharpnesses

    @property
    def zoom(self):
        field = self.camera.zoom
        return 2.0 / (field[2] + field[3])

    @zoom.setter
    def zoom(self, newvalue):
        self._commands.append("zoom")
        if newvalue < 1.0:
            newvalue = 1.0
        field = self.camera.zoom
        centre = [field[0] + field[2] / 2.0, field[1] + field[3] / 2.0]
        size = 1.0 / newvalue
        for index in range(2):
            if abs(centre[index] - 0.5) + size / 2 > 0.5:
                centre[index] = 0.5 + (1.0 - size) / 2 * (1 if centre[index] - 0.5 >= 0 else -1)
        self.camera.zoom = (centre[0] - size / 2, centre[1] - size / 2, size, size)

    # -- hooks for test_driver.py (not Microscope members, never used by the driver) ----------------------------
    def _set_shutter_speed(self, microseconds):
        """The camera reports ``microseconds`` as its shutter speed."""
        self.camera.shutter_speed = int(microseconds)

    def _set_awb_mode(self, mode):
        """The camera reports ``mode`` as its white-balance mode."""
        self.camera.awb_mode = str(mode)
