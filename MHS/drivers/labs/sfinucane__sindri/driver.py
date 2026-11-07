"""OpenMHS driver for gh.sfinucane/sindri: a Tektronix BERTScope bit error rate analyzer.

A direct Driver over ``sindri.tektronix.bertscope:BERTScope_TCP``.  The upstream class is a lantz driver that speaks
SCPI over a TCP connection (``sindri/tektronix/bertscope.py:464-472``); its measurements are Actions and its settings
are Feats.  This package serves the error-detector results, the mainframe run state and the run duration:

* reads: identity, internal temperature, the mainframe run state, the run duration, the detector bit and error
  counts, the bit error rate, the elapsed time, the resync count, the error-free bit count and the error-free time;
* one write: the run duration.  The upstream Feat declares the bound 0 to 36E6 seconds, so the limit is sourced from
  that line (``sindri/tektronix/bertscope.py:184``);
* actions: run, stop (also the safe-state action), factory reset and detector-result reset.  The run, stop and
  factory-reset actions read the mainframe state back after the native command; the detector reset reads the
  cleared counters, so every action returns an output rather than a bare None;
* the e-stop calls the native ``stop()`` (``RST 0``).

DEVIATION FROM THE CARD: the card names the ``PythonObjectDriver`` helper, but each python-object command binds one
native method and needs a non-empty result map.  The actions here call the native command and then read ``RST?`` back
(the native ``is_running`` Feat), so a decorated direct Driver is used instead, as the card's decision
``direct-driver`` allows.

Every Fact and Limit cites a line of the clone at the pinned commit (d560635a28a57230f1fa32cea3b9d4df0c8af8e7).
This package is model-authored and unreviewed: it is checked on the fake backend only (RESULT.json).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


def _magnitude(value):
    """The magnitude of an upstream pint Quantity, or ``value`` when the backend returns a plain number."""
    return getattr(value, "magnitude", value)


class TektronixBERTScope(Driver):
    device_id = "bertscope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "sindri.tektronix.bertscope:BERTScope_TCP"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBERTScope_TCP"}
    vendor = "Tektronix"
    model = "BERTScope bit error rate analyzer"
    display_name = "Tektronix BERTScope bit error rate analyzer (sindri.tektronix.bertscope:BERTScope_TCP)"
    tags = ["bertscope", "tektronix", "bit-error-rate", "ber", "instrument", "scpi", "tcp"]
    facts = [
        Fact("The clone implements the Tektronix BERTScope Bit Error Rate Analyzers and lists the BA1500, "
             "BA1600, BSA85C, BSA125A, BSA125B, BSA125C, BSA175C, BSA220C, BSA250C, BSA260C and BSA286C models",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:6-20"),
        Fact("idn queries *IDN?; the response is user configurable, so the clone does not parse it",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:46-51"),
        Fact("reset sends *RST to set the instrument functions to the factory default power up state",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:53-57"),
        Fact("run sends RST 1 to start all systems and stop sends RST 0 to stop all systems within the "
             "BERTScope mainframe", source="upstream_code", ref="sindri/tektronix/bertscope.py:166-176"),
        Fact("is_running queries RST? and returns 1 while the mainframe runs",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:178-182"),
        Fact("run_duration is in seconds with the limits 0 to 36E6; setting it to 0 lets the run go on forever",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:184-195"),
        Fact("get_internal_temperature queries SENS:TEMP? and returns degrees Celsius; the clone says the "
             "measurement is not calibrated and is only a relative indication",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:283-290"),
        Fact("detector_reset_results sends DET:RRES to reset the error detector results",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:344-348"),
        Fact("get_detector_bit_count queries DET:BITS? for the total bits detected and get_detector_error_count "
             "queries DET:ERR? for the total errors detected during the run",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:350-360"),
        Fact("get_detector_bit_error_rate queries DET:BER? for the computed bit error rate based on run results",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:362-366"),
        Fact("get_detector_elapsed_time queries DET:ETIM? for the elapsed seconds since the last reset and "
             "get_detector_resyncs queries DET:RESY? for the resync count",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:368-378"),
        Fact("get_detector_error_free_bits_count queries DET:EFB? for the latest error-free bit count and "
             "get_detector_error_free_time queries DET:EFT? for the latest error-free time",
             source="upstream_code", ref="sindri/tektronix/bertscope.py:380-390"),
        Fact("BERTScope_TCP mixes the BERTScope core, Mainframe and Detector features with the IEEE 488.2 "
             "subset and a TCP transport", source="upstream_code",
             ref="sindri/tektronix/bertscope.py:464-472"),
    ]
    safe_state = "all mainframe systems stopped (RST 0)"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (*IDN? reply)")
    def identity(self):
        return str(self.native.idn)

    @read("internal_temperature", unit="Cel",
          description="Internal temperature; the clone says it is uncalibrated and only a relative indication")
    def internal_temperature(self):
        return float(_magnitude(self.native.get_internal_temperature()))

    @read("running", type="boolean", description="True while all mainframe systems are running (RST?)")
    def running(self):
        return bool(int(self.native.is_running))

    @read("run_duration", unit="s", description="Run duration in seconds; 0 lets the run go on forever")
    def run_duration(self):
        return float(_magnitude(self.native.run_duration))

    @read("detector_bit_count", type="integer", unit="1",
          description="Total bits detected during the run (DET:BITS?)")
    def detector_bit_count(self):
        return int(_magnitude(self.native.get_detector_bit_count()))

    @read("detector_error_count", type="integer", unit="1",
          description="Total errors detected during the run (DET:ERR?)")
    def detector_error_count(self):
        return int(_magnitude(self.native.get_detector_error_count()))

    @read("detector_bit_error_rate", unit="1",
          description="Computed bit error rate from the run results (DET:BER?)")
    def detector_bit_error_rate(self):
        return float(self.native.get_detector_bit_error_rate())

    @read("detector_elapsed_time", unit="s", description="Elapsed seconds since the last detector reset (DET:ETIM?)")
    def detector_elapsed_time(self):
        return float(_magnitude(self.native.get_detector_elapsed_time()))

    @read("detector_resyncs", type="integer", unit="1",
          description="Resyncs the detector has tried during the run (DET:RESY?)")
    def detector_resyncs(self):
        return int(self.native.get_detector_resyncs())

    @read("detector_error_free_bits_count", type="integer", unit="1",
          description="Latest error-free bit count (DET:EFB?)")
    def detector_error_free_bits_count(self):
        return int(_magnitude(self.native.get_detector_error_free_bits_count()))

    @read("detector_error_free_time", unit="s", description="Latest error-free time (DET:EFT?)")
    def detector_error_free_time(self):
        return float(_magnitude(self.native.get_detector_error_free_time()))

    # -- write ----------------------------------------------------------------------------------------------------
    @write("run_duration", unit="s", description="Run duration in seconds; 0 lets the run go on forever",
           limit=Limit(min=0, max=36_000_000, unit="s", source="upstream_code",
                       ref="sindri/tektronix/bertscope.py:184"))
    def set_run_duration(self, value):
        self.native.run_duration = float(value)
        return float(_magnitude(self.native.run_duration))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.sfinucane.run.v1", description="Start all systems within the BERTScope mainframe (RST 1)",
            output={"running": Field("boolean", description="True once the mainframe reports RST? = 1")})
    def start_run(self):
        self.native.run()
        return {"running": bool(int(self.native.is_running))}

    @action(name="x-cap.sfinucane.stop.v1", safe_state=True,
            description="Stop all systems within the BERTScope mainframe (RST 0, the safe state); it takes no input",
            output={"running": Field("boolean", description="False once the mainframe reports RST? = 0")})
    def halt_run(self):
        self.native.stop()
        return {"running": bool(int(self.native.is_running))}

    @action(name="x-cap.sfinucane.factory_reset.v1",
            description="Set the instrument functions to the factory default power up state (*RST)",
            output={"running": Field("boolean", description="Mainframe run state read back after *RST")})
    def factory_reset(self):
        self.native.reset()
        return {"running": bool(int(self.native.is_running))}

    @action(name="x-cap.sfinucane.reset_detector_results.v1",
            description="Reset the error detector results (DET:RRES)",
            output={"bit_count": Field("integer", unit="1", description="Total bits detected after the reset"),
                    "error_count": Field("integer", unit="1", description="Total errors detected after the reset")})
    def reset_detector_results(self):
        self.native.detector_reset_results()
        return {"bit_count": int(_magnitude(self.native.get_detector_bit_count())),
                "error_count": int(_magnitude(self.native.get_detector_error_count()))}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends RST 0."""
        self.native.stop()
