"""OpenMHS driver for gh.sjtu-visys-team/visfly: the ``NavigationEnv`` quadrotor world (a Gymnasium family driver).

VisFly is a Habitat-Sim quadrotor simulator (``readme.md:3-6``).  Its main environment, ``envs.NavigationEnv``
(``envs/NavigationEnv.py:27``), is a stable-baselines3 ``VecEnv`` subclass (``envs/base/droneGymEnv.py:19``), not a
Gymnasium ``Env``: ``reset(state=None, ...)`` returns one observation mapping and ``step(_action, ...)`` returns a
four-tuple ``(observation, reward, done, info)`` (``envs/base/droneGymEnv.py:302`` and ``:141``).  The class-level
``make_bridge`` below wraps the backend in :class:`_NavigationGymAdapter`, which translates that interface to the
Gymnasium contract the family bridge serves.  The contract itself (``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1``) is still derived from the environment's spaces by ``GymnasiumBridge``: a four-element ``Box``
action from -1 to 1 (``envs/base/droneGymEnv.py:108-116``), a ``Dict`` observation with ``state`` (13 values) and
``target`` (3 values) (``envs/base/droneGymEnv.py:76-82``, ``envs/NavigationEnv.py:58-59``), and the
``max_episode_steps`` time limit (``envs/NavigationEnv.py:41``, ``envs/base/droneGymEnv.py:193`` and ``:264-267``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.
The gate never installs Habitat-Sim or the clone, so the ``fake`` backend is the package's own kinematic stand-in
(``fake.py``); the upstream simulator path (``sim``) is refused with an explanation because it needs the modified
Habitat-Sim build and the ReplicaCAD demo dataset, neither of which is vendored here (``readme.md:36-48`` and
``:62-73``, ``environment.yml:334``).  Every number cited in a Fact is a line of the clone at the pinned commit.

The ``fidelity`` attribute is the contract of the checked fake backend (spec 05-fidelity FID-002): it is F0 because the
fake is a kinematic stand-in, not the Habitat-Sim rigid-body world, and the ``gaps`` say what is not modelled.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import DriverDefinitionError, Fact, GymnasiumDriver

NAVIGATION = "envs/NavigationEnv.py"
GYM_ENV = "envs/base/droneGymEnv.py"
DRONE_ENV = "envs/base/droneEnv.py"
DYNAMICS = "envs/base/dynamics.py"
README = "readme.md"


class _NavigationGymAdapter:
    """Translate the upstream batched ``VecEnv`` interface to the Gymnasium ``Env`` contract of the bridge.

    ``reset`` applies a seed through ``envs.set_seed`` (``envs/base/droneEnv.py:381-385``) and forwards an optional
    ``options`` mapping to the upstream reset arguments.  ``step`` wraps the bridge's four-element action into the
    ``(num_agent, 4)`` batch the upstream step expects (``envs/base/droneGymEnv.py:122`` and ``:143``) and turns the
    upstream done/time-limit information into ``terminated``/``truncated``.  Observations are converted from torch
    tensors to plain JSON data and a leading batch dimension of one is removed, so the observation matches the
    (unbatched) observation space.
    """

    def __init__(self, native):
        self._env = native
        self.action_space = native.action_space
        self.observation_space = native.observation_space

    def reset(self, seed=None, options=None):
        if seed is not None:
            envs = getattr(self._env, "envs", None)
            set_seed = getattr(envs, "set_seed", None)
            if callable(set_seed):
                set_seed(int(seed))
        arguments = {}
        if isinstance(options, dict):
            for name in ("state", "predicted_obs", "is_test", "stoch", "deter"):
                if name in options:
                    arguments[name] = options[name]
        observation = self._env.reset(**arguments) if arguments else self._env.reset()
        return _observation(observation, self.observation_space), {}

    def step(self, action):
        values = action.get("values") if isinstance(action, dict) else action
        result = self._env.step([list(values)])
        if not isinstance(result, (list, tuple)) or len(result) not in (4, 5):
            raise RuntimeError("the upstream step did not return a four- or five-element result")
        if len(result) == 5:
            observation, reward, terminated, truncated, info = result
        else:
            observation, reward, done, info = result
            info = _first_mapping(info)
            truncated = bool(info.get("TimeLimit.truncated", False))
            terminated = bool(_scalar(done)) and not truncated
        return (_observation(observation, self.observation_space), float(_scalar(reward)),
                bool(terminated), bool(truncated), _plain(info))

    def close(self):
        close = getattr(self._env, "close", None)
        if callable(close):
            close()


def _plain(value):
    """Convert torch tensors, numpy arrays and mappings to JSON data without importing either library."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _plain(tolist())
    return value


