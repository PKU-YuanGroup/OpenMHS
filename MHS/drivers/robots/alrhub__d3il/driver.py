"""OpenMHS driver for gh.alrhub/d3il: the sorting-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{"values": [dx, dy]}``
bounded per element by the Box below, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The upstream environment is a legacy ``gym`` environment (``from gym.spaces import Box``, sorting.py:6) registered
with ``gym.envs.registration.register`` (gym_sorting/__init__.py:1-8).  Its ``reset`` takes ``random`` and
``context``, not ``seed``, and its ``step`` returns the legacy four-tuple; the Gymnasium bridge falls back to the
legacy ``gym.Env.seed`` method when ``reset(seed=...)`` is refused (bridge/gymnasium.py:716-751) and accepts a
four-tuple result (bridge/gymnasium.py:674-684).

Why a fake: the clone imports MuJoCo (``mujoco``/``mujoco_py``), numpy, gym and cv2 at module import, and package
code never imports the clone.  The ``fake`` backend is a pure Python kinematic stand-in (fake.py).  A backend name
that ``backends`` does not list (``sim``) is served by ``gym.make("sorting-v0", render=False)``
(GymnasiumDriver.open_native); that path needs the upstream package, MuJoCo 2.1 binaries and a C compiler
(card ``install.system_deps``) and was not run here.

The ``fidelity`` attribute is the complete contract of the model served by the checked fake (spec 05-fidelity
FID-002): a kinematic F0 model, one 35 ms control step per tick, seeded by the fake's own Python generator.  Every
fact cites a line of the clone at the pinned commit (1d9c71850d4fc1477cee17b557c8b97d70b13071).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

SORTING = "environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py"
WRAPPER = "environments/d3il/d3il_sim/gyms/gym_env_wrapper.py"
REGISTRY = "environments/d3il/envs/gym_sorting_env/gym_sorting/__init__.py"
OBJECTS = "environments/d3il/envs/gym_sorting_env/gym_sorting/envs/objects/sorting_objects.py"


class D3ILSorting(GymnasiumDriver):
    device_id = "d3il-sorting"
    env_id = "sorting-v0"
    native = "gym_sorting.envs:Sorting_Env"
    # The registration passes render=True; a headless server opens the MuJoCo scene without a viewer.
    env_kwargs = {"render": False}
    backends = {"fake": ".fake:FakeSortingEnv"}
    action_space_ref = f"{SORTING}:237-239"
    display_name = "d3il sorting-v0 (MuJoCo Panda sorting)"
    vendor, model = "alrhub", "sorting-v0"
    tags = ["sorting", "manipulation", "mujoco", "reinforcement-learning", "simulation", "gymnasium", "d3il"]
    facts = [
        Fact("sorting-v0 is registered with entry point gym_sorting.envs:Sorting_Env, max_episode_steps=2000 and "
             "the kwargs max_steps_per_episode=100, render=True, num_boxes=2 and if_vision=False",
             source="upstream_code", ref=f"{REGISTRY}:3-8"),
        Fact("The action space is a 2-D Box with low [-0.01, -0.01] and high [0.01, 0.01]",
             source="upstream_code", ref=f"{SORTING}:237-239"),
        Fact("The observation space is a Box with shape (8,) and unbounded low -inf and high +inf",
             source="upstream_code", ref=f"{SORTING}:240-242"),
        Fact("With num_boxes=2 the observation concatenates the robot xy, the red box xy and yaw tangent and the "
             "blue box xy and yaw tangent", source="upstream_code", ref=f"{SORTING}:340-350"),
        Fact("get_reward returns 0", source="upstream_code", ref=f"{SORTING}:509-511"),
        Fact("The episode terminates when every red box is in x (0.3, 0.5) and y (0.22, 0.41) and every blue box "
             "is in x (0.525, 0.725) and y (0.22, 0.41); with num_boxes=2 those are the red and blue box",
             source="upstream_code", ref=f"{SORTING}:523-541"),
        Fact("The wrapper ends an episode when terminated, the task's early termination or env_step_counter >= "
             "max_steps_per_episode - 1 is true", source="upstream_code", ref=f"{WRAPPER}:124-137"),
        Fact("The MuJoCo scene is created with the physics timestep dt=0.001 s", source="upstream_code",
             ref=f"{SORTING}:218-220"),
        Fact("n_substeps defaults to 35 controller steps per environment step", source="upstream_code",
             ref=f"{SORTING}:196"),
        Fact("A step passes the action to the Cartesian controller's setSetPoint and executes n_substeps "
             "controller steps", source="upstream_code", ref=f"{WRAPPER}:83-86"),
        Fact("The initial end-effector position is [0.525, -0.3, 0.25]", source="upstream_code",
             ref=f"{OBJECTS}:11"),
        Fact("The context manager samples six box positions from 3-D Box spaces with x in [0.4, 0.5] or "
             "[0.55, 0.65], y in [-0.15, 0.1] and yaw in [-90, 90] degrees", source="upstream_code",
             ref=f"{SORTING}:52-74"),
        Fact("The wrapper's seed method delegates to gym.utils.seeding.np_random and returns the accepted seed",
             source="upstream_code", ref=f"{WRAPPER}:41-43"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step, reset and seed until "
                  "mhs.safety.reset clears the latch, and the last state stays readable")
    #: The fidelity contract of the model served by the fake (spec 05-fidelity section 2).  The bridge derives the
    #: engine, determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym:sorting-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its own Python generator and its state transitions are deterministic, so one "
                     "seed repeats a trajectory of the fake; the upstream manager draws box positions from numpy's "
                     "global generator and GymEnvWrapper.seed sets np_random instead, so a seed does not reproduce "
                     "the upstream start state",
        },
        "timestep_ms": 35.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic 2-D state transitions only: the fake moves the end-effector by the action and pushes a box "
            "it touches; it has no forces, contacts, arm joints, gripper, actuator, sensor or noise model, and the "
            "upstream MuJoCo scene was not imported or run",
            "the upstream scene integrates MuJoCo at dt=0.001 s for n_substeps=35 per environment step (a 1 ms "
            "physics timestep and a 35 ms control period); the fake advances one 35 ms control step per tick and "
            "does not integrate the 1 ms physics substeps",
            "the fake draws start positions with Python's random.Random and shuffles them; the upstream manager "
            "seeds numpy's global generator once (np.random.seed(42)) and GymEnvWrapper.seed sets np_random "
            "instead, so one seed does not give the same start state on the two",
            "the fake interprets the 2-D action as an end-effector displacement, while the wrapper passes it to "
            "CartPosQuatImpedenceController.setSetPoint, whose implementation reads a 3-D position and a "
            "quaternion; the upstream step does not accept the 2-element action unchanged",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by 35 ms only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the fake returns lists of Python floats; upstream returns float32 numpy arrays and renders through "
            "MuJoCo, which the fake does not",
            "sorting-v0 passes max_steps_per_episode=100 in its registration, not the constructor default 2000; "
            "the fake uses the registered value",
        ],
    }
