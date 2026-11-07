# Facts and tags for gh.isri-aist/jvrc_mj_description

Every fact cites its source at commit `8cfc65f5c5793582b55e0d5eb4726dfb3094a224`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF or CMake file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF scene `xml/scene.xml` (`models[0]`), as a `MujocoDriver`. The
scene includes `xml/jvrc1.xml`, so the loaded model is the humanoid robot in the textured scene. The package reads
the model file from the read-only clone; it copies neither the model nor its meshes.

| fact | source | ref |
|---|---|---|
| The package's model is the MJCF scene xml/scene.xml, whose root element is '<mujoco model="jvrc1 scene">' and which includes jvrc1.xml | upstream_code | xml/scene.xml:1-3 |
| jvrc1.xml declares '<compiler angle="radian" meshdir="../meshes" texturedir="../meshes"/>', so the joint ranges are radians and its meshes and textures resolve from ../meshes | upstream_code | xml/jvrc1.xml:4 |
| The model sets '<option timestep="0.001" iterations="50" tolerance="1e-10" solver="Newton" jacobian="dense" cone="pyramidal"/>', so its integration step is 0.001 s | upstream_code | xml/jvrc1.xml:8 |
| The model sets '<size njmax="500" nconmax="100"/>' | upstream_code | xml/jvrc1.xml:6 |
| The jvrc1 default class gives its joints limited="true" and damping="0.2" and its motors ctrllimited="false" forcelimited="false" | upstream_code | xml/jvrc1.xml:11-13 |
| The robot's root body PELVIS_S is placed at pos="0 0 1.4" and has a freejoint named root | upstream_code | xml/jvrc1.xml:206-207 |
| The R_HIP_P joint is a hinge with range -2.0944 to 0.785398 rad and armature 0.1925 | upstream_code | xml/jvrc1.xml:216 |
| The L_KNEE joint is a hinge with range 0 to 2.61799 rad and armature 0.1305 | upstream_code | xml/jvrc1.xml:265 |
| The contact section excludes adjacent pelvis, knee, waist, neck, shoulder, elbow and gripper body pairs from collision | upstream_code | xml/jvrc1.xml:143-200 |
| Ten equality constraints couple the five distal finger joints of each hand to its thumb with polycoef values | upstream_code | xml/jvrc1.xml:480-492 |
| The actuator section has one motor for each leg, waist, neck, shoulder, elbow, wrist and thumb joint, and no motor for the distal finger joints | upstream_code | xml/jvrc1.xml:495-536 |
| The sensor section reads force and torque at both feet and both hands and a gyro and accelerometer at the imu site | upstream_code | xml/jvrc1.xml:538-554 |
| The repository provides JVRC1 model files for MuJoCo and installs the files in the directory so that mc_mujoco can pick them up automatically | vendor_doc | README.md:5 |
| The CMake build sets JVRC1_XML_MODEL_PATH to xml/jvrc1.xml and JVRC1_PDGAINS_PATH to pdgains/PDgains_sim.dat | upstream_code | CMakeLists.txt:14-15 |
| The mc_mujoco configuration template sets xmlModelPath and pdGainsPath to the installed model and PD-gains paths | upstream_code | mc_mujoco/jvrc1.in.yaml:1-2 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator from `actuator_ctrlrange`. This model's `jvrc1` motor class sets `ctrllimited="false"` and
`forcelimited="false"` (`xml/jvrc1.xml:11-13`) and the 34 motors of `xml/jvrc1.xml:495-536` declare no
`ctrlrange`: the model states no actuator control interval, so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. No bound was copied from a catalogue
default or invented. The derived per-actuator dimension is the model's actuator count, not a safety bound.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for
the joint dimensions (a free root joint plus 44 hinges in this model) and the actuator list (34 motors), but its
integration is a placeholder first-order motion and it resolves no mesh, contact, equality, tendon or sensor.
MuJoCo was not importable where the gate ran, so no trajectory was compared with the real engine. The gaps are
listed in the `fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a
backend that imports MuJoCo.

Tags: humanoid, jvrc1, mujoco, robot, simulation, whole-body
