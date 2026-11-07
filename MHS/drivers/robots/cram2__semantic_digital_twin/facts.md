# Facts and tags for gh.cram2/semantic_digital_twin

Every fact cites its source at commit `40a35e7e481b358cd7f9d939c7ff4e0c23826098`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF, Python or packaging file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package is a world model that unifies kinematic information and semantic meaning for robotic world representations | upstream_code | pyproject.toml:15 |
| The package's adapters import scenes in formats including URDF, USD and MJCF | vendor_doc | README.md:44 |
| The scene is the MuJoCo MJCF model named 'panda scene' | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:1 |
| The scene compiles angles in radians and derives limits automatically (autolimits true) | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:2 |
| The panda default class gives its joints the range -2.8973 to 2.8973 rad, armature 0.1 and damping 1 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:7 |
| The panda default class gives general actuators the control range -2.8973 to 2.8973 and force range -87 to 87 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:8 |
| The panda default class gives position actuators the force range -100 to 100 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:9 |
| The finger default class gives finger joints the slide type on axis 0 1 0 and the range 0 to 0.04 m | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:10-11 |
| The arm is the body chain link0 to link7 with the hinge joints joint1 to joint7 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:41-71 |
| joint2 has the range -1.7628 to 1.7628 rad | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:51 |
| joint4 has the range -3.0718 to -0.0698 rad | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:59 |
| joint6 has the range -0.0175 to 3.7525 rad | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:67 |
| The hand carries the two slide joints finger_joint1 and finger_joint2, both of the finger class | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:78-83 |
| An equality constraint couples finger_joint1 and finger_joint2 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:97 |
| The actuator section declares seven position actuators for joint1 to joint7 and one general actuator for finger_joint1 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:101-115 |
| actuator1 and actuator3 have the control range -2.8973 to 2.8973 rad and actuator2 has -1.7628 to 1.7628 rad | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:101-106 |
| actuator4 has the control range -3.0718 to -0.0698 rad and actuator5 has -2.8973 to 2.8973 rad | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:107-110 |
| actuator6 has the control range -0.0175 to 3.7525 rad | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:111-112 |
| actuator7 is the position actuator for joint7 and states no control range of its own | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:113 |
| actuator8 is the general actuator for finger_joint1 with the control range 0 to 0.04 m | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:114-115 |
| The integration step is 0.005 s and the integrator is implicitfast with 5 iterations and 8 line-search iterations | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:118 |
| The custom numeric max_contact_points is 12 | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:122-123 |
| The scene has a static plane floor and a free-floating box body of size 0.02 0.02 0.03 m | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:143-153 |
| The keyframes home, pickup and pickup1 each give 16 qpos values and 8 ctrl values | upstream_code | resources/mjcf/mjx_single_cube_no_mesh.xml:156-165 |
| The upstream test suite loads this exact MJCF file | upstream_code | test/test_adapters/test_multi_sim.py:41 |
| The upstream MJCF adapter parses a scene with mujoco.MjSpec.from_file | upstream_code | src/semantic_digital_twin/adapters/mjcf.py:61 |
| The upstream MJCF adapter iterates the spec's actuators when building its world | upstream_code | src/semantic_digital_twin/adapters/mjcf.py:82 |
| The package requires Python 3.10 or newer | upstream_code | pyproject.toml:17 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [8 numbers]}}`. Each `ctrl` element is bounded by the matching
actuator's control range of `resources/mjcf/mjx_single_cube_no_mesh.xml`:

* actuator1 and actuator3: -2.8973 to 2.8973 rad (lines 101-106);
* actuator2: -1.7628 to 1.7628 rad (lines 103-104);
* actuator4: -3.0718 to -0.0698 rad (lines 107-108);
* actuator5: -2.8973 to 2.8973 rad (lines 109-110);
* actuator6: -0.0175 to 3.7525 rad (lines 111-112);
* actuator7: the panda general default -2.8973 to 2.8973, because a position element is the general actuator
  shortcut and this actuator states no own control range (lines 8 and 113);
* actuator8: 0 to 0.04 m (lines 114-115).

The bridge derives these per-actuator bounds from the loaded model and publishes them with the model reference; no
number is declared as a `Limit` in `driver.py`. `ticks` is bounded by the family at 1 to 10000. The device is
simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:mjx_single_cube_no_mesh`, level F1 (rigid-body MJCF, no rendering or
sensor publication), determinism `exact` with seed control `none`, timestep 5 ms
(`resources/mjcf/mjx_single_cube_no_mesh.xml:118`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and
restore supported through the bridge's integration state. The gaps say that the fake backend is not the engine, that
the box free joint and finger equality are not simulated, that reset does not apply the keyframes, that the upstream
Multiverse adapter is not used, that nothing paces wall-clock time, that no rendering or sensor stream is served, that
no physical robot is modelled, and that the stand-in was not compared with an engine load.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable. There is no hardware e-stop, no physical stop
path and no claim of one.

Tags: mujoco, mjcf, semantic-digital-twin, panda, single-cube, simulation
