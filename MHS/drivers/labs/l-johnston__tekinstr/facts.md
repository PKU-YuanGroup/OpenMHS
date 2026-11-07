# Facts and tags for gh.l-johnston/tekinstr

Every fact cites its source at commit `7949430c1a6818d30aec152663c18dde85f2a7d7`: `upstream_code` is a file and
line of the clone, `vendor_doc` is the clone's README.  The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| CommChannel opens a TCPIP VISA resource and identifies the instrument by *IDN? before returning the model class | upstream_code | tekinstr/__init__.py:43-58 |
| MDO3000 builds its Oscilloscope subsystem with the ANALOG:NUMCHANNELS count of CONFIGURATION | upstream_code | tekinstr/mdo3000/mdo3000.py:18-22 |
| sample_rate reads HORIZONTAL:SAMPLERATE? and is the rate the oscilloscope always acquires at | upstream_code | tekinstr/mdo3000/oscilloscope.py:24-30 |
| record_length takes 1e3, 1e4, 1e5, 1e6, 5e6 or 1e7 samples and is written as HORIZONTAL:RECORDLENGTH | upstream_code | tekinstr/mdo3000/oscilloscope.py:32-39 |
| horizontal_scale is the amount of time per division read and written as HORIZONTAL:SCALE | upstream_code | tekinstr/oscilloscope.py:33-41 |
| horizontal_delay_mode is delay_time or pretrigger_percent and is written as HORIZONTAL:DELAY:MODE ON/OFF | upstream_code | tekinstr/mdo3000/oscilloscope.py:41-54 |
| acquisition_mode is SAMPLE, PEAKDETECT, HIRES, AVERAGE or ENVELOPE | upstream_code | tekinstr/mdo3000/oscilloscope.py:78-89 |
| num_averages is the number of waveforms to average; the range is 2 to 512 in powers of 2 | upstream_code | tekinstr/oscilloscope.py:112-122 |
| acquisition_state starts or stops the acquisition with RUN (1) or STOP (0) | upstream_code | tekinstr/oscilloscope.py:134-142 |
| single_acquisition writes ACQUIRE:STOPAFTER SEQUENCE for True and RUNSTOP for False | upstream_code | tekinstr/oscilloscope.py:144-158 |
| force_trigger writes TRIGGER FORCE | upstream_code | tekinstr/oscilloscope.py:327-329 |
| trigger_state is one of ARMED, AUTO, READY, SAVE or TRIGGER | upstream_code | tekinstr/oscilloscope.py:331-334 |
| read returns the acquired waveform samples as a WaveformDT or a numpy array | upstream_code | tekinstr/oscilloscope.py:240-325 |
| The upstream README reads channel CH1 through CommChannel and receives a waveform object | vendor_doc | README.md:13-18 |
| The MDO3000 series is one of the supported model families | vendor_doc | README.md:31-32 |

Limits: the record length allowed set comes from the six values of `tekinstr/mdo3000/oscilloscope.py:34`; the
acquisition-mode set from `tekinstr/mdo3000/oscilloscope.py:80`; the delay-mode set from
`tekinstr/mdo3000/oscilloscope.py:43`; the acquisition-state set from `tekinstr/oscilloscope.py:136`; the number of
averages is every power of two from 2 to 512 because `tekinstr/oscilloscope.py:115` states that range but not the
individual values.  The horizontal scale has no bound in the clone: it is `Limit.operator_required`, and every write
is refused `MHS.SAFETY.LIMITS_UNSET` until the site supplies the timebase range.  `site-limits.example.json` shows
such an overlay with an example range.

Safety: the e-stop sets the native `acquisition_state` to `STOP` (tekinstr/oscilloscope.py:134-142); the frozen
display is the safe state.  The package is R1 and model-authored; it declares no independent hardware e-stop and
claims no hardware run.

Tags: oscilloscope, tektronix, mdo3000, scpi, visa, test instrument
