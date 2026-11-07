# Facts and tags for gh.karimrayttu/ece-tool-suite

Every fact cites its source at commit `13f7962a674ebc998a2ad2a31eb8592df65ad022`: `vendor_doc` (a
text file of the clone such as `README.md` or `docs/*.md`) or `upstream_code` (`path/in/clone.py:LINE`).
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from
the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The default scope driver speaks the InfiniiVision-compatible SCPI set (:CHANx:SCAL, :TIM:SCAL, :TRIG:EDGE, :MEAS:*, :WAV:PRE? plus an IEEE-488.2 definite-length block) and covers Keysight, Rigol, Siglent, Rohde & Schwarz and GW Instek scopes | vendor_doc | docs/instruments.md:28-31 |
| identify queries *IDN? and passes the reply to parse_idn | upstream_code | backend/ece_suite/instruments/keysight.py:42-43 |
| parse_idn splits the *IDN? reply into vendor, model, serial and firmware | upstream_code | backend/ece_suite/instruments/scpi.py:30-35 |
| reset writes *RST and then *CLS | upstream_code | backend/ece_suite/instruments/keysight.py:45-47 |
| run, stop and single write :RUN, :STOP and :SINGle | upstream_code | backend/ece_suite/instruments/keysight.py:110-117 |
| capture selects :WAV:SOUR, sets :WAV:FORM WORD and :WAV:BYT LSBF, reads :WAV:PRE? and :WAV:DATA?, and returns a Waveform with points and vpp metadata | upstream_code | backend/ece_suite/instruments/keysight.py:151-161 |
| measure queries :MEAS:VPP?, :MEAS:VRMS?, :MEAS:VMAX?, :MEAS:VMIN?, :MEAS:FREQ? and :MEAS:PER? on the requested channel | upstream_code | backend/ece_suite/instruments/keysight.py:163-171 |
| safe_float returns None instead of a value whose magnitude is above 1e30 | upstream_code | backend/ece_suite/instruments/scpi.py:38-42 |
| measure_all queries the 16-item InfiniiVision measurement set and tags each value with the unit V, Hz, s or % | upstream_code | backend/ece_suite/instruments/keysight.py:175-190 |
| The VISA transport opens a pyvisa resource with a default timeout of 5000 ms and newline read and write terminators | upstream_code | backend/ece_suite/instruments/transport.py:42-82 |
| VisaTransport serializes write, query and query_raw on a lock and closes both the instrument handle and the resource manager | upstream_code | backend/ece_suite/instruments/transport.py:87-104 |
| The oscilloscope tab has four channels with V/div, offset, coupling and probe attenuation, timebase and trigger controls, Run/Stop/Single, and a measurement strip read back from the instrument | vendor_doc | README.md:211-214 |
| The control-to-SCPI table maps set_channel, set_timebase, set_trigger, set_acquisition and run/stop/single to the Keysight dialect | vendor_doc | docs/tutorial/03-instruments.md:138-152 |
| The measurement strip polls the full 16-item InfiniiVision set on demand, Keysight's ~9.9E37 invalid sentinel is filtered to null, and the 5 Hz stream carries only the light six-measurement set | vendor_doc | docs/tutorial/03-instruments.md:178 |
| The scope front-end absolute maximum is 5 V at 50 ohm and 300 V at 1 Mohm, scaled by probe attenuation | vendor_doc | docs/tutorial/02-architecture.md:242 |
| The runtime has scope_capture and scope_measure_vpp functions that call capture(1) and measure_vpp(1) | upstream_code | backend/ece_suite/main.py:100-112 |

Limits: there are none in this package.  The upstream class writes channel, timebase, trigger and
acquisition settings (:CHANn:SCAL, :TIM:SCAL, :TRIG:EDGE, :ACQ:TYPE and the rest,
`backend/ece_suite/instruments/keysight.py:49-108`) but exposes no query method for any of those
settings, so a write would not change a state field this driver can read.  Rather than invent a
read-back, the package serves only state it can observe and does not expose writable parameters.
Every action input is an enumerated measurement name, so the driver also has no numeric invoke
input to bound.

Safety: the e-stop and the safe-state action `x-cap.karimrayttu.stop_acquisition.v1` call the native
`stop()` (:STOP, `backend/ece_suite/instruments/keysight.py:113-114`), which halts acquisition; the
frozen display is the oscilloscope's safe state.  The clone documents no independent hardware
e-stop line, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this
R1 hardware driver.

NOT COVERED: the waveform array.  `capture()` transfers an IEEE 488.2 binary block (:WAV:DATA?) as
time and voltage arrays (`backend/ece_suite/instruments/keysight.py:151-161`); the standard has no
trace-array class yet, so the capture action reports only the scalar summary (points, vpp,
duration).  The PNG screenshot and the FFT are not exposed either.  The fake's capture returns a
five-point stand-in, not the acquired record length.

Tags: oscilloscope, scpi, visa, keysight, infiniivision, measurement

Authoring: model-authored (`driver.lock.json` `authored_by` kind `model`, model
`deepseek-v4.1-flash:1017`, run `wC-106`); `reviewed_by` is null.  The package is checked on the fake
backend only; nothing here ran on hardware.
