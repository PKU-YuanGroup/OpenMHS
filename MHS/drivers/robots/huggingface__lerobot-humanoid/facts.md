# Facts and tags for gh.huggingface/lerobot-humanoid

Every fact cites its source at commit `d0b0d9c51853a1e821a12186e9796cded1b79b4b`: `vendor_doc` (a text file of
the clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's primary model, the MJCF scene
`lerobot-humanoid-model/models/bipedal_plateform/mjcf/scene.xml` (`models[0]`), as a `MujocoDriver`. It reads the
model file from the read-only clone; neither the model nor its assets are copied into the package. The model
directory is a git submodule: the pinned superproject commit records `lerobot-humanoid-model` as a gitlink
(`160000 commit ea23cbac9b79833eff974d9196a7edb8043effb6` in `git ls-tree`), so no formal Fact cites a line inside
it: gate G4 reads the superproject tree and would report `REF_MISSING`. The bridge still loads the scene from the
checkout and derives `action.ctrl` from its `actuator_ctrlrange` at run time; that derived limit is not a package
Fact.

| fact | source | ref |
|---|---|---|
| The workspace groups the full LeRobot humanoid project from design to deployment, including mechanical/control co-design, hardware build assets, robot model assets, the runtime and deployment stack, and simulation-based identification | vendor_doc | README.md:3-9 |
| Each folder of the workspace is an independent Git repository with its own history and remotes | vendor_doc | README.md:11 |
| The project aims to build an open and practical low-cost humanoid robot that people can reproduce | vendor_doc | README.md:15 |
| The hardware cost target is less than USD 5,000, depending on sourcing, shipping and taxes | vendor_doc | README.md:19 |
| The design prioritizes 3D-printed custom mechanical parts that are printable and documented | vendor_doc | README.md:21 |
| The lerobot-humanoid-model repository provides versioned MJCF/URDF robot model assets and Python helpers (lerobot_humanoid_models) that the runtime and identification repositories consume | vendor_doc | README.md:40 |
| The lerobot-humanoid-runtime repository makes the robot move in simulation and on real hardware, with controllers, calibration, policy execution and deployment | vendor_doc | README.md:41 |
| The lerobot-humanoid-identification repository replays real logs and tunes simulator parameters with batched replay and CMA-ES identification | vendor_doc | README.md:42 |
| The workspace was initially developed by Virgile Batto during his time at Hugging Face LeRobot | vendor_doc | README.md:97 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator (`actuator_ctrlrange`; the bridge's source is `upstream_code` and its reference is the model file). The
package declares no limit of its own and no `operator_required` bound, because the model file is the system of
record for the control envelope. The runtime refuses an out-of-range element before writing `data.ctrl`.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the scene for the
actuator count, the control ranges, the joint dimensions and the option time step, but its integration is a
placeholder velocity proportional to each control value and it resolves no mesh, contact, equality, tendon or
actuator constraint. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was
compared with the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`.

The card's other models (the no-arms and lerobot_humanoide MJCF scenes, the fixed-base scene and the identification
copies) are not served: one package serves one device, and the driver and fake use `models[0]`.

Tags: huggingface, lerobot, humanoid, bipedal, mujoco, simulation, robot
