"""OpenMHS driver for gh.aalto-qcd/qickodes: the QCoDeS front end of a QICK RFSoC board.

A direct Driver over ``qickodes.instrument_v2:QickInstrument`` (src/qickodes/instrument_v2.py:93), the tProc-v2
QCoDeS instrument of QICKoDeS.  The constructor reaches the board through ``make_proxy(ns_host, ns_port)``
(instrument_v2.py:102), which returns the Pyro4 proxy of the QickSoc and its QickConfig; the instance then builds
one DAC object per generator, one ADC object per readout, and the DDR4 buffer module from that configuration
(instrument_v2.py:107-142).

DEVIATION FROM THE CARD: the card names the ``QcodesDriver`` family.  That helper is a finite, config-only binding of
direct ``Parameter`` assignments, and its source grammar accepts only straight-line initializers.  This upstream
initializes its Parameters inside loops and conditionals, wraps the delays in a ``SweepableParameter`` subclass, and
its control surface is method based (``set_macro_list``, ``run``, ``run_without_saving``, ``ddr4_buffer.arm``), which
the family does not express.  This package is therefore a direct ``Driver`` with a ``native.py`` factory.

Served surface:

* reads of the five scalar controls the upstream creates directly in the instrument constructor: the three shot
  delays in seconds (``SweepableParameter.get_raw``) and the two averaging counts (``ManualParameter.get``);
* writes through ``cap.device.configure.v1``: the same five controls, each limited by the validator bound that the
  constructor itself passes (``min_value=0`` for the delays, ``Ints(min_value=0)`` for the counts);
* one extension action, ``x-cap.aalto-qcd.arm_ddr4.v1``, which reaches ``Ddr4Buffer.arm()`` (instrument_v2.py:693-696)
  and therefore the board's ``soc.arm_ddr4`` call through the upstream module.

The e-stop clears the macro list with ``set_macro_list([])`` (instrument_v2.py:200-217): after that no ``run`` or
``run_without_saving`` of this instrument object can start, because both reject an empty macro list
(instrument_v2.py:240-245 and the readout-trigger assertion at instrument_v2.py:636).  The pinned clone exposes no
stop, abort or disarm method on the instrument or on its DDR4 module, so an acquisition already inside the QICK proxy
and an already armed DDR4 buffer are not aborted.  Model review (2026-11-05): clearing a Python-side list is not a
native stop, and this package never sets a macro list or starts a run, so the author's e-stop stopped nothing; the
@estop still clears the list and then reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held.  The five
served writes only store values in the Python instrument (``SweepableParameter.set_raw`` stores a ``QickParam``,
src/qickodes/parameters_v2.py:72-83; ``hard_avgs``/``soft_avgs`` are ``ManualParameter`` objects); they reach the
board only when ``run``/``run_without_saving`` builds a program, which this package does not serve.  The package is
blocked: its primary control (macro-list pulse programs and their IQ acquisition) is not served and the clone has no
stop for the board's outputs.

NOT COVERED, each for a reason in the pinned source:

* ``run(meas, ...)`` takes a live ``qcodes.Measurement`` and writes through its DataSaver into a QCoDeS dataset
  (instrument_v2.py:227-401); a JSON capability input cannot carry that Python object or its dataset.
* ``run_without_saving()`` and ``run`` depend on a macro list of ``Macro`` objects built from channels, envelopes and
  pulses (instrument_v2.py:200-217, 240-245, 633-654); no JSON schema of this package constructs that object graph.
  ``set_macro_list`` is consequently not served as a write, and the macro-driven acquisition is not exposed.
* The DAC, ADC, tone and DDR4-buffer parameters are nested channel objects created from the board configuration
  (instrument_v2.py:112-142, 657-696).  This package serves only the scalar root controls above; it does not publish
  a board-dependent channel list.

Every Fact and every Limit cites the clone at the pinned commit 29e7efba0021c797f627cf8097df17b5d34cf4f8.  The package
is model-authored and unreviewed (``reviewed_by`` is null); it is checked on the fake backend only and has never
opened a Pyro4 connection or run a pulse.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The module of the selected upstream class, relative to the clone root.
SOURCE = "src/qickodes/instrument_v2.py"

#: The delay bound passed to SweepableParameter in the constructor (instrument_v2.py:169-192).
DELAY_LIMIT = Limit(min=0, source="upstream_code", ref=f"{SOURCE}:175")
WAIT_LIMIT = Limit(min=0, source="upstream_code", ref=f"{SOURCE}:183")
INITIAL_DELAY_LIMIT = Limit(min=0, source="upstream_code", ref=f"{SOURCE}:191")
#: The average-count bounds passed to Ints in the constructor (instrument_v2.py:155-168).
HARD_AVGS_LIMIT = Limit(min=0, source="upstream_code", ref=f"{SOURCE}:159")
SOFT_AVGS_LIMIT = Limit(min=0, source="upstream_code", ref=f"{SOURCE}:166")


class Qickodes(Driver):
    device_id = "qickodes"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "qickodes.instrument_v2:QickInstrument"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeQickodes"}
    vendor, model = "Xilinx / QICK", "RFSoC board with a QICK tProc-v2 processor"
    display_name = "QICK RFSoC instrument (QICKoDeS QCoDeS driver)"
    tags = ["qcodes", "qick", "rf", "quantum-control", "pulse-sequencing", "pyro4"]
    safe_state = ("No safe state is certified: the e-stop clears the instrument's macro list, so no new run of this "
                  "object can start, and reports SAFE_STATE_UNREACHED with the latch held; a program already running "
                  "on the board and an armed DDR4 buffer continue, because the pinned upstream has no stop, abort or "
                  "disarm method")
    facts = [
        Fact("QickInstrument is a QCoDeS Instrument whose constructor takes ns_host and ns_port=8888",
             source="upstream_code", ref=f"{SOURCE}:93-96"),
        Fact("The constructor obtains soc, the Pyro4 proxy of the QickSoc, and soccfg from make_proxy(ns_host, ns_port)",
             source="upstream_code", ref=f"{SOURCE}:99-102"),
        Fact("It asserts exactly one tProc of type qick_processor and refuses any other type",
             source="upstream_code", ref=f"{SOURCE}:107-110"),
        Fact("It builds StandardDacChannel or MultiplexedDacChannel objects from soccfg['gens'] and AdcChannel objects "
             "from soccfg['readouts']", source="upstream_code", ref=f"{SOURCE}:112-142"),
        Fact("hard_avgs is a ManualParameter with vals=Ints(min_value=0) and initial value 1000",
             source="upstream_code", ref=f"{SOURCE}:155-161"),
        Fact("soft_avgs is a ManualParameter with vals=Ints(min_value=0) and initial value 1",
             source="upstream_code", ref=f"{SOURCE}:162-168"),
        Fact("final_delay is a SweepableParameter with unit sec, initial value 1e-6 and min_value=0",
             source="upstream_code", ref=f"{SOURCE}:169-176"),
        Fact("final_wait is a SweepableParameter with unit sec, initial value 0 and min_value=0",
             source="upstream_code", ref=f"{SOURCE}:177-184"),
        Fact("initial_delay is a SweepableParameter with unit sec, initial value 1e-6 and min_value=0",
             source="upstream_code", ref=f"{SOURCE}:185-192"),
        Fact("SweepableParameter.get_raw returns the stored QickParam rounded value, or its start for a scalar, and "
             "SweepableParameter.set_raw stores the value as a QickParam and registers or removes a sweep",
             source="upstream_code", ref="src/qickodes/parameters_v2.py:72-93"),
        Fact("set_macro_list replaces the macro_list ChannelTuple with the given sequence of Macro objects",
             source="upstream_code", ref=f"{SOURCE}:200-217"),
        Fact("run refuses an empty macro_list with a RuntimeError that asks for set_macro_list first",
             source="upstream_code", ref=f"{SOURCE}:240-245"),
        Fact("run takes a qcodes Measurement and returns the datasaver run_id, writing the acquired data to the "
             "QCoDeS dataset", source="upstream_code", ref=f"{SOURCE}:227-401"),
        Fact("run_without_saving builds an AveragerProgram, acquires through qick.qick_asm.AcquireMixin, and returns "
             "a dict of complex IQ values keyed by readout name", source="upstream_code", ref=f"{SOURCE}:633-654"),
        Fact("Ddr4Buffer.arm calls parent.soc.arm_ddr4(selected_adc_channel.get(), num_transfers.get())",
             source="upstream_code", ref=f"{SOURCE}:693-696"),
        Fact("The DDR4 num_transfers parameter is a ManualParameter with vals=Ints(min_value=1)",
             source="upstream_code", ref=f"{SOURCE}:685-691"),
        Fact("get_idn reports vendor Xilinx, the soccfg board name, no serial, and the remote and local QICK versions",
             source="upstream_code", ref=f"{SOURCE}:219-225"),
        Fact("The project depends on pyro4, qcodes and qick>=0.2.255 and requires Python 3.11 or newer",
             source="upstream_code", ref="pyproject.toml:10-26"),
        Fact("The README instructs the operator to start the Pyro4 nameserver on port 8888 and the QICK server on a "
             "Xilinx board before constructing QickInstrument with the board address",
             source="vendor_doc", ref="README.md:60-67"),
    ]

    # -- reads ------------------------------------------------------------------------------------------------
    @read("final_delay", unit="s", description="Delay added at the end of each shot timeline after the last pulse "
                                              "or readout")
    def final_delay(self):
        return self._delay_value(self.native.final_delay.get_raw(), "final_delay")

    @read("final_wait", unit="s", description="Pause of tProc execution at the end of each shot after the last "
                                             "readout")
    def final_wait(self):
        return self._delay_value(self.native.final_wait.get_raw(), "final_wait")

    @read("initial_delay", unit="s", description="Delay added to the timeline before the loop so the tProc can run "
                                                "the initialization commands")
    def initial_delay(self):
        return self._delay_value(self.native.initial_delay.get_raw(), "initial_delay")

    @read("hard_avgs", type="integer", unit="1", description="Number of hardware repetitions averaged in one "
                                                             "acquisition")
    def hard_avgs(self):
        return int(self.native.hard_avgs.get())

    @read("soft_avgs", type="integer", unit="1", description="Number of software repetitions averaged in one "
                                                             "acquisition")
    def soft_avgs(self):
        return int(self.native.soft_avgs.get())

    # -- writes -----------------------------------------------------------------------------------------------
    @write("final_delay", unit="s", description="Delay added at the end of each shot timeline after the last pulse "
                                                "or readout", limit=DELAY_LIMIT)
    def set_final_delay(self, value):
        self.native.final_delay.set_raw(value)

    @write("final_wait", unit="s", description="Pause of tProc execution at the end of each shot after the last "
                                               "readout", limit=WAIT_LIMIT)
    def set_final_wait(self, value):
        self.native.final_wait.set_raw(value)

    @write("initial_delay", unit="s", description="Delay added to the timeline before the loop so the tProc can run "
                                                  "the initialization commands", limit=INITIAL_DELAY_LIMIT)
    def set_initial_delay(self, value):
        self.native.initial_delay.set_raw(value)

    @write("hard_avgs", type="integer", unit="1", description="Number of hardware repetitions averaged in one "
                                                              "acquisition", limit=HARD_AVGS_LIMIT)
    def set_hard_avgs(self, value):
        self.native.hard_avgs.set(int(value))

    @write("soft_avgs", type="integer", unit="1", description="Number of software repetitions averaged in one "
                                                              "acquisition", limit=SOFT_AVGS_LIMIT)
    def set_soft_avgs(self, value):
        self.native.soft_avgs.set(int(value))

    # -- control ------------------------------------------------------------------------------------------------
    @action(name="x-cap.aalto-qcd.arm_ddr4.v1",
            description="Arm the DDR4 acquisition buffer with the configured ADC channel and transfer count",
            output={"armed": Field("boolean", description="True once the upstream arm method returned; the buffer "
                                                          "has no readback in the pinned source")})
    def arm_ddr4(self):
        self.native.ddr4_buffer.arm()
        return {"armed": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Clear the macro list, then refuse to certify a stop (model review, 2026-11-05).

        No new run of this object can start, but the clone has no stop, abort or disarm method: a program already
        running on the board and an armed DDR4 buffer are not stopped.
        """
        self.native.set_macro_list([])
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the macro list was cleared, but the pinned QICKoDeS has no stop, abort or disarm method: a program "
            "already running on the board and an armed DDR4 buffer are not stopped",
        )

    @staticmethod
    def _delay_value(value, name):
        """Return a scalar delay; the upstream getter can also expose a hardware-sweep QickParam."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            from mhs.driver import DriverFailed

            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"{name} is configured as a hardware sweep, not a scalar delay",
                               native_code=str(type(value).__name__))
        return float(value)
