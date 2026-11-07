# Facts and tags for gh.discoverse-dev/mujoco-lidar

Every fact cites its source at commit `e6b879df4b96daaed30ef10fe02650d29048fa9b`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

The package serves the card's main scene, `models/scene_g1.xml` (card `models[0]`), as a `MujocoDriver`. It reads the
model file from the read-only clone; the package copies neither the model nor its assets and never imports the
upstream package. The scene includes the G1 MJCF model, which carries a site named `lidar`; the G1 example loads that
scene and builds the LiDAR wrapper on that site.

| fact | source | ref |
|---|---|---|
| The card's main scene includes the Unitree G1 MJCF model | upstream_code | models/scene_g1.xml:2 |
| The card's main scene also includes the shared obstacle and ground scene scene.xml | upstream_code | models/scene_g1.xml:3 |
| The G1 model integrates with the Euler scheme at a 0.002 s timestep | upstream_code | models/unitree_g1/g1_mjx_feetonly.xml:4 |
| The G1 model carries a site named 'lidar' on the torso at position 0 0 0.405 | upstream_code | models/unitree_g1/g1_mjx_feetonly.xml:265 |
| The body tree has a freejoint named floating_base_joint and 29 named hinge joints | upstream_code | models/unitree_g1/g1_mjx_feetonly.xml:136-358 |
| The actuator section has 29 position actuators, one per leg, waist, arm and wrist joint | upstream_code | models/unitree_g1/g1_mjx_feetonly.xml:388-422 |
| The position actuator default sets inheritrange to 1, so an actuator's ctrlrange is its joint range: the hip pitch -2.5307 to 2.8798, the hip roll -0.5236 to 2.9671 and the knee -0.087267 to 2.8798 | upstream_code | models/unitree_g1/g1_mjx_feetonly.xml:13-27 |
| The scene's home keyframe supplies a qpos and ctrl starting pose | upstream_code | models/scene_g1.xml:5-21 |
| The included scene.xml adds a ground plane and four wall boxes around the robot | upstream_code | models/scene.xml:19-23 |
| The G1 example loads models/scene_g1.xml | upstream_code | examples/unitree_g1.py:15 |
| The G1 example constructs MjLidarWrapper for that model with site_name 'lidar' | upstream_code | examples/unitree_g1.py:66-71 |
| MjLidarWrapper takes the MuJoCo model and the name of the LiDAR site | vendor_doc | docs/en/API.md:19-23 |
| MjLidarWrapper.trace_rays traces rays and returns a distance array with the same shape as the theta and phi ray angles | vendor_doc | docs/en/API.md:33-47 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself (one interval per
actuator, `actuator_ctrlrange`; the source is `upstream_code` and the reference is the model path), so no
`operator_required` bound is needed. The G1 position actuator default sets `inheritrange="1"`
(`g1_mjx_feetonly.xml:13`), so each actuator interval is the range of its joint; the hip pitch interval is
-2.5307 to 2.8798 (`:17`), the hip roll -0.5236 to 2.9671 (`:20`) and the knee -0.087267 to 2.8798 (`:27`).

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the model file for
the actuator count, the control ranges and the qpos/qvel layout, but its integration is a placeholder first-order
motion and it resolves no mesh, contact, equality, tendon or sensor constraint. MuJoCo was not importable where the
gate ran (no network, no pip), so no trajectory or scan was compared with the real engine. The gaps are listed in the
`fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that imports
MuJoCo.

NOT COVERED: the LiDAR range image (one distance per ray, the same shape as the theta and phi arrays) and the point
cloud that `MjLidarWrapper.trace_rays` produces. `cap.world.step.v1` and `cap.world.reset.v1` carry the world state
only; the scan, the scan patterns, the cpu/taichi/jax/warp backends, the cutoff distance and the sensor pose are not
exposed by this package.

Tags: mujoco, simulation, lidar, unitree-g1, world, scene
