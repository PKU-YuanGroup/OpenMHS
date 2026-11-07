# Facts and tags for gh.aalto-qcd/qickodes

Every fact cites its source at commit `29e7efba0021c797f627cf8097df17b5d34cf4f8`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). Copy each fact into `facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| QickInstrument is a QCoDeS Instrument whose constructor takes ns_host and ns_port=8888 | upstream_code | src/qickodes/instrument_v2.py:93-96 |
| The constructor obtains soc, the Pyro4 proxy of the QickSoc, and soccfg from make_proxy(ns_host, ns_port) | upstream_code | src/qickodes/instrument_v2.py:99-102 |
| It asserts exactly one tProc of type qick_processor and refuses any other type | upstream_code | src/qickodes/instrument_v2.py:107-110 |
| It builds StandardDacChannel or MultiplexedDacChannel objects from soccfg['gens'] and AdcChannel objects from soccfg['readouts'] | upstream_code | src/qickodes/instrument_v2.py:112-142 |
| hard_avgs is a ManualParameter with vals=Ints(min_value=0) and initial value 1000 | upstream_code | src/qickodes/instrument_v2.py:155-161 |
| soft_avgs is a ManualParameter with vals=Ints(min_value=0) and initial value 1 | upstream_code | src/qickodes/instrument_v2.py:162-168 |
| final_delay is a SweepableParameter with unit sec, initial value 1e-6 and min_value=0 | upstream_code | src/qickodes/instrument_v2.py:169-176 |
| final_wait is a SweepableParameter with unit sec, initial value 0 and min_value=0 | upstream_code | src/qickodes/instrument_v2.py:177-184 |
| initial_delay is a SweepableParameter with unit sec, initial value 1e-6 and min_value=0 | upstream_code | src/qickodes/instrument_v2.py:185-192 |
| SweepableParameter.get_raw returns the stored QickParam rounded value, or its start for a scalar, and SweepableParameter.set_raw stores the value as a QickParam and registers or removes a sweep | upstream_code | src/qickodes/parameters_v2.py:72-93 |
| set_macro_list replaces the macro_list ChannelTuple with the given sequence of Macro objects | upstream_code | src/qickodes/instrument_v2.py:200-217 |
| run refuses an empty macro_list with a RuntimeError that asks for set_macro_list first | upstream_code | src/qickodes/instrument_v2.py:240-245 |
| run takes a qcodes Measurement and returns the datasaver run_id, writing the acquired data to the QCoDeS dataset | upstream_code | src/qickodes/instrument_v2.py:227-401 |
| run_without_saving builds an AveragerProgram, acquires through qick.qick_asm.AcquireMixin, and returns a dict of complex IQ values keyed by readout name | upstream_code | src/qickodes/instrument_v2.py:633-654 |
| Ddr4Buffer.arm calls parent.soc.arm_ddr4(selected_adc_channel.get(), num_transfers.get()) | upstream_code | src/qickodes/instrument_v2.py:693-696 |
| The DDR4 num_transfers parameter is a ManualParameter with vals=Ints(min_value=1) | upstream_code | src/qickodes/instrument_v2.py:685-691 |
| get_idn reports vendor Xilinx, the soccfg board name, no serial, and the remote and local QICK versions | upstream_code | src/qickodes/instrument_v2.py:219-225 |
| The project depends on pyro4, qcodes and qick>=0.2.255 and requires Python 3.11 or newer | upstream_code | pyproject.toml:10-26 |
| The README instructs the operator to start the Pyro4 nameserver on port 8888 and the QICK server on a Xilinx board before constructing QickInstrument with the board address | vendor_doc | README.md:60-67 |

## Limits

| bound | value | source | ref |
|---|---|---|---|
| final_delay minimum | 0 s | upstream_code | src/qickodes/instrument_v2.py:175 |
| final_wait minimum | 0 s | upstream_code | src/qickodes/instrument_v2.py:183 |
| initial_delay minimum | 0 s | upstream_code | src/qickodes/instrument_v2.py:191 |
| hard_avgs minimum | 0 | upstream_code | src/qickodes/instrument_v2.py:159 |
| soft_avgs minimum | 0 | upstream_code | src/qickodes/instrument_v2.py:166 |

No source in the clone states an upper bound for any of these five controls, so the driver declares only the minimum
and does not invent a maximum. The bounds come from the validator arguments the constructor passes, not from the
constructor's initial values.

## Model review (2026-11-05)

The author's e-stop and safe state cleared the macro list with `set_macro_list([])`. That is a Python-side list, not a
native stop: this package never sets a macro list or starts a run, and the pinned clone has no stop, abort or disarm
method for a running program or an armed DDR4 buffer. The e-stop now clears the list and reports
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held, and the gate fails G6.ESTOP_FAILED. The five served writes
only store values in the Python instrument; they reach the board only when `run` or `run_without_saving` builds a
program, which the package does not serve, so the primary control of the repository (macro-list pulse programs and
their IQ acquisition) is not covered. The package is blocked.

## Tags

`qcodes`, `qick`, `rf`, `quantum-control`, `pulse-sequencing`, `pyro4`
