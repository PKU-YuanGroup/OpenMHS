# Facts and tags for gh.basf/pytem

Every fact cites its source at commit `d2b2800329524c205c266fe72a35c7fd477cc735`: `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The stage position is kept in micrometres for x, y and z and in degrees for alpha and beta | upstream_code | pyTEM/Interface.py:87-91 |
| A stage x move is refused when the absolute x value exceeds 1000 um | upstream_code | pyTEM/lib/mixins/StageMixin.py:141-145 |
| A stage y move is refused when the absolute y value exceeds 1000 um | upstream_code | pyTEM/lib/mixins/StageMixin.py:155-159 |
| A stage z move is refused when the absolute z value exceeds 375 um | upstream_code | pyTEM/lib/mixins/StageMixin.py:169-173 |
| A stage alpha tilt is refused when the absolute alpha value exceeds 80 degrees | upstream_code | pyTEM/lib/mixins/StageMixin.py:183-187 |
| A stage beta tilt is refused when the absolute beta value exceeds 29.7 degrees | upstream_code | pyTEM/lib/mixins/StageMixin.py:203-207 |
| The stage speed is a fraction of the standard speed, clamped to 0.00032 at the low end and 1.0 at the high end | upstream_code | pyTEM/lib/mixins/StageMixin.py:85-93 |
| reset_stage_position sets x, y, z, alpha and beta to zero | upstream_code | pyTEM/lib/mixins/StageMixin.py:396-402 |
| stage_is_home compares every axis against the home position with a default threshold of 0.1 | upstream_code | pyTEM/lib/mixins/StageMixin.py:404-418 |
| make_safe closes the column valve, blanks the beam and inserts the fluorescent screen | upstream_code | pyTEM/Interface.py:107-114 |
| get_column_vacuum and get_accelerator_vacuum return a log value or a pressure in pascals | upstream_code | pyTEM/lib/mixins/VacuumMixin.py:61-97 |
| The column valve position is 'open' or 'closed' | upstream_code | pyTEM/lib/mixins/VacuumMixin.py:117-126 |
| The fluorescent screen position is 'retracted' or 'inserted' | upstream_code | pyTEM/lib/mixins/ScreenMixin.py:21-34 |
| beam_is_blank reports whether the beam is blanked | upstream_code | pyTEM/lib/mixins/BeamBlankerMixin.py:20-27 |
| The instrument mode is TEM or STEM | upstream_code | pyTEM/lib/mixins/ModeMixin.py:23-37 |
| The projection mode is imaging or diffraction | upstream_code | pyTEM/lib/mixins/ModeMixin.py:64-76 |
| The illumination mode is nanoprobe or microprobe | upstream_code | pyTEM/lib/mixins/ModeMixin.py:139-153 |

Limits: every stage axis is bounded by a check in `StageMixin.set_stage_position`: x and y to -1000..1000 um
(`StageMixin.py:141-159`), z to -375..375 um (`StageMixin.py:169-173`), alpha to -80..80 degrees
(`StageMixin.py:183-187`) and beta to -29.7..29.7 degrees (`StageMixin.py:203-207`). The limits in `driver.py` cite
the single code line that holds each bound. The clone writes the x and y ranges as "-1,000" with a thousands comma on
`StageMixin.py:142,156`; the gate's number reader splits that token, so the two negative limits produce
`G4.REF_VALUE` warnings that the notes of `RESULT.json` list.

Safety: `Interface.make_safe` closes the column valve, blanks the beam and inserts the fluorescent screen
(`Interface.py:107-114`). It is both the `@estop` method and the safe-state action
`x-cap.basf.enter_safe_state.v1`. No text file of the clone states an independent physical e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R3 hardware driver. The loader
refuses the hardware backend while `reviewed_by` is null.

Tags: tem, electron-microscope, stage, vacuum, beam-blanker
