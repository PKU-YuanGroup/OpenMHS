# Facts and tags for gh.steiva/opentrons-ot2-http-python-wrapper

Every fact cites its source at commit `6bf929c11fe94a03c8b444c70e13be273933f365`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The wrapper's default robot address is 169.254.241.245:31950; OT2_HOST overrides the host | upstream_code | ot2_api.py:11-13 |
| health() sends GET /health and returns the robot server's name, api_version and robot_model without a run | upstream_code | ot2_api.py:149-159 |
| create_run() must be called before movement or aspiration; toggling the lights and homing do not need a run | upstream_code | ot2_api.py:187-189 |
| create_run() stores the run id from the server's data and fills the run command and action endpoints | upstream_code | ot2_api.py:208-212 |
| get_run_info() reads the run list, adopts the current run's id, pipette and labware, and returns the run data | upstream_code | ot2_api.py:226-259 |
| home_robot() posts target robot to the home endpoint | upstream_code | ot2_api.py:261-269 |
| load_pipette() requires a run id, sends the configured PIPETTE name, and stores the returned pipette id | upstream_code | ot2_api.py:298-324 |
| load_labware() requires a run id, accepts a slot in range(1, 12), and stores the returned labware id under the slot name | upstream_code | ot2_api.py:521-572 |
| control_run() accepts play, pause, stop and resume-from-recovery and posts the action to the run actions endpoint | upstream_code | ot2_api.py:360-367 |
| aspirate() requires a run id and a pipette id | upstream_code | ot2_api.py:758 |
| aspirate() takes volume in uL and flow rate in uL/s | upstream_code | ot2_api.py:773-774 |
| dispense() requires a run id and a pipette id | upstream_code | ot2_api.py:841 |
| dispense() takes volume in uL and flow rate in uL/s | upstream_code | ot2_api.py:857-858 |
| The default pipette name is p300_single_gen2 and the caller may change the instance's PIPETTE | vendor_doc | README.md:88 |

Limits:

- `slot_name` (the deck slot input of `x-cap.steiva.load_labware.v1`) is 1 to 11, from the upstream
  `assert slot_name in range(1, 12)` at `ot2_api.py:537`.
- The volume and flow-rate inputs of `cap.fluid.aspirate.v1` and `cap.fluid.dispense.v1` use the catalogue class
  envelopes (0 to 1000 uL, and a non-negative flow rate). The clone states no pipette capacity or flow-rate range of
  its own; the installed pipette is a configuration choice (`ot2_api.py:87`), not a driver-invented bound.
- No driver limit needs an operator overlay, so there is no `site-limits.example.json`.

Safety: the clone documents no separate hardware stop. The native stop is the run action `stop` sent through
`control_run("stop")` (`ot2_api.py:360-367`); it is both the `@estop` method and the `safe_state=True` action
`x-cap.steiva.stop_run.v1`. `control_run()` is decorated with `require_ids(["run_id"])` (`ot2_api.py:360`), so on a
real robot the run stop needs a run created first; no command of this wrapper can move or aspirate without a run
(`ot2_api.py:187-189`). The hardware path was never run.

Not exposed: `move_to_coordinates`, `move_to_well`, `move_relative`, `pick_up_tip`, `drop_tip`, `blow_out`,
`aspirate_in_place`, `dispense_in_place`, `move_labware`, `retract_axis` and the labware-offset methods. No text of the
clone states the travel envelope those motions need, and the card's `writes` list is empty. The fluid actions also
omit the optional `flow_rate` because the clone states no range for it; the upstream default of 25 uL/s then applies
(`ot2_api.py:765`, `ot2_api.py:848`).

Tags: liquid-handler, pipette, robot, http
