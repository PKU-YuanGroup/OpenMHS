"""Fake backend of the Agilent PSA driver: an in-memory stand-in for AgilentE44nn.

Gate G7: every public member defined here exists on the upstream class
labtoolkit.SpectrumAnalyser.AgilentE44nn:AgilentE44nn in the clone (IDN comes from its IEEE488 base,
src/labtoolkit/IEEE488.py:36-38; the settings come from the class itself,
src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:58-74, 94-104, 158-171, 173-184 and 242-248), and the same names are
the ones the driver reads and writes.  The values below are test data only, not facts: every one is marked
``# placeholder``.  Each property holds one plain attribute and the value never moves by itself, so reading the state
twice gives the same state.  Nothing here talks to a device or opens a resource.
"""


class FakeAgilentE44nn:
    def __init__(self, **_options):
        self._idn = "Agilent Technologies,E4440A,US00000000,A.14.00"   # placeholder
        self._frequency_center = 1.0e9                                 # placeholder
        self._frequency_span = 10.0e6                                  # placeholder
        self._sweep_points = 1001                                      # placeholder (inside 101 to 8192)
        self._resolution_bandwidth = 1.0e6                             # placeholder
        self._video_bandwidth = 1.0e6                                  # placeholder
        self._continuous = True                                        # placeholder

    @property
    def IDN(self):
        return self._idn

    @property
    def frequency_center(self):
        return self._frequency_center

    @frequency_center.setter
    def frequency_center(self, frequency):
        self._frequency_center = float(frequency)

    @property
    def frequency_span(self):
        return self._frequency_span

    @frequency_span.setter
    def frequency_span(self, span):
        self._frequency_span = float(span)

    @property
    def sweep_points(self):
        return self._sweep_points

    @sweep_points.setter
    def sweep_points(self, points):
        self._sweep_points = int(points)

    @property
    def resolution_bandwidth(self):
        return self._resolution_bandwidth

    @resolution_bandwidth.setter
    def resolution_bandwidth(self, resolutionbandwidth):
        self._resolution_bandwidth = float(resolutionbandwidth)

    @property
    def video_bandwidth(self):
        return self._video_bandwidth

    @video_bandwidth.setter
    def video_bandwidth(self, videobandwidth):
        self._video_bandwidth = float(videobandwidth)

    @property
    def continuous(self):
        return self._continuous

    @continuous.setter
    def continuous(self, continuous):
        self._continuous = bool(continuous)
