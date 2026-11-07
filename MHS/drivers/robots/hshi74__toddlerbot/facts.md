# Facts and tags for gh.hshi74/toddlerbot

Every fact cites its source at commit `e337f3b177b4b53abff70b31d1695a7b66cc6d2e`: `vendor_doc` (a text file of the
clone) or `upstream_code` (code or XML of the clone). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

The package serves one device: the card's `models[0]`, the ToddlerBot 2XC MJCF scene
(`toddlerbot/descriptions/toddlerbot_2xc/scene.xml`), which includes the robot model
`toddlerbot/descriptions/toddlerbot_2xc/toddlerbot_2xc.xml`. The scene and its 66 MB asset directory are read from
the read-only clone at the pinned commit; they are never copied into this package and never imported as code. The fake
parses the two XML files to derive the model shape.

| fact | source | ref |
|---|---|---|
| ToddlerBot is a low-cost, open-source humanoid robot platform built for scalable policy learning and research in robotics and AI | vendor_doc | README.md:12 |
| The upstream package is fully pip-installable on Python 3.10 or newer | vendor_doc | README.md:16 |
| The upstream requires Python 3.10 or newer | vendor_doc | pyproject.toml:14 |
| The upstream pins mujoco 3.3.4 and mujoco-mjx 3.3.4 | vendor_doc | pyproject.toml:36-37 |
| The card's primary scene is the MJCF model toddlerbot_2xc_scene and includes the robot model toddlerbot_2xc.xml | upstream_code | toddlerbot/descriptions/toddlerbot_2xc/scene.xml:2-3 |
| The scene sets a statistic center and extent for the camera and adds a floor plane, four trackcom cameras and explicit floor contact pairs for the torso, head, pelvis and limb collision geoms | upstream_code | toddlerbot/descriptions/toddlerbot_2xc/scene.xml:4-50 |
| The robot model compiles in radians with the mesh directory assets and autolimits enabled | upstream_code | toddlerbot/descriptions/toddlerbot_2xc/toddlerbot_2xc.xml:3 |
| The main default class sets the motor ctrlrange to -10 10 | upstream_code | toddlerbot/descriptions/toddlerbot_2xc/toddlerbot_2xc.xml:31 |
| The actuator block declares 30 motors, from neck_yaw_drive through right_wrist_roll, one per actuated joint, and none of them overrides the main default class | upstream_code | toddlerbot/descriptions/toddlerbot_2xc/toddlerbot_2xc.xml:562-593 |
| The torso body carries the free joint torso_freejoint, so the robot base is not actuated | upstream_code | toddlerbot/descriptions/toddlerbot_2xc/toddlerbot_2xc.xml:34-35 |
| The environment base class is MJXEnv, a brax PipelineEnv subclass | upstream_code | toddlerbot/locomotion/mjx_env.py:315 |
| The environment loads its MJCF with brax.io.mjcf and replaces the model's opt.timestep and opt.solver with cfg.sim.timestep and cfg.sim.solver | upstream_code | toddlerbot/locomotion/mjx_env.py:484-491 |
| The card's first entry symbol is CartwheelEnv, registered with env_name cartwheel | upstream_code | toddlerbot/locomotion/cartwheel_env.py:18 |
| The cartwheel environment samples a zero command because the motion reference supplies the motion | upstream_code | toddlerbot/locomotion/cartwheel_env.py:44-48 |
| The default simulation config sets a 0.005 s time step and the Newton solver | upstream_code | toddlerbot/locomotion/mjx_config.py:21-22 |

## The card's entry symbols

The card lists five MJX training environments. This package uses the first, `CartwheelEnv`, as its `native` symbol and
serves the raw MuJoCo scene they are built from, not an environment. The others are named for the reviewer:

| entry symbol | file:line |
|---|---|
| `toddlerbot.locomotion.cartwheel_env:CartwheelEnv` | toddlerbot/locomotion/cartwheel_env.py:18 |
| `toddlerbot.locomotion.climb_down_box_env:ClimbDownBoxEnv` | toddlerbot/locomotion/climb_down_box_env.py:14 |
| `toddlerbot.locomotion.climb_up_box_env:ClimbUpBoxEnv` | toddlerbot/locomotion/climb_up_box_env.py:12 |
| `toddlerbot.locomotion.climb_wall_env:ClimbWallEnv` | toddlerbot/locomotion/climb_wall_env.py:13 |
| `toddlerbot.locomotion.crawl_down_stairs_env:CrawlDownStairsEnv` | toddlerbot/locomotion/crawl_down_stairs_env.py:12 |

The scene `scene.xml` is `models[0]` of the card. It is the plain MuJoCo scene, not one of the `scene_mjx_*.xml`
variants: `MJXEnv` adds its own terrain and uses `scene_mjx.xml` (mjx_env.py:456-484), while this driver loads the scene
file as it stands.

## Limits

The driver declares no `Limit` of its own. The only actuation bound is the model's per-actuator `ctrlrange`, which the
MuJoCo bridge derives from the MJCF at load time: the main default class sets `<motor ctrlrange="-10 10"/>`
(toddlerbot_2xc.xml:31) and the 30 motors of the actuator block do not override it (toddlerbot_2xc.xml:562-593). The
derived bound is published by the bridge as the `action.ctrl` limits of `cap.world.step.v1`; no operator-required bound
is needed because the model file is the system of record and the device is simulated. `ticks` is bounded by the family's
`max_ticks` (10000 by default), and the reset input `seed` is metadata of the bridge and does not seed a random draw.

## Fidelity contract

`driver.py` publishes the bridge-derived contract: engine `mujoco:toddlerbot_2xc_scene`, level F1, determinism
`seeded` with `seed_control` `none`, `realtime_factor` 0, clock `lockstep`, reset `full`, and snapshot/restore offered
by the bridge. The time step is the one the loaded model states (the bridge reads `model.opt.timestep`); the scene sets
no `<option timestep>` and the upstream environment overrides the value with `cfg.sim.timestep` (mjx_env.py:487), which
this package does not do. The gaps state that the fake is a stand-in for the MuJoCo library, not the engine, that no
mesh or constraint is resolved, and that the upstream environment's motion reference, observation, reward and episode
logic are not exposed.

## Safety

Simulated R0 device. There is no hardware backend and no physical stop path. The e-stop is the runtime's software latch:
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the integration state stays
readable. The native `cap.world.step` and `cap.world.reset` are served by the MuJoCo bridge.

## Licence of the model assets

The repository licence is MIT (LICENSE:1-2, README.md:165). The README also says the ToddlerBot design, including the
STL files, is released under CC BY-NC-SA (README.md:167). This package copies no model or asset: `model_path` points
into the read-only clone and the driver loads the file there, so the package adds no copy of the restricted design
files.

## Tags

humanoid, locomotion, mujoco, simulation, toddlerbot, world, scene
