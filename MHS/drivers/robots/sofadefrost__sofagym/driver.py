"""OpenMHS driver for gh.sofadefrost/sofagym: the trunk-v0 soft-trunk environment (a Gymnasium family driver).

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.*`` contract from the environment's spaces.  ``trunk-v0`` is registered with entry point
``sofagym.envs:TrunkEnv`` (sofagym/envs/__init__.py:64-67).  ``TrunkEnv`` is not itself a ``gym.Env``: it wraps an
``AbstractEnv`` in ``self.env`` and forwards every missing attribute to it (sofagym/envs/Trunk/TrunkEnv.py:61-65 and
:82-85), so ``step``, ``seed`` and ``close`` are ``AbstractEnv`` methods.  The action space is ``Discrete(16)`` and the
observation space is a 66-element ``Box`` from -1 to 1 (TrunkEnv.py:32, :54, :72 and :75-77).  ``cap.world.step.v1``
therefore takes ``{ticks, action: {index}}`` with ``index`` from 0 to 15; actions 0-7 pull cables 0-7 by +1 and actions
8-15 by -1 (TrunkToolbox.py:331-378).

The device is simulated (R0): there is no hardware backend, no path to a machine and no operator-required bound.  The
upstream environment needs a SOFA v23.06 installation with SofaPython3 and the SoftRobots plugins (README.md:12-20),
which the gate does not have and package code never imports, so the ``fake`` backend is this package's own pure Python
``FakeTrunkEnv`` (fake.py).  A backend name that ``backends`` does not list (``sim``) would be served by
``gym.make("trunk-v0")`` after importing the clone; that path was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit f5ad4e44a0dc522d8018c184245b7aa630292118.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

TRUNK_ENV = "sofagym/envs/Trunk/TrunkEnv.py"
TRUNK_TOOLBOX = "sofagym/envs/Trunk/TrunkToolbox.py"
TRUNK_SCENE = "sofagym/envs/Trunk/TrunkScene.py"
ABSTRACT_ENV = "sofagym/AbstractEnv.py"
ENV_REGISTRY = "sofagym/envs/__init__.py"
README = "README.md"


class SofaGymTrunk(GymnasiumDriver):
    device_id = "sofagym-trunk"
    env_id = "trunk-v0"
    native = "sofagym.envs.Trunk.TrunkEnv:TrunkEnv"
    backends = {"fake": ".fake:FakeTrunkEnv"}
    display_name = "SofaGym soft trunk (trunk-v0)"
    vendor, model = "SofaDefrost", "trunk-v0"
    tags = ["soft-robotics", "trunk", "cable-actuated", "reinforcement-learning", "simulation", "sofagym"]
    facts = [
        Fact("SofaGym registers 'trunk-v0' with entry point 'sofagym.envs:TrunkEnv'", source="upstream_code",
             ref=f"{ENV_REGISTRY}:64-67"),
        Fact("TrunkEnv.DEFAULT_CONFIG sets scene Trunk, deterministic True, goal True, the goalList positions "
             "[40, 40, 100] and [-10, 20, 80], scale_factor 5, timer_limit 250, discrete True, dt 0.01, nb_actions 16, "
             "dim_state 66 and randomize_states False", source="upstream_code", ref=f"{TRUNK_ENV}:33-59"),
        Fact("TrunkEnv sets the wrapped environment's action_space to spaces.Discrete(nb_actions)",
             source="upstream_code", ref=f"{TRUNK_ENV}:72"),
        Fact("TrunkEnv sets the wrapped environment's observation_space to a Box with low -1 and high 1 and "
             "dim_state elements", source="upstream_code", ref=f"{TRUNK_ENV}:75-77"),
        Fact("TrunkEnv constructs an AbstractEnv (or a ServerEnv when use_server is set) and keeps it in self.env",
             source="upstream_code", ref=f"{TRUNK_ENV}:65"),
        Fact("TrunkEnv defines __getattr__ and forwards any missing attribute to its wrapped environment",
             source="upstream_code", ref=f"{TRUNK_ENV}:82-85"),
        Fact("TrunkEnv.reset calls initialize_states, init_goal and the wrapped environment's reset, then returns "
             "the state array", source="upstream_code", ref=f"{TRUNK_ENV}:87-101"),
        Fact("AbstractEnv.step returns the legacy four-tuple obs, reward, done, info", source="upstream_code",
             ref=f"{ABSTRACT_ENV}:324-367"),
        Fact("AbstractEnv.step calls step_simulation once per environment step", source="upstream_code",
             ref=f"{ABSTRACT_ENV}:351"),
        Fact("step_simulation applies the action and then runs scale_factor simulation steps of dt seconds each",
             source="upstream_code", ref=f"{ABSTRACT_ENV}:544-548"),
        Fact("The default trunk configuration sets scale_factor 5 and dt 0.01 s, so one environment step advances "
             "0.05 s of simulated time", source="upstream_code", ref=f"{TRUNK_ENV}:40-53"),
        Fact("action_to_command maps actions 0-7 to cables 0-7 with displacement +1 and actions 8-15 to cables 0-7 "
             "with displacement -1, and raises NotImplementedError for any other action", source="upstream_code",
             ref=f"{TRUNK_TOOLBOX}:331-378"),
        Fact("The trunk prefab is documented as actuated with 8 cables", source="upstream_code",
             ref=f"{TRUNK_SCENE}:42"),
        Fact("The trunk scene creates four large cables and four small cables in self.cables; each large cable has "
             "21 positions (a pull point plus the 20 points of the loop) and each small one 11 (a pull point plus "
             "10)", source="upstream_code", ref=f"{TRUNK_SCENE}:80-123"),
        Fact("getState reads the point count of the first cable, averages those points over the first four cables, "
             "rounds every coordinate to 3 decimals and divides it by 4, then appends the goal position",
             source="upstream_code", ref=f"{TRUNK_TOOLBOX}:204-235"),
        Fact("The tip used by the reward is the mean of the last points of the first four cables",
             source="upstream_code", ref=f"{TRUNK_TOOLBOX}:103-121"),
        Fact("The reward is min(sqrt(max((previous distance - current distance) / previous distance, 0)), 1.0) and "
             "the cost is the current tip-to-goal distance", source="upstream_code", ref=f"{TRUNK_TOOLBOX}:77-82"),
        Fact("getReward returns done True when the tip-to-goal distance is at most 1.0 and False otherwise",
             source="upstream_code", ref=f"{TRUNK_TOOLBOX}:238-257"),
        Fact("A reset draws a new goal from goalList with np_random.choice", source="upstream_code",
             ref=f"{ABSTRACT_ENV}:228-234"),
        Fact("seed() replaces np_random with seeding.np_random(seed)", source="upstream_code",
             ref=f"{ABSTRACT_ENV}:250"),
        Fact("AbstractEnv initializes np_random from config['seed'] in __init__", source="upstream_code",
             ref=f"{ABSTRACT_ENV}:161-163"),
        Fact("AbstractEnv.step increments timer and sets a local truncated flag at timer_limit but returns the "
             "four-tuple without it, so the flag is discarded", source="upstream_code", ref=f"{ABSTRACT_ENV}:359-367"),
        Fact("The cable constraints set maxPositiveDisp 70 for the large cables and 40 for the small cables, with "
             "maxDispVariation 1", source="upstream_code", ref=f"{TRUNK_SCENE}:98-121"),
        Fact("The trunk length is 195 and the four pull points sit at distance 10 from the axis",
             source="upstream_code", ref=f"{TRUNK_SCENE}:72-77"),
        Fact("TrunkEnv declares dim_state 66", source="upstream_code", ref=f"{TRUNK_ENV}:32"),
        Fact("SofaGym needs a SOFA installation, currently supported version v23.06, with the mandatory SofaPython3 "
             "plugin and SoftRobots among the optional plugins", source="vendor_doc", ref=f"{README}:12-20"),
        Fact("The README states SofaGym works with gym v0.21.0", source="vendor_doc", ref=f"{README}:29"),
        Fact("The documented loop is gym.make('trunk-v0'), env.seed(42), env.reset(), then env.step(action) "
             "returning observation, reward, done and info, and env.close()", source="vendor_doc",
             ref=f"{README}:108-118"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "sofagym:trunk-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the goal is drawn from goalList with the environment's np_random, seeded by seed() or by the "
                     "legacy reset(seed) fallback of the bridge, and the cable model is deterministic, so one "
                     "implementation repeats a trajectory for the same seed and actions; this package's fake draws "
                     "with Python's random.Random and upstream with gym's numpy generator, so one seed can give a "
                     "different goal and trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "SOFA TetrahedronFEM deformation of a soft trunk with eight cable constraints is replaced by a "
            "placeholder kinematic bend (a lateral offset proportional to the cable displacement), so trajectories "
            "do not match the clone's finite-element solve",
            "the scene's own cable geometry (length 195, 21 points, four radial families) is rebuilt from "
            "TrunkScene.py:72-95, but the four small cables do not change the state the clone reads (getState uses "
            "cables[:4]) and are folded into the shared bend by this fake",
            "the goal is drawn with Python's random.Random; upstream draws it with gym.utils.seeding.np_random, so "
            "the same seed can select a different goal",
            "the clone's step returns a four-tuple and discards the timer_limit truncation it computes "
            "(AbstractEnv.py:359-367); the fake does the same, so a long episode is never truncated or terminated "
            "by the timer",
            "the declared observation_space Box(-1, 1, 66) does not bound the coordinates getState returns; neither "
            "the bridge nor the fake clamps observations",
            "no rendering, viewer, camera or image output is modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
