# Facts and tags for gh.enactic/openarm_mujoco

Every fact cites its source at commit `0e050bb5d3472b75c6bfa00b310a77c7c2c5be79`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF, Python or packaging file of the clone).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository holds MJCF description files for OpenArm v2, Cell, v1 and v0.3 simulation in MuJoCo | vendor_doc | README.md:1-4 |
| The README's v1 bimanual launch command opens v1/scene.xml with the home keyframe | vendor_doc | README.md:64 |
| The v1 scene is the MJCF model 'openarm_bimanual scene' and includes openarm_bimanual.xml from the same directory | upstream_code | v1/scene.xml:17-18 |
| The included bimanual model sets the integration step to 0.001 s and the implicitfast integrator | upstream_code | v1/openarm_bimanual.xml:19 |
| The actuator section declares 16 position actuators: eight per arm (seven arm joints and one finger) | upstream_code | v1/openarm_bimanual.xml:547-563 |
| The left arm control ranges are joint1 -3.490659 to 1.396263 rad, joint2 -3.3161253267948965 to 0.17453267320510335, joint3 -1.570796 to 1.570796, joint4 0 to 2.443461, joint5 -1.570796 to 1.570796, joint6 -0.785398 to 0.785398 and joint7 -1.570796 to 1.570796 | upstream_code | v1/openarm_bimanual.xml:548-554 |
| The right arm control ranges are joint1 -1.396263 to 3.490659 rad, joint2 -0.17453267320510335 to 3.3161253267948965, joint3 -1.570796 to 1.570796, joint4 0 to 2.443461, joint5 -1.570796 to 1.570796, joint6 -0.785398 to 0.785398 and joint7 -1.570796 to 1.570796 | upstream_code | v1/openarm_bimanual.xml:556-562 |
| The motor_finger default class gives the finger position actuators the control range -0.005 to 0.044 m | upstream_code | v1/openarm_bimanual.xml:41-45 |
| The left arm's first joint is the hinge openarm_left_joint1 with the range -3.490659 to 1.396263 rad | upstream_code | v1/openarm_bimanual.xml:170-171 |
| The right arm's first joint is the hinge openarm_right_joint1 with the range -1.396263 to 3.490659 rad | upstream_code | v1/openarm_bimanual.xml:349-350 |
| The left hand has two slide finger joints, openarm_left_finger_joint1 and openarm_left_finger_joint2, with the range 0 to 0.044 m | upstream_code | v1/openarm_bimanual.xml:297-315 |
| The right hand has the matching pair of slide finger joints, openarm_right_finger_joint1 and openarm_right_finger_joint2, also with the range 0 to 0.044 m | upstream_code | v1/openarm_bimanual.xml:476-495 |
| The two fingers of each hand are coupled by an equality constraint | upstream_code | v1/openarm_bimanual.xml:540-543 |
| The model provides a home keyframe with 18 qpos values (nine per arm) and 16 ctrl values (eight per arm) | upstream_code | v1/openarm_bimanual.xml:566-572 |
| The package requires Python 3.10 or newer and depends on mujoco 3.6.0 or newer and numpy | upstream_code | pyproject.toml:27-30 |
| The upstream launcher loads a model with mujoco.MjModel.from_xml_path and creates its data with mujoco.MjData | upstream_code | src/openarm_mujoco/v2/launch.py:72-73 |
| The launcher hands the model to mujoco.viewer.launch unless --static is given; static mode calls mj_forward without stepping | upstream_code | src/openarm_mujoco/v2/launch.py:114-128 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [16 numbers]}}`.  Each `ctrl` element is bounded by the matching
actuator's `ctrlrange` of `v1/openarm_bimanual.xml`: the seven left arm ranges at lines 548-554, the seven right arm
ranges at lines 556-562, and the two finger actuators inherit `-0.005` to `0.044` m from the `motor_finger` default
class at lines 41-45.  The bridge derives these per-actuator bounds from the loaded model and publishes them with the
model reference; no number is written into this package.  `ticks` is bounded by the family at 1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:openarm_bimanual`, level F1 (rigid-body MJCF, no rendering or sensor
publication), determinism `exact` with seed control `none`, timestep 1 ms (`v1/openarm_bimanual.xml:19`),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore supported through the bridge's integration
state.  The gaps say that the fake backend is not the engine, that the meshes are not loaded, that reset does not
apply the home keyframe, that nothing paces wall-clock time, that no rendering or sensor stream is served, and that
no physical arm is modelled.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, openarm, bimanual, robot arm, manipulation, simulation
