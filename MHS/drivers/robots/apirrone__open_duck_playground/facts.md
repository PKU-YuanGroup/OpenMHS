# Facts and tags for gh.apirrone/open_duck_playground

Every fact cites the read-only clone at commit `b9be205ac64488c23504ca42e5ec790337adeec3`: `upstream_code` is an
MJCF, Python or config file of the clone and `vendor_doc` is a text file of the clone.  The same facts are written
into `driver.py`; `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

The package serves the card's first model, the MJCF scene
`playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml`, as a `MujocoDriver` (device kind
`world.sim`, simulated, R0).  It reads the model file from the clone; the package copies neither the model nor its
assets.  The card's other models are not served by this package; changing `model_path` and the facts serves
another scene.  The clone's own inference script defaults to the flat terrain scene
(`playground/open_duck_mini_v2/mujoco_infer.py:254-257`), while the card lists the rough terrain backlash scene
first.

| fact | source | ref |
|---|---|---|
| The package serves the card's first model, the MJCF scene `playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml`, whose root element is `<mujoco model="Open Duck Mini V2 rough terrain scene">` and which includes `open_duck_mini_v2_backlash.xml` | upstream_code | playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml:1-3 |
| The rough scene's floor is a geom of type hfield that uses the hfield asset assets/hfield.png with size `10 10 .01 0.1`, and the floor geom's friction is 1.0 | upstream_code | playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml:22-28 |
| The robot model's root element is `<mujoco model="open_duck_mini_v2">` | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:4 |
| The robot's compiler element declares angle `radian` and meshdir `assets` | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:9 |
| The robot option sets iterations 1, ls_iterations 5 and eulerdamp disable, and it sets no timestep | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:6-8 |
| The sts3215 default class sets joint damping 0.56, frictionloss 0.068 and armature 0.027 | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:49 |
| The sts3215 default class sets the position actuator kp 17.11, kv 0.0 and forcerange -3.23 3.23 | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:50 |
| The backlash default class limits its hinge range to -0.008726646259971648 to 0.008726646259971648 rad, commented as plus or minus 0.5 degrees | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:52-55 |
| The robot base body has the free joint floating_base | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:59-61 |
| The model has 14 position actuators, one for each actuated hinge joint, and every one sets inheritrange 1 and class sts3215 | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:497-512 |
| The left_hip_yaw hinge joint has range -0.5235987755982979 to 0.5235987755982997 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:118 |
| The left_hip_roll hinge joint has range -0.4363323129985815 to 0.43633231299858327 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:137 |
| The left_hip_pitch hinge joint has range -1.2217304763960306 to 0.5235987755982988 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:153 |
| The left_knee hinge joint has range -1.5707963267948966 to 1.5707963267948966 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:178 |
| The left_ankle hinge joint has range -1.5707963267948957 to 1.5707963267948974 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:199 |
| The neck_pitch hinge joint has range -0.3490658503988437 to 1.1344640137963364 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:229 |
| The head_pitch hinge joint has range -0.7853981633974483 to 0.7853981633974483 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:246 |
| The head_yaw hinge joint has range -2.792526803190927 to 2.792526803190927 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:256 |
| The head_roll hinge joint has range -0.523598775598218 to 0.5235987755983796 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:272 |
| The right_hip_yaw hinge joint has range -0.523598775598297 to 0.5235987755983006 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:328 |
| The right_hip_roll hinge joint has range -0.4363323129985797 to 0.43633231299858505 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:346 |
| The right_hip_pitch hinge joint has range -0.5235987755982988 to 1.2217304763960306 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:362 |
| The right_knee hinge joint has range -1.5707963267948966 to 1.5707963267948966 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:387 |
| The right_ankle hinge joint has range -1.5707963267948957 to 1.5707963267948974 rad | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:409 |
| The sensor block names gyro, local_linvel, accelerometer, upvector, forwardvector, global_linvel, global_angvel, position, orientation, the left and right foot velocities and positions, and the left and right foot upvectors | upstream_code | playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml:26-42 |
| The rough scene defines a home keyframe with a qpos list and a ctrl list; the ctrl list has the 14 actuator targets | upstream_code | playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml:32-74 |
| The README documents MuJoCo inference for open_duck_mini_v2 with mujoco_infer.py | vendor_doc | README.md:31-38 |
| The inference script's default model path is playground/open_duck_mini_v2/xmls/scene_flat_terrain.xml | upstream_code | playground/open_duck_mini_v2/mujoco_infer.py:254-257 |

Limits: the bridge derives `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator (`actuator_ctrlrange`).  Each position actuator sets `inheritrange="1"` and names the joint it drives
(`open_duck_mini_v2_backlash.xml:498-511`), so the intervals are the 14 joint ranges cited above.  The class
source is `upstream_code`, so no driver-declared or `operator_required` bound is needed.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo.  It reads the model file
for the joint count, the actuator count and the control ranges, but its integration is a placeholder first-order
motion toward the control target, it loads no mesh, texture or hfield, and it resolves no contact, equality or
tendon constraint.  MuJoCo was not importable where the gate ran, so no trajectory was compared with the real
engine.  The gaps are listed in the `fidelity` attribute of `driver.py`.
