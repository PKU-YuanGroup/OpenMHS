# Facts and tags for gh.vikashplus/adroit

Every fact cites its source at commit `c98c9c92fc9729e92a10c8db79588348897d8fe3`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF scene `Adroit_hand.xml` (`models[0]`). It reads the model
file and its included resource files from the read-only clone; the package copies neither the model nor its
assets.

| fact | source | ref |
|---|---|---|
| Adroit is a 28 degree of freedom system: a 24 degree of freedom ShadowHand and a 4 degree of freedom arm | vendor_doc | README.md:6 |
| The Adroit platform is tendon-driven and pneumatically actuated; the README describes the hand as a system with 24 degrees of freedom and 40 tendons | vendor_doc | README.md:3 |
| Adroit_hand.xml includes resources/assets.xml and resources/joint_position_actuation.xml; the tendon torque actuation include is commented out | upstream_code | Adroit_hand.xml:12-14 |
| The model declares <compiler angle="radian"/> | upstream_code | resources/assets.xml:11 |
| The model's <option> element sets the physics timestep to 0.002 s | upstream_code | resources/assets.xml:22 |
| The hand mount body at the world origin includes resources/chain.xml and declares no joint of its own | upstream_code | Adroit_hand.xml:32-36 |
| The chain's base free joint is commented out, so the forearm and hand are fixed to the hand mount | upstream_code | resources/chain.xml:14 |
| The only free joint of the scene belongs to the ball body at pos .1 -.1 .25 | upstream_code | Adroit_hand.xml:38-41 |
| A weld equality connects the mocap1 body to the forearm body | upstream_code | Adroit_hand.xml:46 |
| The position actuators name one joint and an explicit ctrlrange each; A_WRJ1 has ctrlrange -0.52 to 0.17 and kp 50, and A_WRJ0 has ctrlrange -0.79 to 0.61 and kp 50 | upstream_code | resources/joint_position_actuation.xml:14-37 |
| The Adroit default class sets general actuators to ctrllimited="true" with ctrlrange -1 1 | upstream_code | resources/assets.xml:88 |
| WRJ1 is a hinge joint with range -0.524 to 0.175 rad | upstream_code | resources/chain.xml:26 |
| THJ0 is a hinge joint with range -1.571 to 0 rad | upstream_code | resources/chain.xml:219 |
| The tendon section declares fixed tendons from T_WRJ1r to T_THJ0l with ranges | upstream_code | resources/assets.xml:132-290 |
| The mesh assets are named with the file paths ../Adroit/resources/meshes/*.stl | upstream_code | resources/assets.xml:34-44 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
position actuator, `actuator_ctrlrange`). The intervals are declared in
`resources/joint_position_actuation.xml:14-37`; for example `A_WRJ1` is `-0.52 0.17` and `A_FFJ2` is `0 1.6`.
The class source is `upstream_code` and the reference is the model file, so no driver-declared or
`operator_required` bound is needed.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file
for the joint dimensions, the actuator count and the control ranges, but its integration is a placeholder
motion of each actuated hinge toward its control value, and it resolves no mesh, contact, equality or tendon
constraint. The model's base free joint is commented out and the only free body is a ball. MuJoCo was not
importable where the gate ran, so no trajectory was compared with the real engine. The gaps are listed in the
`fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that
imports MuJoCo.

Tags: adroit, dexterous-hand, mujoco, robot, shadow-hand, simulation, tendon-driven
