"""Fake backend of the UC480 driver: an in-memory stand-in for UC480_Camera.

Gate G7: every public method and property defined here exists on
``instrumental.drivers.cameras.uc480:UC480_Camera`` (uc480.py:573-1199), including its Camera base
(cameras/__init__.py:16-205) for ``open``/``close``.  The fake keeps scalar camera state in plain attributes; it
does not load the uc480 DLL, allocate image memory or talk to a camera.  The values never move by themselves, so
reading the state twice gives the same state.

Every number below is test data of the fake, not a device fact and not a device limit: the frame is a small
placeholder while a real frame has the configured AOI width and height (uc480.py:921-923), and the starting scalar
values are canned replies.  The real initial values are unknown and must not be copied into a Fact or a Limit.
"""

# placeholder: a 3 x 2 frame of test values, not the device's array size and not a sensor size.
_FRAME = [
    [0, 0, 0],                                              # placeholder
    [0, 0, 0],                                              # placeholder
]


class FakeUC480Camera:
    """The fake camera object; its public surface is the upstream UC480_Camera surface."""

    def __init__(self, **_options):
        self.is_open = True                                 # placeholder: open-flag test value
        self._trigger_mode = "software"                     # placeholder: canned trigger mode
        self._trigger_level = 0                             # placeholder: canned trigger level
        self._trigger_delay_us = 0.0                        # placeholder: canned trigger delay
        self._exposure_ms = 10.0                            # placeholder: canned exposure
        self._gamma = 1.0                                   # placeholder: canned gamma
        self._auto_exposure = False                         # placeholder: canned auto switch
        self._auto_gain = False                             # placeholder: canned auto switch
        self._auto_framerate = False                        # placeholder: canned auto switch
        self._auto_whitebalance = False                     # placeholder: canned auto switch
        self._auto_sensor_exposure = False                  # placeholder: canned auto switch
        self._auto_sensor_framerate = False                 # placeholder: canned auto switch
        self._auto_sensor_gain = False                      # placeholder: canned auto switch
        self._auto_sensor_whitebalance = False              # placeholder: canned auto switch
        self._width = 3                                     # placeholder: canned image width
        self._height = 2                                    # placeholder: canned image height
        self._bytes_per_line = 3                            # placeholder: canned line stride
        self._live = False                                  # placeholder: call flag of the fake

    # -- read-only properties (uc480.py:1181-1196) -----------------------------------------------------------
    @property
    def trigger_mode(self):
        return self._trigger_mode

    @property
    def bytes_per_line(self):
        return self._bytes_per_line

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def exposure(self):
        return self._exposure_ms

    @exposure.setter
    def exposure(self, value):
        self._exposure_ms = float(value)

    @property
    def gamma(self):
        return self._gamma

    @gamma.setter
    def gamma(self, value):
        self._gamma = round(float(value), 2)                # placeholder: fake mirrors the integer-percent store

    @property
    def auto_exposure(self):
        return self._auto_exposure

    @auto_exposure.setter
    def auto_exposure(self, value):                          # pragma: no cover - the driver uses set_auto_exposure
        self._auto_exposure = bool(value)

    @property
    def auto_gain(self):
        return self._auto_gain

    @property
    def auto_framerate(self):
        return self._auto_framerate

    @property
    def auto_whitebalance(self):
        return self._auto_whitebalance

    @property
    def auto_sensor_exposure(self):
        return self._auto_sensor_exposure

    @property
    def auto_sensor_framerate(self):
        return self._auto_sensor_framerate

    @property
    def auto_sensor_gain(self):
        return self._auto_sensor_gain

    @property
    def auto_sensor_whitebalance(self):
        return self._auto_sensor_whitebalance

    # -- scalar methods (uc480.py:629, 973-1052) --------------------------------------------------------------
    def set_auto_exposure(self, enable=True):
        self._auto_exposure = bool(enable)

    def set_trigger(self, mode="software", edge="rising"):
        if mode not in ("off", "software", "hardware"):
            raise ValueError("Unrecognized trigger mode {}".format(mode))
        if mode == "hardware" and edge not in ("rising", "falling"):
            raise ValueError("Trigger edge value {} must be either 'rising' or 'falling'".format(edge))
        self._trigger_mode = mode

    def get_trigger_level(self):
        return self._trigger_level

    def set_trigger_delay(self, delay):
        if delay is None:
            value = 0.0                                     # placeholder: the upstream maps None to zero
        elif hasattr(delay, "m_as"):
            value = float(delay.m_as("us"))
        else:
            text = str(delay).strip()
            value = float(text.split()[0]) if text else 0.0  # placeholder: the fake accepts its test input
        self._trigger_delay_us = value

    def get_trigger_delay(self):
        return self._trigger_delay_us

    # -- acquisition (uc480.py:856-892) -----------------------------------------------------------------------
    def grab_image(self, timeout="1s", copy=True, **kwds):
        if self._trigger_mode == "off":
            self._trigger_mode = "software"                 # upstream start_capture promotes off (uc480.py:825-826)
        return [list(row) for row in _FRAME]                # placeholder: always the small test frame

    def start_live_video(self, framerate=None, **kwds):
        self._live = True
        self._trigger_mode = "off"                          # upstream live video uses the off trigger (uc480.py:885)

    def stop_live_video(self):
        self._live = False

    # -- connection (uc480.py:670-752) ------------------------------------------------------------------------
    def open(self, num_bufs=1, force=False):
        if self.is_open and not force:
            return
        self.is_open = True

    def close(self, force=False):
        if not self.is_open and not force:
            return
        self.is_open = False
        self._live = False
