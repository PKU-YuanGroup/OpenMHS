"""OpenMHS driver for gh.christofferkrook/laserphysics_devices: an Ando AQ-6315A optical spectrum analyzer.

A direct Driver over the upstream class ``OSA.old_osa.Ando:Ando``.  The upstream class is a thin pyvisa wrapper:
every getter returns the raw GPIB reply (a string) and every setter sends one short command assembled from a
command word and the value.  The driver therefore calls the wrapper methods unchanged, parses the numeric replies
into numbers for the MHS state, and leaves the wire syntax to the wrapper.

* reads: the sweep start, stop and centre wavelengths, the span, the number of averages, the resolution, the
  scale, the active trace, the trace display state, the trace write (hold/update) state and the sweep state;
* writes: the same settings.  The clone states no absolute wavelength range and no average-count range, so those
  five limits are ``Limit.operator_required``: a write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site
  supplies the range of its unit (``site-limits.example.json`` is an example).  The resolution choices, the scale,
  the trace and the sweep states come from the clone;
* the native stop is ``set_sweep_status('STOP')``, which writes ``STP`` and is the e-stop and the safe state.

The trace arrays returned by ``get_trace`` are not exposed: the standard carries scalar state, and the clone's
array shape depends on the configured sweep.  This is recorded in RESULT.json notes ("NOT COVERED: ...").

Every Fact cites a line of the clone at the pinned commit 7af657f90b192af988610525ead54bb2cc83a11d.  This package
is model-authored and unreviewed.  It is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

_WAVELENGTH = "nm"


class AndoOSA(Driver):
    device_id = "ando-osa"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = "OSA.old_osa.Ando:Ando"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAndoOSA"}
    vendor, model = "Ando", "AQ-6315A"
    display_name = "Ando AQ-6315A optical spectrum analyzer"
    tags = ["spectrum-analyzer", "optical", "gpib", "spectrometer"]
    facts = [
        Fact("The repository controls an Ando AQ-6315A Optical Spectrum Analyzer.",
             source="upstream_code", ref="OSA/old_osa/README.md:1"),
        Fact("The Ando class opens a pyvisa GPIB resource for the OSA.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:13-17"),
        Fact("set_current_trace writes ACTV0 for A, ACTV1 for B and ACTV2 for C.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:59-66"),
        Fact("get_sweep_status maps reply 0 to STOP, 1 to SINGLE, 2 and 3 to AUTO and 4 to SEGMENT_MEASURE.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:105-117"),
        Fact("set_sweep_status writes STP for STOP, SGL for SINGLE, RPT for AUTO and MEAS for SEGMENT_MEASURE.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:121-130"),
        Fact("set_start_wl and set_stop_wl send the value with the STAWL and STPWL commands and append '.00'.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:140-153"),
        Fact("set_center_wl and set_span send the CTRWL and SPAN commands.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:167-179"),
        Fact("The GUI labels the wavelength axis and the start, stop, center and span values in nm.",
             source="upstream_code", ref="OSA/old_osa/controller.py:233-460"),
        Fact("The trace plot labels power in dBm for LOG scale and mW for LIN scale.",
             source="upstream_code", ref="OSA/old_osa/controller.py:234-237"),
        Fact("The resolution menu offers 0.05, 0.1, 0.2, 0.5, 1, 2, 5 and 10.",
             source="upstream_code", ref="OSA/old_osa/OSAview.py:134"),
        Fact("get_trace returns the intensity and wavelength arrays for traces A, B and C.",
             source="upstream_code", ref="OSA/old_osa/Ando.py:225-256"),
        Fact("The GUI changes the measurement state through set_sweep_status.",
             source="upstream_code", ref="OSA/old_osa/controller.py:521-531"),
    ]
    safe_state = "sweep stopped (STP command): the OSA holds no acquisition"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("start_wl", unit=_WAVELENGTH, description="Start wavelength of the sweep")
    def start_wl(self):
        return float(self.native.get_start_wl())

    @read("stop_wl", unit=_WAVELENGTH, description="Stop wavelength of the sweep")
    def stop_wl(self):
        return float(self.native.get_stop_wl())

    @read("center_wl", unit=_WAVELENGTH, description="Centre wavelength of the sweep")
    def center_wl(self):
        return float(self.native.get_center_wl())

    @read("span", unit=_WAVELENGTH, description="Span of the sweep")
    def span(self):
        return float(self.native.get_span())

    @read("averages", type="integer", unit="1", description="Number of averages")
    def averages(self):
        return int(self.native.get_averages())

    @read("resolution", unit="1",
          description="Resolution setting in device-native units (the clone states no unit)")
    def resolution(self):
        return float(self.native.get_resolution())

    @read("scale", type="string", description="Display scale of the active trace: LIN or LOG")
    def scale(self):
        return self.native.get_scale()

    @read("current_trace", type="string", description="Active trace: A, B or C")
    def current_trace(self):
        return self.native.get_current_trace()

    @read("display_on", type="boolean", description="True while the active trace is displayed")
    def display_on(self):
        return bool(self.native.get_display_status())

    @read("write_enabled", type="boolean",
          description="True while the active trace is written (update); False keeps it fixed (hold)")
    def write_enabled(self):
        return bool(self.native.get_write_status())

    @read("sweep_status", type="string", description="Sweep state: STOP, SINGLE, AUTO or SEGMENT_MEASURE")
    def sweep_status(self):
        return self.native.get_sweep_status()

    # -- writes -------------------------------------------------------------------------------------------------
    @write("start_wl", unit=_WAVELENGTH, description="Start wavelength of the sweep",
           limit=Limit.operator_required(
               "the clone states no absolute wavelength range for the Ando AQ-6315A; the site supplies the "
               "range of its installed unit"))
    def set_start_wl(self, value):
        return float(self.native.set_start_wl(value))

    @write("stop_wl", unit=_WAVELENGTH, description="Stop wavelength of the sweep",
           limit=Limit.operator_required(
               "the clone states no absolute wavelength range for the Ando AQ-6315A; the site supplies the "
               "range of its installed unit"))
    def set_stop_wl(self, value):
        return float(self.native.set_stop_wl(value))

    @write("center_wl", unit=_WAVELENGTH, description="Centre wavelength of the sweep",
           limit=Limit.operator_required(
               "the clone states no absolute wavelength range for the Ando AQ-6315A; the site supplies the "
               "range of its installed unit"))
    def set_center_wl(self, value):
        return float(self.native.set_center_wl(value))

    @write("span", unit=_WAVELENGTH, description="Span of the sweep",
           limit=Limit.operator_required(
               "the clone states no absolute wavelength range for the Ando AQ-6315A; the site supplies the "
               "range of its installed unit"))
    def set_span(self, value):
        return float(self.native.set_span(value))

    @write("averages", type="integer", unit="1", description="Number of averages",
           limit=Limit.operator_required(
               "the clone names no range for the average count of the Ando AQ-6315A; the site supplies the "
               "range of its unit"))
    def set_averages(self, value):
        return int(self.native.set_averages(value))

    @write("resolution", unit="1",
           description="Resolution setting (device-native units)",
           limit=Limit(allowed=[0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10], unit="1",
                       source="upstream_code", ref="OSA/old_osa/OSAview.py:134"))
    def set_resolution(self, value):
        return float(self.native.set_resolution(value))

    @write("scale", type="string", description="Display scale: LIN or LOG",
           limit=Limit(allowed=["LIN", "LOG"], source="upstream_code", ref="OSA/old_osa/Ando.py:204-223"))
    def set_scale(self, value):
        return self.native.set_scale(value)

    @write("current_trace", type="string", description="Active trace: A, B or C",
           limit=Limit(allowed=["A", "B", "C"], source="upstream_code", ref="OSA/old_osa/Ando.py:59-66"))
    def set_current_trace(self, value):
        return self.native.set_current_trace(value)

    @write("display_on", type="boolean", description="True to display the active trace")
    def set_display_on(self, value):
        return bool(self.native.set_display_status(value))

    @write("write_enabled", type="boolean",
           description="True to update the trace; False to hold it")
    def set_write_enabled(self, value):
        return bool(self.native.set_write_status(value))

    @write("sweep_status", type="string", description="Sweep state: STOP, SINGLE, AUTO or SEGMENT_MEASURE",
           limit=Limit(allowed=["STOP", "SINGLE", "AUTO", "SEGMENT_MEASURE"],
                       source="upstream_code", ref="OSA/old_osa/Ando.py:121-130"))
    def set_sweep_status(self, value):
        return self.native.set_sweep_status(value)

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop_sweep(self):
        """The native stop: the runtime latches first, then set_sweep_status('STOP') writes STP."""
        self.native.set_sweep_status("STOP")
