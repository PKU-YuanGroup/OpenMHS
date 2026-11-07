# Facts and tags for gh.instrumentkit/instrumentkit

Every fact cites its source at commit `a13c15020b6d62621c326d04b89ce79e471d50d2`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TekDPO70000 is a multi-channel oscilloscope with analog bandwidths ranging up to 33 GHz | upstream_code | src/instruments/tektronix/tekdpo70000.py:31-35 |
| acquire_enhanced_enob reads and writes ACQ:ENHANCEDE and its documented values are AUTO and OFF | upstream_code | src/instruments/tektronix/tekdpo70000.py:641-647 |
| acquire_enhanced_state reads and writes ACQ:ENHANCEDE:STATE as a boolean | upstream_code | src/instruments/tektronix/tekdpo70000.py:649-653 |
| acquire_interp_8bit reads and writes ACQ:INTERPE and its documented values are AUTO, ON and OFF | upstream_code | src/instruments/tektronix/tekdpo70000.py:655-661 |
| acquire_magnivu reads and writes ACQ:MAG as a boolean | upstream_code | src/instruments/tektronix/tekdpo70000.py:663 |
| acquire_mode reads and writes ACQ:MOD using the AcquisitionMode values | upstream_code | src/instruments/tektronix/tekdpo70000.py:665 |
| acquire_mode_actual is the read-only ACQ:MOD:ACT acquisition mode | upstream_code | src/instruments/tektronix/tekdpo70000.py:667 |
| acquire_num_acquisitions is the read-only ACQ:NUMAC count of acquisitions since ACQuire:STATE RUN | upstream_code | src/instruments/tektronix/tekdpo70000.py:669-676 |
| acquire_num_avgs reads and writes ACQ:NUMAV, the number of waveform acquisitions to average | upstream_code | src/instruments/tektronix/tekdpo70000.py:678-683 |
| acquire_num_envelop reads and writes ACQ:NUME, the number of waveform acquisitions to be enveloped | upstream_code | src/instruments/tektronix/tekdpo70000.py:685-690 |
| acquire_num_frames is the read-only ACQ:NUMFRAMESACQ count of frames acquired in FastFrame mode | upstream_code | src/instruments/tektronix/tekdpo70000.py:692-699 |
| acquire_state reads and writes ACQ:STATE and starts or stops acquisitions | upstream_code | src/instruments/tektronix/tekdpo70000.py:713-720 |
| trigger_state reads TRIG:STATE and reports the TriggerState | upstream_code | src/instruments/tektronix/tekdpo70000.py:891 |
| force_trigger sends TRIG FORC to force a trigger event | upstream_code | src/instruments/tektronix/tekdpo70000.py:939-944 |
| run sends :RUN to enable the trigger | upstream_code | src/instruments/tektronix/tekdpo70000.py:946-951 |
| stop sends :STOP to disable the trigger | upstream_code | src/instruments/tektronix/tekdpo70000.py:953-956 |
| reset sends *RST and may revert all settings to their defaults | upstream_code | src/instruments/generic_scpi/scpi_instrument.py:104-110 |
| trigger sends *TRG, a software trigger event | upstream_code | src/instruments/generic_scpi/scpi_instrument.py:118-126 |

Limits: this driver declares no numeric write and no numeric action input, so it has no Limit. The acquisition
counters are read-only in this package. The clone documents a range for `acquire_num_samples` (5,000 to
2,147,400,000 samples; `src/instruments/tektronix/tekdpo70000.py:701-711`), but this driver does not expose that
setting and therefore does not copy the range into a Limit.

Safety: the `@estop` method and the safe-state action `x-cap.instrumentkit.acquisition_stop.v1` both call the native
`stop()` (`:STOP`). No line of the clone documents an independent hardware e-stop for the oscilloscope, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for a hardware driver (not required at R0).

Scope: the package drives `instruments.tektronix.tekdpo70000:TekDPO70000`. The clone's other entry classes in the
card (`APTPiezoInertiaActuator`, `APTPiezoStage`, `HP6632b`, `SRS830`) are different devices and are not bound here.
The waveform array of the oscilloscope is not covered: the standard has no array measurement class for it in this
package, so the driver exposes the scalar settings and counters named above.

Tags: oscilloscope, tektronix, scpi, acquisition
