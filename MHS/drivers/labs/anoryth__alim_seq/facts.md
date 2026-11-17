# Facts and tags for gh.anoryth/alim_seq

Every fact cites the upstream clone `labs/anoryth/alim_seq` at commit
`4264b54bdb8087636da640420735c0633fd1dcb9`. `vendor_doc` refs name a text file of the clone (`README.md`,
`docs/*.md`); `upstream_code` refs name a Python line. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project sequences the power supply of an electronic board and controls R&S HMP40xx/20xx supplies over SCPI | vendor_doc | README.md:3-6 |
| The upstream README warns that its software protections do not replace a hardware safety device nor the operator's judgement | vendor_doc | README.md:11-15 |
| HMP4040 is the SCPI driver for the Rohde & Schwarz HMP4040 through pyvisa | upstream_code | alim_seq/psu.py:148-154 |
| BasePSU declares n_channels = 4 | upstream_code | alim_seq/psu.py:119 |
| HMP4030 and HMP2030 declare three channels, and HMP2020 declares two channels | upstream_code | alim_seq/psu.py:403-420 |
| connect() opens the VISA resource with pyvisa and probes *IDN? | upstream_code | alim_seq/psu.py:199-231 |
| connect() sends *CLS, switches every channel output off with OUTP:SEL OFF and then enables the general output with OUTP:GEN ON | upstream_code | alim_seq/psu.py:249-255 |
| A setting selects the channel with INST OUT<n> and then writes VOLT, CURR or OUTP:SEL | upstream_code | alim_seq/psu.py:344-359 |
| A measurement selects the channel and queries MEAS:VOLT? or MEAS:CURR? | upstream_code | alim_seq/psu.py:361-367 |
| When status reading is enabled, measure_status queries STAT:QUES:INST:ISUM<channel>:COND? and decodes CC/CV/OTP/OVP/FUSE bits; a disabled or failed status query returns mode=None and no faults | upstream_code | alim_seq/psu.py:372-397 |
| all_outputs_off() calls set_output(ch, False) for every channel | upstream_code | alim_seq/psu.py:143-145 |
| close() attempts all_outputs_off with a shortened timeout and use_opc=False, suppresses its failure, then closes the VISA session | upstream_code | alim_seq/psu.py:289-317 |
| _write sends a command and optionally queries *OPC? without inspecting its reply | upstream_code | alim_seq/psu.py:328-330 |
| _select caches a channel number, and setting voltage, current or output selects a channel before writing its command; those methods contain no lock | upstream_code | alim_seq/psu.py:344-359 |
| The HMP4040 declares max_voltage = 32.0 V, max_current = 10.0 A and max_power = 160.0 W per channel | upstream_code | alim_seq/psu.py:156-160 |
| The config validator rejects a channel max_voltage above the model's max_voltage and a max_current above max_current, but does not combine them into a power bound | upstream_code | alim_seq/config.py:402-410 |
| The controller's emergency_stop() takes each instrument lock non-blocking and still calls all_outputs_off() when the lock is busy | upstream_code | alim_seq/controller.py:1056-1078 |
| The upstream factory builds MockPSU when simulate is true and the model class otherwise | upstream_code | alim_seq/psu.py:562-575 |

Limits: the channel selector is 1 through 4 (`alim_seq/psu.py:111-119`, numbered from 1 with four channels).
Each voltage/current setpoint is `operator_required`: the cited model-maxima lines state 32.0 V and 10.0 A but
state no lower bound. The example overlay supplies test bounds only; the deployment must set both bounds for its
load within the model maxima. No fake value is a source for an envelope.

The model also declares 160.0 W per channel (`alim_seq/psu.py:156-160`). Separate voltage/current maxima do not
implement the complete safe operating area. The controller/configuration and its load protections are not served.

Safety and block:

* `all_outputs_off()` loops through `set_output(ch, False)` (`alim_seq/psu.py:143-145`). `_write()` optionally
  queries `*OPC?` but discards its reply (`alim_seq/psu.py:328-330`); `use_opc=False` skips it entirely. A returned
  method call therefore does not validate completion. There is no output-enable-state query in this class.
* `_select()` shares a cached channel with reads and commands (`alim_seq/psu.py:344-367`). Its selection and command
  writes are separate and unprotected, while an MHS stop can run concurrently with an ordinary call. An in-flight
  query or command can interfere with this cut-off attempt; the upstream controller's nonblocking-lock attempt
  (`alim_seq/controller.py:1056-1078`) does not establish a serialized, acknowledged stop for this package.
* `@estop` still attempts the upstream off request, then raises `MHS.SAFETY.SAFE_STATE_UNREACHED`. The runtime keeps
  the latch engaged; the ordinary all-outputs-off action reports `off_requested`, and has no `safe_state=True`.
  The package supplies no independently documented physical stop. Its R2 hardware view therefore fails G3/SAFE-045.
* VISA calls default to 5000 ms (`alim_seq/psu.py:162`), and the stop can involve several writes/queries. A timeout
  can delay even the first channel cut-off beyond the endpoint's stop budget. `close()` suppresses errors from its
  off attempt (`alim_seq/psu.py:289-317`), so teardown is not a substitute for a verified stop.
* Recovery needs a source-backed helper that orders concurrent I/O, validates shutdown acknowledgement and meets a
  bounded stop deadline, plus the complete deployment envelope. No output-off or safe-hardware state is claimed.

Mock path: the card prefers the upstream simulator, `MockPSU` (alim_seq/psu.py:423-528). This package uses its own
in-memory fake instead. It does not import the clone, and `MockPSU` exposes `set_load`, `set_current_source` and
`output_power`, which the `HMP4040` class named by `native` does not have. The fake implements only the HMP4040
method surface and marks every value as `# placeholder`; it is not a recording and does not model a load.

Tags: power supply, DC source, SCPI, VISA, HMP4040, alim_seq
