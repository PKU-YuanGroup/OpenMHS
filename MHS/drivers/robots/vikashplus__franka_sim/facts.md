# Facts and tags for gh.vikashplus/franka_sim

Every fact cites its source at commit `b54d271388cf9b179d3fb6cff7a430040afca33f`: `vendor_doc` (README.md of the
clone) or `upstream_code` (the MJCF text of the clone, `path:LINE`). The `facts = [Fact(...)]` list in `driver.py` is
the source; `reference.json` and `REFERENCE.md` are generated from it.

## Facts

| fact | source | ref |
|---|---|---|
| The repository is a collection of MuJoCo models of the Franka Panda ("Franka panda mujoco models") | vendor_doc | `README.md:2` |
| The models adjust the default joint positions with an offset of -pi/2 on joint6 and -pi/4 on joint7 | vendor_doc | `README.md:10` |
| The joint4 range was reduced to avoid the gimbal-lock configuration | vendor_doc | `README.md:11` |
| The joint limits were adjusted to avoid hitting the limits during operation with the hardware | vendor_doc | `README.md:12` |
| The meshes and specs are credited to franka_ros and the Franka control_parameters page | vendor_doc | `README.md:17-21` |
| The card's first model is the MJCF scene `<mujoco model="bi-franka_panda v200">` | upstream_code | `bi-franka_panda.xml:1` |
| The scene includes assets/basic_scene.xml, assets/assets.xml and assets/gripper_assets.xml and sets an empty meshdir | upstream_code | `bi-franka_panda.xml:10-13` |
| The scene is a torso with a leftarm including assets/chain0.xml and a rightarm including assets/chain1.xml | upstream_code | `bi-franka_panda.xml:23-35` |
| The scene includes the left arm actuator set assets/actuator0.xml and the two-arm set assets/actuator1.xml | upstream_code | `bi-franka_panda.xml:41-42` |
| The compiler angle is radian | upstream_code | `assets/assets.xml:10` |
| The model sets an explicit option timestep of 0.002 s | upstream_code | `assets/assets.xml:12` |
| The panda default class makes its position actuators ctrllimited and forcelimited and its joints limited | upstream_code | `assets/assets.xml:42-44` |
| The finger default class gives its joints damping 100 and armature 5 | upstream_code | `assets/assets.xml:61-64` |
| The left arm has seven hinge joints with the ranges -2.8973..2.8973, -1.7628..1.7628, -2.8973..2.8973, -3.0718..-0.4, -2.8973..2.8973, -1.6573..2.1127 and -2.8973..2.8973 | upstream_code | `assets/chain0.xml:16-46` |
| The right arm has seven hinge joints with the ranges -2.9671..2.9671, -1.8326..1.8326, -2.9671..2.9671, -3.0718..-0.4, -2.9671..2.9671, -1.6573..2.1127 and -2.8973..2.8973 | upstream_code | `assets/chain1.xml:14-46` |
| panda0_finger_joint1 and panda0_finger_joint2 are slide joints with range 0 to 0.04 m | upstream_code | `assets/chain0.xml:62-88` |
| panda1_finger_joint1 and panda1_finger_joint2 are slide joints with range 0 to 0.04 m | upstream_code | `assets/chain1.xml:60-84` |
| The left arm has seven position actuators with ctrlranges -2.9671..2.9671, -1.8326..1.8326, -2.9671..2.9671, -3.1416..0.0, -2.9671..2.9671, -1.66..2.1817 and -2.9671..2.9671 | upstream_code | `assets/actuator0.xml:11-17` |
| The right arm has seven position actuators with ctrlranges -2.9671..2.9671, -1.8326..1.8326, -2.9671..2.9671, -3.1416..0.0, -2.9671..2.9671, -0.0873..3.8223 and -0.0873..3.8223 | upstream_code | `assets/actuator1.xml:10-16` |
| The right finger joints have position actuators panda1_leftfinger and panda1_rightfinger with ctrlrange 0 to 0.04 | upstream_code | `assets/actuator1.xml:17-18` |
| The model declares a Franka_wrist_cam camera and an end_effector site on panda0_link7 | upstream_code | `assets/chain0.xml:52-53` |
| The mesh assets are STL files under meshes/collision and meshes/visual | upstream_code | `assets/assets.xml:16-38` |

## Tags

`arm`, `bimanual`, `franka`, `manipulator`, `mujoco`, `panda`, `robot`, `simulation`.

## Limits

The package declares no `Limit` of its own. The step envelope (`action.ctrl`) is derived by the MuJoCo bridge from
each actuator's `ctrlrange` of the served model, so the numbers live in the clone and are not copied into
`driver.py`. No `site-limits.example.json` is needed: there is no operator-required bound and the overlay would only
narrow a bound the model file already states.
