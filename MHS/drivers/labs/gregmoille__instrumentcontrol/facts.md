# Facts and tags for gh.gregmoille/instrumentcontrol

Every fact cites its source at commit `2cf8c78dea007c636fff1f3d006a039fc1876055`: `upstream_code` is a text line of
the clone (`path/in/clone.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TekDPO70000 is the Tektronix DPO70000 series oscilloscope class | upstream_code | pyScope/PyTektronixScope.py:34-35 |
| Acquisition modes are SAM, PEAK, HIR, AVE, WFMDB and ENV | upstream_code | pyScope/PyTektronixScope.py:61-66 |
| Acquisition states are ON, OFF, RUN and STOP | upstream_code | pyScope/PyTektronixScope.py:75-78 |
| Stop-after modes are RUNST and SEQ | upstream_code | pyScope/PyTektronixScope.py:87-88 |
| Sampling modes are RT, ET and IT | upstream_code | pyScope/PyTektronixScope.py:97-99 |
| Trigger states are ARMED, AUTO, DPO, PARTIAL and READY | upstream_code | pyScope/PyTektronixScope.py:152-156 |
| ACQ:ENHANCEDE accepts AUTO and OFF | upstream_code | pyScope/PyTektronixScope.py:655-660 |
| ACQ:ENHANCEDE:STATE uses 1 for true and 0 for false | upstream_code | pyScope/PyTektronixScope.py:663-667 |
| ACQ:INTERPE accepts AUTO, ON and OFF | upstream_code | pyScope/PyTektronixScope.py:669-674 |
| ACQ:MAG uses ON for true and OFF for false | upstream_code | pyScope/PyTektronixScope.py:677 |
| The ACQ:NUMSAM range is 5,000 to 2,147,400,000 samples | upstream_code | pyScope/PyTektronixScope.py:720-721 |
| run() sends :RUN and stop() sends :STOP | upstream_code | pyScope/PyTektronixScope.py:960-970 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| acquisition_mode | ACQ:MOD | SAM, PEAK, HIR, AVE, WFMDB or ENV | pyScope/PyTektronixScope.py:61-66 |
| acquisition_num_samples | ACQ:NUMSAM | 5000 to 2147400000 samples | pyScope/PyTektronixScope.py:720-721 (the line writes the bounds with thousands separators) |
| acquisition_sampling_mode | ACQ:SAMP | RT, ET or IT | pyScope/PyTektronixScope.py:97-99 |
| acquisition_state | ACQ:STATE | ON, OFF, RUN or STOP | pyScope/PyTektronixScope.py:75-78 |
| acquisition_stop_after | ACQ:STOPA | RUNST or SEQ | pyScope/PyTektronixScope.py:87-88 |
| acquisition_enhanced_enob | ACQ:ENHANCEDE | AUTO or OFF | pyScope/PyTektronixScope.py:659 |
| acquisition_enhanced_state | ACQ:ENHANCEDE:STATE | true or false (1 or 0) | pyScope/PyTektronixScope.py:665-666 |
| acquisition_interp_8bit | ACQ:INTERPE | AUTO, ON or OFF | pyScope/PyTektronixScope.py:673 |
| acquisition_magnivu | ACQ:MAG | true or false (ON or OFF) | pyScope/PyTektronixScope.py:677 |

Safety: the e-stop writes `:STOP`, the command of the upstream `stop()` method (pyScope/PyTektronixScope.py:966-970),
which disables the trigger and stops the acquisition.  At R1 no hardware e-stop is needed, and none is cited.

Not covered: waveform arrays (`CURV?`/`get_waveform`), channel configuration, edge-trigger configuration, timebase
configuration and the `force_trigger`/`run` helper methods.  The driver exposes acquisition state instead, so the
scope's scalar settings and state are available without the array.

Tags: oscilloscope, tektronix, dpo70000, scpi
