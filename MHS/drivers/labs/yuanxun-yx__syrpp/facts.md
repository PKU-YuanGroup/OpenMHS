# Facts and limits for gh.yuanxun-yx/syrpp

Every fact cites its source at commit `ae784882903cd9d1b72162835902dca0074b2e14`: `upstream_code` for a code
line of the clone or `vendor_doc` for a text file (README.md here). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| A command is the pump address, the command code and its arguments concatenated and terminated with CR LF | upstream_code | src/syrpp/pump_conn.py:628-650 |
| The command table maps DIA, PHN, FUN, RAT, VOL, DIR, DIS, CLD, SAF, AL, PF, TRG, BP, OUT, IN, BUZ, VER, RUN and STP to the pump operations | upstream_code | src/syrpp/pump_conn.py:14-34 |
| DATA_RANGE gives phase 1-41, count 1-99, TTL level 0-1, timeout 0-255 and address 0-99 | upstream_code | src/syrpp/pump_conn.py:155-162 |
| set_phase rejects a phase outside DATA_RANGE['phase'] before sending PHN | upstream_code | src/syrpp/pump_conn.py:369-375 |
| get_diameter sends DIA and returns the reply as a float; set_diameter sends DIA with the truncated number | upstream_code | src/syrpp/pump_conn.py:345-350 |
| PHASE_FUNCTION maps RAT/INC/DEC to rate/increment/decrement, STP to stop, LPS/LPE to loop start and loop end, and EVR/BEP to event reset and beep, among others | upstream_code | src/syrpp/pump_conn.py:117-134 |
| PHASE_FUN_DATA lists the functions that carry data: jump phase, loop count, pause number, if phase, event phase and output TTL | upstream_code | src/syrpp/pump_conn.py:136-143 |
| get_function sends FUN and returns the function name; set_function sends FUN with the function code and optional data | upstream_code | src/syrpp/pump_conn.py:377-416 |
| VOLUME_UNITS maps U to microliter aliases and M to milliliter aliases; TIME_UNITS maps M to minute aliases and H to hour aliases | upstream_code | src/syrpp/pump_conn.py:145-153 |
| get_rate sends RAT and splits the reply into a value and the trailing volume and time units; when they are not known units it returns only the value | upstream_code | src/syrpp/pump_conn.py:418-429 |
| set_rate sends RAT with the value and, when both are given, the volume and time unit codes | upstream_code | src/syrpp/pump_conn.py:431-440 |
| PUMP_DIRECTION maps INF to infuse, WDR to withdraw and REV to reverse | upstream_code | src/syrpp/pump_conn.py:70-74 |
| get_direction and set_direction translate through PUMP_DIRECTION | upstream_code | src/syrpp/pump_conn.py:442-448 |
| get_volume sends VOL and splits the trailing two characters into a volume value and a unit | upstream_code | src/syrpp/pump_conn.py:352-360 |
| get_volume_dispensed sends DIS and returns the infused and withdrawn volumes with one unit | upstream_code | src/syrpp/pump_conn.py:579-591 |
| get_status sends an address-only query and maps the prompt character to a status text | upstream_code | src/syrpp/pump_conn.py:601-606 |
| start_program sends RUN and stop_program sends STP | upstream_code | src/syrpp/pump_conn.py:573-577 |
| get_alarm and set_alarm use AL; get_power_fail and set_power_fail use PF | upstream_code | src/syrpp/pump_conn.py:468-489 |
| get_key_beep and set_key_beep use BP; get_buzzer and set_buzzer use BUZ | upstream_code | src/syrpp/pump_conn.py:533-571 |
| The pump address and baud rate are set on the pump manually before use | vendor_doc | README.md:17 |
| The package is tested on the New Era SyringeONE NE-1000 (distributed by Braintree as BS-9000) | vendor_doc | README.md:46 |
| The upstream examples address the pump at 0 | upstream_code | test/config.py:4 |

Limits:

| parameter | command | limit | source | ref |
|---|---|---|---|---|
| diameter (unit 1) | DIA | operator_required: the clone states no numeric diameter range | operator | site-limits.example.json |
| phase (unit 1) | PHN | 1 to 41 | upstream_code | src/syrpp/pump_conn.py:157 |
| phase_function | FUN | only the names that take no data argument (rate, increment, decrement, stop, loop start, loop end, event reset, beep) | upstream_code | src/syrpp/pump_conn.py:117-143 |
| pumping_rate (unit 1) | RAT | operator_required: the clone states no numeric rate range | operator | site-limits.example.json |
| direction | DIR | one of infuse, withdraw, reverse | upstream_code | src/syrpp/pump_conn.py:70-74 |

The diameter and rate bounds are the operator's: the clone's `_float` only truncates a number to four digits and
three decimals (src/syrpp/pump_conn.py:678-696), which is an encoder limit, not a device range. The phase range is
the upstream's own DATA_RANGE['phase'] and `set_phase` checks it before it sends PHN (line 374). The writable
phase functions are exactly the PHASE_FUNCTION names that PHASE_FUN_DATA does not list; the data-bearing
functions (jump, loop, pause, if, event, output) need a number whose range differs per function and is not
stated, so they are not exposed. The pumping rate is sent with `set_rate(address, value)` alone; the pump's
currently configured volume and time units apply, and the driver does not change them.

Safety: the native stop is `stop_program` (STP). It is the `@estop` method and, as
`x-cap.yuanxun-yx.stop_program.v1`, the safe-state action required at R2. The clone is software only and does not
describe an independent hardware e-stop, so `estop_physical_ref` is not set. The device can dispense liquid, so
the driver is R2 even though the task card's floor is R1. The package is model-authored and unreviewed; no
hardware was attached, and the R2 hardware backend is refused until a human sets `reviewed_by`.

Not covered: the pump network scan (`get_avail_address`), the bulk file configuration (`get_config`/`set_config`),
the safe-communications timeout (`get_com_mode`/`set_com_mode`), the TTL input/output pins (`get_ttl_input`,
`set_ttl_output`), the trigger setup (`get_trigger`/`set_trigger`), the dispensed-volume clear
(`clear_dispensed_volume`) and the host serial timeout (`set_timeout`) are not exposed. The clone does not state
the SAF timeout range, the TTL electrical limits or the trigger behavior; exposing them would need sources this
clone does not have. The driver talks to one pump at the `address` backend option (default 0, the address of the
upstream examples), not to a multi-pump network.

Tags: syringe-pump, serial, infuse, withdraw, pump
