# Facts and tags for gh.mclim9/rssd

Every fact cites its source at commit `7b040ee12841e721953a1f737297586135c0c110`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

The driver serves the upstream phase noise analyzer class `rssd/PNA/Common.py:PNA` (its constructor sets
`Model = "FSWP"`) over the SCPI lines that class builds. The upstream opens the instrument through
`rssd/yaVISA.py` with pyvisa; this driver does not import or install that package: the ScpiDriver bridge opens the
socket or VISA resource itself.

| fact | source | ref |
|---|---|---|
| The PNA class is the phase noise analyzer object of the repository; its constructor sets Model to 'FSWP' | upstream_code | rssd/PNA/Common.py:1-8 |
| INP:ATT? reads the mechanical input attenuation | upstream_code | rssd/PNA/Common.py:13-15 |
| INP:ATT <dB> sets the mechanical input attenuation, formatted without decimals | upstream_code | rssd/PNA/Common.py:133-135 |
| INST:LIST? returns the measurement channels as one comma-separated reply | upstream_code | rssd/PNA/Common.py:17-19 |
| A channel name in the INST:LIST? reply is quoted, so Set_Channel compares each entry with a quoted name | upstream_code | rssd/PNA/Common.py:151-157 |
| The channel names the clone knows are SAN, IQ, NR5G, LTE, WLAN, PNOISE, NOISE, SPUR, ADEM, DDEM, V5GT and AMPL | upstream_code | rssd/PNA/Common.py:148 |
| :SENS:FREQ:CENT? reads the center frequency of the measurement | upstream_code | rssd/PNA/Common.py:22 |
| The center frequency is written as ':SENS:FREQ:CENT <value> HZ' | upstream_code | rssd/PNA/Common.py:163 |
| :SENS:SWE:POIN? reads the number of trace points of a sweep | upstream_code | rssd/PNA/Common.py:91 |
| The number of sweep points is written as ':SENS:SWE:POIN <value>' with six decimals | upstream_code | rssd/PNA/Common.py:240 |
| SENS:SWE:TIME? reads the sweep or capture time | upstream_code | rssd/PNA/Common.py:95 |
| The sweep time is written in seconds and 0 selects the automatic sweep time | upstream_code | rssd/VNA/Common.py:177-179 |
| :SENS:SWE:TYPE? reads the sweep type, one of AUTO, SWE and FFT | upstream_code | rssd/PNA/Common.py:99-101 |
| DISP:TRAC:Y:RLEV? reads the reference level of the trace | upstream_code | rssd/PNA/Common.py:78 |
| The reference level is written as 'DISP:WIND:TRAC:Y:SCAL:RLEV <value> dBm' | upstream_code | rssd/PNA/Common.py:210 |
| INIT:CONT OFF selects a single sweep and INIT:CONT ON a continuous sweep | upstream_code | rssd/PNA/Common.py:232-237 |
| :INP:ATT:AUTO ON returns the input attenuation to automatic | upstream_code | rssd/PNA/Common.py:137-138 |
| The upstream wrapper queries *IDN? and splits the reply on ', ' into make, model, device and version | upstream_code | rssd/yaVISA.py:75-85 |

Limits: no text file of the clone states a range for the attenuation, the center frequency or the number of sweep
points, so all three writable parameters are `Limit.operator_required`: every write is refused
`MHS.SAFETY.LIMITS_UNSET` until the operator overlay (`site-limits.json`, see `site-limits.example.json`) supplies
the bounds of the site. The overlay may only narrow them.

Safety: the e-stop writes `INIT:CONT OFF` (single sweep; the continuous acquisition stops) and `:INP:ATT:AUTO ON`
(the input attenuation returns to automatic, which protects the receiver front end from an overload). The
instrument is a receiver: the driver drives no output. This is a software-commanded safe state; no independent
hardware stop is claimed, and none is needed at R1.

Identity: the driver probes `*IDN?` on connect (the default of the SCPI bridge) but does not check its content,
because no text file of the clone states the identity string of an FSWP.

Tags: phase noise analyzer, signal analyzer, fswp, scpi, rohde-schwarz
