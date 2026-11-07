# Facts and tags for gh.wetenschaap/pymista

Every fact cites the clone at commit `b30040a192c329b6144a120f0dfea2ca68060760`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README states that units of distance are always given in micrometres | vendor_doc | README.md:21 |
| ZaberStage sets the Zaber library length unit to LENGTH_MICROMETRES | upstream_code | pymista/zaber.py:14 |
| ZaberStage.connectStage opens the Zaber ASCII serial connection, enables alerts and builds one axis from every detected device | upstream_code | pymista/zaber.py:17-33 |
| ZaberStage.move_absolute sends every axis its target position in the stage unit and, when wait_until_idle is true, waits until all axes are idle | upstream_code | pymista/zaber.py:35-39 |
| ZaberStage.move_relative sends every axis its displacement in the stage unit and, when wait_until_idle is true, waits until all axes are idle | upstream_code | pymista/zaber.py:41-45 |
| ZaberStage.get_position reads every axis position in the stage unit | upstream_code | pymista/zaber.py:47-48 |
| UniversalStage.home homes every axis that is not homed, or every axis when force is true | upstream_code | pymista/universal.py:13-19 |
| UniversalStage.stop calls stop() on every axis | upstream_code | pymista/universal.py:84-86 |
| UniversalStage.is_moving is true when any axis reports is_busy | upstream_code | pymista/universal.py:94-96 |
| UniversalStage.is_homed returns one entry per axis | upstream_code | pymista/universal.py:21-25 |
| UniversalStage.close closes the stage connection | upstream_code | pymista/universal.py:27-31 |
| The README says a stage typically has 2 or 3 axes (x, y, z) | vendor_doc | README.md:68 |
| The clone provides DummyStage as a fake stage for troubleshooting | upstream_code | pymista/dummy.py:6-9 |

Limits: both motion inputs (`positions` of `x-cap.wetenschaap.move_absolute.v1`, `displacements` of
`x-cap.wetenschaap.move_relative.v1`) are `Limit.operator_required`.  No text file of the clone states the travel
range of the stage or of the stage mounted on a controller; `UniversalStage.get_bounds` reads `limit.min` and
`limit.max` from the device settings (pymista/universal.py:98-101), and the mounted stage is configured at the site.
`site-limits.example.json` shows the overlay; its numbers are placeholders for one bench, not a statement about any
device.  No numeric write is exposed.

Safety: the e-stop and the safe-state action `cap.motion.stop.v1` both call the native `stop()`
(pymista/universal.py:84-86), which calls `stop()` on every axis.  No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set.  The driver is R1, so SAFE-045 does not require a hardware stop
reference or a safe-state action; the stop class is declared as the safe-state action anyway.

Mock path: `fake.py` is an in-memory `FakeZaberStage` with the two-axis surface the driver calls.  The clone's
DummyStage is not used because it is a different class with four arbitrary axes (pymista/dummy.py:6-9,
pymista/universal.py:8-11) and the gate's G7 checks the fake against `ZaberStage`.

Tags: stage, motion, zaber, microscopy, micrometre
