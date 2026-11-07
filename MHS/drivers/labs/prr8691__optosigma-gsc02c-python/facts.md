# Facts and tags for gh.prr8691/optosigma-gsc02c-python

Every fact cites its source at commit `d3403dc83f62fd39a3b437c13076ee676122e760`: `upstream_code` is a code or
comment line of the clone, `vendor_doc` is a text file of the clone. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The controller uses ASCII text commands Q:, M:, A:, G:, D:, H:, L: and !: | upstream_code | optosigma_gsc02c/controller.py:59-68 |
| Q: returns the position/status string and !: returns B for busy or R for ready | upstream_code | optosigma_gsc02c/controller.py:281-298 |
| get_position_pulses returns the controller's commanded pulse coordinate; it is not an independent encoder measurement of the carriage | upstream_code | optosigma_gsc02c/controller.py:328-332 |
| For the OSMS20-85 half-step configuration one pulse is 1 um, so 1000 pulses are 1 mm | upstream_code | optosigma_gsc02c/controller.py:239-243 |
| StageConfig's default software travel range is 0.0 to 85.0 mm | upstream_code | optosigma_gsc02c/controller.py:37-40 |
| StageConfig says to change um_per_pulse, min_position_mm and max_position_mm when the controller or stage is configured differently | upstream_code | optosigma_gsc02c/controller.py:31 |
| set_motion validates start and maximum speed in 1..30000 pulses/s and acceleration time in 0..1000 ms | upstream_code | optosigma_gsc02c/controller.py:393-411 |
| set_max_speed_mm_s converts mm/s to pulses/s and clamps each speed to at least 1 pulse/s | upstream_code | optosigma_gsc02c/controller.py:440-452 |
| The D: command carries the starting speed S, the maximum speed F and the acceleration time R | upstream_code | optosigma_gsc02c/controller.py:377-390 |
| M: prepares a relative movement in signed pulses and G: starts the prepared motion | upstream_code | optosigma_gsc02c/controller.py:504-515 |
| A: prepares an absolute movement in signed pulses and G: starts the prepared motion | upstream_code | optosigma_gsc02c/controller.py:594-605 |
| H: starts the home/origin search and homing waits up to 120 s | upstream_code | optosigma_gsc02c/controller.py:660-667 |
| L: requests a controlled deceleration stop | upstream_code | optosigma_gsc02c/controller.py:669-676 |
| wait_until_idle waits at most 60 s by default | upstream_code | optosigma_gsc02c/controller.py:300-303 |
| The GSC-02C can control two axes, 1 or 2 | upstream_code | optosigma_gsc02c/controller.py:83-84 |
| The README documents the software travel range of the OSMS20-85 configuration as 0 to 85 mm | vendor_doc | README.md:21 |
| The README states that the GSC-02C is an open-loop stepper controller whose reported coordinate is based on commanded pulses, not on encoder feedback | vendor_doc | README.md:124-126 |
| The RS-232 link is 9600 baud, 8 data bits, no parity, 1 stop bit with RTS/CTS handshaking | upstream_code | optosigma_gsc02c/controller.py:139-149 |
| Every command ends with carriage-return plus line-feed | upstream_code | optosigma_gsc02c/controller.py:96-97 |

Limits: every position, relative-distance and speed input is `Limit.operator_required`. The clone states 0 to 85 mm
for its OSMS20-85 stage (README.md:21), but `min_position_mm` and `max_position_mm` are `StageConfig` constructor
defaults and the upstream says to change them for another stage (controller.py:31), so the site supplies the range of
the stage it attached. `site-limits.example.json` shows the overlay; it is an example, not a statement about any unit.
The only sourced numeric bound is the acceleration time, 0 to 1000 ms (controller.py:409).

Safety: the e-stop and the safe-state action `x-cap.prr8691.stop_motion.v1` both call the native `stop()`, which sends
the controller's controlled-deceleration `L:` command (controller.py:669-676). No line of the clone documents an
independent hardware e-stop, so `estop_physical_ref` is not set. The driver is R1; it does not claim the loader
refuses an unreviewed package's hardware backend (that applies only at R2 and R3).

Tags: motion, stage, delay-stage, serial, open-loop
