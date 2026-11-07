# Facts and tags for gh.hogunkee/robocasa_g1

Every fact cites its source at commit `6796d20bbee3fbe49e8f80a08f04bece07f481fd`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RoboCasaEnv is a Gymnasium environment (class RoboCasaEnv(gym.Env)) | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:82 |
| The wrapper creates the underlying simulation with robosuite.make(**env_kwargs) | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:78 |
| The wrapper sets ignore_done=True when it builds the robosuite environment | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:69 |
| The action space is a Dict of per-part Box spaces with low -1 and high 1, plus a Discrete(2) base_mode for a hybrid mobile base | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:145-159 |
| step pops every per-part action from the dict, concatenates the per-robot arrays and asserts that no action key remains | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:235-250 |
| step returns the observation, reward, done, truncated=False and info | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:252-263 |
| reset calls np.random.seed(seed) before env.reset() | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:223-225 |
| reset returns the observation and info with success and grasp_distractor_obj set false | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:229-233 |
| get_basic_observation flips the image rows and casts every non-image observation to float32 | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:196-209 |
| GrootRoboCasaEnv derives its observation space from the robot key converter and adds a Box(0, 255) of shape (256, 256, 3) for each mapped camera | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:26-37 |
| GrootRoboCasaEnv adds a Text annotation of at most 256 characters and derives its action space from the robot key converter | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:58-66 |
| get_groot_observation maps hand.* and body.* keys to state.* and raises ValueError for any other key | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:106-113 |
| GrootRoboCasaEnv.step unmaps the action, calls the parent step and maps the observation back | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:160-172 |
| The Groot observation uses annotation.human.coarse_action with an unlocked_waist prefix for G1ArmsAndWaist | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:147-150 |
| The G1 arms-and-waist converter maps left_hand, right_hand, left_arm, right_arm and waist, and unmap_action reads them as action.<part> keys | upstream_code | robocasa/models/robots/__init__.py:390-410 |
| The same converter configures the egoview, rs_view and worldview cameras at 1280 by 800 | upstream_code | robocasa/models/robots/__init__.py:369-375 |
| deduce_action_space makes an integer action member a Discrete(2) and an array member a Box with low -1 and high 1 of the array length | upstream_code | robocasa/models/robots/__init__.py:229-240 |
| The repository example creates the environment id g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env | upstream_code | test_env.py:17 |
| The repository example steps the G1 arms-and-waist environment with action arrays of 7 (left and right hand), 7 (left and right arm) and 3 (waist) elements | upstream_code | test_env.py:25-33 |
| The G1 arms-and-waist alias maps the robot class G1ArmsAndWaistDex31Hands to g1_arms_waist_dex31_hands | upstream_code | robocasa/models/robots/__init__.py:1052-1055 |
| make_key_converter selects G1ArmsAndWaistKeyConverter for the G1 arms-and-waist robot names | upstream_code | robocasa/models/robots/__init__.py:1110-1111 |
| The wrapper registers every registered robosuite environment for every Groot robot alias and adds g1_unified ids for the g1_arms_waist_dex31_hands alias | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:204-220 |
| Tabletop's constructor defaults control_freq to 20 Hz and horizon to 1000 | upstream_code | robocasa/environments/tabletop/tabletop.py:294-295 |
| Tabletop forwards control_freq to the robosuite environment | upstream_code | robocasa/environments/tabletop/tabletop.py:399 |
| render returns the cached observation frame and refuses before a reset or step; close delegates to the inner environment | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:265-271 |

Limits: the driver declares one bound on every action array element: -1 to 1, from the converter's
`Box(low=-1, high=1)` (`robocasa/models/robots/__init__.py:229-240`). `ticks` (1 to 10000) and `seed` (minimum 0) are
the catalogue class schemas and the runtime enforces them; the device is simulated R1, so no bound is
`operator_required` and no `site-limits.example.json` is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine
`gymnasium:g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env (kinematic fake stand-in)`, level F0
(placeholder kinematic transitions, no contacts, controllers, MuJoCo or camera), determinism `seeded` with
`seed_control` `parameter`, timestep 50 ms (the `control_freq=20` default of Tabletop, `tabletop.py:294`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled,
including the 2x2x3 placeholder frames where the observation space declares 256x256x3
(`gymnasium_groot.py:29-30`).

Safety: simulated R1 (simulation stepping, MHS/spec/04-safety.md:67), above the card's R0 floor. The e-stop calls
`GrootRoboCasaEnv.close` and the runtime latches: no step or reset is accepted until `mhs.safety.reset` clears the
latch and reopens the environment at the recorded seed; the last observation and tick stay readable. There is no
hardware backend, no physical e-stop path and no hardware run.

Tags: robocasa, robosuite, gymnasium, tabletop, manipulation, humanoid, unitree-g1, simulation,
reinforcement-learning
