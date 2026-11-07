"""OpenMHS driver for gh.abrar2652/imitation-learning-aloha: the Gym Aloha insertion environment.

The served environment is ``gym_aloha/AlohaInsertion-v0``, registered in the clone's ``gym_aloha/__init__.py:3-10``
with ``entry_point="gym_aloha.env:AlohaEnv"``, ``max_episode_steps=300``, and the registration kwargs
``obs_type="pixels"`` and ``task="insertion"``.  A GymnasiumDriver is configuration only: ``env_id`` names the
environment and the bridge derives the action and observation schemas from the environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` a 14-element vector bounded by
``Box(-1, 1, shape=(14,), float32)`` (six arm targets and a normalized gripper per arm, ``constants.py:30-48``);
``cap.world.reset.v1`` takes ``{seed, options}``, ``cap.world.seed.v1`` takes ``{seed}``, and the observation for the
``pixels`` mode is ``{"top": 480 x 640 x 3 uint8}`` (``env.py:56-66``).  The device is simulated (R0): there is no
hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import gymnasium, dm_control or MuJoCo, so the ``fake`` backend is the package's own pure Python
stand-in (``fake.py``).  A backend name that ``backends`` does not list (``sim``) would be served by
``gymnasium.make("gym_aloha/AlohaInsertion-v0")`` (``GymnasiumDriver.open_native``); that path needs the upstream
dependencies and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
the upstream is a MuJoCo/dm_control rigid-body simulation at a 20 ms control timestep (``constants.py:5``), so the
claim is F1; the package's fake is a kinematic stand-in.  The gaps state what is not modelled and that the fake was not
compared with the upstream environment.  Every constant and rule cites a line of the clone at the pinned commit
``4180b39b634420e614be283c9336c1a62e307499``.  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "gym-aloha/gym_aloha/__init__.py"
ENV = "gym-aloha/gym_aloha/env.py"
CONST = "gym-aloha/gym_aloha/constants.py"
UTILS = "gym-aloha/gym_aloha/utils.py"
SIM = "gym-aloha/gym_aloha/tasks/sim.py"


class Aloha(GymnasiumDriver):
    device_id = "aloha-insertion"
    env_id = "gym_aloha/AlohaInsertion-v0"
    env_kwargs = {"obs_type": "pixels", "task": "insertion"}
    native = "gym_aloha.env:AlohaEnv"
    backends = {"fake": ".fake:FakeAlohaEnv"}
    action_space_ref = f"{ENV}:127-132"
    display_name = "Gym Aloha bimanual insertion (AlohaInsertion-v0)"
    vendor, model = "abrar2652", "gym_aloha/AlohaInsertion-v0"
    tags = ["aloha", "bimanual", "insertion", "manipulation", "imitation-learning", "simulation", "gymnasium"]
    risk = "R0"
    facts = [
        Fact("gym_aloha/AlohaInsertion-v0 is registered with entry_point gym_aloha.env:AlohaEnv, "
             "max_episode_steps 300 and kwargs obs_type pixels and task insertion", source="upstream_code",
             ref=f"{INIT}:3-10"),
        Fact("The registered environment is nondeterministic: the registration says so because even seeded "
             "rendered observations are slightly different", source="upstream_code", ref=f"{INIT}:7-9"),
        Fact("For a task other than pick_and_place the action space is Box(low=-1, high=1, shape=(len(ACTIONS),), "
             "dtype=float32)", source="upstream_code", ref=f"{ENV}:126-132"),
        Fact("ACTIONS has 14 entries: six arm targets and a normalized gripper position per arm, with the gripper "
             "0 close and 1 open", source="upstream_code", ref=f"{CONST}:30-48"),
        Fact("pick_and_place uses the seven SINGLE_ARM_ACTIONS instead of the bimanual ACTIONS", source="upstream_code",
             ref=f"{ENV}:119-125"),
        Fact("With obs_type pixels the observation space is a Dict with one top Box of shape "
             "(observation_height, observation_width, 3), values 0 to 255 and dtype uint8", source="upstream_code",
             ref=f"{ENV}:56-66"),
        Fact("The default observation_width is 640 and observation_height is 480", source="upstream_code",
             ref=f"{ENV}:31-34"),
        Fact("The pixels observation keeps only the top camera frame from the raw observation",
             source="upstream_code", ref=f"{ENV}:188-197"),
        Fact("The simulation control timestep is DT = 0.02 seconds (50 Hz)", source="upstream_code",
             ref=f"{CONST}:5-6"),
        Fact("The insertion task loads gym_aloha/assets/bimanual_viperx_insertion.xml and the InsertionTask",
             source="upstream_code", ref=f"{ENV}:162-165"),
        Fact("A reset with a seed seeds the task RNG and samples the insertion peg and socket poses from that seed",
             source="upstream_code", ref=f"{ENV}:209-219"),
        Fact("The insertion reset samples the peg x uniformly from 0.1 to 0.2 and the socket x from -0.2 to -0.1, "
             "both y from 0.4 to 0.6 at z 0.05", source="upstream_code", ref=f"{UTILS}:18-43"),
        Fact("The insertion reward is 0, 1, 2 or 3 on the way and 4 when the pin is touched; the pin-touch check is "
             "the successful insertion", source="upstream_code", ref=f"{SIM}:203-222"),
        Fact("step returns the observation, reward, terminated, truncated and info; terminated is reward == 4, "
             "info is_success is the same test, and AlohaEnv itself always returns truncated False",
             source="upstream_code", ref=f"{ENV}:234-247"),
        Fact("The registered max_episode_steps is 300", source="upstream_code", ref=f"{INIT}:6"),
        Fact("render returns the top camera image from the MuJoCo physics", source="upstream_code",
             ref=f"{ENV}:134-152"),
        Fact("close does nothing in AlohaEnv", source="upstream_code", ref=f"{ENV}:249-250"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2): the upstream MuJoCo model.
    #: The bridge derives the engine, the determinism kind and the lockstep clock; they are written out so the whole
    #: contract reads in one place.
    fidelity = {
        "engine": "gym_aloha:AlohaInsertion-v0 (dm_control MuJoCo)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "statistical",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the task RNG and the insertion pose sampler, but the upstream registration "
                     "sets nondeterministic=True because seeded rendered observations are slightly different "
                     "(gym_aloha/__init__.py:7-9).  This package's fake repeats a trajectory for a seed; that is not "
                     "a bit-exact replay claim about the upstream MuJoCo renderer.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream is a MuJoCo/dm_control rigid-body model of two ViperX arms, a peg, a socket and a table; "
            "this package's fake is kinematic and models none of the contacts, friction, actuator dynamics or "
            "gravity, so it is an F0 stand-in for the F1 upstream model",
            "the fake returns a 4 x 4 x 3 uint8 stand-in for the environment's 480 x 640 x 3 top camera RGB frame "
            "(env.py:56-66) to keep receipts small; it does not render MuJoCo",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the fake's reset draws from Python's random.Random while upstream uses numpy RandomState and MuJoCo "
            "physics, so one seed does not give the same trajectory on the two",
            "the fake's success rule is a placeholder action threshold, not the upstream contact test between the "
            "red peg, the pin and the grippers (tasks/sim.py:177-222)",
            "snapshot and restore are not offered: AlohaEnv defines set_state but no get_state (env.py:252), so the "
            "bridge cannot offer the pair",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
