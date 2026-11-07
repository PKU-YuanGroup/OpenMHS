# Facts and tags for gh.google-deepmind/mujoco_playground

Every fact cites its source at commit `d59156e099a8785dd58fbce2e25a6ee1f7b5800c`: `vendor_doc` (a text file of the
clone) or `upstream_code` (code or XML of the clone). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

The package serves one device: the card's `models[0]`, the dm_control acrobot MJCF
(`mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml`). The model file is read from the read-only clone at the
pinned commit and is never copied into this package or imported as code.

| fact | source | ref |
|---|---|---|
| The repository is a suite of GPU-accelerated environments for robot learning and sim-to-real, built with MuJoCo MJX | vendor_doc | README.md:7 |
| The suite includes the classic control environments from dm_control | vendor_doc | README.md:11 |
| The dm_control suite is a re-implementation of the DeepMind Control Suite using MJX | vendor_doc | mujoco_playground/_src/dm_control_suite/README.md:3 |
| acrobot-swingup is one of the implemented dm_control suite environments | vendor_doc | mujoco_playground/_src/dm_control_suite/README.md:12 |
| The acrobot environment class is Balance, a subclass of mjx_env.MjxEnv | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:45 |
| The acrobot default config sets ctrl_dt=0.01, sim_dt=0.01, episode_length=1000 and action_repeat=1 | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:32-42 |
| The environment reads the acrobot MJCF text, builds mujoco.MjModel.from_xml_string with the suite assets and writes sim_dt to model.opt.timestep | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:62-67 |
| The suite assets are all files of the xmls/common directory, read as bytes | upstream_code | mujoco_playground/_src/dm_control_suite/common.py:21-29 |
| The acrobot MJCF is a model named acrobot that includes the visual, skybox and materials files | upstream_code | mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml:8-11 |
| The MJCF default sets joint damping to .05 and capsule geoms of mass 1 | upstream_code | mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml:13-16 |
| The MJCF sets timestep 0.01 s, iterations 2 and ls_iterations 4, with constraint and eulerdamp disabled | upstream_code | mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml:18-20 |
| The model has a floor plane, a target site at z=4 and fixed and lookat cameras | upstream_code | mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml:22-27 |
| The model has two hinge joints named shoulder and elbow, a capsule arm for each, and a tip site at the far end of the lower arm | upstream_code | mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml:28-37 |
| The model has one motor actuator on the elbow joint with gear 2 and ctrlrange -1 to 1 | upstream_code | mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml:41 |
| The environment's reset draws every qpos value uniformly from -pi to pi | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:80-85 |
| The environment steps through mjx_env.step with n_substeps and reports done when qpos or qvel contains NaN | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:104-110 |
| The observation concatenates the orientation vector and the joint velocities | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:112-116 |
| The orientation vector is the horizontal and vertical components of the two arm body z-axes | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:132-148 |
| The reward is a tolerance of the tip-to-target distance with bounds 0 to target_radius | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:118-130 |
| The reward margin is 0.0 for the sparse variant and 1.0 for the dense variant | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:60 |
| The action size is the model's number of actuators nu | upstream_code | mujoco_playground/_src/dm_control_suite/acrobot.py:154-156 |
| The package requires Python 3.11 or newer | vendor_doc | pyproject.toml:12 |
| The runtime dependencies include mujoco-mjx>=3.6.0 and mujoco>=3.6.0 | vendor_doc | pyproject.toml:24-38 |

## Limits

The driver declares no `Limit` of its own. The only actuation bound is the model's per-actuator `ctrlrange`, which the
MuJoCo bridge derives from the MJCF at load time (`acrobot.xml:41` gives the elbow motor `ctrlrange="-1 1"`). The
derived bound's source is the model file itself, so it is not copied into a driver limit and no operator-required bound
is needed. `ticks` is bounded by the family's `max_ticks` (10000 by default), and the reset input `seed` is accepted
as metadata of the bridge and does not seed a random draw.

## Fidelity contract

`driver.py` publishes the contract the bridge derives: engine `mujoco:acrobot`, level F1, timestep 10 ms
(`acrobot.xml:18`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot/restore offered by the bridge, and
determinism `seeded` with `seed_control` `none`. The gaps state that the fake is a stand-in for the MuJoCo library, not
the engine, and that the upstream environment's random reset, observation, reward and episode logic are not exposed.

## Safety

Simulated R0 device. There is no hardware backend and no physical stop path. The e-stop is the runtime's software latch:
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the integration state stays
readable. The native `cap.world.step` and `cap.world.reset` are served by the MuJoCo bridge.

## Tags

acrobot, dm-control, mujoco, playground, simulation, robot
