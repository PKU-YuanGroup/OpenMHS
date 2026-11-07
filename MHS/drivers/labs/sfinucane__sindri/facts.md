# Facts and limits for gh.sfinucane/sindri

Every fact cites its source at commit `d560635a28a57230f1fa32cea3b9d4df0c8af8e7`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.  The clone has no
vendor manual text for the BERTScope, so every citation is `upstream_code`.

| fact | source | ref |
|---|---|---|
| The clone implements the Tektronix BERTScope Bit Error Rate Analyzers and lists the BA1500, BA1600, BSA85C, BSA125A, BSA125B, BSA125C, BSA175C, BSA220C, BSA250C, BSA260C and BSA286C models | upstream_code | sindri/tektronix/bertscope.py:6-20 |
| idn queries *IDN?; the response is user configurable, so the clone does not parse it | upstream_code | sindri/tektronix/bertscope.py:46-51 |
| reset sends *RST to set the instrument functions to the factory default power up state | upstream_code | sindri/tektronix/bertscope.py:53-57 |
| run sends RST 1 to start all systems and stop sends RST 0 to stop all systems within the BERTScope mainframe | upstream_code | sindri/tektronix/bertscope.py:166-176 |
| is_running queries RST? and returns 1 while the mainframe runs | upstream_code | sindri/tektronix/bertscope.py:178-182 |
| run_duration is in seconds with the limits 0 to 36E6; setting it to 0 lets the run go on forever | upstream_code | sindri/tektronix/bertscope.py:184-195 |
| get_internal_temperature queries SENS:TEMP? and returns degrees Celsius; the clone says the measurement is not calibrated and is only a relative indication | upstream_code | sindri/tektronix/bertscope.py:283-290 |
| detector_reset_results sends DET:RRES to reset the error detector results | upstream_code | sindri/tektronix/bertscope.py:344-348 |
| get_detector_bit_count queries DET:BITS? for the total bits detected and get_detector_error_count queries DET:ERR? for the total errors detected during the run | upstream_code | sindri/tektronix/bertscope.py:350-360 |
| get_detector_bit_error_rate queries DET:BER? for the computed bit error rate based on run results | upstream_code | sindri/tektronix/bertscope.py:362-366 |
| get_detector_elapsed_time queries DET:ETIM? for the elapsed seconds since the last reset and get_detector_resyncs queries DET:RESY? for the resync count | upstream_code | sindri/tektronix/bertscope.py:368-378 |
| get_detector_error_free_bits_count queries DET:EFB? for the latest error-free bit count and get_detector_error_free_time queries DET:EFT? for the latest error-free time | upstream_code | sindri/tektronix/bertscope.py:380-390 |
| BERTScope_TCP mixes the BERTScope core, Mainframe and Detector features with the IEEE 488.2 subset and a TCP transport | upstream_code | sindri/tektronix/bertscope.py:464-472 |

Limits:

| parameter | limit | source | ref |
|---|---|---|---|
| run_duration | 0 to 36E6 s (0 runs forever) | upstream_code | sindri/tektronix/bertscope.py:184 |

The run duration is the only writable setting this package serves; every other numeric input is absent from the
method signatures, so the hardware view has no unbounded numeric input.  The upstream detector settings
(`detector_data_delay`, `detector_update_interval`, `detector_ber_display_mode`) declare no numeric range in the
clone; this package does not write them and does not expose them.

Safety: the e-stop calls the native `stop()` (`RST 0`, sindri/tektronix/bertscope.py:172-176), which stops all
systems within the mainframe; the same native `stop()` is the `safe_state=True` action `x-cap.sfinucane.stop.v1`.
No line of the clone documents an independent hardware e-stop, and the card's floor is R1, so
`estop_physical_ref` is not set.  The driver does not start an acquisition on its own; `run` is an explicit action.

Not exposed from the upstream class: `event_status_reg` is declared as a Feat with only a setter and no getter
(sindri/tektronix/bertscope.py:94-102), and `set_operation_complete_bit` sends `*OPC` through `query()`
(sindri/tektronix/bertscope.py:138-146); both are left out because this driver cannot read them reliably.
`detector_auto_align` is also left out of this package's scope.

Tags: bertscope, tektronix, bit-error-rate, ber, instrument, scpi, tcp

Authoring: model-authored (`driver.lock.json` `authored_by` kind `model`, model `deepseek-v4.1-flash:1017`, run
`wP-023`); `reviewed_by` is null.  The package is checked on the fake backend only; nothing here ran on hardware.
