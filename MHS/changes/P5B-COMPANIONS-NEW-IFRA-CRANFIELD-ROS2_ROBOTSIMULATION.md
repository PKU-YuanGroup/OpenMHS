# P5B companions, new fetches: ifra-cranfield/ros2_robotsimulation stays blocked

The integrator did not apply this unit's package files. Codex's package decision was not accept (`gh.ifra-cranfield/ros2_robotsimulation` decision `block`). The package directory stays at snapshot-6. The sections below are the unit's own account.


The Foxy lock companions for this package are present. A controller switch with the E4 list-element read-back does not stop the arm on gazebo_ros2_control 0.1.1, so the package stays blocked. The round-1 review raised the existing command surface from R0 to R2. `driver.py:176` now declares `risk = "R2"`, and `reference.json` and `REFERENCE.md` were regenerated from that declaration. No re-enable was added.

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the external unit `ext-p5b-companions-new--ifra-cranfield__ros2_robotsimulation`. `reviewed_by` stays null. No hardware, Gazebo, ROS graph or human review was run. The gate evidence is fake `contract_checked` only, and this package does not pass the gate.

## What was decided

User decision 2 of `user-decisions-20261105b.json` allowed the Foxy clones. `work/companions/LOCK.json` already lists them, both profile `ros2-foxy-gazebo11`, `needed_by` already `gh.ifra-cranfield/ros2_robotsimulation`:

- `ros-controls__ros2_control@0.11.0`, commit `393ac4a71001103f6a0c4d9f5c2803b981678d8a`
- `ros-controls__gazebo_ros2_control@0.1.1`, commit `0ab18b56f7fbdd05fe1ad8739ada21870707c5a7`

No `LOCK.json` edit and no registry override. The class E triage row in `drafts/retriage-result.json` (`robots/ifra-cranfield__ros2_robotsimulation`) has no separate verifier verdict; it is under `packages`, not `candidates`. The row's route was followed and then refused, for the reason below.

The package keeps `authored_by` (`deepseek-v4.1-flash:1017`, run `ros-wave-c-057`). `RESULT.json` notes gained a MODEL REVIEW paragraph, then a second correction paragraph after the round-1 review. The author's text before the first MODEL REVIEW paragraph was shortened at a sentence boundary, ending ` [...]`, so the notes stay within 8,000 characters. The Claude review paragraph and the first Grok review paragraph were not edited. The unshortened `RESULT.json` is in this unit's `originals/`.

## Why the switch is not a stop

The triage asked for `/controller_manager/switch_controller` deactivating one arm trajectory controller, confirmed by `/controller_manager/list_controllers` with that one element in state `inactive`. Foxy's list service does return `ControllerState[] controller` (`controller_manager_msgs/srv/ListControllers.srv:5`), and the callback copies `name` and `state` from `get_current_state().label()` (`controller_manager/src/controller_manager.cpp:852-856`). The inactive label is the string `inactive` (`controller_interface/include/controller_interface/controller_state_names.hpp:28`). That label is the lifecycle state, not a held joint.

`GazeboRosControlPrivate::Update` calls `controller_manager_->write()` on every simulation iteration (`gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:373-381`). The manager node name is `controller_manager` (`:313-318`). `GazeboSystem::write` calls `SetPosition`, `SetVelocity` or `SetForce` only while the matching control-method bit is set (`gazebo_ros2_control/src/gazebo_system.cpp:581-595`). Registering a command interface sets that bit (`:241-254`).

The IRB120 `ros2_control` block exports position and velocity on each arm joint (`ABBRobots/IRB120/irb120_ros2_gazebo/urdf/irb120_ros2control.xacro:92-99`). `irb120_controller` is a `joint_trajectory_controller/JointTrajectoryController` and its parameters claim position only (`config/irb120_controller.yaml:5-6` and `:35-36`). Each other arm controller yaml in the clone lists position the same way (for example `PandaRobot/panda_ros2_gazebo/config/panda_controller.yaml:65-66`). Scoping the package to one robot does not avoid the hardware path below.

