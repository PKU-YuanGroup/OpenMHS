# Facts and tags for gh.mosesandlily/whip-project-targeting

Every fact cites its source at commit `8025f9f156bf3cf591afbedca18eaa03e3846d4a`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a Python file or an MJCF file of the clone).  The same facts are written
into `facts = [...]` in `driver.py`; the reference file is generated from the driver, not from this page.

The card's entry symbol `modules.simulation:Simulation` exists at `modules/simulation.py:16`, and the card's helper
`MujocoDriver` fits the runtime the clone uses: the class loads an MJCF with `mujoco-py` and steps it.  This package
serves the user-facing 3D scene `models/3D_model_w_whip_T1.xml` (the script builds the name as
`"3D_model_w_whip_T" + target_type`, `main_whip.py:43-44`), not the card's `models[0]` 2D scene; the other scenes are
not served and that is listed in the fidelity gaps.  It does not import `Simulation`, which needs an argparse
Namespace and flat `sys.path` imports (`modules/simulation.py:21,35-36`); the bridge loads the model file in place.

| fact | source | ref |
|---|---|---|
| The README presents the repository as a controller-design study that controls a whip, described as a complex object with significant dynamics | vendor_doc | README.md:3 |
| The README's setup downloads the requirements with pip for the mujoco-py simulation | vendor_doc | README.md:40-42 |
| The module defines class Simulation, documented as running a single whip simulation | upstream_code | modules/simulation.py:16-19 |
| The Simulation constructor loads the selected model with mjPy.load_model_from_path from C.MODEL_DIR + model_name + '.xml' and wraps it in mjPy.MjSim | upstream_code | modules/simulation.py:35-36 |
| Simulation reads n_act from the model's actuator_names, nq from its joint_names and dt from model.opt.timestep | upstream_code | modules/simulation.py:47-57 |
| Simulation.set_init_posture writes the caller's qpos and qvel into mj_data and calls mj_sim.forward; it takes no seed | upstream_code | modules/simulation.py:98-116 |
| Simulation.reset calls mj_sim.reset and resets each attached controller | upstream_code | modules/simulation.py:125-132 |
| Simulation.run halts the loop as unstable when max(abs(mj_data.qacc)) exceeds 10 ** 6 | upstream_code | modules/simulation.py:250-261 |
| Simulation.get_state returns the concatenated mj_data.qpos and mj_data.qvel arrays | upstream_code | modules/simulation.py:263-267 |
| Simulation.stepML writes the action into mj_data.ctrl[:n_act] and calls mj_sim.step | upstream_code | modules/simulation.py:305-313 |
| The user-facing main_whip.py builds the model name as '3D_model_w_whip_T' + str(target_type) | upstream_code | main_whip.py:43-44 |
| The model root is '<mujoco model="1_3D_model_w_N25">' and its compiler declares the angle unit as radian | upstream_code | models/3D_model_w_whip_T1.xml:1-2 |
| The option element sets timestep 0.0001 s, 50 iterations, the PGS solver, the Euler integrator and gravity 0 0 -9.81 | upstream_code | models/3D_model_w_whip_T1.xml:3-5 |
| The arm has four hinge joints named joint_shoulder_flex_ext, joint_shoulder_add_abd, joint_shoulder_med_lat and joint_elbow | upstream_code | models/3D_model_w_whip_T1.xml:41-52 |
| The whip chain runs from body_whip_node1 to body_whip_node25, and every node carries an X hinge and a Y hinge | upstream_code | models/3D_model_w_whip_T1.xml:61-186 |
| The target sphere geom has position 1.9950 0.0000 0.0000, size 0.03 and mass 0 | upstream_code | models/3D_model_w_whip_T1.xml:216 |
| The actuator section declares four motor actuators, one per arm joint, and each sets forcelimited false and states no ctrlrange | upstream_code | models/3D_model_w_whip_T1.xml:220-225 |

Limits: the driver declares none.  The bridge derives `cap.world.step.v1` `action.ctrl` from the model's
`actuator_ctrlrange`.  The four motor elements of `models/3D_model_w_whip_T1.xml:220-225` declare no `ctrlrange`, and
MuJoCo leaves such a control unclamped, so the bridge publishes `action.ctrl` as `operator_required`: the endpoint
refuses a step that sets it (`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json`
bounds it, and a step without `action` keeps the controls as they are.  The model states no control bound that could
be cited, so none is invented.  `site-limits.example.json` is operator example data (-10.0 to 10.0, a scalar over the
four controls), not a bound of the model.

Fidelity: the real path is MuJoCo loading `models/3D_model_w_whip_T1.xml` at a 0.0001 s timestep (0.1 ms), level F1,
with no seed input, `realtime_factor` 0, `clock` `lockstep`, `reset` `full`; `snapshot_restore` is the bridge's
declared snapshot capability, not a claim that a snapshot was exercised.  The fake backend is a stand-in for the
MuJoCo library (fake.py), not MuJoCo: it reads the model for the 54 hinges, the four motors, their absent ctrlranges
and the 0.0001 s timestep, but its integration is a placeholder and it resolves no mesh, contact, equality, tendon,
sensor or camera; its contract is level F0.  The upstream `Simulation` task interface is NOT COVERED: it sets an
initial posture, makes the whip downwards, runs joint-impedance controllers, an objective and a 10 ** 6 acceleration
instability halt, while the bridge serves raw `data.ctrl` and the integration state.  MuJoCo and mujoco-py are not
importable where the gate runs, so no trajectory was compared with the real engine and the `sim` backend was not run.

Safety: simulated R0 device (`world.sim`).  The e-stop is the runtime's software latch (no native stop exists); after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the integration state stays readable.
The last controls are retained; a later explicit step without `action` reuses them.

Tags: whip, targeting, dynamic-primitives, mujoco, robot, simulation
