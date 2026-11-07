"""OpenMHS driver for gh.huggingface/gym-aloha: the ALOHA bimanual manipulation environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the whole
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [...]}`` bounded element by element by the 14-element ``Box(low=-1, high=1)`` of ``AlohaEnv``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The configuration is the insertion environment: ``task="insertion"`` is the ``task`` of the kwargs that
``gym_aloha/__init__.py:10`` registers and ``obs_type="pixels_agent_pos"`` is the observation the README documents at
``README.md:95`` (the registered default is ``pixels``, ``gym_aloha/__init__.py:10``).  The second registered
environment, ``gym_aloha/AlohaTransferCube-v0`` (``gym_aloha/__init__.py:13-21``), runs the same class with the
``transfer_cube`` task; this package serves one environment, so switching means changing ``env_id`` and ``env_kwargs``.

The gate cannot import gym_aloha (MuJoCo and a GL context, see fake.py), so the ``fake`` backend is the package's own
pure Python environment.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (bd3325740ea8d1c97411c41ea1e0f4ce0a7de8da).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver


class Aloha(GymnasiumDriver):
    device_id = "aloha"
    env_id = "gym_aloha/AlohaInsertion-v0"
    env_kwargs = {"task": "insertion", "obs_type": "pixels_agent_pos"}
    native = "gym_aloha.env:AlohaEnv"
    backends = {"fake": ".fake:FakeAlohaEnv"}
    action_space_ref = "gym_aloha/env.py:86"
    display_name = "gym-aloha ALOHA bimanual simulation (AlohaInsertion-v0)"
    vendor, model = "Hugging Face", "gym-aloha 0.1.4"
    tags = ["aloha", "bimanual", "manipulation", "reinforcement-learning", "simulation", "mujoco", "gymnasium"]
    facts = [
        Fact("The action space is a Box with low -1 and high 1 shaped by the ACTIONS list", source="upstream_code",
             ref="gym_aloha/env.py:86"),
        Fact("ACTIONS lists six absolute arm joints and then the normalized gripper position (0 close, 1 open), for "
             "the left arm and then for the right arm", source="upstream_code", ref="gym_aloha/constants.py:29-47"),
        Fact("The control timestep DT is 0.02 and FPS is 50; the comment on the DT line derives 50 hz from it",
             source="upstream_code", ref="gym_aloha/constants.py:4-5"),
        Fact("The simulation's control timestep is that DT, passed to the dm_control Environment as control_timestep",
             source="upstream_code", ref="gym_aloha/env.py:133-135"),
        Fact("The observation of obs_type pixels_agent_pos is a Dict of a nested pixels Dict whose top member is a "
             "uint8 Box of 0 to 255 shaped observation_height x observation_width x 3, and an agent_pos Box between "
             "-1000.0 and 1000.0", source="upstream_code", ref="gym_aloha/env.py:64-84"),
        Fact("observation_width defaults to 640 and observation_height to 480", source="upstream_code",
             ref="gym_aloha/env.py:30-31"),
        Fact("The observation image is rendered 480 high and 640 wide from the top camera", source="upstream_code",
             ref="gym_aloha/tasks/sim.py:92"),
        Fact("The gripper observation is the finger position normalized by normalize_puppet_gripper_position, so 0 "
             "is closed and 1 is open", source="upstream_code", ref="gym_aloha/constants.py:94-97"),
        Fact("The start qpos is waist 0, shoulder -0.96, elbow 1.16, forearm roll 0, wrist angle -0.3, wrist rotate "
             "0 and fingers 0.02239 and -0.02239 for each arm", source="upstream_code",
             ref="gym_aloha/constants.py:50-67"),
        Fact("reset(seed) seeds the task's random generator and replaces its numpy RandomState with RandomState(seed)",
             source="upstream_code", ref="gym_aloha/env.py:153-156"),
        Fact("The object poses are drawn uniformly: the peg x from 0.1 to 0.2, the socket x from -0.2 to -0.1, both "
             "y from 0.4 to 0.6 and both z from 0.05 to 0.05", source="upstream_code", ref="gym_aloha/utils.py:20-38"),
        Fact("step returns terminated = is_success = (reward == 4), truncated False and an info carrying is_success",
             source="upstream_code", ref="gym_aloha/env.py:180-187"),
        Fact("The InsertionTask reward is 1 when both grippers touch peg and socket, 2 when neither object touches "
             "the table, 3 when the peg touches a socket and 4 when the red peg touches the pin", source="upstream_code",
             ref="gym_aloha/tasks/sim.py:208-219"),
        Fact("The TransferCubeTask reward rises from 1 to 4 with the right gripper, the lift, the left gripper and a "
             "transfer that leaves the table", source="upstream_code", ref="gym_aloha/tasks/sim.py:140-149"),
        Fact("AlohaInsertion-v0 registers AlohaEnv with max_episode_steps 300, obs_type pixels and task insertion, and "
             "AlohaTransferCube-v0 registers the same class with task transfer_cube", source="upstream_code",
             ref="gym_aloha/__init__.py:3-21"),
        Fact("Both registered environments set nondeterministic True because even after seeding the rendered "
             "observations are slightly different", source="upstream_code", ref="gym_aloha/__init__.py:7-9"),
        Fact("The state observation type is not implemented: obs_type state raises NotImplementedError",
             source="upstream_code", ref="gym_aloha/env.py:46-47"),
        Fact("close does nothing", source="upstream_code", ref="gym_aloha/env.py:189-190"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:gym_aloha/AlohaInsertion-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the object poses through a numpy RandomState(seed) "
                     "(gym_aloha/utils.py:9 and :24) and the joint dynamics of MuJoCo are deterministic, so one "
                     "implementation repeats a trajectory for the same seed and actions; the upstream registers "
                     "nondeterministic True because the rendered images still differ slightly "
                     "(gym_aloha/__init__.py:7-9), and this package's fake draws with Python's random.Random instead "
                     "of numpy's generator, so a seed gives different poses on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "MuJoCo rigid-body physics of two ViperX arms in the scenes of gym_aloha/assets: no contacts, no "
            "friction, no actuator, sensor or noise model, and no camera physics",
            "the fake backend does not integrate any dynamics: the commanded joint targets and the unnormalized "
            "gripper positions become the state, so the contact-based reward (gym_aloha/tasks/sim.py:174-219) is "
            "always 0 and a success (reward 4) can never be observed there",
            "the fake backend returns a 4 x 6 x 3 stand-in image where the environment renders 480 x 640 x 3 "
            "(gym_aloha/tasks/sim.py:92); that stand-in is a uniform colour derived from the seeded peg pose, it is "
            "not a picture of the scene",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (DT 0.02 s, "
            "gym_aloha/constants.py:4) only",
            "snapshot and restore are not offered: AlohaEnv exposes no get_state or set_state",
            "the fake backend was not compared with the upstream environment (gym_aloha was not importable where "
            "the gate ran), its object poses come from Python's random.Random instead of numpy's RandomState, and "
            "its action is a list where AlohaEnv asserts a one-dimensional numpy array "
            "(gym_aloha/env.py:174)",
        ],
    }
