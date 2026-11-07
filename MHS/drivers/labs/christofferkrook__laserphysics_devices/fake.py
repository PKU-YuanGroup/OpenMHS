"""Fake backend of the Ando OSA driver: an in-memory stand-in for OSA.old_osa.Ando.

Gate G7: every public method defined here is a method of OSA.old_osa.Ando in the clone.  The methods return the same
kinds of values as the wrapper: the wavelength, averages and resolution getters return the raw reply string, the
scale, trace and sweep getters return one of the names the wrapper maps, and the display and write states return
booleans.  The setters keep a plain attribute and return the getter result like the wrapper.  The starting values are
test data, not facts about an OSA; each is marked ``# placeholder``.  Nothing here talks to a device.
"""


class FakeAndoOSA:
    def __init__(self, **_options):
        self._start = "400.00"          # placeholder
        self._stop = "1600.00"          # placeholder
        self._center = "1000.00"        # placeholder
        self._span = "1200.00"          # placeholder
        self._averages = "2"            # placeholder
        self._resolution = "0.1"        # placeholder
        self._scale = "LOG"             # placeholder
        self._trace = "B"               # placeholder
        self._display = False           # placeholder
        self._write_enabled = False     # placeholder
        self._sweep = "SINGLE"          # placeholder

    def get_start_wl(self):
        return self._start

    def set_start_wl(self, wl):
        self._start = str(wl)
        return self.get_start_wl()

    def get_stop_wl(self):
        return self._stop

    def set_stop_wl(self, wl):
        self._stop = str(wl)
        return self.get_stop_wl()

    def get_center_wl(self):
        return self._center

    def set_center_wl(self, wl):
        self._center = str(wl)
        return self.get_center_wl()

    def get_span(self):
        return self._span

    def set_span(self, span):
        self._span = str(span)
        return self.get_span()

    def get_averages(self):
        return self._averages

    def set_averages(self, averages):
        self._averages = str(averages)
        return self.get_averages()

    def get_resolution(self):
        return self._resolution

    def set_resolution(self, resolution):
        self._resolution = str(resolution)
        return self.get_resolution()

    def get_scale(self):
        return self._scale

    def set_scale(self, scale):
        if scale in ("LIN", "LOG"):
            self._scale = scale
        return self.get_scale()

    def get_current_trace(self):
        return self._trace

    def set_current_trace(self, trace):
        if trace in ("A", "B", "C"):
            self._trace = trace
        return self.get_current_trace()

    def get_display_status(self):
        return self._display

    def set_display_status(self, status):
        self._display = bool(status)
        return self.get_display_status()

    def get_write_status(self):
        return self._write_enabled

    def set_write_status(self, status):
        self._write_enabled = bool(status)
        return self.get_write_status()

    def get_sweep_status(self):
        return self._sweep

    def set_sweep_status(self, sweep):
        if sweep in ("STOP", "SINGLE", "AUTO", "SEGMENT_MEASURE"):
            self._sweep = sweep
        return self.get_sweep_status()
