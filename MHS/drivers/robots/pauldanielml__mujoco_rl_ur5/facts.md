# Facts and tags for gh.pauldanielml/mujoco_rl_ur5

The package is a simulated R0 `GymnasiumDriver` for `gym_grasper.envs:GraspEnv` (`Grasper-v0`).  Every fact cites the
upstream clone at commit `206d33edf0bc29aca6cd14778de6488e1d1ed0b3`: `upstream_code` is a code or comment line and
`vendor_doc` is a text file of the clone.  The driver copies these into `facts` in `driver.py`; the generated
`reference.json` and `REFERENCE.md` are the canonical rendering.

## Tags

`ur5`, `gripper`, `pick-and-place`, `mujoco`, `reinforcement-learning`, `simulation`, `gymnasium`

## Facts

| fact | source | ref |
|---|---|---|
| The default scene is `UR5+gripper/UR5gripper_2_finger_many_objects.xml` | upstream_code | `gym_grasper/envs/GraspingEnv.py:30` |
| The default image width and height are 200 pixels | upstream_code | `gym_grasper/envs/GraspingEnv.py:31-32` |
| The wrist rotations are 0, 30, 60, 90, -30 and -60 degrees, indexed 0 to 5 | upstream_code | `gym_grasper/envs/GraspingEnv.py:40` |
| The action space is `MultiDiscrete([IMAGE_HEIGHT * IMAGE_WIDTH, len(rotations)])` | upstream_code | `gym_grasper/envs/GraspingEnv.py:163-165` |
| An action is decoded as `x = action[0] % IMAGE_WIDTH`, `y = action[0] // IMAGE_WIDTH` and `rotation = action[1]` | upstream_code | `gym_grasper/envs/GraspingEnv.py:94-97` |
| The environment steps MuJoCo with `frame_skip` 1 | upstream_code | `gym_grasper/envs/GraspingEnv.py:47` |
| The default scene's MuJoCo integration timestep is 2e-3 s | upstream_code | `UR5+gripper/UR5gripper_2_finger_many_objects.xml:19` |
| An observation is a dictionary with an `rgb` array and a `depth` array returned by the controller's camera | upstream_code | `gym_grasper/envs/GraspingEnv.py:402-404` |
| `get_observation` requests an `IMAGE_WIDTH` by `IMAGE_HEIGHT` image and converts the depth image to meters | upstream_code | `gym_grasper/envs/GraspingEnv.py:398-401` |
| The reward is binary: 0 when the pixel is skipped or the grasp fails, and 1 when `move_and_grasp` reports a grasp | upstream_code | `gym_grasper/envs/GraspingEnv.py:130-142` |
| A pixel whose projected world z is below 0.8 m or whose world y is above -0.3 m is skipped with reward 0 | upstream_code | `gym_grasper/envs/GraspingEnv.py:124-131` |
| `step` always returns `done=False` and an empty info dictionary, and increments `step_called` | upstream_code | `gym_grasper/envs/GraspingEnv.py:76-156` |
| `reset_model` is called by the parent class reset method and returns an observation image | upstream_code | `gym_grasper/envs/GraspingEnv.py:411-412` |
| `reset_model` sets the seven actuated joints to `[0, -1.57, 1.57, -1.57, -1.57, 0.0, 0.3]` | upstream_code | `gym_grasper/envs/GraspingEnv.py:418` |
| `reset_model` randomizes 40 object joints: x in `[-0.25, 0.25]`, y in `[-0.77, -0.43]`, z in `[1.0, 1.5]` and a random unit quaternion | upstream_code | `gym_grasper/envs/GraspingEnv.py:420-430` |
| `Grasper-v0` is registered with entry point `gym_grasper.envs:GraspEnv` | upstream_code | `gym_grasper/__init__.py:4-7` |
| `close` closes the MuJoCo environment and destroys the OpenCV windows | upstream_code | `gym_grasper/envs/GraspingEnv.py:479-481` |
| The README documents the default action space as 200 x 200 pixels (40000 choices) and the state as a dictionary with an RGB image and a depth image of that resolution | vendor_doc | `README.md:68-69` |

## Limits

The package declares no `Limit`: the only numeric bounds are the environment's own action space (0 to 39999 for the
pixel index and 0 to 5 for the rotation), which `GymnasiumDriver` derives from the fake's `MultiDiscrete`
(`gym_grasper/envs/GraspingEnv.py:163-165`).  The fake uses the same real 200 x 200 by 6 space.  Its 8 x 8
observation arrays are stand-ins for the real 200 x 200 x 3 and 200 x 200 arrays (`GraspingEnv.py:31-32`), named in
the fidelity gaps and in RESULT.json.

No `Limit.operator_required` is needed: the device is simulated (R0) and the action space is the bound.

## Safe state

An e-stop latches the runtime before the driver is consulted.  For this simulated family driver the latch refuses
every step and reset until `mhs.safety.reset`; the bridge keeps the last observation readable.  There is no hardware
stop, no physical e-stop and no actuator to put in a safe position, because the package has no hardware backend.
