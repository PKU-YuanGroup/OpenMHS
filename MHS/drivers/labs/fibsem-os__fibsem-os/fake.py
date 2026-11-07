"""Fake backend of the fibsem-os remote fluorescence microscope driver.

Gate G7: every public attribute defined here is an attribute of
fibsem.fm.remote:RemoteFluorescenceMicroscope or of a base class in the clone.  The ``camera`` object stands for the
remote camera device the real FM holds (fibsem/fm/microscope.py:511, 519), and the driver reads and writes its
parameters through the FM API's own setters and properties.  The starting values are test data only (marked
``# placeholder``); nothing here talks to a device.
"""


class _FakeCamera:
    """The FM's camera device: the three parameters this driver reads and writes."""

    def __init__(self):
        self.exposure_time = 0.05       # placeholder
        self.binning = 1                # placeholder
        self.gain = 0.5                 # placeholder


class FakeRemoteFluorescenceMicroscope:
    """In-memory stand-in for the FM API over a device server."""

    def __init__(self, **_options):
        self._camera = _FakeCamera()
        self._streaming = False
        self._acquiring = False
        self._acquiring_reason = ""
        self._channel_name = "DAPI"     # placeholder
        self._channel_color = "#0000FF"  # placeholder

    @property
    def camera(self):
        return self._camera

    @property
    def is_acquiring(self):
        return self._streaming or self._acquiring

    @property
    def is_interactive(self):
        return not self.is_acquiring or self._streaming

    @property
    def acquiring_reason(self):
        if self._acquiring:
            return self._acquiring_reason
        if self._streaming:
            return "live acquisition"
        return ""

    @property
    def channel_name(self):
        return self._channel_name

    @property
    def channel_color(self):
        return self._channel_color

    def set_channel_name(self, name):
        self._channel_name = name

    def set_channel_color(self, color):
        self._channel_color = color

    def set_binning(self, binning):
        self._camera.binning = int(binning)

    def set_exposure_time(self, exposure_time):
        self._camera.exposure_time = float(exposure_time)

    def set_gain(self, gain):
        self._camera.gain = float(gain)

    def start_acquisition(self, channel_settings=None):
        self._streaming = True

    def stop_acquisition(self):
        self._streaming = False
        self._acquiring = False
