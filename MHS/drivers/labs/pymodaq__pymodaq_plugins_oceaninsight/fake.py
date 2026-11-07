"""Fake backend of the Ocean Insight driver: an in-memory stand-in for the upstream PyMoDAQ plugin class.

The driver's native class is the card's entry symbol
``pymodaq_plugins_oceaninsight.daq_viewer_plugins.plugins_1D.daq_1Dviewer_Omnidriver:DAQ_1DViewer_Omnidriver``
(src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:26).  Gate G7: every public
method defined here exists on that upstream class:

* ``get_xaxis`` (:130-134) reads the calibrated wavelengths;
* ``commit_settings`` (:59-66) applies an exposure-time change to the controller;
* ``stop`` (:168-173) stops the averaging of every discovered spectrometer;
* ``close`` (:136-140) closes every spectrometer.

The driver also reaches ``self.native.controller``: the upstream class assigns it in ``ini_attributes``/``ini_detector``
(:54-56, :79), and every method the helper below implements is one the upstream class itself calls on its controller:
``getWavelengths`` (:131), ``getSpectrum`` (:151), ``getIntegrationTime`` (:66, :95), ``setIntegrationTime`` (:64),
``stopAveraging`` (:173) and ``closeAllSpectrometers`` (:140).  The helper only stands in for the NETWrapper the plugin
would obtain from OmniDriver; it is a separate object and never derives from the upstream class (G3 FAKE_IS_NATIVE).

Every number below is test data of this stand-in and is marked ``# placeholder``.  It is not a device fact, not a
bound, and never enters a Fact, a Limit or the reference.  A real detector has the pixel count and wavelength
calibration of its own model (the plugin reads them from OmniDriver at runtime, :130-134), and its integration time
comes from the controller (:95).  Nothing here talks to a device.
"""

#: Calibrated wavelength of the first detector pixel, in nm (placeholder test data).
FIRST_WAVELENGTH_NM = 400.0                    # placeholder
#: Wavelength step between neighbouring detector pixels, in nm (placeholder test data).
WAVELENGTH_STEP_NM = 40.0                      # placeholder
#: Number of detector pixels of this stand-in (placeholder test data).
PIXELS = 16                                    # placeholder
#: Integration time before anything sets one, in microseconds (placeholder test data).
INTEGRATION_TIME_US = 100000                   # placeholder
#: The measured intensity of each pixel, in arbitrary units (placeholder test data).
INTENSITIES = [10.0, 20.0, 30.0, 250.0, 50.0, 60.0, 70.0, 80.0,      # placeholder
               90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0]
#: Name this stand-in reports for its single spectrometer (placeholder test data).
SPECTROMETER_NAME = "FAKE-OCEAN-INSIGHT"       # placeholder


class _FakeController:
    """Stand-in for the NETWrapper controller the upstream plugin owns (only the methods the plugin calls)."""

    def __init__(self, **_options):
        self._wavelengths = [FIRST_WAVELENGTH_NM + WAVELENGTH_STEP_NM * index for index in range(PIXELS)]
        self._intensities = list(INTENSITIES)
        self._integration_time_us = INTEGRATION_TIME_US
        self._averaging_stopped = False
        self._closed = False

    def getWavelengths(self, index):                       # upstream daq_1Dviewer_Omnidriver.py:131
        return list(self._wavelengths)

    def getSpectrum(self, index):                          # upstream daq_1Dviewer_Omnidriver.py:151
        return list(self._intensities)

    def getIntegrationTime(self, index):                   # upstream daq_1Dviewer_Omnidriver.py:66, :95
        return self._integration_time_us

    def setIntegrationTime(self, index, microseconds):     # upstream daq_1Dviewer_Omnidriver.py:64
        self._integration_time_us = int(round(float(microseconds)))

    def stopAveraging(self, index):                        # upstream daq_1Dviewer_Omnidriver.py:173
        self._averaging_stopped = True

    def closeAllSpectrometers(self):                       # upstream daq_1Dviewer_Omnidriver.py:140
        self._closed = True


class _FakeParameter:
    """Stand-in for a PyMoDAQ Parameter: only the members upstream ``commit_settings`` reads."""

    def __init__(self, name, parent, value):
        self._name = name
        self._parent = parent
        self._value = float(value)

    def name(self):
        return self._name

    def parent(self):
        return self._parent

    def value(self):
        return self._value

    def setValue(self, value):                             # upstream daq_1Dviewer_Omnidriver.py:66, :111
        self._value = float(value)


class _FakeGroup:
    """Stand-in for the Parameter tree the plugin builds (``settings.child(...)``)."""

    def __init__(self, name):
        self._name = name
        self._children = {}

    def add(self, child):
        self._children[child.name()] = child

    def name(self):
        return self._name

    def child(self, *names):
        node = self
        for name in names:
            node = node._children[name]
        return node


def _fake_settings():
    """The exposure-time branch the upstream ``ini_detector`` adds per spectrometer (:103-114)."""
    settings = _FakeGroup("Settings")
    spectrometers = _FakeGroup("spectrometers")
    spectro = _FakeGroup("spectro0")
    spectro.add(_FakeParameter("exposure_time", spectro, INTEGRATION_TIME_US / 1000.0))
    spectrometers.add(spectro)
    settings.add(spectrometers)
    return settings


class FakeOmnidriver:
    """The PyMoDAQ plugin object the driver talks to, with one in-memory spectrometer behind it."""

    def __init__(self, **_options):
        self.controller = _FakeController()
        self.spectro_names = [SPECTROMETER_NAME]
        self.spectro_id = ["spectro0"]                     # placeholder identifier of the single stand-in
        self.settings = _fake_settings()

    def get_xaxis(self, ind_spectro):
        """Calibrated wavelengths of one spectrometer, in nm (upstream line 130-134)."""
        return self.controller.getWavelengths(ind_spectro)

    def commit_settings(self, param):
        """Apply an exposure-time change like the upstream hook (upstream line 59-66)."""
        if param.name() == "exposure_time":
            ind_spectro = self.spectro_id.index(param.parent().name())
            self.controller.setIntegrationTime(ind_spectro, param.value() * 1000)
            param.setValue(self.controller.getIntegrationTime(ind_spectro) / 1000)

    def stop(self):
        """Stop the hardware averaging of every spectrometer (upstream line 168-173; this is the native stop)."""
        for ind_spectro, _name in enumerate(self.spectro_names):
            self.controller.stopAveraging(ind_spectro)

    def close(self):
        """Close every spectrometer (upstream line 136-140)."""
        if self.controller is not None:
            self.controller.closeAllSpectrometers()
