# Facts and tags for gh.samdejong86/tektronix-serial-daq-python

Every fact cites its source at commit `e7728bc44030b530d76ea3dbd66904237c12e180`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`tekdaq.py:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is DAQ software for a Tektronix TDS 3052 oscilloscope over an RS-232 connection | vendor_doc | README.md:5 |
| The clone opens the scope into the module-level VISA resource tds | upstream_code | tekdaq.py:70 |
| The script asks the instrument for its identity with *IDN? and reads the reply | upstream_code | tekdaq.py:85-90 |
| A setting is sent as a command word, a space and its value, for example 'CH1:SCA ' + value | upstream_code | tekdaq.py:111 |
| The channel vertical scales are read back with CH1:SCALE? and CH2:SCALE? | upstream_code | tekdaq.py:153-156 |
| The record length is restricted to the tokens 5.E2 and 1.E4 | upstream_code | tekdaq.py:41 |
| The coupling choices are AC and DC, and the input impedance choices are FIF and MEG | upstream_code | tekdaq.py:49-52 |
| The trigger source is written as EXT or CH<n> | upstream_code | tekdaq.py:132-135 |
| The trigger slope choices are RISE and FALL | upstream_code | tekdaq.py:46 |
| The clone locks the front panel with LOC All and sets the acquisition stop condition to SEQ | upstream_code | tekdaq.py:221-222 |
| The clone releases the front-panel lock with LOC NONE when it finishes | upstream_code | tekdaq.py:321 |
| The module's only top-level definitions are the plotting callbacks init, finished, writeEvent and animate | upstream_code | tekdaq.py:307-375 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| ch1_scale (V) | CH1:SCA | operator_required: the clone states no vertical-scale range | - |
| ch2_scale (V) | CH2:SCA | operator_required: the clone states no vertical-scale range | - |
| coupling_ch1 | CH1:COUPL | AC or DC | tekdaq.py:49 |
| coupling_ch2 | CH2:COUPL | AC or DC | tekdaq.py:50 |
| horizontal_scale (s) | HOR:SCA | operator_required: the clone states no time-per-division range | - |
| impedance_ch1 | CH1:IMPED | FIF or MEG | tekdaq.py:51 |
| impedance_ch2 | CH2:IMPED | FIF or MEG | tekdaq.py:52 |
| record_length | HOR:RECORDLENGTH | 5.E2 or 1.E4 | tekdaq.py:41 |
| trigger_level (V) | TRIGGER:A:LEVEL | operator_required: the clone states no level range | - |
| trigger_position (%) | HOR:TRIG:POS | operator_required: the clone states no percentage range | - |
| trigger_source | TRIG:A:EDGE:SOU | CH1, CH2 or EXT | tekdaq.py:132-135 |
| trigger_slope | TRIG:A:EDGE:SLO | RISE or FALL | tekdaq.py:46 |

The numeric writes have no bound in the clone, so `Limit.operator_required` refuses every write until an operator
fills the bound in `site-limits.json`; `site-limits.example.json` is an example overlay only.

Safety: the e-stop writes `ACQ:STOPA SEQ` and `LOC NONE` (tekdaq.py:222, 321).  The clone has no immediate-stop
command; `ACQ:STOPA SEQ` makes the acquisition stop after the current sequence, and `LOC NONE` releases the remote
front-panel lock.  The driver declares R1 because `cap.device.configure.v1` has that class floor; the instrument
itself only changes settings.  No hardware backend was run.

Tags: oscilloscope, tds 3052, tektronix, serial, scpi

Not covered: the waveform array (the `WFMPRE?` preamble at tekdaq.py:205 and the IEEE 488.2 binary `CURVE?` block at
tekdaq.py:402).  The SCPI bridge is line-oriented, so this package exposes the settings the clone reads and writes,
not the acquired waveform.
