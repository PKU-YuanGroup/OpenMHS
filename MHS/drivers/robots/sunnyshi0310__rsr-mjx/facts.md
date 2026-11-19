# Facts and tags for gh.sunnyshi0310/rsr-mjx

Every fact cites its source at commit `b2fd0b84865f3c5fa784bc1f0cac410c9d10d67c`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a text file of the clone, `path:LINE`). The same facts are in `driver.py`; the reference
file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project calls itself an RSR (Real-to-Sim-to-Real) reinforcement-learning framework built on MuJoCo MJX and Brax | vendor_doc | README.md:3 |
| The two experimental platforms are an Airbot Play arm and a Unitree Go2 quadruped trained for flat/rough terrain joystick control | vendor_doc | README.md:9-10 |
| Go2 training scripts need PYTHONPATH=ppo_train/go2_training and the Go2 assets are bundled under mujoco_playground/_src/locomotion/go2/xmls | vendor_doc | README.md:67-68 |
| The card's entry Joystick is the Go2 joystick task and its default task is flat_terrain | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py:83-87 |
| The registry's Go2JoystickFlatTerrain entry is Joystick with task=flat_terrain | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/__init__.py:16-22 |
| task_to_xml maps flat_terrain to scene_mjx_feetonly_flat_terrain.xml and rough_terrain to scene_mjx_feetonly_rough_terrain.xml | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/go2_constants.py:5-19 |
| The served scene is the MuJoCo model 'go2 feetonly flat terrain scene' and it includes go2_mjx_feetonly.xml | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/scene_mjx_feetonly_flat_terrain.xml:1-2 |
| The model compiler declares radian angles, a mesh directory, and autolimits enabled | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/go2_mjx_feetonly.xml:2 |
| The model integrates with Euler at a 0.004 s timestep | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/go2_mjx_feetonly.xml:4 |
| The go2 default class gives its position actuators inheritrange 1 and forcerange -24 to 24; the knee class overrides the force range to -35.55 to 35.55 | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/go2_mjx_feetonly.xml:9-24 |
| The abduction joints have range -1.0472 to 1.0472 rad, the hip (thigh) joints -1.5708 to 3.4907 rad and the knee (calf) joints -2.7227 to -0.83776 rad | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/go2_mjx_feetonly.xml:15-24 |
| The actuator block declares twelve position actuators, one per Go2 leg joint: four abduction (hip), four hip (thigh) and four knee (calf) channels | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/go2_mjx_feetonly.xml:191-204 |
| Joystick initializes _init_q and _default_pose from the home keyframe's qpos | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py:98-99 |
| Joystick.reset starts from _init_q, then draws a base x/y offset from -0.5 to 0.5, a yaw from -3.14 to 3.14 rad and a base velocity from -0.5 to 0.5 | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py:123-138 |
| The joystick default config sets action_scale 0.5, ctrl_dt 0.02 s and sim_dt 0.004 s | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py:13-21 |
| Joystick.step selects actual_action from the delay buffer when enabled, otherwise from the input, and sets motor_targets to _default_pose plus actual_action times action_scale | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py:207-216 |
| The joystick episode terminates when the IMU up vector's vertical component falls below zero | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py:281-283 |
| The scene's home keyframe sets the nominal qpos and ctrl of the standing pose | upstream_code | ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/scene_mjx_feetonly_flat_terrain.xml:27-35 |

## Limits

The driver declares no `Limit`. The only numeric envelope is the model's own actuator control range, which the bridge
derives at run time from `model.actuator_ctrlrange`: the go2 default class gives every position actuator
`inheritrange="1"` (`go2_mjx_feetonly.xml:13`), so each control range equals the range of the joint it drives
(`go2_mjx_feetonly.xml:15-24`): +-1.0472 rad for the four abduction channels, -1.5708 to 3.4907 rad for the four hip
(thigh) channels and -2.7227 to -0.83776 rad for the four knee (calf) channels. The runtime refuses an element outside
them before any native call. Every one of the twelve actuators has a range, so no `site-limits.example.json` is needed
and no operator bound is withheld.

## Safety

The device is simulated (R0). The e-stop is the runtime's software latch (the simulation has no machine stop); after it
no step or reset is accepted until `mhs.safety.reset` clears the latch, and the integration state stays readable. No
hardware can be attached to this package: `backends` lists only `fake`, and `sim` is the real `mujoco` engine on the
same scene.

## Mock path

The card prefers `upstream-sim`. The upstream simulator is the bundled MJX environment, which needs `jax`,
`mujoco-mjx` and `mujoco_playground`, none of which is importable where the gate runs and none of which may be
installed (no network, no pip). `fake.py` is therefore a package-local stand-in for the `mujoco` module the MuJoCo
bridge imports. It parses the same scene and its include for the model shape (joint layout, control ranges inherited
from the joint ranges, 4 ms timestep) but integrates a placeholder first-order motion; the driver's fidelity `gaps`
state every difference. The real `sim` path (the official `mujoco` module loading the same scene) was not run.

## Tags

`go2`, `unitree`, `quadruped`, `joystick`, `mujoco`, `mjx`, `simulation`, `rsr`
