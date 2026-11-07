# Facts and tags for gh.noetix-robotics/noetix_n2_gym

Every fact cites its source at commit `153aad12dcc44aeafe378efe2f652873b02e0d89`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README's sim-to-sim procedure tells the user to update the policy_config in sim2sim/configs/n2_18dof.yaml before starting the MuJoCo deployment | vendor_doc | README.md:59 |
| The README labels the deployment MuJoCo-based sim-to-sim and gives python sim2sim/sim2sim.py as the command | vendor_doc | README.md:60-63 |
| The sim2sim config selects resources/robots/N2/mjcf/n2_18dof.xml as the model | upstream_code | sim2sim/configs/n2_18dof.yaml:3 |
| The sim2sim config sets simulation_dt to 0.002 s and control_decimation to 10 | upstream_code | sim2sim/configs/n2_18dof.yaml:8-10 |
| run_mujoco opens the YAML config named by its cfg argument and resolves its xml_path | upstream_code | sim2sim/sim2sim.py:65-68 |
| run_mujoco loads the robot model with mujoco.MjModel.from_xml_path(xml_path) | upstream_code | sim2sim/sim2sim.py:90 |
| run_mujoco overwrites model.opt.timestep with the config's simulation_dt and then creates MjData | upstream_code | sim2sim/sim2sim.py:91-92 |
| run_mujoco computes PD torques and writes the torque vector to data.ctrl | upstream_code | sim2sim/sim2sim.py:159-161 |
| run_mujoco advances the simulation with mujoco.mj_step(model, data) | upstream_code | sim2sim/sim2sim.py:163 |
| The script's __main__ block defaults the config file to n2_10dof.yaml | upstream_code | sim2sim/sim2sim.py:176 |
| The MJCF root element declares the model N2 | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:1 |
| The model uses radians and resolves its meshes from ../meshes/ | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:2 |
| The default joint class sets damping 0.001, armature 0.01 and frictionloss 0.1 | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:4-6 |
| The base_link body is placed at 0 0 0.75 and carries the free joint named root | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:43-47 |
| Eighteen limited hinge joints carry the arms and legs: four per arm and five per leg, each with its own range | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:52-156 |
| The actuator section declares eighteen motor actuators, one per hinge joint | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:169-191 |
| No actuator element sets ctrlrange or ctrllimited, so the model states no control range for any motor | upstream_code | resources/robots/N2/mjcf/n2_18dof.xml:169-191 |
| The package declares mujoco==2.3.6 and mujoco-python-viewer in install_requires | upstream_code | setup.py:20-22 |
| The package declares isaacgym (preview 4) in install_requires | upstream_code | setup.py:12 |

The served file is the card's `models[1]`, `resources/robots/N2/mjcf/n2_18dof.xml`: the README's sim2sim section
points the user at `sim2sim/configs/n2_18dof.yaml` (`README.md:59`) and that config selects this model
(`n2_18dof.yaml:3`). The script's `__main__` default is `n2_10dof.yaml` (`sim2sim.py:176`), an inconsistency of the
clone; the 18-dof file is the model the documented sim2sim procedure configures. The 10-dof model is the card's
`models[0]` and is not served by this package.

Limits: the driver declares none of its own. `cap.world.step.v1` takes `{ticks, action: {ctrl: [18 numbers]}}`; the
MJCF sets no `ctrlrange` or `ctrllimited` on its eighteen motors (`n2_18dof.xml:169-191`),
so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by default). The joint ranges (`n2_18dof.xml:52-156`) are position limits in MuJoCo, not control bounds, and the bridge does
not use them.

Contract: `MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource. A step applies
the control vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`,
with 25 qpos values (a free base of 7 plus 18 hinges) and 24 qvel values (a free base of 6 plus 18 hinges). A reset
calls `mj_resetData` and `mj_forward`, restoring the model defaults; a seed is accepted for the class contract but a
MuJoCo reset does not use it.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:N2`, level F1, determinism `seeded` with
`seed_control` `none`, timestep 2 ms (the upstream config's `simulation_dt: 0.002` at `n2_18dof.yaml:8`, which
`run_mujoco` writes into `model.opt.timestep` at `sim2sim.py:91`; the MJCF itself states no `<option timestep>`),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore available. The gaps state that the fake is
not MuJoCo, that it loads no meshes or contacts, that the model declares no control range, that the model's foot-force
and IMU sensors are not exposed, that the upstream loop overrides the model step and drives torques from a policy, and
that no trajectory was compared with the real engine or with a physical robot.

Safety: simulated R0 device. The e-stop is the runtime's software latch; there is no native stop and no physical
e-stop claim. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state
stays readable.

Tags: noetix, n2, humanoid, legged, mujoco, simulation, robot
