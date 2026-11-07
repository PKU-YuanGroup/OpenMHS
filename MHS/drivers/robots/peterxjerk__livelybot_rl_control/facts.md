# Facts and tags for gh.peterxjerk/livelybot_rl_control

Every fact cites its source at commit `86b2e85a2e6093e478dea8c8a48bbe4adbfc7445`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's primary model, the MJCF file
`resources/robots/pai_12dof/mjcf/pai_12dof.xml` (`models[0]`), as a `MujocoDriver`. It reads the model file from the
read-only clone; neither the model nor its meshes are copied into the package. The card's second model,
`resources/robots/pai_12dof/mjcf/pai_12dof_terrain.xml`, is not served (one package serves one model).

| fact | source | ref |
|---|---|---|
| The repository is an Isaac Gym reinforcement learning environment for HighTorque's legged robot and also integrates a sim-to-sim framework from Isaac Gym to MuJoCo | vendor_doc | README.md:3 |
| The README describes the MuJoCo-based sim-to-sim deployment as running humanoid/scripts/sim2sim.py with an exported policy | vendor_doc | README.md:67-69 |
| The sim-to-sim entry point is the module-level function run_mujoco(policy, cfg) | upstream_code | humanoid/scripts/sim2sim.py:89 |
| run_mujoco loads the model with mujoco.MjModel.from_xml_path, overrides model.opt.timestep with the configured dt, creates mujoco.MjData and calls mujoco.mj_step once before the loop | upstream_code | humanoid/scripts/sim2sim.py:100-103 |
| Every loop iteration writes the clipped PD torques to data.ctrl and advances the model with mujoco.mj_step | upstream_code | humanoid/scripts/sim2sim.py:161-172 |
| Sim2simCfg sets sim_config.dt to 0.001 s and sim_duration to 60.0 s, with decimation 10 | upstream_code | humanoid/scripts/sim2sim.py:195-197 |
| The default non-terrain model path ends at resources/robots/pai_12dof/mjcf/pai_12dof without the .xml extension, so an importing caller must supply the explicit file path | upstream_code | humanoid/scripts/sim2sim.py:194 |
| The MuJoCo model is declared as pai_12dof_v2_0312 | upstream_code | resources/robots/pai_12dof/mjcf/pai_12dof.xml:1 |
| The model sets the physics timestep to 0.001 s | upstream_code | resources/robots/pai_12dof/mjcf/pai_12dof.xml:3 |
| The default block makes joints limited and motors control-limited unless an element overrides it | upstream_code | resources/robots/pai_12dof/mjcf/pai_12dof.xml:13-16 |
| The base is floating: the base_link body carries three slide joints and one ball joint | upstream_code | resources/robots/pai_12dof/mjcf/pai_12dof.xml:68-71 |
| The two legs carry twelve named hinge joints with per-joint ranges on the cited lines | upstream_code | resources/robots/pai_12dof/mjcf/pai_12dof.xml:80-141 |
| The actuator section declares twelve motor actuators, one per leg joint, each with ctrllimited=true and ctrlrange -200 to 200 | upstream_code | resources/robots/pai_12dof/mjcf/pai_12dof.xml:153-164 |
| setup.py install_requires lists isaacgym, mujoco==2.3.6, mujoco-python-viewer and the training stack; there is no serial, USB or VISA dependency | upstream_code | setup.py:43-51 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator (`actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model file). The package
declares no limit of its own and no `operator_required` bound, because the model file is the system of record for the
control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the model file for
the actuator count, the control ranges and the joint dimensions, but its integration is a placeholder motion
proportional to each control value and it resolves no mesh, contact, friction, equality, tendon, actuator or sensor
constraint. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was compared with the
real engine. The gaps are listed in the `fidelity` attribute of `driver.py`. The driver declares F0 because the
deployed fake has no dynamics; the MJCF and the real engine would support F1.

Risk: the device is simulated and its only capability advances a legged-robot model. The package declares R1, the
class the safety spec gives simulation stepping (`MHS/spec/04-safety.md` section 2.1). There is no hardware backend,
no native stop and no operator-required bound; the runtime's software e-stop latch stops accepting steps and resets.

Tags: pai, 12-dof, humanoid, mujoco, simulation, reinforcement-learning, livelybot
