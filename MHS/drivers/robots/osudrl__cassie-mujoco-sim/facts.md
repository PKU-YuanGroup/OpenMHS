# Facts and tags for gh.osudrl/cassie-mujoco-sim

Every fact cites its source at commit `188d3d7f04f0c4ed12db66bdec67884e1c0eb743`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a simulation library for Agility Robotics' Cassie robot using MuJoCo | vendor_doc | README.md:3 |
| CassieSim.step_pd calls cassie_sim_step_pd | upstream_code | example/cassiemujoco.py:69-72 |
| cassie_sim_step_pd simulates one step of the Cassie simulator with PD input and state estimator output | upstream_code | include/cassiemujoco.h:92-95 |
| The model timestep is 0.0005 s because the controller runs at 2 kHz | upstream_code | model/cassie.xml:5-6 |
| The ten actuators are the two legs' hip roll, hip yaw, hip pitch, knee and foot motors, with gear ratios 25, 25, 16, 16 and 50 and ctrlrange +-4.5, +-4.5, +-12.2, +-12.2 and +-0.9 in the motor order | upstream_code | model/cassie.xml:258-267 |
| motor() computes the motor-side torque as the output-side torque divided by the actuator gear, clamps it to actuator_ctrlrange and writes data.ctrl | upstream_code | src/cassiemujoco.c:641-658 |
| cassie_sim_full_reset copies a 35-element initial qpos and zeroes qvel, ctrl, qfrc_applied, xfrc_applied and qacc, clears the torque delay and reinitializes the state estimator; it does not write the simulator time | upstream_code | src/cassiemujoco.c:2008-2032 |
| CassieSim.set_time writes the simulator time | upstream_code | example/cassiemujoco.py:144-146 |
| The state read-back methods take a slice of the MuJoCo data: qpos is the first nq entries, qvel the first nv entries and ctrl the first nu entries | upstream_code | example/cassiemujoco.py:104-134 |

Limits: one limit on `cap.world.step.v1` `action.ctrl`, per element, the ten `actuator_ctrlrange` values of
`model/cassie.xml:258-267` (motor-side actuator control, unit `1`). No text of the clone states any other numeric
bound for this interface, so no other limit is declared and none is `operator_required`: the device is simulated
(R0) and every input the driver accepts is bounded by the model or the catalogue class. The `ticks` input inherits
the catalogue class's 1 to 10000 integer bounds through the binding merge; it is not a device limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco`, level F1 (rigid-body dynamics with contacts,
based on the upstream MuJoCo model), determinism `none` with `seed_control` `none` (the class exposes no full
snapshot and `full_reset` does not clear MuJoCo's warm-start accelerations, so no replay equality is claimed),
timestep 0.5 ms (`model/cassie.xml:5`), `realtime_factor` 0, clock `lockstep`, reset `partial` (model data, torque
delay and estimator are reset; the time is set to zero by the driver, the warm-start accelerations are not cleared)
and no snapshot/restore. The gaps say that the fake is not MuJoCo and was never compared with the upstream library.

Safety: simulated R0 device. There is no hardware backend and no native stop; the e-stop is the runtime's software
latch. After it, no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays
readable. No independent hardware e-stop, no hardware run and no human review are claimed.

Mock path: the card prefers `upstream-sim`, but the upstream simulator is the ctypes wrapper over a MuJoCo 2.10 build
(`Makefile:5`, `include/cassiemujoco.h:110-190`); it is not installed by the card and package code may not import or
run the clone. `fake.py` is therefore the package's own pure Python stand-in, with exactly the public methods of
`CassieSim` that the driver calls. Every number in it is placeholder test data.

Tags: cassie, mujoco, robot, simulation, biped, world