def _scalar(value):
    """A one-element batch (a tensor or a list) as its element."""
    value = _plain(value)
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    return value


def _first_mapping(info):
    """The upstream ``info`` is one mapping per agent; the bridge serves one world."""
    if isinstance(info, (list, tuple)) and info and isinstance(info[0], dict):
        return info[0]
    return info if isinstance(info, dict) else {}


def _shape(value):
    shape = []
    item = value
    while isinstance(item, (list, tuple)):
        shape.append(len(item))
        item = item[0] if item else None
    return tuple(shape)


def _observation(observation, space):
    """JSON observation; drop one leading batch dimension when the space (and not the batch) has the inner shape."""
    plain = _plain(observation)
    if not isinstance(plain, dict):
        return plain
    spaces = getattr(space, "spaces", None)
    if not isinstance(spaces, dict):
        return plain
    out = {}
    for key, value in plain.items():
        expected = getattr(spaces.get(key), "shape", None)
        if expected is not None and _shape(value) == (1,) + tuple(expected):
            value = value[0]
        out[str(key)] = value
    return out


class VisFlyNavigation(GymnasiumDriver):
    device_id = "visfly-navigation"
    env_id = "VisFly-Navigation-v0"
    native = "envs.NavigationEnv:NavigationEnv"
    backends = {"fake": ".fake:FakeNavigationEnv"}
    seed = 42
    display_name = "VisFly NavigationEnv (Habitat-Sim quadrotor navigation)"
    vendor, model = "SJTU-ViSYS Team", "VisFly NavigationEnv"
    tags = ["drone", "quadrotor", "navigation", "vision-based-flight", "reinforcement-learning", "simulation",
            "habitat-sim", "gymnasium"]
    facts = [
        Fact("VisFly is a quadrotor simulator for vision-based flight and is built on Habitat-Sim",
             source="vendor_doc", ref=f"{README}:3-6"),
        Fact("The demo datasets are built from ReplicaCAD and are downloaded separately from Hugging Face with Git "
             "LFS", source="vendor_doc", ref=f"{README}:36-48"),
        Fact("The modified habitat-sim is cloned separately and built from source", source="vendor_doc",
             ref=f"{README}:62-73"),
        Fact("The conda environment pins habitat-sim==0.3.1", source="upstream_code", ref="environment.yml:334"),
        Fact("NavigationEnv extends DroneGymEnvsBase", source="upstream_code", ref=f"{NAVIGATION}:27"),
        Fact("DroneGymEnvsBase extends the stable-baselines3 VecEnv", source="upstream_code", ref=f"{GYM_ENV}:19"),
        Fact("NavigationEnv defaults to seed 42, visual=True and max_episode_steps=256", source="upstream_code",
             ref=f"{NAVIGATION}:32-41"),
        Fact("The action space is a four-element Box with low -1 and high 1 for bodyrate, thrust, velocity and "
             "position control", source="upstream_code", ref=f"{GYM_ENV}:108-116"),
        Fact("The default action type is bodyrate", source="upstream_code", ref=f"{DYNAMICS}:29"),
        Fact("The control interval ctrl_dt defaults to 0.03 s and the integration step dt to 0.005 s",
             source="upstream_code", ref=f"{DYNAMICS}:32-33"),
        Fact("The state is position (3), orientation quaternion (4), velocity (3) and angular velocity (3), 13 "
             "values in total", source="upstream_code", ref=f"{DYNAMICS}:779-786"),
        Fact("The observation space is a Dict whose state Box has state_size elements", source="upstream_code",
             ref=f"{GYM_ENV}:76-82"),
        Fact("NavigationEnv adds a target Box of 3 values to the observation space and the default target is "
             "[9, 0, 1]", source="upstream_code", ref=f"{NAVIGATION}:58-59"),
        Fact("When visual is true the observation also carries a depth array read from the sensor observations",
             source="upstream_code", ref=f"{NAVIGATION}:69-74"),
        Fact("reset accepts an optional state and returns the observations", source="upstream_code",
             ref=f"{GYM_ENV}:302-309"),
        Fact("The reset state is a four- or six-part tuple: position, orientation, velocity, angular velocity and "
             "optionally motor speed and thrust", source="upstream_code", ref=f"{DRONE_ENV}:270-276"),
        Fact("step requires a reset first, converts the action to a tensor and advances the simulator",
             source="upstream_code", ref=f"{GYM_ENV}:141-146"),
        Fact("An episode is done on success, failure, out of bounds, collision, or when the step count reaches "
             "max_episode_steps", source="upstream_code", ref=f"{GYM_ENV}:187-193"),
        Fact("collect_info sets TimeLimit.truncated when the step count has reached max_episode_steps",
             source="upstream_code", ref=f"{GYM_ENV}:264-267"),
        Fact("Success means the distance from the position to the target is at most success_radius", source="upstream_code",
             ref=f"{NAVIGATION}:81-82"),
        Fact("The success radius defaults to 0.5", source="upstream_code", ref=f"{NAVIGATION}:61"),
        Fact("DroneEnvsBase.set_seed forwards the seed to the dynamics and the scene manager", source="upstream_code",
             ref=f"{DRONE_ENV}:381-385"),
        Fact("Dynamics.set_seed calls torch.manual_seed", source="upstream_code", ref=f"{DYNAMICS}:556-557"),
        Fact("The dynamics constructor seeds itself with its seed argument", source="upstream_code",
             ref=f"{DYNAMICS}:80"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the checked fake backend (spec 05-fidelity FID-002).  It describes the kinematic
    #: stand-in that the package actually serves, not the Habitat-Sim model that would sit behind ``sim``.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "a reset seed is applied through DroneEnvsBase.set_seed, which calls torch.manual_seed and sets "
                     "the scene-manager seed (envs/base/droneEnv.py:381-385, envs/base/dynamics.py:556-557); the fake "
                     "reseeds its start-state generator from the same seed. The two use different generators, so one "
                     "seed repeats a trajectory within one implementation but not across the fake and upstream",
        },
        "timestep_ms": 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic point model: the four commands are mapped to a velocity vector; there is no rigid-body "
            "dynamics, motor, rotor, drag, contact, wind, sensor-noise or scene model (the upstream engine is "
            "Habitat-Sim, readme.md:6)",
            "the fake rewards are a placeholder distance term, not the upstream navigation reward "
            "(envs/NavigationEnv.py:85-99)",
            "the depth/RGB rendering and the habitat-sim scenes are NOT COVERED: the fake observation has only state "
            "(13 values) and target (3 values), while the upstream visual observation adds depth "
            "(envs/NavigationEnv.py:69-74); the fake start state is drawn from Python's random generator, upstream "
            "draws it from a torch state generator",
            "the sim backend is refused: the upstream simulation needs the modified habitat-sim built from source "
            "and the ReplicaCAD demo dataset (readme.md:36-48, readme.md:62-73), neither of which was installed or run",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }

    def open_native(self):
        if self.backend == "sim":
            raise DriverDefinitionError(
                "the upstream VisFly simulator is not provided by this package: it needs the modified habitat-sim "
                "build (readme.md:62-73, environment.yml:334) and the ReplicaCAD demo dataset (readme.md:36-48), "
                "neither of which was installed or run; use the fake backend")
        return super().open_native()

    def make_bridge(self, native):
        from mhs.bridge.gymnasium import GymnasiumBridge

        cls = type(self)
        # the adapter hands the bridge the backend's own action space
        origin = f"the {self.backend} backend {dict(cls.backends).get(self.backend)}"
        return GymnasiumBridge(env=_NavigationGymAdapter(native), env_id=cls.env_id, seed=cls.seed,
                               device_id=self.device_id, autoreset=cls.autoreset, max_ticks=cls.max_ticks,
                               env_origin=origin)
