OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.pcdshub/pcdsdevices

Every fact cites the pinned clone at commit `d13b06eb53e6185088a7534ce0e17ab154463407`. `upstream_code` refs name
`path/in/clone:LINE`; the same facts are written into `driver.py` (`facts = [...]`), and the reference file is generated
from the driver, not from this page.

Tags: `ophyd`, `epics`, `timing`, `trigger`, `lcls`.

## Facts

| fact | source | ref |
|---|---|---|
| TprTrigger is an ophyd BaseInterface/Device for an individual TPR trigger. | upstream_code | pcdsdevices/tpr.py:60-63 |
| The TprTrigger channel argument is an integer from 0 through 11. | upstream_code | pcdsdevices/tpr.py:71-72 |
| TimingMode has the members LCLS1 = 1 and LCLS2 = 2. | upstream_code | pcdsdevices/tpr.py:19-21 |
| TprTrigger formats the channel as `:CHnn_` and the trigger as `:TRGnn_` and rejects any other timing mode. | upstream_code | pcdsdevices/tpr.py:137-152 |
| `enable_ch_cmd` and `enable_trg_cmd` are EpicsSignal channel-enable and trigger-enable commands. | upstream_code | pcdsdevices/tpr.py:124-131 |
| `enable()` calls `enable_ch()` then `enable_trg()`; `disable()` calls `disable_ch()` then `disable_trg()`. | upstream_code | pcdsdevices/tpr.py:154-162 |
| `enable_ch` and `enable_trg` put 1; `disable_ch` and `disable_trg` put 0. | upstream_code | pcdsdevices/tpr.py:164-178 |
| `ns_delay` is a MultiDerivedSignal over `delay_ticks`, `delay_taps` and `delay_setpoint` with the doc "Get/set trigger delay in ns". | upstream_code | pcdsdevices/tpr.py:95-101 |
| `width` is a MultiDerivedSignal over `width_ticks` and `width_setpoint` with the doc "Get/set trigger width in nsec". | upstream_code | pcdsdevices/tpr.py:117-123 |
| TPR_TICK_NS is 70 / 13, from the 1.3 GHz phase-reference line divided by 7, and TPR_TAP_NS is 0.08. | upstream_code | pcdsdevices/tpr.py:13-16 |
| The delay read is `delay_ticks` times TPR_TICK_NS plus `delay_taps` times TPR_TAP_NS, and the width read is `width_ticks` times TPR_TICK_NS. | upstream_code | pcdsdevices/tpr.py:24-31 |
| `_put_last` writes the value only to the last signal of a MultiDerivedSignal. | upstream_code | pcdsdevices/tpr.py:34-36 |
| `delay_setpoint` is the TDES EpicsSignal and `width_setpoint` the TWID EpicsSignal of the trigger. | upstream_code | pcdsdevices/tpr.py:92-113 |
| `AggregateSignal.get` calls `get` on every member signal and recalculates the value. | upstream_code | pcdsdevices/signal.py:229-241 |
| `MultiDerivedSignal.put` calls `set`, and `set` passes the `calculate_on_put` mapping to `utils.set_many`. | upstream_code | pcdsdevices/signal.py:696-750 |
| `set_many` logs an exception raised by a member `set`, re-raises it only with `raise_on_set_failure`, and returns a finished Status when no member set started. | upstream_code | pcdsdevices/utils.py:556-579 |
| `eventrate` is an EpicsSignalRO for the channel event rates. | upstream_code | pcdsdevices/tpr.py:86 |
| `label` is an EpicsSignal for the channel description. | upstream_code | pcdsdevices/tpr.py:87 |

## Scope

The package serves one concrete `pcdsdevices.tpr:TprTrigger` (`pcdsdevices/tpr.py:60`), the card's confirmed entry
symbol.  The card proposes the config-only `OphydDriver`, but that proof accepts only direct classic
`Component(EpicsSignal, ...)` declarations; `TprTrigger` builds every signal with `FormattedComponent`
(`pcdsdevices/tpr.py:75-132`), which the Ophyd source proof does not resolve.  The package therefore uses a direct
`Driver` with a `native.py` factory and records the deviation in `RESULT.json`.

