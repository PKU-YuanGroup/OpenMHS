"""OpenMHS driver for gh.davidlutton/labtoolkit: an Agilent PSA spectrum analyser (AgilentE44nn) over pyvisa.

A direct Driver (decorated methods) over the upstream class
labtoolkit.SpectrumAnalyser.AgilentE44nn:AgilentE44nn (src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:15).  The
package's registry maps the Agilent PSA models E4440A, E4443A, E4445A, E4447A, E4446A and E4448A to that one class
(src/labtoolkit/drivers.py:94-99); the class wraps a pyvisa resource (src/labtoolkit/Instrument.py:13-21) and talks
SCPI through it.  ``native.py`` opens the VISA resource and hands it to the class, exactly as the upstream loader does
(src/labtoolkit/__init__.py:96-99) and as the README's manual demo does (README.md:46-47).

* reads: identification (*IDN?), the sweep window (center and span in Hz), the number of sweep points, the resolution
  and video bandwidths in Hz, and the continuous-sweep state;
* writes: the sweep window, the sweep points and the two bandwidths.  The sweep-point range is the one the class's
  comment gives for the E4440A (101 to 8192 points).  No text file of the clone states a frequency or a bandwidth
  range of the E44nn family: the registry lists six PSA models whose top frequencies differ
  (src/labtoolkit/drivers.py:94-99) and the bandwidth comments in the class name the N9030B, another model.  Those
  four fields are therefore ``Limit.operator_required``: every call that sets them is refused
  MHS.SAFETY.LIMITS_UNSET until the site supplies the range of its analyser (site-limits.example.json shows the
  overlay an operator writes);
* the native stop is the continuous sweep switched off (INIT:CONTinuous OFF through the ``continuous`` property,
  src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:242-248); the same native call is the safe-state action
  ``x-cap.davidlutton.stop_sweep.v1``.

What this package does not expose: the trace itself.  ``trace_data`` reads the analyser's binary trace array
(FORM:DATA REAL,32, then TRAC:DATA? TRACE1, src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:289-300) and the README
returns it as a DataFrame (README.md:53-54); this package carries the sweep settings only and reports no measurement
value.

Every Fact cites a line of the clone at the pinned commit (1c27b35490002822f9860f45a86235cce949c172).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on an analyser.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream driver module of the native class, relative to the clone root.
E44NN = "src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py"
#: The registry that maps the PSA models to the class.
REGISTRY = "src/labtoolkit/drivers.py"

#: Why the two frequency settings need the site's range (see site-limits.example.json).
FREQUENCY_REASON = (
    "no line of the clone states one frequency range of the E44nn family: the registry maps six Agilent PSA models "
    "with different top frequencies from 6.7 GHz to 50 GHz (src/labtoolkit/drivers.py:94-99) and the class does not "
    "report which model is attached; the site states the range of its analyser")
#: Why the two bandwidth settings need the site's range (see site-limits.example.json).
BANDWIDTH_REASON = (
    "no line of the clone states the bandwidth range of an E44nn: the range comments in this file name the N9030B, "
    "another model (src/labtoolkit/SpectrumAnalyser/AgilentE44nn.py:161-165 and 176-177), and "
    "resolution_bandwidths() is a helper table, not a stated limit; the site states the range of its analyser")


class AgilentPsa(Driver):
    device_id = "agilent-e44nn"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "labtoolkit.SpectrumAnalyser.AgilentE44nn:AgilentE44nn"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAgilentE44nn"}
    vendor, model = "Agilent Technologies", "PSA spectrum analyser (E4440A to E4448A)"
    display_name = "Agilent PSA spectrum analyser (labtoolkit AgilentE44nn)"
    tags = ["spectrum-analyser", "psa", "scpi", "sweep", "spectrum"]
    facts = [
        Fact("The registry maps the Agilent PSA models E4440A, E4443A, E4445A, E4447A, E4446A and E4448A to "
             "AgilentE44nn", source="upstream_code", ref=f"{REGISTRY}:94-99"),
        Fact("AgilentE44nn wraps a pyvisa instrument: __init__ stores it in self.inst, sets the read and write "
             "termination to a newline and calls __post__", source="upstream_code",
             ref="src/labtoolkit/Instrument.py:13-21"),
        Fact("The upstream loader opens the VISA resource and passes it to the driver class: "
             "driver(self.rm.open_resource(instrument.Resource))", source="upstream_code",
             ref="src/labtoolkit/__init__.py:96-99"),
        Fact("IDN is the *IDN? query reply", source="upstream_code", ref="src/labtoolkit/IEEE488.py:36-38"),
        Fact("frequency_center reads :FREQuency:CENT? and writes :FREQuency:CENT; frequency_span reads "
             ":FREQuency:SPAN? and writes :FREQuency:SPAN", source="upstream_code", ref=f"{E44NN}:58-74"),
        Fact("The trace's frequency axis is labelled 'Frequency (Hz)' and is built from frequency_start, "
             "frequency_stop and sweep_points", source="upstream_code", ref=f"{E44NN}:338-346"),
        Fact("sweep_points reads :SWEep:POINts? and writes :SWEep:POINts as a whole number; the class's comment "
             "gives the E4440A range 101 to 8192 points, and 2 to 8192 in zero span", source="upstream_code",
             ref=f"{E44NN}:99-104"),
        Fact("resolution_bandwidth reads :BANDwidth:RESolution? and writes it with the setter's unit keyword, "
             "which states 'Hz'", source="upstream_code", ref=f"{E44NN}:158-171"),
        Fact("video_bandwidth reads :BANDwidth:VIDeo? and writes :BANDwidth:VIDeo", source="upstream_code",
             ref=f"{E44NN}:173-184"),
        Fact("continuous reads :INIT:CONTinuous? through query_bool and writes it as a boolean", source="upstream_code",
             ref=f"{E44NN}:242-248"),
        Fact("The README's manual driver demo opens GPIB0::18::INSTR with pyvisa and passes the resource to "
             "AgilentE44nn", source="vendor_doc", ref="README.md:46-47"),
        Fact("The README sets frequency_center to 1e9, frequency_span to 10e6 and sweep_points to 8192 in its demo",
             source="vendor_doc", ref="README.md:49-51"),
        Fact("The trace data is read as binary values after FORM:DATA REAL,32 and FORM:BORD SWAP, by TRAC:DATA? "
             "TRACE1", source="upstream_code", ref=f"{E44NN}:289-300"),
        Fact("The README returns the trace as a DataFrame of the trace data", source="vendor_doc",
             ref="README.md:53-54"),
    ]
    safe_state = "continuous sweep off (INIT:CONTinuous OFF): the analyser takes no new sweep"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identification", type="string", description="Identification string the analyser answers to *IDN?")
    def identification(self):
        return str(self.native.IDN).strip()

    @read("frequency_center", unit="Hz", description="Center frequency of the sweep window")
    def frequency_center(self):
        return float(self.native.frequency_center)

    @read("frequency_span", unit="Hz", description="Frequency span of the sweep window")
    def frequency_span(self):
        return float(self.native.frequency_span)

    @read("sweep_points", type="integer", unit="1", description="Number of points of a sweep")
    def sweep_points(self):
        return int(self.native.sweep_points)

    @read("resolution_bandwidth", unit="Hz", description="Resolution bandwidth (RBW) of the sweep")
    def resolution_bandwidth(self):
        return float(self.native.resolution_bandwidth)

    @read("video_bandwidth", unit="Hz", description="Video bandwidth (VBW) of the sweep")
    def video_bandwidth(self):
        return float(self.native.video_bandwidth)

    @read("continuous", type="boolean", description="True while the analyser sweeps continuously")
    def continuous(self):
        return bool(self.native.continuous)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("frequency_center", unit="Hz", description="Center frequency of the sweep window",
           limit=Limit.operator_required(FREQUENCY_REASON))
    def set_frequency_center(self, value):
        self.native.frequency_center = float(value)

    @write("frequency_span", unit="Hz", description="Frequency span of the sweep window",
           limit=Limit.operator_required(FREQUENCY_REASON))
    def set_frequency_span(self, value):
        self.native.frequency_span = float(value)

    @write("sweep_points", type="integer", unit="1", description="Number of points of a sweep",
           limit=Limit(min=101, max=8192, source="upstream_code", ref=f"{E44NN}:101-102",
                       reason="the class's comment gives the E4440A range 101 to 8192 points (2 to 8192 in zero "
                              "span); fewer than 101 is refused even in zero span"))
    def set_sweep_points(self, value):
        self.native.sweep_points = int(value)

    @write("resolution_bandwidth", unit="Hz", description="Resolution bandwidth (RBW) of the sweep",
           limit=Limit.operator_required(BANDWIDTH_REASON))
    def set_resolution_bandwidth(self, value):
        self.native.resolution_bandwidth = float(value)

    @write("video_bandwidth", unit="Hz", description="Video bandwidth (VBW) of the sweep",
           limit=Limit.operator_required(BANDWIDTH_REASON))
    def set_video_bandwidth(self, value):
        self.native.video_bandwidth = float(value)

    @write("continuous", type="boolean", description="True to sweep continuously, false to sweep on demand only")
    def set_continuous(self, value):
        self.native.continuous = bool(value)

    # -- the safe-state action ------------------------------------------------------------------------------------
    @action(name="x-cap.davidlutton.stop_sweep.v1", safe_state=True,
            description="Stop continuous sweeping (the native stop, INIT:CONTinuous OFF); it takes no input",
            output={"continuous": Field("boolean",
                                        description="False once the analyser reports continuous sweeping off")})
    def stop_sweep(self):
        self.native.continuous = False
        return {"continuous": bool(self.native.continuous)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="continuous")
    def stop(self):
        """The native stop: the runtime latches first, then sets the continuous sweep off."""
        self.native.continuous = False
