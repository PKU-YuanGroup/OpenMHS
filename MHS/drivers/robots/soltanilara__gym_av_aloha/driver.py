"""OpenMHS driver for gh.soltanilara/gym_av_aloha: the cube-transfer-v1 Gymnasium environment.

The upstream repository is a MuJoCo simulation of the ALOHA bimanual robot with eight registered Gymnasium
environments.  This package serves ``gym_av_aloha/cube-transfer-v1``: a simulated R0 world, driven only through
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  A GymnasiumDriver is configuration only;
the bridge derives the action schema from the environment's spaces.  With the default ``enable_av=True`` the action
and the ``agent_pos`` observation are 21-value vectors; ``CubeTransferEnv`` adds a 7-value ``environment_state``
(the bound cube pose).  The action space is an unbounded Box, so there is no finite action limit to declare.

The package configures ``env_kwargs = {"cameras": {}}``: the registered default renders six 480x640 cameras, and
that pixel array is NOT COVERED by this package (fake.py returns no pixels).  The driver therefore publishes the
scalar observation only.  The gate cannot import the upstream package (it needs mujoco, dm-control and numpy), so
the ``fake`` backend is a pure-Python kinematic stand-in for ``CubeTransferEnv``; the ``sim`` backend would be
``gymnasium.make("gym_av_aloha/cube-transfer-v1", cameras={})`` and was not run here.

Every Fact cites a line of the clone at the pinned commit 3e8edfdf5e2ff9cfc6e330ab9f970417e0e2a77d.  The package is
model-authored and unreviewed: it is checked on the fake backend only, and its evidence is ``contract_checked``.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "gym_av_aloha/__init__.py"
SIM_ENV = "gym_av_aloha/env/sim_env.py"
SIM_CONFIG = "gym_av_aloha/env/sim_config.py"
CUBE = "gym_av_aloha/env/tasks/cube_transfer_env.py"
ROBOT = "gym_av_aloha/env/robot.py"
PYPROJECT = "pyproject.toml"


class AVAlohaCubeTransfer(GymnasiumDriver):
    device_id = "av-aloha-cube-transfer"
    env_id = "gym_av_aloha/cube-transfer-v1"
    env_kwargs = {"cameras": {}}
    native = "gym_av_aloha.env.tasks.cube_transfer_env:CubeTransferEnv"
    backends = {"fake": ".fake:FakeCubeTransferEnv"}
    display_name = "gym_av_aloha cube-transfer-v1 (MuJoCo ALOHA simulation)"
    vendor, model = "Soltanilara", "gym_av_aloha/cube-transfer-v1"
    tags = ["aloha", "bimanual", "mujoco", "simulation", "reinforcement-learning", "gymnasium"]
    facts = [
        Fact("cube-transfer-v1 is registered with entry point "
             "gym_av_aloha.env.tasks.cube_transfer_env:CubeTransferEnv", source="upstream_code",
             ref=f"{INIT}:19-21"),
        Fact("The registration marks cube-transfer-v1 nondeterministic=True because rendered observations differ "
             "even after seeding", source="upstream_code", ref=f"{INIT}:22-24"),
        Fact("The default camera set has six cameras, each rendered at 480x640 pixels", source="upstream_code",
             ref=f"{SIM_CONFIG}:7-14"),
        Fact("AVAlohaEnv adds a pixels observation only when len(cameras) > 0", source="upstream_code",
             ref=f"{SIM_ENV}:151-163"),
        Fact("AV_STATE_DIM is 21 and AV_ACTION_DIM is 21; STATE_DIM and ACTION_DIM are 14", source="upstream_code",
             ref=f"{SIM_CONFIG}:25-28"),
        Fact("With enable_av=True the action space is a Box with low -inf, high inf and shape (action_dim,)",
             source="upstream_code", ref=f"{SIM_ENV}:167-172"),
        Fact("The agent_pos observation is a Box with low -inf, high inf and shape (state_dim,), and the "
             "observation space is a Dict", source="upstream_code", ref=f"{SIM_ENV}:144-165"),
        Fact("With enable_av=True get_obs builds agent_pos from the left joint positions, left gripper, right joint "
             "positions, right gripper and middle joint positions", source="upstream_code",
             ref=f"{SIM_ENV}:179-197"),
        Fact("CubeTransferEnv adds an environment_state Box with shape (ENV_STATE_DIM,) to the observation and "
             "rebuilds the observation space as a Dict", source="upstream_code", ref=f"{CUBE}:39-45"),
        Fact("ENV_STATE_DIM is 7", source="upstream_code", ref=f"{CUBE}:15"),
        Fact("CubeTransferEnv.get_obs sets environment_state to the bound cube joint qpos, a 7-value pose",
             source="upstream_code", ref=f"{CUBE}:47-50"),
        Fact("CubeTransferEnv sets max_reward to 4", source="upstream_code", ref=f"{CUBE}:25"),
        Fact("CubeTransferEnv.get_reward returns a reward from 0 to 4 from cube, gripper and table contacts",
             source="upstream_code", ref=f"{CUBE}:57-92"),
        Fact("reset(seed, options) passes seed and options to gym.Env.reset, resets the physics, optionally "
             "randomizes the light and prompt, restores the fixed arm poses and returns observation and info",
             source="upstream_code", ref=f"{SIM_ENV}:307-344"),
        Fact("CubeTransferEnv.reset draws the cube position uniformly from x [-0.05, 0.05], y [0.05, 0.15], z 0 "
             "with the global np.random generator", source="upstream_code", ref=f"{CUBE}:94-105"),
        Fact("step applies the action as control over n_ctrl_steps, each advancing SIM_PHYSICS_ENV_STEP_RATIO "
             "physics steps, and returns observation, reward, terminated, truncated and info", source="upstream_code",
             ref=f"{SIM_ENV}:269-288"),
        Fact("terminated is reward == max_reward and info is_success is the same comparison", source="upstream_code",
             ref=f"{SIM_ENV}:282-286"),
        Fact("SIM_PHYSICS_DT is 0.002 s and SIM_DT is 0.04 s from 20 physics steps", source="upstream_code",
             ref=f"{SIM_CONFIG}:19-22"),
        Fact("The default fps is 25", source="upstream_code", ref=f"{SIM_ENV}:38"),
        Fact("step_dt is 1/fps and n_ctrl_steps is round(step_dt/SIM_DT)", source="upstream_code",
             ref=f"{SIM_ENV}:66-67"),
        Fact("SimRobotArm.set_joint_ctrl clips joint control to the actuator ctrlrange", source="upstream_code",
             ref=f"{ROBOT}:91-94"),
        Fact("The environment's render_fps is 1/SIM_DT and its only render mode is rgb_array", source="upstream_code",
             ref=f"{SIM_ENV}:27"),
        Fact("The upstream package requires Python ^3.10 and mujoco 3.3.3, dm-control ^1.0.31 and datasets 3.3.2",
             source="upstream_code", ref=f"{PYPROJECT}:9-12"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge supplies the engine
    #: and the lockstep clock; the members below state the simulated interval and what the fake does not model.
    fidelity = {
        "engine": "mujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds gymnasium's np_random, but CubeTransferEnv.reset draws the cube position "
                     "from the global np.random generator (cube_transfer_env.py:94-105), so upstream seed control "
                     "is imperfect for that draw; the fake uses Python's random.Random(seed) for the cube pose and "
                     "a fixed arm pose, so it repeats a trajectory for one seed.  The registration declares the "
                     "default rendered setup nondeterministic (__init__.py:22-24); this driver configures "
                     "cameras={} and makes no claim about rendered frames.",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic: it stores the 21-value action as the agent_pos observation and a "
            "7-value cube pose as environment_state; it has no MuJoCo rigid-body dynamics, contacts, actuators, "
            "sensors or noise, while the upstream environment integrates 20 physics steps of 2 ms per step",
            "pixel observations are NOT COVERED: the registered default renders six 480x640 RGB cameras "
            "(480x640x3 per camera); this driver configures cameras={} and the fake returns no pixels, so vision "
            "and the lighting model are not modelled",
            "reward and termination are simplified: the fake returns reward 0 and never terminates, while "
            "CubeTransferEnv computes 0 to 4 from cube, gripper and table contacts and terminates at max_reward 4",
            "action clipping is not modelled: SimRobotArm clips joint control to the actuator ctrlrange and the "
            "grippers to 0..1, while the fake applies the commanded unbounded action values directly",
            "reset options (randomize_light, prompt, distractors) are accepted and ignored by the fake; only the "
            "seeded cube placement and the fixed arm pose are modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: AVAlohaEnv has set_state but no get_state/get_state_dict pair, "
            "so the bridge cannot snapshot",
            "the fake was not compared with a real MuJoCo run: mujoco 3.3.3 and dm-control 1.0.31 are not "
            "installed where the gate runs, and no physical device is modelled",
        ],
    }