Reads: the two enable command values, the channel event rate, the derived trigger delay and width (both in ns), and
the channel description label.  The delay and width reads are computed from the tick and tap PVs
(`pcdsdevices/tpr.py:24-31`), not read back from the setpoints, so after a write they show what the IOC derived in
whole ticks (about 5.38 ns) and taps (0.08 ns), not the written number.

Writes (changed by the model review): `ns_delay.put` and `width.put` write only their setpoint member (`_put_last`,
`pcdsdevices/tpr.py:34-36`) through `utils.set_many`, which logs and drops an exception raised by the member's `set`
and then returns a finished Status (`pcdsdevices/utils.py:556-579`), so a failed setpoint write would have been
reported as completed.  The driver therefore calls `set` on the same member (`delay_setpoint`, the TDES PV, or
`width_setpoint`, the TWID PV) with a 5 s timeout and waits up to 6 s on its Status: a failed or timed-out set fails
the write.  Neither the clone nor a text file in the clone states a numeric range for either setpoint; both writes are
`Limit.operator_required`, so the runtime refuses them with `MHS.SAFETY.LIMITS_UNSET` until the operator's
`site-limits.json` supplies the range.  The example overlay is illustrative only and must be replaced at a site.

One extension capability, `x-cap.pcdshub.tpr_trigger.v1`, wraps the upstream `enable_ch`, `disable_ch`,
`enable_trg` and `disable_trg` calls (`pcdsdevices/tpr.py:164-178`) and reports the observed command values.  No
catalogue class fits a fixed-channel trigger enable/disable: `cap.actuation.gpio.v1` requires a caller-supplied output
pin number, and the TPR channel is fixed when the Device is constructed.  `RESULT.json` requests the id.

Not served: `ns_delay_scan` (a `TprMotor` PV positioner with its own motion semantics), `count` (a counter signal whose
meaning the source does not state), and the many configuration signals such as `ratemode`, `group`, `src`, `polarity`
and `operation`.  They are present on the Device but outside this package's declared scope.

## Safety

The risk is R1 (the card's floor).  The class controls TTL timing trigger outputs; it is not a laser, a high-voltage
contact, a high-force actuator or a robot, and no text of the clone declares an independent hardware e-stop.  The
e-stop method calls the native `disable()` (`pcdsdevices/tpr.py:159-162`), a plain `put(0)` on both the channel and
trigger enable commands with no wait or callback (`pcdsdevices/tpr.py:168-178`); since the model review it then reads
both enable commands back and reports `MHS.SAFETY.SAFE_STATE_UNREACHED`, with the latch held, unless both read 0.  The
runtime latches the endpoint first and refuses every actuating call until an operator reset.  The readback shows the
IOC's enable records; it is not evidence that downstream devices stopped: the TPR has no readback in the served
interface that proves the absence of output pulses, and a downstream laser or shutter is outside this device.  What
the channel triggers decides the real hazard of a deployment (a laser or pulsed high-voltage system raises it).

## Hardware backend

`native.py` imports `pcdsdevices.tpr` only when an operator loads the hardware backend.  The operator supplies the PV
prefix and channel (documented 0 through 11); the factory refuses an empty prefix, a channel outside 0..11, a timing
mode other than LCLS1/LCLS2, or a wait timeout outside (0, 60] s.  It constructs `TprTrigger` and calls
`wait_for_connection` once, so a missing PV raises before any MHS command is served.  It was never run: the package has
never connected to an IOC.

## Licence

The card and `driver.lock.json` record BSD-3-Clause from the repository metadata, matching the clone's licence class.
Model review: `LICENSE.md` is the three BSD clauses plus an "Enhancements" clause that grants SLAC a licence to
enhancements made available publicly or to SLAC (`LICENSE.md:31-39`), and the conda recipe names the licence
"SLAC Open License" (`conda-recipe/meta.yaml:54`); the owner decides whether that matters for publication.
