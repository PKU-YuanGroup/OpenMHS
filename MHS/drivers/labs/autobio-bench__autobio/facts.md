# Facts and tags for gh.autobio-bench/autobio

Every fact cites its source at commit `08504213356cbfe9a82bcd33a43cd282945a45df`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF or Python file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF `autobio/model/hand/dexhand021_right.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model file from the read-only clone in place; the package copies neither the model nor
its STL assets.

| fact | source | ref |
|---|---|---|
| AutoBio is a simulation and benchmark for robotic automation in a digital biology laboratory | vendor_doc | README.md:3 |
| The autobio package installs mujoco==3.3.0 and its model/ folder holds simulation-ready lab assets and scenes in the MJCF language | vendor_doc | autobio/README.md:12-20 |
| The served model is 'dexhand021_right_sim' | upstream_code | autobio/model/hand/dexhand021_right.xml:2 |
| The model uses radian angles, resolves its meshes from ../../assets and uses autolimits; its option element sets the implicitfast integrator, a 0.01 s timestep, an elliptic cone and impratio 10 | upstream_code | autobio/model/hand/dexhand021_right.xml:3-5 |
| The base body rh_base carries no joint, so the hand is fixed to the world frame | upstream_code | autobio/model/hand/dexhand021_right.xml:37-40 |
| The hand has 19 hinge joints: four for the thumb, index, ring and little finger and three for the middle finger | upstream_code | autobio/model/hand/dexhand021_right.xml:42-144 |
| Every joint range starts at zero; for example rh_thj1 is 0 to 2.2 rad and rh_ffj1 is 0 to 0.3 rad | upstream_code | autobio/model/hand/dexhand021_right.xml:42-65 |
| Seven equality constraints couple joint pairs; the ring and little finger base joints are tied to the index base joint with polycoef '0 1' and '0 2' | upstream_code | autobio/model/hand/dexhand021_right.xml:201-205 |
| The model has twelve position actuators: seven act on joints and five act on tendon transmissions | upstream_code | autobio/model/hand/dexhand021_right.xml:208-220 |
| Each actuator has an explicit ctrlrange; rh_thj1 is 0 to 2.2, rh_fft1 is 0 to 0.3, and the other actuators are 0 to 1.3 | upstream_code | autobio/model/hand/dexhand021_right.xml:209-220 |

Limits: the bridge derives `cap.world.step.v1`'s `action.ctrl` from each actuator's `ctrlrange`
(`mhs.bridge.mujoco.MujocoBridge.action_limits`). The model's twelve `<position>` elements carry explicit `ctrlrange`
values (`autobio/model/hand/dexhand021_right.xml:209-220`), so the bridge publishes one interval per actuator and the
package declares no `Limit` of its own. The joint `range` and `actuatorfrcrange` values are model facts, not limits of
this driver. No operator-required bound is declared because the model file is the system of record for the control
envelope.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the model for the 19
hinge joints, the twelve position actuators, their explicit control ranges and the 0.01 s option step, but its
integration is a placeholder first-order motion. It has no transmission model, so the five tendon actuators move no
joint; it applies no equality, contact, damping, armature or force limit; it loads no STL mesh; and its reset restores
zeros. MuJoCo itself was not importable where the gate ran (no network, no pip), so no trajectory was compared with
the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`.

Tags: autobio, dexhand, dexhand021, hand, mujoco, robot, simulation
