"""OpenMHS driver for gh.instrumentkit/instrumentkit: a Tektronix DPO70000 oscilloscope.

A direct Driver (decorated methods) over the upstream device class
``instruments.tektronix.tekdpo70000:TekDPO70000``.  The upstream class is a SCPI instrument, but its command strings
are assembled by the property factories from a command name and a value, so the package talks to the upstream object
rather than to a command table.

* reads: the acquisition mode (commanded and actual), the acquisition counters, the acquisition state, the trigger
  state and the acquisition settings exposed as attributes of the upstream class;
* actions: run and stop the acquisition, force a trigger event, send the SCPI software trigger and reset the
  instrument.  They are extension capabilities because the catalogue has no class for oscilloscope acquisition
  control, and ``cap.sensing.read.v1`` binds sensor resource kinds only;
* the native stop (``:STOP``) is the e-stop and the safe-state action.

No text file of the clone states a numeric range for the values this driver reads or changes, and the driver declares
no numeric write, so there is no Limit to source.  Every Fact cites a line of the clone at the pinned commit
(a13c15020b6d62621c326d04b89ce79e471d50d2).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Driver, Fact, Field, action, estop, read


def _enum_name(value):
    """The name of an upstream Enum member, or the value itself when the backend already returns a string."""
    return getattr(value, "name", value)


class TekDPO70000(Driver):
    device_id = "tek_dpo70000"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R0"
    native = "instruments.tektronix.tekdpo70000:TekDPO70000"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeTekDPO70000"}
    vendor, model = "Tektronix", "DPO70000 series"
    display_name = "Tektronix DPO70000 oscilloscope (instrumentkit)"
    tags = ["oscilloscope", "tektronix", "scpi", "acquisition"]
    facts = [
        Fact("TekDPO70000 is a multi-channel oscilloscope with analog bandwidths ranging up to 33 GHz",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:31-35"),
        Fact("acquire_enhanced_enob reads and writes ACQ:ENHANCEDE and its documented values are AUTO and OFF",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:641-647"),
        Fact("acquire_enhanced_state reads and writes ACQ:ENHANCEDE:STATE as a boolean",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:649-653"),
        Fact("acquire_interp_8bit reads and writes ACQ:INTERPE and its documented values are AUTO, ON and OFF",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:655-661"),
        Fact("acquire_magnivu reads and writes ACQ:MAG as a boolean",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:663"),
        Fact("acquire_mode reads and writes ACQ:MOD using the AcquisitionMode values",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:665"),
        Fact("acquire_mode_actual is the read-only ACQ:MOD:ACT acquisition mode",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:667"),
        Fact("acquire_num_acquisitions is the read-only ACQ:NUMAC count of acquisitions since ACQuire:STATE RUN",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:669-676"),
        Fact("acquire_num_avgs reads and writes ACQ:NUMAV, the number of waveform acquisitions to average",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:678-683"),
        Fact("acquire_num_envelop reads and writes ACQ:NUME, the number of waveform acquisitions to be enveloped",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:685-690"),
        Fact("acquire_num_frames is the read-only ACQ:NUMFRAMESACQ count of frames acquired in FastFrame mode",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:692-699"),
        Fact("acquire_state reads and writes ACQ:STATE and starts or stops acquisitions",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:713-720"),
        Fact("trigger_state reads TRIG:STATE and reports the TriggerState",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:891"),
        Fact("force_trigger sends TRIG FORC to force a trigger event",
             source="upstream_code", ref="src/instruments/tektronix/tekdpo70000.py:939-944"),
        Fact("run sends :RUN to enable the trigger", source="upstream_code",
             ref="src/instruments/tektronix/tekdpo70000.py:946-951"),
        Fact("stop sends :STOP to disable the trigger", source="upstream_code",
             ref="src/instruments/tektronix/tekdpo70000.py:953-956"),
        Fact("reset sends *RST and may revert all settings to their defaults", source="upstream_code",
             ref="src/instruments/generic_scpi/scpi_instrument.py:104-110"),
        Fact("trigger sends *TRG, a software trigger event", source="upstream_code",
             ref="src/instruments/generic_scpi/scpi_instrument.py:118-126"),
    ]
    safe_state = "acquisition stopped (native stop, :STOP)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("acquire_enhanced_enob", type="string",
          description="ACQ:ENHANCEDE setting; the upstream documentation names AUTO and OFF")
    def acquire_enhanced_enob(self):
        return self.native.acquire_enhanced_enob

    @read("acquire_enhanced_state", type="boolean",
          description="True when the ACQ:ENHANCEDE:STATE enhanced state is on")
    def acquire_enhanced_state(self):
        return self.native.acquire_enhanced_state

    @read("acquire_interp_8bit", type="string",
          description="ACQ:INTERPE setting; the upstream documentation names AUTO, ON and OFF")
    def acquire_interp_8bit(self):
        return self.native.acquire_interp_8bit

    @read("acquire_magnivu", type="boolean", description="True when the ACQ:MAG MagniVu setting is on")
    def acquire_magnivu(self):
        return self.native.acquire_magnivu

    @read("acquire_mode", type="string", description="Commanded acquisition mode (ACQ:MOD)")
    def acquire_mode(self):
        return _enum_name(self.native.acquire_mode)

    @read("acquire_mode_actual", type="string", description="Acquisition mode the instrument reports (ACQ:MOD:ACT)")
    def acquire_mode_actual(self):
        return _enum_name(self.native.acquire_mode_actual)

    @read("acquire_num_acquisitions", type="integer",
          description="Number of waveform acquisitions since starting acquisition with ACQuire:STATE RUN")
    def acquire_num_acquisitions(self):
        return self.native.acquire_num_acquisitions

    @read("acquire_num_avgs", type="integer", description="Number of waveform acquisitions to average")
    def acquire_num_avgs(self):
        return self.native.acquire_num_avgs

    @read("acquire_num_envelop", type="integer", description="Number of waveform acquisitions to be enveloped")
    def acquire_num_envelop(self):
        return self.native.acquire_num_envelop

    @read("acquire_num_frames", type="integer",
          description="Number of frames acquired in FastFrame Single Sequence while acquisitions are running")
    def acquire_num_frames(self):
        return self.native.acquire_num_frames

    @read("acquire_state", type="string", description="Acquisition state (ACQ:STATE)")
    def acquire_state(self):
        return _enum_name(self.native.acquire_state)

    @read("trigger_state", type="string", description="Trigger state reported by TRIG:STATE")
    def trigger_state(self):
        return _enum_name(self.native.trigger_state)

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.instrumentkit.acquisition_run.v1",
            description="Enable the trigger and start acquisition (the native run, :RUN)",
            output={"acquire_state": Field("string",
                                           description="Acquisition state reported after the native run returned")})
    def run_acquisition(self):
        self.native.run()
        return {"acquire_state": _enum_name(self.native.acquire_state)}

    @action(name="x-cap.instrumentkit.acquisition_stop.v1", safe_state=True,
            description="Disable the trigger and stop acquisition (the native stop, :STOP); it takes no input",
            output={"acquire_state": Field("string",
                                           description="Acquisition state reported after the native stop returned")})
    def stop_acquisition(self):
        self.native.stop()
        return {"acquire_state": _enum_name(self.native.acquire_state)}

    @action(name="x-cap.instrumentkit.force_trigger.v1",
            description="Force a trigger event (the native force_trigger, TRIG FORC)",
            output={"trigger_state": Field("string",
                                           description="Trigger state reported after the forced trigger event")})
    def force_trigger(self):
        self.native.force_trigger()
        return {"trigger_state": _enum_name(self.native.trigger_state)}

    @action(name="x-cap.instrumentkit.software_trigger.v1",
            description="Send a SCPI software trigger event (the inherited native trigger, *TRG)",
            output={"trigger_state": Field("string",
                                           description="Trigger state reported after the software trigger event")})
    def software_trigger(self):
        self.native.trigger()
        return {"trigger_state": _enum_name(self.native.trigger_state)}

    @action(name="x-cap.instrumentkit.reset.v1",
            description="Reset the instrument (the inherited native reset, *RST); it may revert all settings",
            output={"reset": Field("boolean", description="True after the native reset returned")})
    def reset_instrument(self):
        self.native.reset()
        return {"reset": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends :STOP."""
        self.native.stop()
