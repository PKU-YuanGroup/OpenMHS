# Facts and tags for gh.google-deepmind/mujoco_mpc

Every fact cites its source at commit `ff572a21e7c2bf9fda62e1862a758da7e9a8719b`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's `models[0]`, the MJCF task `mjpc/tasks/fingers/task.xml`, as a `MujocoDriver`. It
reads the model file (and its `../common.xml` include) from the read-only clone; the package copies neither the model
nor its assets.

| fact | source | ref |
|---|---|---|
| MJPC is an interactive application and software framework for real-time predictive control with MuJoCo, developed by Google DeepMind | vendor_doc | README.md:14-16 |
| MJPC supports multiple shooting-based planners: iLQG and Gradient Descent are derivative-based and Predictive Sampling is derivative-free | vendor_doc | README.md:18-21 |
| An MJPC task needs an MJCF file that describes the simulated model and the task parameters and a C++ file that implements the residual | vendor_doc | docs/OVERVIEW.md:108-111 |
| The Fingers task loads fingers/task.xml from XmlPath and is named FreeFingers | upstream_code | mjpc/tasks/fingers/fingers.cc:25-28 |
| The Fingers task is registered in the MJPC task list | upstream_code | mjpc/tasks/tasks.cc:54 |
| The task XML's root model is named 'Free-Floating Fingers' | upstream_code | mjpc/tasks/fingers/task.xml:1 |
| The task XML includes ../common.xml, the shared visual assets and materials | upstream_code | mjpc/tasks/fingers/task.xml:2 |
| The model integrates with timestep 0.001 s, an elliptic friction cone, five noslip iterations and the implicit integrator | upstream_code | mjpc/tasks/fingers/task.xml:4 |
| The object and target bodies each have a free joint and a box geom; the object's collision default class sets mass 0.2 and its visual class mass 0.001 | upstream_code | mjpc/tasks/fingers/task.xml:43-68 |
| The finger_a and finger_b bodies each have three slide joints along x, y and z | upstream_code | mjpc/tasks/fingers/task.xml:73-84 |
| The six intvelocity actuators A_x, A_y, A_z, B_x, B_y and B_z each have ctrlrange -.99 to .99, ctrllimited true and kp 1000; the x and y actranges are -1 to 1 and the z actranges 0 to 1.4 | upstream_code | mjpc/tasks/fingers/task.xml:93-100 |
| The home keyframe holds 20 qpos values (two free joints of 7 and six slides) and 6 act values | upstream_code | mjpc/tasks/fingers/task.xml:20-34 |
| The sensors are the user sensors Reach (dim 6), Bring (dim 3) and Control (dim 6), plus framepos sensors for both fingers, the object and the six sites | upstream_code | mjpc/tasks/fingers/task.xml:101-114 |
| The Fingers residual subtracts each finger's position from the object's, writes the distance of three object sites to their target sites, and copies data->ctrl for each of model->nu actuators | upstream_code | mjpc/tasks/fingers/fingers.cc:34-54 |

Limits: the driver declares none. The bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself
(one interval per actuator, `actuator_ctrlrange`; the class source is `upstream_code` and the reference is the model
file at the pinned commit), so no `operator_required` bound is needed and no number is copied into a `Limit`. The
model's own step is 0.001 s (`task.xml:4`), and `ticks` is the class input (1 to 10000).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:Free-Floating Fingers`, level F1, realtime factor
0, lockstep clock, full reset. The gaps say what is not modelled: the fake backend is a stand-in for the `mujoco`
library with a placeholder first-order integration, no contacts, friction, inertia, actuator or sensor dynamics, no
free-body motion, meshes or textures; MuJoCo was not importable where the gate ran, so no trajectory was compared
with the engine; the MJPC residual, planners and GUI are not served; the home keyframe is not applied by the bridge's
reset; snapshots use the bridge's fallback copy; there is no rendering and no physical device.

Safety: simulated R0 device (`world.sim`). The e-stop is the runtime's software latch; no native stop exists and no
physical stop is claimed. After the latch no step or reset is accepted until `mhs.safety.reset` clears it, and the
integration state stays readable.

Tags: mujoco, mujoco-mpc, simulation, manipulation, fingers, world-sim
