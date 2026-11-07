# Facts and tags for gh.maxiv-kitscontrols/sardana-albaem

Every fact cites its source at commit `99e701a5101781fbd7855a03b5ec3a755e8c6d46`: `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| em2.py is the ALBA EM2 client | upstream_code | `sardana_albaem/ctrl/em2.py:1-2` |
| SCPI_CONTROL_PORT is 5025 and ZMQ_STREAMING_PORT is 22003 | upstream_code | `sardana_albaem/ctrl/em2.py:30-31` |
| Em2 creates a SCPI TCP socket to (host, port) and a ZMQ stream receiver | upstream_code | `sardana_albaem/ctrl/em2.py:128-132` |
| The electrometer channels are numbered 1 to 4 | upstream_code | `sardana_albaem/ctrl/em2.py:35-36` |
| Channel.current reads CHANxx:INSC? and converts the reply to float | upstream_code | `sardana_albaem/ctrl/em2.py:68-70` |
| Channel.range reads and writes CHANxx:CABO:RANGE | upstream_code | `sardana_albaem/ctrl/em2.py:51-57` |
| Channel.inversion reads CHANxx:CABO:INVE?, returns True only for 'On', and the setter writes 'On' or 'Off' | upstream_code | `sardana_albaem/ctrl/em2.py:59-66` |
| The amplifier range list runs from 1 mA to 100 pA | upstream_code | `sardana_albaem/macro/albaEmUtils.py:10` |
| MINIMUM_INTEGRATION_TIME_MS is 0.1 and MAXIMUM_INTEGRATION_TIME_WITHOUT_OVERFLOW_MS is 2621.0 | upstream_code | `sardana_albaem/ctrl/Albaem2OneDCtrl.py:17-20` |
| LoadOne refuses an integration time below 0.1 ms or above 2621.0 ms | upstream_code | `sardana_albaem/ctrl/Albaem2OneDCtrl.py:192-203` |
| Em2.acquisition_time is in seconds on the client and is sent to the device in milliseconds | upstream_code | `sardana_albaem/ctrl/em2.py:204-210` |
| Em2.idn queries *idn? | upstream_code | `sardana_albaem/ctrl/em2.py:187-189` |
| Em2.acquisition_state queries ACQU:STAT? and returns the suffix after STATE_ | upstream_code | `sardana_albaem/ctrl/em2.py:200-202` |
| Em2.nb_points queries ACQU:NTRIG? and writes ACQU:NTRIG <value> | upstream_code | `sardana_albaem/ctrl/em2.py:212-218` |
| Em2.nb_points_ready returns the number of received streaming points or queries ACQU:NDAT? | upstream_code | `sardana_albaem/ctrl/em2.py:220-228` |
| Em2.trigger_mode, trigger_input, trigger_polarity, trigger_precision and trigger_delay read and write the TRIG:* settings; the delay is in seconds on the client and milliseconds on the wire | upstream_code | `sardana_albaem/ctrl/em2.py:230-268` |
| Em2.software_trigger sends TRIG:SWSE True | upstream_code | `sardana_albaem/ctrl/em2.py:270-271` |
| Em2.start_acquisition sends ACQU:START, appending SWTRIG when soft_trigger is true | upstream_code | `sardana_albaem/ctrl/em2.py:289-292` |
| Em2.stop_acquisition sends ACQU:STOP True and stops the ZMQ receiver | upstream_code | `sardana_albaem/ctrl/em2.py:294-297` |
| Em2.timestamp_data reads TMST? and writes TMST True/False | upstream_code | `sardana_albaem/ctrl/em2.py:281-287` |
| The alternate controller names the acquisition modes CHARGE, CURRENT and STREAMING | upstream_code | `sardana_albaem/ctrl/Albaem2CoTiCtrl.py:63-69` |
| The manual test names the trigger modes SOFTWARE, HARDWARE, GATE, AUTOTRIGGER and HW_AUTOTRIGGER | upstream_code | `sardana_albaem/ctrl/manual_test_em2.py:113-116` |

## Limits

- `integration_time` is bounded to 0.1 to 2621.0 ms by the upstream controller constants
  (`sardana_albaem/ctrl/Albaem2OneDCtrl.py:17-20`) and its LoadOne check
  (`sardana_albaem/ctrl/Albaem2OneDCtrl.py:192-203`).
- `nb_points` and `trigger_delay` have no bound in the clone, so they are `Limit.operator_required`. Every write is
  refused with `MHS.SAFETY.LIMITS_UNSET` until the site supplies a bound. `site-limits.example.json` is an example
  overlay, not a statement about any electrometer.
- The `x-cap.maxiv-kitscontrols.configure_channel.v1` `amplifier_range` input accepts only the amplifier ranges
  named by the upstream macro (`sardana_albaem/macro/albaEmUtils.py:10`); the `range_chN` state fields are read-only
  and report the range the device returns.
- The `cap.measure.current.v1` `channel` input accepts only the channel numbers 1 to 4
  (`sardana_albaem/ctrl/em2.py:35-36`).

## Safety

- The upstream stop path is `Em2.stop_acquisition()`: it sends `ACQU:STOP True`
  (`sardana_albaem/ctrl/em2.py:294-297`). It is the `@estop` method and the `safe_state=True` extension action.
- No line of the clone documents an independent hardware e-stop. The device is at risk class R1 (it measures
  current and has no actuation of its own); no hardware e-stop is claimed.
- The hardware backend was never opened, and the fake is an in-memory object, not a recording of an electrometer.

## Not covered

NOT COVERED: the buffered acquisition arrays from `Em2.read()` (`ACQU:MEAS?`) and the ZMQ streaming path
(`ZmqStreamReceiver`). The driver exposes the instant current of each channel and the scalar acquisition and trigger
settings; the array is not the only data the device gives.

Tags: electrometer, current, four-channel, scpi, alba
