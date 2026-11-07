# Facts and tags for gh.simple-robotics/simple

Every fact cites its source at commit `03d4784ed87b2b4986c74564d20ef5544b30936d`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF or Python file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF `sandbox/robots/humanoid.xml` (`models[0].file`), as a
configuration-only `MujocoDriver`. The model file and the sandbox scripts are read from the read-only clone in place;
the package copies neither the model nor its assets and does not import or run upstream code.

## Scope and shape

The card is `family: ros` with the `RosDriver` helper, but the clone has no ROS endpoint: `cmake/ros.cmake` and
`cmake/ros2.cmake` are build helpers, and no publisher, subscriber, service or action server is declared. The
upstream is a C++ physics engine with pybind11 bindings (`bindings/python/.../expose-simulator.cpp`), and the card's
model is a MuJoCo MJCF. The upstream itself runs that model in MuJoCo with `--mujoco` (`sandbox/humanoid_mj.py:115-116`,
`sandbox/sim_utils.py:253-279`), so this package uses the `MujocoDriver` family for that model. This is a deviation
from the card helper, recorded in `RESULT.json`. The Simple-engine loop (`sandbox/humanoid_mj.py:84-88`) is not
exposed: its class is C++/pybind, it is not installed here, and the clone has no Python `step`/`reset` class for a
direct driver's native surface. The served MJCF is DeepMind's Humanoid model (Apache License 2.0, header at
`sandbox/robots/humanoid.xml:1-13`) as copied into the sandbox, which the sandbox runs for comparison with the
Simple engine; the Simple engine itself (`simple.Simulator`) is not served by this package.

| fact | source | ref |
|---|---|---|
| Simple is a differentiable physics engine that uses Pinocchio for dynamics computations and Coal for collision detection | vendor_doc | README.md:3 |
| The upstream README states the code is released under the permissive BSD-3 license | vendor_doc | README.md:7 |
| The simple Python package re-exports the compiled simple_pywrap extension | upstream_code | bindings/python/simple/__init__.py:7 |
| exposeSimulator exposes the C++ Simulator class through SimulatorPythonVisitor | upstream_code | bindings/python/core/expose-simulator.cpp:12-14 |
| The sandbox imports mujoco in a try block and sets mujoco_imported false when the optional dependency is missing | upstream_code | sandbox/sim_utils.py:11-17 |
| runMujocoXML prints 'Can't run, need to install mujoco' when the optional mujoco import failed | upstream_code | sandbox/sim_utils.py:253-255 |
| The humanoid sandbox script sets its model path to ./sandbox/robots/humanoid.xml | upstream_code | sandbox/humanoid_mj.py:27 |
| Without --mujoco the script builds a Pinocchio model and geometry from the MJCF | upstream_code | sandbox/humanoid_mj.py:29-34 |
| The Simple-engine loop calls sim.reset() and sim.step(q, v, zero_torque, dt) | upstream_code | sandbox/humanoid_mj.py:84-88 |
| With --mujoco the script calls runMujocoXML on the same model path | upstream_code | sandbox/humanoid_mj.py:115-116 |
| SimulationArgs.dt defaults to 1e-3 s | upstream_code | sandbox/sim_utils.py:20-22 |
| runMujocoXML loads an .xml model with mujoco.MjModel.from_xml_path, creates MjData and calls mujoco.mj_step | upstream_code | sandbox/sim_utils.py:253-279 |
| runMujocoXML sets the loaded model's opt.timestep to args.dt | upstream_code | sandbox/sim_utils.py:262 |
| The served model file carries a DeepMind Technologies Limited copyright notice and the Apache License, Version 2.0 | upstream_code | sandbox/robots/humanoid.xml:1-13 |
| The served model file is the MuJoCo Humanoid model | upstream_code | sandbox/robots/humanoid.xml:16 |
| The model's option element sets a 0.005 s timestep | upstream_code | sandbox/robots/humanoid.xml:17 |
| The top-level default motor element sets ctrlrange -1 1 with ctrllimited true | upstream_code | sandbox/robots/humanoid.xml:36 |
| The torso body starts at 0 0 1.282 and carries a freejoint named root | upstream_code | sandbox/robots/humanoid.xml:110-113 |
| The model has 21 hinge joints: three abdomen, six per leg (hip x/z/y, knee, ankle y/x) and three per arm (shoulder1, shoulder2, elbow) | upstream_code | sandbox/robots/humanoid.xml:122-178 |
| The worldbody has a floor box with size 10 10 0.1 at position 0 0 -0.1 | upstream_code | sandbox/robots/humanoid.xml:107 |
| The contact section excludes waist_lower against thigh_right and thigh_left | upstream_code | sandbox/robots/humanoid.xml:188-191 |
| Two fixed tendons named hamstring_right and hamstring_left couple hip_y and knee with coefficients .5 and -.5 and a range of -0.3 to 2 | upstream_code | sandbox/robots/humanoid.xml:193-202 |
| The model has 21 motor actuators, one per hinge joint, each with an explicit gear | upstream_code | sandbox/robots/humanoid.xml:204-225 |
| The model defines four keyframes: squat, stand_on_left_leg, prone and supine | upstream_code | sandbox/robots/humanoid.xml:228-268 |

## Limits

The package declares no `Limit` of its own. The bridge derives `cap.world.step.v1`'s `action.ctrl` from each
actuator's `ctrlrange` and `ctrllimited` (`mhs.bridge.mujoco.MujocoBridge.action_limits`). The model's top-level
`<motor ctrlrange="-1 1" ctrllimited="true"/>` (`sandbox/robots/humanoid.xml:36`) is inherited by the 21 motor
elements, which carry no `class` attribute (`sandbox/robots/humanoid.xml:204-225`), so the reference publishes one
interval per actuator, all `-1` to `1`. No operator-required bound is declared because the model file is the system of
record for the control envelope.

## Fidelity

The fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the model for the free joint
and 21 hinge joints, the 21 motor actuators, the inherited control range and the 0.005 s option step, but its
integration is a placeholder first-order motor model. It does not integrate the free base, resolve the floor contact,
apply the two hamstring tendons, the contact exclusions, the joint ranges, damping, stiffness, armature or gear
forces, and it does not reproduce the real model's qpos0 or the four keyframes. MuJoCo was not importable where the
gate ran (no network, no pip), so no trajectory was compared with the real engine. `driver.py` declares the real
engine's contract (`mujoco:Humanoid`, F1, used by the implicit `sim` backend) in `fidelity` and the stand-in's own
contract (`analytic:stand-in mujoco module (no physics)`, F0) in `fidelity_by_backend["fake"]`, each with its gaps.

Tags: simple, simulation, mujoco, humanoid, physics, reinforcement-learning
