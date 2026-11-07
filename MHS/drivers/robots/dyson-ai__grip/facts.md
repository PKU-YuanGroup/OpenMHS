# Facts and tags for gh.dyson-ai/grip

Every fact cites its source at commit `eee9f38f86ac636ba4b4ddd1e6b9cfb783f0e203`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). Copy each fact
into `facts = [Fact(text, source=..., ref=...)]` in `driver.py`; the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Grip is a Bullet3-powered prototyping toolbox for manipulation environments, robot arms, grippers and RGBD cameras, with ROS2 integration | vendor_doc | README.md:5 |
| The Env abstract base declares step(action), reset() and render(mode) | upstream_code | grip/environments/base_env.py:8-77 |
| TemplateEnvironment is defined as an Env subclass | upstream_code | grip/environments/template_env.py:32 |
| PickAndPlaceEnvironment is defined as a TemplateEnvironment subclass | upstream_code | grip/environments/pick_and_place_env.py:21 |
| The constructor reads seed (default 77) and seeds Python's random and NumPy's generator with it | upstream_code | grip/environments/template_env.py:34-37 |
| The constructor defaults time_step to 1/240 s and sim_steps to 10 | upstream_code | grip/environments/template_env.py:42-43 |
| The constructor creates a BulletWorld with the configured render mode, real_time_sim False and the time step | upstream_code | grip/environments/template_env.py:59-61 |
| The environment spawns a BulletPandaArmGripper with the configured gripper type and maximum force | upstream_code | grip/environments/template_env.py:99-105 |
| init registers the plane, robot and table, the shoulder camera for the selected modes and the wrist camera for the wrist/all modes | upstream_code | grip/environments/template_env.py:123-131 |
| reset restores the world state, resets the panda and returns obs() | upstream_code | grip/environments/template_env.py:148-155 |
| step applies joint_position_cmd with set_angles and gripper_cmd with control_fingers or apply_gripper_delta_action, advances sim_steps world steps and returns (obs, reward, done, info) | upstream_code | grip/environments/template_env.py:160-185 |
| obs returns each entity's state and, unless camera_mode is none, each camera's rgb, depth, seg and pose | upstream_code | grip/environments/template_env.py:190-204 |
| sample returns seven joint-position values and one gripper value drawn with np.random.randn | upstream_code | grip/environments/template_env.py:206-210 |
| PickAndPlaceEnvironment adds a fixed tray and a free duck object loaded from pybullet_data URDFs | upstream_code | grip/environments/pick_and_place_env.py:38-72 |
| The panda arm controls panda_joint1 through panda_joint7 and defaults gripper_max_force to 12 | upstream_code | grip/robot/panda_robot.py:57-61 |
| PandaGripper.apply_gripper_delta_action takes a delta finger-distance action, adds it to the finger positions and clips each finger to its lower and upper joint limit | upstream_code | grip/robot/panda_gripper.py:54-65 |
| The documented pure-python example runs the pick-and-place environment with python3 -m grip_examples.environments.ex01_pick_and_place | vendor_doc | README.md:19-23 |
| The package metadata requires Python >=3.10,<3.13 | vendor_doc | setup.py:41 |
| The runtime dependencies include NumPy, pybullet, open3d, OpenCV and Matplotlib | vendor_doc | pyproject.toml:10-24 |

Tags (short lowercase keywords): `pybullet`, `manipulation`, `pick-and-place`, `franka`, `simulation`,
`reinforcement-learning`.

## Reviewed adapter behavior

The shared adapter calls the selected raw environment once per requested tick, preserves seven arm joint targets
(radians), and forwards numeric default-Panda gripper displacement (metres). `panda_gripper.py:56` identifies finger
distance; line 58 contains stale phase4 angle text. `panda_robot.py:36-40` falls back from the unsupported phase4 name
to default Panda. The sim factory selects default explicitly and uses DIRECT rendering with non-realtime stepping,
as `template_env.py:59-61` configures. Numeric gripper open/close strings remain outside this published scope because
`panda_gripper.py:84-88` performs additional physics steps for them. No numeric safety bound was invented.

A software safe-state action fences new calls and fails while a native call is active. It only acknowledges idle once
that call returns; safety reset cannot clear the fence while active. This is not a physical native emergency stop.
The lazy sim factory is tested with a controlled constructor only. No real PyBullet environment ran. Constructor
seed/substeps/timestep are copied into instance metadata; reset does not reseed. Owned idle-world cleanup calls
`BulletWorld.disconnect` (`grip/robot/world.py:174-189`) because inherited `Env.close` is a no-op. No L14 physics-tick
receipt extension is used: an MHS tick remains one environment transition, with nominal duration from configuration.

## Model review lifecycle correction

The shared adapter enters an irreversible closing state before cleanup. No safety recovery or new native control is admitted afterward. Cleanup waits for the last in-flight call and executes once; failures are retained without reopening. This is local lifecycle bookkeeping, not an independently confirmed external stop.
