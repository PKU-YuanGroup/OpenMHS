OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of an Anthropic research preview.

# Facts and tags for gh.hanshangzhu/collab_qrc

Every fact cites the pinned clone at commit `f9e6998d2f7b086f60810b35683791c8c6a41d87`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name README text.
The same facts are declared in `driver.py`; the reference files are generated from
the driver, not from this page.

## Shape and scope

The repository is a ROS 2 Humble multi-robot exploration stack for Unitree Go2W
(wheeled-legged) and Go2 (walking) quadrupeds. Its MuJoCo path is the
`mujoco_ros2_control` node started by the base launch, with the selected MJCF
scene passed as `robot_model_path` (`single_go2w_mujoco_cfpa2.launch.py:281-291`).
The VLM launch selects `go2_gazebo_sim/mujoco/vlm_exploration_scene.xml` when no
override is supplied (`single_vlm_mujoco_far.launch.py:142-146`).

DEVIATION FROM THE CARD: the card names `RosDriver`, but its own candidate
classes are `cap.world.reset.v1`, `cap.world.step.v1` and `cap.world.seed.v1`,
its `models` list is a set of MJCF scenes, and its mock strategy prefers the
upstream simulator. The executable environment-step interface is the MuJoCo
model, not a Python class in the clone. This package therefore serves the
launch-bound MJCF scene through `MujocoDriver`. The production path is the
official MuJoCo engine loading the same file; the package has no Python native
and does not import or start ROS.

The model is read from the read-only clone in place. It is not copied into the
package and is not modified. Only the VLM exploration scene is served; the other
MJCF scenes, the ROS 2 control and sensor graph, Nav2, SLAM and the real-robot
ROS 1 deployment are outside this package.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes heterogeneous multi-robot autonomy on Unitree Go2W (wheeled-legged) and Go2 (walking) quadrupeds with ROS 2 Humble, a MuJoCo simulation and a native ROS 1 Noetic deployment on the real Go2's Jetson Orin NX. | vendor_doc | README.md:3 |
| The README architecture diagram starts from `MuJoCo ops2 (500 Hz)` or a real or HIL Mid-360 LiDAR, followed by `mujoco_sensor_bridge` or `livox_ros_driver2`. | vendor_doc | README.md:20-21 |
| The README lists `mujoco_ros2_control/` as the DFKI MuJoCo ros2_control hardware interface. | vendor_doc | README.md:157 |
| The VLM MuJoCo launch defaults `mujoco_model_path` to `go2_gazebo_sim/mujoco/vlm_exploration_scene.xml` when the argument is empty. | upstream_code | src/vlm_explorer/launch/single_vlm_mujoco_far.launch.py:142-146 |
| The base MuJoCo launch starts the `mujoco_ros2_control` node with `robot_model_path` set to the selected MJCF, `simulation_frequency` 500.0 and `real_time_factor` 1.0. | upstream_code | src/go2w/go2_gazebo_sim/launch/single_go2w_mujoco_cfpa2.launch.py:281-291 |
| The scene is an MJCF model named `vlm_exploration_scene` that compiles angles in radians and resolves mesh files from the assets directory. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:1-2 |
| The scene sets option timestep 0.002 s, gravity `0 0 -9.81`, the `implicitfast` integrator and elliptic friction cones. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:4-5 |
| The Go2W base body starts at `pos 4.0 0 0.6` and carries a free joint named `root`. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:158-161 |
| The base body carries the free joint `root` and each of the four legs carries hip, thigh, calf and foot joints, 16 named leg and foot joints in total. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:161-349 |
| The `go2` default class sets the motor `ctrlrange` to `-23.7 23.7`, the `knee` class overrides it to `-45.43 45.43`, and the abduction/front_hip/back_hip/knee classes bound the leg joint ranges. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:18-36 |
| The actuator block has 12 `motor` actuators on the leg joints and four `velocity` actuators on the foot joints; each velocity actuator declares `ctrlrange -15 15`. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:361-381 |
| The scene declares accelerometer, gyro, foot touch and base frame sensors. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:384-402 |
| The `knee` default class sets the joint range `-2.7227 -0.83776`. | upstream_code | src/go2w/go2_gazebo_sim/mujoco/vlm_exploration_scene.xml:33-36 |
| The README's License section says: 'Research project. Contact maintainers for licensing.' | vendor_doc | README.md:183-185 |
| The `go2_gazebo_sim` package manifest declares the MIT licence. | upstream_code | src/go2w/go2_gazebo_sim/package.xml:4-8 |

