# Facts and tags for gh.unitreerobotics/unitree_mujoco

Every fact cites its source at commit `1eb6642e3f3fdfb7fb13a9794fd6a2dd93ea0e7d`: `vendor_doc` (a text file of the
clone such as readme.md) or `upstream_code` (an MJCF or Python file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's `unitree_robots/h2/scene.xml` (models[2]) as a simulated R0 `world.sim`. It reads the
scene from the read-only clone; the package copies neither the model nor its meshes. The card's models[0]
`unitree_robots/h1/scene.xml` is not served because its `not_use_joint` motor has no `ctrlrange`
(`unitree_robots/h1/h1.xml:209`), so the bridge would publish an unbounded control interval for it; the H2 model
states a `ctrlrange` for all 31 motors.

| fact | source | ref |
|---|---|---|
| The package's model is the MJCF scene unitree_robots/h2/scene.xml, whose root element is '<mujoco model="Unitree H2">' and which includes h2_mujoco.xml | upstream_code | unitree_robots/h2/scene.xml:1-2 |
| h2_mujoco.xml declares '<compiler angle="radian" meshdir="meshes/"/>', so the joint ranges and the control ranges of the model are radians and its meshes are resolved from meshes/ | upstream_code | unitree_robots/h2/h2_mujoco.xml:2 |
| The model sets the integration step to 0.001 s | upstream_code | unitree_robots/h2/h2_mujoco.xml:8 |
| The model's floating base is the joint floating_base_joint of type free | upstream_code | unitree_robots/h2/h2_mujoco.xml:47 |
| The actuator block has 31 <motor> elements, one per actuated hinge joint, and every motor states a ctrlrange | upstream_code | unitree_robots/h2/h2_mujoco.xml:241-277 |
| The leg motors state ctrlrange +-360 for the hip pitch, hip roll, hip yaw and knee, +-19 for the ankle roll and +-66.88 for the ankle pitch | upstream_code | unitree_robots/h2/h2_mujoco.xml:242-254 |
| The waist motors state ctrlrange +-120 for the waist yaw and +-180 for the waist roll and waist pitch | upstream_code | unitree_robots/h2/h2_mujoco.xml:256-258 |
| The arm motors state ctrlrange +-130 for the shoulder pitch, +-60 for the shoulder roll, shoulder yaw, elbow and wrist roll, and +-10 for the wrist pitch and wrist yaw | upstream_code | unitree_robots/h2/h2_mujoco.xml:260-274 |
| The head motors state ctrlrange +-50 for the head pitch and head yaw | upstream_code | unitree_robots/h2/h2_mujoco.xml:276-277 |
| The left hip pitch joint has range -2.4526 to 2.77542 rad | upstream_code | unitree_robots/h2/h2_mujoco.xml:52 |
| The left ankle roll joint has range -0.349066 to 0.296706 rad | upstream_code | unitree_robots/h2/h2_mujoco.xml:71 |
| The left wrist pitch joint has range -0.576 to 0.576 rad | upstream_code | unitree_robots/h2/h2_mujoco.xml:181 |
| The repository describes itself as a simulator developed based on Unitree sdk2 and mujoco | vendor_doc | readme.md:3 |
| The unitree_robots directory holds the MJCF description files for the robots supported by unitree_sdk2 | vendor_doc | readme.md:9 |
| The Python simulator loads the scene with mujoco.MjModel.from_xml_path and creates the MjData | upstream_code | simulate_python/unitree_mujoco.py:15-16 |
| The Python simulator overrides the model timestep with config.SIMULATE_DT | upstream_code | simulate_python/unitree_mujoco.py:31 |
| config.py sets SIMULATE_DT to 0.005 s | upstream_code | simulate_python/config.py:13 |
| UnitreeSdk2Bridge reads num_motor from mj_model.nu and its step from mj_model.opt.timestep | upstream_code | simulate_python/unitree_sdk2py_bridge.py:40-44 |
| UnitreeSdk2Bridge maps a Unitree LowCmd motor command to data.ctrl as tau + kp*(q - sensordata) + kd*(dq - sensordata) | upstream_code | simulate_python/unitree_sdk2py_bridge.py:111-123 |
| The Python simulator publishes and subscribes the DDS topics rt/lowcmd, rt/lowstate and rt/sportmodestate | upstream_code | simulate_python/unitree_sdk2py_bridge.py:25-27 |
| The Python simulator needs unitree_sdk2_python and mujoco-python, installed with pip3 | vendor_doc | readme.md:97-115 |

Limits: the driver declares none. The bridge derives the `cap.world.step.v1` input `action.ctrl` from the model
itself, one interval per actuator (`actuator_ctrlrange`); the 31 intervals are the ctrlrange values of
`unitree_robots/h2/h2_mujoco.xml:242-277`. The model's joint ranges (`h2_mujoco.xml:52`, `:71`, `:181`, and the
others) are not the action bound: the step input is `data.ctrl`, and the bridge checks it against the actuator
control ranges. The class source is `upstream_code` and the reference is the model file, so no driver-declared or
`operator_required` bound is needed. The device is simulated (R0), so no operator overlay is needed.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It parses the scene and its
include for the joint count, the actuator count, the control ranges and the 0.001 s timestep, but integrates a
placeholder torque response and resolves no mesh, texture, contact, constraint, gravity, inertia or sensor. MuJoCo
was not importable where the gate ran, so no trajectory was compared with the real engine. The upstream Python
simulator uses a different loop: it overrides the model timestep with `SIMULATE_DT = 0.005` s
(`simulate_python/unitree_mujoco.py:31`, `simulate_python/config.py:13`) and maps Unitree LowCmd messages into
`data.ctrl` (`simulate_python/unitree_sdk2py_bridge.py:111-123`); this driver loads the scene directly and keeps the
model's 1 ms step. The gaps are listed in the `fidelity` attribute of `driver.py`.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. There is no hardware stop to cite and no `operator_required` limit.

Tags: h2, humanoid, mujoco, robot, simulation, unitree
