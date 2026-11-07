# Facts and tags for gh.shanpenghui/robomimicdeploy_g1

Every fact cites its source at commit `8e5ab747a4c847e28d41d3084ff9822f877b147c`: `upstream_code` (an MJCF, Python
or YAML file of the clone) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's `models[0]` `g1_description/scene.xml` as a simulated R0 `world.sim`. It reads the
scene from the read-only clone; the package copies neither the model nor its meshes. The scene includes
`g1_29dof_rev_1_0.xml`, whose 29 motor actuators have no `ctrlrange`; the bridge publishes `action.ctrl` as
`operator_required` and the driver declares no control limit of its own.

| fact | source | ref |
|---|---|---|
| The default MuJoCo configuration runs the scene g1_description/scene.xml | upstream_code | deploy_mujoco/config/mujoco.yaml:1 |
| The scene includes the robot model g1_29dof_rev_1_0.xml | upstream_code | g1_description/scene.xml:1-2 |
| The robot model uses radians and resolves its meshes from meshes/ | upstream_code | g1_description/g1_29dof_rev_1_0.xml:2 |
| The robot model sets the integration step to 0.002 s and the implicit integrator | upstream_code | g1_description/g1_29dof_rev_1_0.xml:10-11 |
| The robot model declares a free floating-base joint named floating_base_joint | upstream_code | g1_description/g1_29dof_rev_1_0.xml:54 |
| The floating base starts at the pelvis body pose (0 0 0.793) | upstream_code | g1_description/g1_29dof_rev_1_0.xml:52 |
| The actuator block has 29 motor elements, one for each actuated joint, and none states a ctrlrange | upstream_code | g1_description/g1_29dof_rev_1_0.xml:247-277 |
| The left hip pitch joint has range -2.5307 to 2.8798 rad and actuatorfrcrange -88 to 88 | upstream_code | g1_description/g1_29dof_rev_1_0.xml:61 |
| The left ankle roll joint has range -0.2618 to 0.2618 rad and actuatorfrcrange -50 to 50 | upstream_code | g1_description/g1_29dof_rev_1_0.xml:86 |
| The left wrist pitch joint has range -1.61443 to 1.61443 rad and actuatorfrcrange -5 to 5 | upstream_code | g1_description/g1_29dof_rev_1_0.xml:182 |
| The simulation loop loads the scene with mujoco.MjModel.from_xml_path and creates the MjData | upstream_code | deploy_mujoco/deploy_mujoco.py:33-34 |
| The simulation loop overrides the model timestep with cfg.simulation_dt | upstream_code | deploy_mujoco/deploy_mujoco.py:35 |
| The configuration sets simulation_dt to 0.003 s and control_decimation to 7 | upstream_code | deploy_mujoco/config/mujoco.yaml:3-4 |
| The configuration's tau_limit array lists the per-actuator torque magnitudes: 88, 139 and 50 for the leg motors, 88, 50 and 50 for the waist, 25 for the shoulder and elbow motors and 5 for the wrist motors | upstream_code | deploy_mujoco/config/mujoco.yaml:5-9 |
| The simulation loop clips the computed torque with np.clip(tau, -tau_limit, tau_limit) before writing it to d.ctrl | upstream_code | deploy_mujoco/deploy_mujoco.py:86-87 |
| The simulation loop calls mujoco.mj_step once per iteration | upstream_code | deploy_mujoco/deploy_mujoco.py:88 |
| The simulation loop treats qpos[7:] as the 29 joint positions and qvel[6:] as the 29 joint velocities, so the first seven qpos and six qvel values are the floating base | upstream_code | deploy_mujoco/deploy_mujoco.py:85 |
| The simulation loop runs the FSM when sim_counter is a multiple of control_decimation | upstream_code | deploy_mujoco/deploy_mujoco.py:89-90 |
| The README documents running the MuJoCo simulation with python deploy_mujoco/deploy_mujoco.py | vendor_doc | README.md:62 |
| The README documents the LieDown start model with the override xml_path=g1_description/g1_29dof_LieDown.xml | vendor_doc | README.md:94 |

Limits: the driver declares none. The MJCF states no `ctrlrange` for any of its 29 motors
(`g1_29dof_rev_1_0.xml:247-277`), so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. The model's `actuatorfrcrange` values (`:61`, `:86`, `:182`, and the other joint lines) are
joint force ranges, not the action bound the bridge publishes. The upstream application clips `tau` to its
`tau_limit` configuration (`deploy_mujoco/config/mujoco.yaml:5-9`, `deploy_mujoco/deploy_mujoco.py:86-87`), but that
is a clamp of the joystick/policy loop, not a bound of the MJCF model, so it is not presented as a device limit. No
bound was invented or copied from a catalogue default. The reset input `seed` is accepted by the class
contract and echoed as the bridge's configured seed; MuJoCo `mj_resetData` restores the model defaults and does not
use a seed.

Expected warnings, all explained: `G6.NOT_RECORDED` and `G7.UPSTREAM_BACKEND` (the fake is a stand-in library
object, not the upstream simulator, so native calls are not recorded and G7 has no fake surface);
`G8.NO_UNIT` x3 (the bridge-derived inputs `ticks`, `action.ctrl[*]` and `seed`). No catalogue request is needed:
only `cap.world.step.v1` and `cap.world.reset.v1` are used.

Fidelity: the model's own 0.002 s step is used (`g1_29dof_rev_1_0.xml:10`). The upstream `deploy_mujoco.py` loop
instead overrides the timestep with `simulation_dt = 0.003` s, runs the FSM every 7 steps and reads a joystick
(`deploy_mujoco.py:35`, `:57-90`; `config/mujoco.yaml:3-4`); this package loads the scene directly and exposes
`data.ctrl`, so it is not the upstream joystick and policy application. MuJoCo was not importable where the gate ran,
so the `fake` backend is a stand-in `mujoco` module (fake.py): it parses the scene and its include for the joint and
actuator counts, the free-base start pose and the 2 ms timestep, but integrates a placeholder torque response and
resolves no mesh, texture, contact, constraint, gravity, inertia or sensor. No trajectory was compared with MuJoCo
and the sim path was not run; the driver's `fidelity.gaps` list every difference.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. There is no hardware stop to cite and no `operator_required` limit.

Tags: g1, humanoid, mujoco, robot, simulation, unitree
