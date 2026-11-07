# Facts and tags for gh.uwo-fast/openreactor

Every fact cites its source at commit `ade88dc17e1c06775ddcb1cdc9ca6c40e4083db0`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Start-up sends the safe state (setpoints to zero, then open-loop duty to zero) before arming the command watchdog and setting closed-loop mode | upstream_code | src/openreactor/rlht.py:290-320 |
| The safe state is always SET_SETPOINTS(0, 0) and then SET_OPEN_DUTY(0, 0), both sent even if the first fails | upstream_code | src/openreactor/rlht.py:399-408 |
| An RLHT channel's setpoint is in degC to the slice's tenth of a degree: from 0 up to the channel's max_setpoint, or 3276.7 degC when the config sets none | vendor_doc | README.md:108-111 |
| status() reports the slice state, version, capabilities, mode, e-stop flag, both outputs, the watchdog and the desired setpoints | upstream_code | src/openreactor/rlht.py:410-437 |
| Each output status carries a temperature and setpoint in degC (from tenths) and an on-time and period in ms | upstream_code | src/openreactor/rlht.py:146-171 |
| set_setpoint(output, deci) takes tenths of a degree and updates the desired setpoints only after the send | upstream_code | src/openreactor/rlht.py:439-467 |
| An e-stop pressed on a slice sends stop-all, and its setpoints stay at zero until the operator sets them again | vendor_doc | README.md:96-100 |
| The heater and motor boards run their own control loops and stop their outputs if they lose contact with the Pi | vendor_doc | README.md:16-17 |
| An RLHT heater slice has two heater outputs, each with an onboard PID on one of two thermocouples | vendor_doc | examples/openreactor.toml:38-39 |

Limits: each setpoint write is bounded to 0 to 3276.7 Cel, the highest setpoint the slice takes when the config sets
no lower `max_setpoint` (`README.md:108-111`). A site that configures a lower `max_setpoint` narrows that range with
`site-limits.example.json`, which may only narrow.

Safety: the e-stop and the `safe_state=True` action `x-cap.uwo-fast.stop_heating.v1` both call the native
`RlhtSlice.send_safe()`: setpoints zero, then open-loop duty zero (`src/openreactor/rlht.py:399-408`). No text file of
the clone documents an independent hardware e-stop that a driver can cite, so `estop_physical_ref` is not set; the
safe-state action satisfies SAFE-045 for this R2 hardware driver. The slice's own e-stop, when pressed, is handled by
the upstream controller and sends stop-all (`README.md:96-100`).

Tags: reactor, heater, thermal, rlht, i2c
