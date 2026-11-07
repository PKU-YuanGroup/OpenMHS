# Facts and tags for gh.vision-agh/crazyflie-sim

All facts cite the pinned clone at commit `95002dc7006e7577a80d497f44467a26a96ac896`.  `upstream_code` means a
code or comment line; `vendor_doc` means README text.  The reference file is generated from `facts` in
`driver.py`; this page mirrors those facts for review.

The `evs_gz_utils` directory is a git submodule.  The pinned parent commit records it as a gitlink at
`b8893f58d1eb62b9ca43e63c413264dbd01ca0dd`; the code facts below cite files of that submodule.  The gate reads
them at the gitlink commit from the submodule's own object store (`.git/modules/evs_gz_utils`) and reports that
as the warning `G1.SUBMODULE_SOURCE`; `show_refs.py` prints them the same way.  Before the SDK read submodules
(2026-11-05) these citations failed `G4.REF_MISSING` and the native `G7.NATIVE_NOT_FOUND`.

| fact | source | ref |
|---|---|---|
| The parent repository declares `evs_gz_utils` as a git submodule at path `evs_gz_utils`. | `upstream_code` | `.gitmodules:1-3` |
| `GzStepExample` imports the `ControlWorld` service type from `ros_gz_interfaces.srv`. | `upstream_code` | `evs_gz_utils/evs_gz_utils/gz_step_example.py:8` |
| `GzStepExample` declares a `world_name` ROS parameter and reads its string value from the parameter server. | `upstream_code` | `evs_gz_utils/evs_gz_utils/gz_step_example.py:19-23` |
| `GzStepExample` builds the service name as `/world/<world_name>/control` and creates a `ControlWorld` client for it. | `upstream_code` | `evs_gz_utils/evs_gz_utils/gz_step_example.py:26-27` |
| The stepping launch file bridges the parameterized world control service with type `ros_gz_interfaces/srv/ControlWorld`. | `upstream_code` | `evs_gz_utils/launch/gz_step.launch.py:28-37` |
| `step_simulation` sets `world_control.pause` to `True` on every request; it sets `world_control.step` to `True` for one step and `world_control.multi_step` to the requested count otherwise. | `upstream_code` | `evs_gz_utils/evs_gz_utils/gz_step_example.py:36-44` |
| The constructor calls `step_simulation` with `steps` set to zero under the comment "Ensure the simulation is paused". | `upstream_code` | `evs_gz_utils/evs_gz_utils/gz_step_example.py:32-34` |
| The service call spins without a timeout until the future completes and logs success when a result exists; it logs an error when the result is `None`, does not inspect any response field and returns `None` in both cases. | `upstream_code` | `evs_gz_utils/evs_gz_utils/gz_step_example.py:44-49` |
| The `model_state` node creates an `Odometry` publisher on `/evs/<model_name>/state` and subscribes through a Gazebo node to `/world/<world_name>/pose/info`. | `upstream_code` | `evs_gz_utils/evs_gz_utils/model_state_gazebo.py:41-51` |
| The `model_state` node writes the Gazebo position and orientation into the Odometry pose and derives linear and angular velocity from consecutive samples. | `upstream_code` | `evs_gz_utils/evs_gz_utils/model_state_gazebo.py:55-117` |
| The `model_state` launch file bridges `/clock` as `rosgraph_msgs/msg/Clock` and sets `use_sim_time`. | `upstream_code` | `evs_gz_utils/launch/model_state.launch.py:16-24` |
| The README identifies CrazySim 1.2x at commit `8ad9bb8` as the external simulation component. | `vendor_doc` | `README.md:7` |
| The README states that no ROS is needed to control the CrazyFlie inside CrazySim. | `vendor_doc` | `README.md:76` |

## Scope

The package serves the pinned `GzStepExample` environment-step interface: `cap.world.step.v1` forwards the
catalogue `ticks` count to `step_simulation`, and `x-cap.vision-agh.pause.v1` sends the constructor's zero-step
pause request.  The `/evs/<model_name>/state` Odometry observation and the cflib UDP control example are not
served; the README says the cflib path is how the CrazyFlie is controlled without ROS.  No live ROS or Gazebo
run exists for this package.

## Stop (model review, 2026-11-05)

`step_simulation` returns `None` for an answered and an unanswered ControlWorld call alike and never reads the
response's `success` field, so nothing acknowledges the pause.  The e-stop still sends the zero-step pause request
and then reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held; the pause action no longer claims a safe
state and returns `pause_requested`.  The author's fake raised on a failed call, which the upstream method never
does; it now returns `None` like the upstream.  The gate therefore fails `G6.ESTOP_FAILED`, its only failure
since the submodule is read.

## Tags

`ros2`, `gazebo`, `simulation`, `crazyflie`, `world`, `step`, `pause`, `evs_gz_utils`.
