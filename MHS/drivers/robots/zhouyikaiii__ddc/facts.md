# Facts and tags for gh.zhouyikaiii/ddc

Every fact cites its source at commit `33d221d5c9e51ae009dbad9aaabb66a90509f5bd`: `vendor_doc` (README.md or
DEPLOYMENT.md of the clone) or `upstream_code` (a text file of the clone, `path:LINE`). The same facts are in
`driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository releases a benchmark whose eval/ directory is a self-contained MuJoCo sim2sim harness built on numpy, mujoco and torch | vendor_doc | README.md:45 |
| The robot/g1_29dof/ directory is the exact Unitree G1 29-DoF MuJoCo plant the policy was validated on | vendor_doc | README.md:47 |
| The physical-robot runtime is the Holosoma two-process stack, and that framework and the Unitree SDK are not bundled in this repository | vendor_doc | DEPLOYMENT.md:7-10 |
| The rollout module imports mujoco directly and is a self-contained MuJoCo rollout | upstream_code | eval/wbt_rollout.py:1-17 |
| The default robot XML is robot/g1_29dof/g1_29dof.xml | upstream_code | eval/wbt_rollout.py:34-35 |
| The model file is the MJCF document named g1_29dof, compiled in radians with its meshes under ./meshes/ | upstream_code | robot/g1_29dof/g1_29dof.xml:12-13 |
| The deploy loader drops the contact pair block, injects a floor plane and rewrites the mesh directory before compiling the model | upstream_code | eval/wbt_rollout.py:159-178 |
| The physics timestep is SIM_DT = 0.0005 s (2000 Hz) | upstream_code | eval/wbt_rollout.py:39 |
| G1Sim assigns model.opt.timestep = SIM_DT after loading the deploy model | upstream_code | eval/wbt_rollout.py:206 |
| The plant has one free base joint and the 29 policy joints, and G1Sim skips the first 7 qpos and 6 qvel entries of the free joint | upstream_code | eval/wbt_rollout.py:213-214 |
| G1Sim.step advances the physics with mujoco.mj_step(self.model, self.data) | upstream_code | eval/wbt_rollout.py:415-416 |
| The pelvis body carries the freejoint named floating_base_joint inside the body with childclass g1_29dof | upstream_code | robot/g1_29dof/g1_29dof.xml:145-147 |
| The 29 motor actuators are named after the 29 joints; hip pitch/roll/yaw and waist yaw use +-88, knee +-139, ankle pitch/roll and waist roll/pitch +-50, shoulder, elbow and wrist roll +-25, and wrist pitch/yaw +-5, all as actuator ctrlrange | upstream_code | robot/g1_29dof/g1_29dof.xml:442-476 |
| The model declares a contact block of 14 foot<->floor pairs whose second geom is named floor | upstream_code | robot/g1_29dof/g1_29dof.xml:388-405 |
| The sensor block declares pelvis frame quaternion, gyro and accelerometer sensors, and mid360 frame quaternion and position sensors | upstream_code | robot/g1_29dof/g1_29dof.xml:478-485 |
| The bundled G1 model and meshes derive from Unitree's BSD-3-Clause model; the notice attributes the actuator and visual-group modifications to Apache-2.0 Holosoma | vendor_doc | robot/g1_29dof/NOTICE:4-17 |

## Limits

The only numeric envelope is the model's own actuator control range. The driver declares no `Limit` of its own: the
MuJoCo bridge derives `action.ctrl` from `actuator_ctrlrange` at run time, one element per motor, with the ranges
above (`robot/g1_29dof/g1_29dof.xml:443-475`). Every actuator in this model has a `ctrlrange`, so no control is
`operator_required` and there is no `site-limits.example.json`. The endpoint refuses an out-of-range element with
`MHS.SAFETY.ENVELOPE_VIOLATION` before any native call; the bridge also refuses a non-finite control before
`mj_step`.

The model file itself sets no `<option timestep>`. The driver's patched deploy scene writes the upstream
`SIM_DT = 0.0005 s` (eval/wbt_rollout.py:39, :206), so the published `timestep_ms` is 0.5. That is a simulation
timing from the upstream code, not a hardware safety bound.

## Tags

`unitree`, `g1`, `humanoid`, `mujoco`, `simulation`, `ddc`, `single-leg-balance`

## Mock path

The card prefers the upstream simulator. MuJoCo is not installed where the gate runs (no network, no pip), so
`fake.py` is a package-local stand-in for the `mujoco` module the MuJoCo bridge imports. It parses the same patched
model XML for the qpos/qvel dimensions, the 29 actuator control ranges and the option timestep, but integrates a
placeholder effort-driven acceleration with unit inverse inertia; it loads no mesh, resolves no
contact/friction/tendon/dynamics and does not integrate the free base. The driver's fidelity `gaps` state every
difference. The real `sim` path (the official `mujoco` module loading the same patched XML) was not run.

The fake is published as `analytic:g1-29dof-effort-fake`, F0, through `fidelity_by_backend`; the common F1 MuJoCo
description applies to the real engine only. The fake interprets motor controls as efforts rather than position
targets, but its unit inverse inertia is a placeholder and predicts no physical joint response. Its e-stop keeps
qpos, qvel and ctrl; clearing the latch alone integrates nothing, while a later explicit world step may reuse ctrl.

The repository license is Apache-2.0; the selected model and meshes retain their own BSD-3-Clause license and
attribution in `robot/g1_29dof/LICENSE` and `NOTICE`. No model or mesh is redistributed by this package.

## Entry symbol

The card's `entry_symbols` names `eval.wbt_rollout:G1Sim`; the class is at eval/wbt_rollout.py:199 and wraps the
card model, and its `step` calls `mujoco.mj_step` (eval/wbt_rollout.py:415-416). The MuJoCo family serves the model
the class wraps through the catalogue's `cap.world.step.v1` and `cap.world.reset.v1`; the class's PD controller,
q_target interface and observation builder are not part of the family contract.