## Contract

`cap.world.step.v1` takes `{ticks, action: {ctrl: [16 numbers]}}`. The bridge
checks each `ctrl` element against the model's `actuator_ctrlrange` before
writing `data.ctrl`, then runs `mj_step` `ticks` times. The selected scene
declares `ctrlrange` through its default `go2`/`knee` classes and its four
`velocity` elements, so the reference shows the per-element bounds

```
[-23.7, -23.7, -45.43, ... -15.0] .. [23.7, 23.7, 45.43, ... 15.0]
```

and the driver does not invent a bound outside the model. `cap.world.reset.v1`
restores the model defaults with `mj_resetData` + `mj_forward`.

The bridge publishes the world state `{time_ms, qpos, qvel, ctrl, tick,
timestep_ms, seed, native_checkpoint}`. The free joint and 16 leg and foot joints give
23 `qpos` entries and 22 `qvel` entries; the 12 motor and four velocity
actuators give 16 `ctrl` entries. The option timestep 0.002 s is read from the
model.

`cap.world.seed.v1` is not served: the `MujocoBridge` exposes only
`cap.world.step.v1` and `cap.world.reset.v1`. The reset accepts the class's seed
field but MuJoCo's `mj_resetData` does not use a seed.

## Fidelity

The fake backend is a package-local stand-in for the `mujoco` module, not the
MuJoCo engine. It parses the same MJCF and its includes for the model shape,
the default pose qpos0, actuator names, kinds and ctrlranges, then advances a
placeholder joint state: each motor's force `gear * ctrl` and each velocity
actuator's force `kv * (ctrl - qvel)` accelerates only its own joint against a
placeholder unit inertia. Reset restores qpos0 (the base at `4.0 0 0.6` with an
identity quaternion), as `mj_resetData` does. (Model review, 2026-11-05: the
stand-in used to zero every qpos entry, including the quaternion, and to treat
every control value as a joint velocity.) It loads no mesh, texture, inertia or
contact model and resolves no friction, tendon, equality, joint-limit or force
constraint. Its snapshot uses the bridge's basic profile
(time, `qpos`, `qvel`, `act`, `ctrl`) and does not preserve warm-start or derived
quantities. These differences are listed in the driver's `fidelity_by_backend`
fake gaps and in `RESULT.json`.

The real `sim` backend is the official `mujoco` module loading the same file; it
was not installed or run here. No trajectory was compared with the engine and no
physical robot is modelled. The deployed fake is F0; the real engine path is
described as F1 with the model's timestep. The ROS 2 control and sensor graph is
NOT COVERED. The real engine's reset restores qpos0, where every leg joint is
at 0, outside the calf joints' `-2.7227..-0.83776` range, and the scene has no
keyframe; the twelve motors take raw torques with no controller.

## Licence

The README's License section says "Research project. Contact maintainers for
licensing." (`README.md:183-185`), while the `go2_gazebo_sim` manifest declares
MIT (`src/go2w/go2_gazebo_sim/package.xml:4-8`); the card says NOASSERTION and
`publish_review: required`, so the owner decides before publication.

## Safety

The served device is simulated at R0: the only capabilities are `world.step` and
`world.reset`, whose effects are confined to simulated state (MHS-004 SAFE-006).
No mobile-base motion, actuator torque, camera, LiDAR, IMU, physical stop or
hardware command is exposed. The runtime's software e-stop latch blocks further
step and reset calls; it is not a hardware emergency stop and makes no physical
safety claim. The model's free base, contact and actuator force limits are not
validated here.

## Tags

`mujoco`, `mjcf`, `simulation`, `quadruped`, `go2w`, `go2`, `ros2`, `multi-robot`
