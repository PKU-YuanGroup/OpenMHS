# Facts and tags for gh.ussoftware1/mujoco-planar-reach-rl-demo

Every fact cites its source at commit `863bd473bc478e93cb05bbef22fcbf5905fb977d`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (an MJCF, Python or packaging file of the clone).  The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| The card's model is the MJCF 'planar_reach', whose root element is '<mujoco model="planar_reach">' | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:1 |
| The model is compiled with angles in radians and autolimits enabled | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:2 |
| The model integrates with the RK4 integrator at a 0.002 s timestep under gravity 0 0 -9.81 | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:3 |
| The default joint attributes are armature 0.01, damping 0.8 and limited true; the default motor is ctrl-limited with ctrlrange -1 to 1 | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:5-9 |
| The shoulder joint turns about the +z axis with the range -3.1416 to 3.1416 rad | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:27 |
| The elbow joint turns about the +z axis with the range -3.1416 to 3.1416 rad | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:32 |
| The arm is two links of 0.25 m: the link bodies sit 0.25 m apart and each capsule spans -0.25 to 0.25 m | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:30-36 |
| The end effector is the site ee_site at the tip of link2, 0.25 m from the elbow | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:37 |
| The target is the mocap body target_body, placed at 0.45 0.10 0.045; it is not a joint of the arm | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:42 |
| The actuator section declares two motors: shoulder_motor with gear 2.0 and elbow_motor with gear 1.5, both with ctrlrange -1 to 1 | upstream_code | mujoco_planar_reach_rl/assets/planar_reach.xml:47-50 |
| The environment loads the MJCF with mujoco.MjModel.from_xml_path and creates its state with mujoco.MjData | upstream_code | mujoco_planar_reach_rl/env.py:76-77 |
| The environment's observation is 12 numbers: cos and sin of both joint positions, both joint velocities, the end-effector xy, the target xy and the target delta | upstream_code | mujoco_planar_reach_rl/env.py:49-51 |
| The environment's action is the two shoulder and elbow torque commands in [-1, 1] | upstream_code | mujoco_planar_reach_rl/env.py:53-54 |
| The environment defaults to frame_skip 10, max_episode_steps 250 and a success_threshold of 0.035 m | upstream_code | mujoco_planar_reach_rl/env.py:33-35 |
| The target is sampled at an angle uniform in -pi to pi and at a radius uniform in 0.18 to 0.48 m | upstream_code | mujoco_planar_reach_rl/env.py:195-198 |
| A reset draws both joint positions uniformly from -0.35 to 0.35 rad and both joint velocities from a normal distribution with scale 0.02 | upstream_code | mujoco_planar_reach_rl/env.py:116-117 |
| Each control step applies the action to data.ctrl and advances frame_skip (10) MuJoCo steps | upstream_code | mujoco_planar_reach_rl/env.py:132-135 |
| The episode succeeds when the end-effector distance to the target is at or below the success threshold and truncates at max_episode_steps | upstream_code | mujoco_planar_reach_rl/env.py:144-146 |
| The package requires Python 3.10 or newer and depends on mujoco 3.2.0 or newer, gymnasium 1.0.0 or newer and numpy 1.26 or newer | upstream_code | pyproject.toml:10-16 |

## Limits

The driver declares no explicit `Limit`; the served model is the source of the one bound the bridge publishes.
`cap.world.step.v1` takes `{ticks, action: {ctrl: [2 numbers]}}`.  Each `ctrl` element is bounded by the matching
motor's `ctrlrange` of `mujoco_planar_reach_rl/assets/planar_reach.xml`: the default motor class gives `-1` to `1`
(line 8) and the two motor elements repeat it (`shoulder_motor` at line 48 and `elbow_motor` at line 49).  The bridge
derives these per-actuator bounds from the loaded model and publishes them with the model reference; no number is
written into this package.  `ticks` is bounded by the family at 1 to 10000.

The device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity = {...}`: engine `mujoco:planar_reach`, level F1 (rigid-body MJCF, no rendering or sensor
publication), determinism `exact` with seed control `none`, timestep 2 ms
(`mujoco_planar_reach_rl/assets/planar_reach.xml:3`), `realtime_factor` 0, clock `lockstep`, reset `full`, snapshot
and restore supported through the bridge's integration state.  The gaps say that the fake backend is not the engine,
that the bridge's reset does not reproduce the environment's random start
(`mujoco_planar_reach_rl/env.py:116-117`) or its sampled target (`:195-206`), that the environment's 12-number
observation, reward and success threshold are not served, that nothing paces wall-clock time, that no rendering or
sensor stream is served, and that no physical arm is modelled.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware e-stop, no physical
stop path and no claim of one.

Tags: mujoco, planar-arm, two-link, robot-arm, reinforcement-learning, simulation
