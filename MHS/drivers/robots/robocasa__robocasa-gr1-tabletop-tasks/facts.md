# Facts and tags for gh.robocasa/robocasa-gr1-tabletop-tasks

Every fact cites its source at commit `4840e671596f93ca03651524b9f72ffb1aadfeff`: `vendor_doc` (a text file of the
clone such as README.md), or `upstream_code` (a code or comment line as `path/in/clone.py:LINE`).  The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is the official release of simulation environments for the GR-1 Tabletop Tasks | vendor_doc | README.md:7 |
| The package is a RoboCasa fork that adds environments, assets and tooling for the GR-1 Tabletop tasks | vendor_doc | README.md:13 |
| The first task id in the README's list of 24 tabletop task names is gr1_unified/PnPCupToDrawerClose_GR1ArmsAndWaistFourierHands_Env | vendor_doc | README.md:99 |
| The simulation dependency is pinned to mujoco==3.2.6 | upstream_code | setup.py:21 |
| GrootRoboCasaEnv extends RoboCasaEnv | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:22 |
| RoboCasaEnv is a gymnasium.Env subclass | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:77 |
| The wrapper creates its underlying environment with robosuite.make | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:73 |
| The wrapper passes ignore_done=True to the robosuite environment | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:64 |
| The per-part controller action Box is bounded by min -1 and max 1 | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:140 |
| A hybrid mobile base adds a Discrete(2) base_mode action | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:149 |
| The GR-1 arms-and-waist key converter maps action.left_hand, action.right_hand, action.left_arm, action.right_arm and action.waist to the robosuite controllers | upstream_code | robocasa/models/robots/__init__.py:312-320 |
| The key converter derives each action space key by prefixing the mapped name with 'action.' and bounds each Box by -1 and 1 | upstream_code | robocasa/models/robots/__init__.py:203-213 |
| The GR1 arms-and-waist initial joint vector is 17 values, with a seven-value right arm at indices 3:10 and a seven-value left arm at 10:17, leaving the first three values before the right arm | upstream_code | robocasa/models/robots/manipulators/gr1_robot.py:49-53 |
| The Fourier hand action selection keeps the six values at indices 0, 1, 4, 6, 8 and 10 | upstream_code | robocasa/models/robots/__init__.py:24-25 |
| reset(seed, options) seeds numpy with the seed and resets the wrapped robosuite environment; the options argument is not used | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:213-215 |
| step takes a dict of per-robot actions and calls the wrapped environment's step | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:225-242 |
| The wrapper reports truncated=False on every step | upstream_code | robocasa/utils/gym_utils/gymnasium_basic.py:246 |
| The Groot observation image resolution is 256 x 256 | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:19 |
| The Groot image observation is a uint8 Box of shape 256 x 256 x 3 | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:29 |
| The Groot language annotation is a Text field of max_length 256 | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:38-39 |
| The gr1_unified id prefix is used for the GR-1 arms, waist and Fourier hands registration | upstream_code | robocasa/utils/gym_utils/gymnasium_groot.py:163-167 |
| Tabletop is the base class of the tabletop environments | upstream_code | robocasa/environments/tabletop/tabletop.py:90 |
| Tabletop's default control_freq is 20 control signals per second | upstream_code | robocasa/environments/tabletop/tabletop.py:278 |
| Tabletop's default horizon is 1000 timesteps | upstream_code | robocasa/environments/tabletop/tabletop.py:279 |
| Tabletop steps the model at the model timestep rate until the control period elapses | upstream_code | robocasa/environments/tabletop/tabletop.py:1069-1071 |

Limits: the driver declares none.  The only bounds are the action space and ``ticks``, both derived by the Gymnasium
bridge from the environment: every action member is ``[-1, 1]`` (`gymnasium_basic.py:140`), a hybrid mobile base has
``base_mode`` 0 or 1 (`:149`), and ``ticks`` is 1 to ``max_ticks`` (the bridge default 10000).  The device is simulated
(R0), so no limit is ``operator_required``.  The fake's action dimensions are the default GR-1 part sizes named by the
clone (seven per arm, three for the waist, six per Fourier hand); a different controller configuration can change them.

Fidelity contract (`driver.py`, `fidelity = {...}`): the model as deployed is the analytic fake, level F0: no rigid-body
dynamics, contacts, actuators, sensors, noise or rendering.  Determinism is `seeded` with `seed_control` `parameter`
(the fake re-seeds its Python generator on `reset(seed)`); `timestep_ms` is 0 because the clone states no physics
timestep (it states `control_freq=20`, tabletop.py:278, and decimation at tabletop.py:1069-1071), `realtime_factor` is 0,
the clock is `lockstep`, reset is `full` and snapshot/restore is not offered.  The gaps list the omissions, the
default-size caveat for the dimensions, the reduced 2 x 2 x 3 image and the missing task success model.  The upstream simulator itself
is robosuite with MuJoCo 3.2.6 (setup.py:21) and is not run by this package.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable.  There is no hardware
backend and no operator-required bound.

Tags: robocasa, gr1, humanoid, tabletop, manipulation, reinforcement-learning, simulation, gymnasium
