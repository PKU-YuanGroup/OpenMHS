# Facts and tags for gh.google-deepmind/mujoco_menagerie

Every fact cites its source at commit `0059d4335f8156206f63a35662313385f7ad6d74`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (an MJCF or Python file of the clone). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF scene `agilex_piper/scene.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model file from the read-only clone; the package copies neither the model nor its assets.

| fact | source | ref |
|---|---|---|
| The package's model is the MJCF scene agilex_piper/scene.xml, whose root element is '<mujoco model="piper_scene">' and which includes piper.xml | upstream_code | agilex_piper/scene.xml:1-2 |
| piper.xml declares '<compiler angle="radian" meshdir="assets"/>', so the joint ranges of the model are radians and its meshes are resolved from assets/ | upstream_code | agilex_piper/piper.xml:2 |
| The model uses the implicitfast integrator with an elliptic friction cone and impratio 10, and its <option> element sets no timestep | upstream_code | agilex_piper/piper.xml:4 |
| The piper default class sets frictionloss 0.3 and armature 0.005 on its joints and gives its position actuators inheritrange 1 and forcerange -100 to 100 | upstream_code | agilex_piper/piper.xml:8-9 |
| The finger default class inherits the piper class and overrides the joints to type slide with frictionloss 0 and the position actuators to forcerange -10 to 10 | upstream_code | agilex_piper/piper.xml:10-13 |
| The body base_link sets childclass piper, so the joints and geoms below it use the piper defaults | upstream_code | agilex_piper/piper.xml:120 |
| joint1 is a hinge with range -2.618 to 2.618 rad | upstream_code | agilex_piper/piper.xml:128 |
| joint2 is a hinge with range 0 to 3.14 rad | upstream_code | agilex_piper/piper.xml:134 |
| joint3 is a hinge with range -2.697 to 0 rad | upstream_code | agilex_piper/piper.xml:171 |
| joint4 is a hinge with range -1.832 to 1.832 rad | upstream_code | agilex_piper/piper.xml:204 |
| joint5 is a hinge with range -1.22 to 1.22 rad | upstream_code | agilex_piper/piper.xml:214 |
| joint6 is a hinge with range -3.14 to 3.14 rad | upstream_code | agilex_piper/piper.xml:226 |
| joint7 is a slide joint with range 0 to 0.035 m | upstream_code | agilex_piper/piper.xml:232 |
| joint8 is a slide joint with range -0.035 to 0 m | upstream_code | agilex_piper/piper.xml:240 |
| The model has seven position actuators: joint1 to joint6, and a gripper actuator on joint7 | upstream_code | agilex_piper/piper.xml:262-269 |
| The gripper actuator of joint7 has kp 40 and kv 5; joint1 to joint3 have kp 80 and kv 5, joint4 has kp 40 and kv 5, and joint5 and joint6 have kp 10 and kv 1.5 | upstream_code | agilex_piper/piper.xml:263-269 |
| joint7 and joint8 are coupled by an equality constraint with polycoef '0 -1 0 0 0', so the right finger mimics the left | upstream_code | agilex_piper/piper.xml:258-259 |
| The model has a home keyframe with qpos '0 1.57 -1.3485 0 0 0 0 0' and ctrl '0 1.57 -1.3485 0 0 0 0' | upstream_code | agilex_piper/piper.xml:272-273 |
| The package's description is a simplified MJCF of the AgileX PiPER, derived from the publicly available PiPER ROS model | vendor_doc | agilex_piper/README.md:12 |
| The model adds position controlled actuators | vendor_doc | agilex_piper/README.md:29 |
| The scene adds a textured groundplane, a skybox and haze | vendor_doc | agilex_piper/README.md:31 |
| The model requires MuJoCo 2.3.4 or later | vendor_doc | agilex_piper/README.md:4 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`). `piper.xml:9` sets `inheritrange="1"` on the piper position actuators, so each
position actuator inherits the range of the joint it drives; the seven intervals are the joint ranges of
`piper.xml:128`, `:134`, `:171`, `:204`, `:214`, `:226` and `:232`. The class source is `upstream_code` and the
reference is the model file, so no driver-declared or `operator_required` bound is needed.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for
the joint count, the actuator count and the control ranges, but its integration is a placeholder first-order motion,
and it resolves no mesh, contact, equality or tendon constraint. MuJoCo was not importable where the gate ran, so no
trajectory was compared with the real engine. The gaps are listed in the `fidelity` attribute of `driver.py`; a site
that needs MuJoCo's physics runs the driver with a backend that imports MuJoCo.

Tags: agilex, arm, manipulator, menagerie, mujoco, piper, robot, simulation
