# Facts and tags for gh.nely-epfl/flygym

Every fact cites its source at commit `38c8ec61034cd59bc5ba0de20688d4a3c0000d60`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF document `src/flygym/assets/model/flybody/fruitfly.xml`
(`models[0]`), as a `MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the
model nor its mesh assets, and it does not import the upstream Python package. The card's entry symbol
`flygym_demo.muscle_imitation.env:ImitationEnv` was confirmed at `src/flygym_demo/muscle_imitation/env.py:83`: it is
a Gymnasium environment that needs a pre-built `flygym.Simulation`, gymnasium, numpy and the upstream package to
construct. The card's `models` list and the `MujocoDriver` helper describe the MJCF model itself, so the package serves
`models[0]` as PLAYBOOK.md section 8 directs for MuJoCo cards.

| fact | source | ref |
|---|---|---|
| FlyGym is the Python library for NeuroMechFly v2, a digital twin of the adult fruit fly Drosophila melanogaster | vendor_doc | README.md:25 |
| The biomechanical model is based on a micro-CT scan of a real adult female fly | vendor_doc | README.md:28 |
| The card's first model is the MJCF document whose root element is '<mujoco model="fruitfly">' | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:1 |
| The model compiles angles in radians and derives limits automatically (autolimits true) | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:2 |
| The model integrates at 0.0001 s per step (0.1 ms) with gravity 0 0 -981 | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:4 |
| The thorax is a free-floating body: the model declares the freejoint named free on the thorax body | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:299-300 |
| The wing default class gives its actuators a control range of -1 to 1 | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:57-59 |
| The six wing actuators are wing_yaw_left, wing_roll_left, wing_pitch_left, wing_yaw_right, wing_roll_right and wing_pitch_right | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:957-962 |
| The adhesion default classes give the labrum and claw adhesion actuators a control range of 0 to 1 | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:28-34 |
| The eight adhesion actuators are adhere_labrum_left, adhere_labrum_right and the claw actuators adhere_claw_T1, T2 and T3 for the left and right sides | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:1013-1021 |
| The leg default classes declare control ranges such as twist_coxa_T1 -0.8 to 0.8, abduct_coxa_T1 -1 to 0.7, extend_coxa_T1 -0.2 to 1.7, twist_femur -1 to 1, extend_femur -0.15 to 2, extend_tibia -1.35 to 1.3 and extend_tarsus -0.36 to 0.36 | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:98-193 |
| The actuator section declares 78 actuators: 70 general actuators driving head, antenna, wing, abdomen, leg, tarsus and tendon targets, and 8 adhesion actuators attached to the labrum and the six claws | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:943-1021 |
| The model declares 15 sensors: an accelerometer, a gyro and a velocimeter on the thorax, six force sensors on the tarsi and six touch sensors on the claws | upstream_code | src/flygym/assets/model/flybody/fruitfly.xml:1023-1038 |

Limits: the package declares none of its own. The bridge derives `cap.world.step.v1`'s `action.ctrl` from the served
model: one interval per actuator, from `actuator_ctrlrange` in the model file (upstream_code, fruitfly.xml:943-1021;
the wing interval is at 57-59, the leg intervals at 98-193 and the adhesion interval at 28-34), and the class source of
that derived limit is the model (`mhs.bridge.mujoco`). Every one of the 78 actuators states a finite control range, so
no interval is `operator_required`. `ticks` is bounded by the catalogue class (1 to `max_ticks`, 10000 by default),
not by a device bound. The device is simulated (R0), so no limit is `operator_required` and no
`site-limits.example.json` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:fruitfly`, level F1. Determinism is `exact`: the
model has no random element and MuJoCo integrates it deterministically from the reset state. The bridge reads the time
step from `model.opt.timestep`; the served model sets 0.0001 s (fruitfly.xml:4), so the published `timestep_ms` is
0.1. `realtime_factor` 0, clock `lockstep`, reset `full`. The fake implements the integration-state snapshot
functions, so `snapshot_restore` is true. The gaps say that the stand-in is not the engine (no mesh, contact,
adhesion, exclusion, tendon, inertia or actuator dynamics), that the 15 sensors and nine cameras are not exposed, that
the card's Gymnasium entry symbol is not run, and that no trajectory was compared with MuJoCo or with a physical fly.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the world
state stays readable. The catalogue classes `cap.world.step.v1` and `cap.world.reset.v1` are R0.

Tags: fruitfly, neuromechfly, drosophila, mujoco, simulation, fly, biomechanics