`perform_command_mode_switch` clears a stopped position interface with `joint_control_methods_ &= (VELOCITY & EFFORT)` (`gazebo_system.cpp:453-458`). `ControlMethod_` is `NONE = 0`, `POSITION = 1<<0`, `VELOCITY = 1<<1`, `EFFORT = 1<<2` (`include/gazebo_ros2_control/gazebo_system_interface.hpp:78-81`), so `VELOCITY & EFFORT` is 0 and the assignment clears every bit. The velocity stop uses `POSITION & EFFORT` and the effort stop uses `POSITION & VELOCITY` (`:460-469`); both masks are 0 as well. `ControllerManager::manage_switch` performs that mode switch and then calls `stop_controllers` (`controller_manager/src/controller_manager.cpp:663-672`). `stop_controllers` then calls `deactivate` and `release_interfaces` (`:705-708`). `ControllerInterface::deactivate` stores `inactive` only when `on_deactivate` returns SUCCESS (`controller_interface/src/controller_interface.cpp:94-96`). The ERROR branch stores `finalized` (`:98-101`). The FAILURE branch leaves the state unchanged (`:103-104`). None of those branches writes a joint command. `release_interfaces` only clears the loan vectors (`:162-166`). The inactive label an E4 read would see is the success path, and that path writes no joint command.

`command_interface_configuration` is pure virtual (`controller_interface/include/controller_interface/controller_interface.hpp:78`). The names on the stop list come from the `JointTrajectoryController` plugin, which is `ros-foxy-ros2-controllers`. `LOCK.json` has no Foxy `ros2_controllers` clone, and this unit must not fetch one. A switch that stops the position interfaces named in the yaml therefore drops Gazebo's position and velocity commands instead of leaving a held setpoint. `state == inactive` is not a stop. This is the same class of refusal as the effort-controller finding for panda_gz_moveit2: deactivation does not leave the simulator holding a stopped command.

No re-enable is declared. The plugin that would show whether a stored trajectory survives deactivation is not in the fetched companions, so a later start could resume a command this package cannot clear first (SAFE-042, `MHS/handoff/REVIEW.md` item 5).

Foxy `SwitchController` requests `start_controllers` and `stop_controllers`, with `STRICT = 2` (`controller_manager_msgs/srv/SwitchController.srv:22-27`). Those are not the Humble `activate_controllers` / `deactivate_controllers` fields used by `blackcoffeerobotics/bcr_arm`.

MoveIt's cancel still calls `move_group_interface.stop()` and accepts with no stopped result (`ros2_actions/scripts/moveJ_action.cpp:117-128`). That remains not an acknowledged stop.

No Foxy `gazebo_ros` pause companion is fetched. `ros-simulation__gazebo_ros_pkgs@3.9.0` is profile `ros2-humble-gazebo11`, and the package's README names ROS 2 Foxy (`README.md:52`, install lines `:176`, `:180`, `:185-187`). A distro mismatch stays blocked (`REVIEW.md` item 13). The E1 stall route is not used.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/ifra-cranfield__ros2_robotsimulation --backend fake --no-report --companions-root $PWD/work/companions` on 2026-11-05, run twice after the risk change. Both failed G6 (`G6.ESTOP_FAILED`, `MHS.SAFETY.SAFE_STATE_UNREACHED`, latch engaged) and G8 (`TCAP-003` on `/MoveG`, and `SAFE-028`). `SAFE-028` is required once `risk_class` is R1, R2 or R3 (`mhs/conformance/tests_core.py`, `_estop_reach_required`). The stable digest of both runs is `sha256:cf600721558a8ceebac2a6e6e56f55aec1a839e30f72f8b30b2c6203e2e98121`. That replaces the previous blocked digest `sha256:9c985513d654c092fc6fb14b0c3f97eb506328eaac1b1bdc06408266fc706c2d`, because `driver.py:176` now declares `risk = "R2"`. Blocked status does not leave the existing arm and gripper commands at R0 (`REVIEW.md` item 12, `CODEX-HANDOFF.md` section 2 rule 13). A stock fake endpoint advertises `risk_class` R2 and completes `/MoveJ` with `MoveJ:SUCCESS`.

## Not taken from the stopped attempts

`development/p5b-companions-new/project` does not exist. `development/ext-p5b-companions-new.fast-stopped/project` has no file under this package, the companion overrides, or a new change record whose sha256 differs from that tree's `base-manifest.json`. Nothing was copied from either attempt.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

No package file and no shared edit from this unit was merged. This change record is kept so the exclusion is visible.

Left out:

- MHS/drivers/robots/ifra-cranfield__ros2_robotsimulation/RESULT.json: package decision is not accept
- MHS/drivers/robots/ifra-cranfield__ros2_robotsimulation/driver.py: package decision is not accept

Codex package decisions that were not accept:

- `gh.ifra-cranfield/ros2_robotsimulation`: decision `block`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
