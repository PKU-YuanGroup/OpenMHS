"""OpenMHS driver for gh.openai/robosumo: the RoboSumo two-agent sumo environment (a Gymnasium family driver).

``robosumo.envs:SumoEnv`` is a two-agent ``gym.Env`` built from MuJoCo models.  This package serves the first
registered variant, ``RoboSumo-Ant-vs-Ant-v0`` (``robosumo/__init__.py:8``): both agents are ants, each with eight
motors limited to ``-1.0 .. 1.0`` (``robosumo/envs/assets/ant.xml:58-65``).  The bridge derives the contract from the
environment's spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` where ``action`` is
``{"ant0": [<eight controls>], "ant1": [<eight controls>]}``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The upstream action space is a ``Tuple`` of two ``Box``
spaces (``robosumo/envs/sumo.py:112-114``); the fake names the same two Boxes as ``Dict`` members so the gymnasium
bridge derives the real per-motor ``ctrlrange`` limits (it derives no limits from the elements of a ``Tuple``).  The
device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package (it needs ``gym``, ``mujoco_py`` and MuJoCo, ``requirements.txt:1-5``), so
the ``fake`` backend is this package's pure Python stand-in (``fake.py``).  It is a reduced planar kinematic model,
not MuJoCo, and it was never compared with the upstream environment: the fidelity ``gaps`` below say so, including
the real 120-value per-agent observation it replaces with a three-value position.  A backend name that ``backends``
does not list (``sim``) would be served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path was
not run and would need the upstream package registered with the bridge's gym.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (3a317e27d2342dd47a869950e93315b23a74921a).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

SUMO = "robosumo/envs/sumo.py"
AGENTS = "robosumo/envs/agents.py"
MUJOCO_ENV = "robosumo/envs/mujoco_env.py"
ANT_XML = "robosumo/envs/assets/ant.xml"
TATAMI_XML = "robosumo/envs/assets/tatami.xml"
REGISTRY = "robosumo/__init__.py"


class RoboSumo(GymnasiumDriver):
    device_id = "robosumo"
    env_id = "RoboSumo-Ant-vs-Ant-v0"
    native = "robosumo.envs:SumoEnv"
    backends = {"fake": ".fake:FakeSumoEnv"}
    action_space_ref = f"{ANT_XML}:58-65"
    display_name = "OpenAI RoboSumo Ant-vs-Ant (two-agent MuJoCo sumo)"
    vendor, model = "OpenAI", "RoboSumo-Ant-vs-Ant-v0"
    tags = ["robosumo", "sumo", "multi-agent", "mujoco", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("SumoEnv is a multi-agent sumo environment whose goal is for each agent to push the other agent "
             "outside the tatami area", source="upstream_code", ref=f"{SUMO}:28-36"),
        Fact("RoboSumo-Ant-vs-Ant-v0 registers SumoEnv with agent_names ['ant', 'ant'], agent_densities [13., 13.], "
             "tatami_size 2.0 and timestep_limit 500", source="upstream_code", ref=f"{REGISTRY}:8-17"),
        Fact("The agent models are ant, bug and spider, loaded from assets/ant.xml, assets/bug.xml and "
             "assets/spider.xml", source="upstream_code", ref=f"{SUMO}:21-25"),
        Fact("The observation space and the action space are Tuple spaces of the per-agent spaces",
             source="upstream_code", ref=f"{SUMO}:109-114"),
        Fact("Each agent's action space is a Box built from the actuator ctrlrange; the ant's eight motors each "
             "have ctrlrange -1.0 1.0", source="upstream_code", ref=f"{ANT_XML}:58-65"),
        Fact("An agent's observation concatenates its qpos, its qvel and its clipped external contact forces, then "
             "the opponent's first seven qpos values and the opponent torso contact forces",
             source="upstream_code", ref=f"{AGENTS}:190-212"),
        Fact("A reset places each agent on a circle of radius 1.15 at height 1.25 with a random start angle, then "
             "adds uniform position noise and Gaussian velocity noise", source="upstream_code", ref=f"{SUMO}:232-252"),
        Fact("An agent loses when its z position is below 0.29 or max(|x|, |y|) is at least the environment's "
             "_tatami_size", source="upstream_code", ref=f"{SUMO}:149-150"),
        Fact("The environment stores _tatami_size as tatami_size + 0.1", source="upstream_code", ref=f"{SUMO}:55"),
        Fact("The reward constants are WIN_REWARD 2000, DRAW_PENALTY -1000, MOVE_TO_OPP_COEF 0.1 and PUSH_OUT_COEF "
             "10.0", source="upstream_code", ref=f"{SUMO}:38-43"),
        Fact("The control cost coefficient is 0.1", source="upstream_code", ref=f"{AGENTS}:15-19"),
        Fact("The control reward is minus the control cost coefficient times the sum of the squared action values",
             source="upstream_code", ref=f"{AGENTS}:217-221"),
        Fact("An episode is drawn when the step counter is greater than the timestep limit",
             source="upstream_code", ref=f"{SUMO}:165-167"),
        Fact("The environment step is model.opt.timestep times frame_skip", source="upstream_code",
             ref=f"{MUJOCO_ENV}:122-123"),
        Fact("The tatami model sets the MuJoCo option timestep to 0.01 s and the RK4 integrator",
             source="upstream_code", ref=f"{TATAMI_XML}:3"),
        Fact("SumoEnv takes frame_skip with a default of 5", source="upstream_code", ref=f"{SUMO}:50"),
        Fact("The RoboSumo-Ant-vs-Ant-v0 registration sets no frame_skip", source="upstream_code",
             ref=f"{REGISTRY}:8-17"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    #: The fake is a reduced kinematic stand-in; the real sizes and the missing terms are named in ``gaps``.
    fidelity = {
        "engine": "robosumo:RoboSumo-Ant-vs-Ant-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial state and the reduced dynamics are "
                     "deterministic, so the fake repeats a trajectory for the same seed and actions; the upstream "
                     "environment draws its reset noise from numpy's generator and integrates MuJoCo, so a seed "
                     "does not give the same trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake has no dynamics: positions change by a fixed planar kinematic rule, not by forces or contacts; "
            "there is no friction, actuator, sensor or noise model, and it was not compared with the upstream "
            "environment",
            "the fake exposes the action space as a Dict with the named members ant0 and ant1 so the bridge derives "
            "the real per-motor ctrlrange limits; the upstream action space is a Tuple of the same two Box spaces "
            "(sumo.py:112-114), so the sim backend, which was not run, would present the Tuple shape",
            "the real per-agent observation is 120 values for Ant-vs-Ant: 15 qpos, 14 qvel, 78 clipped contact "
            "forces from 13 bodies, 7 opponent torso qpos values and 6 opponent torso forces "
            "(agents.py:190-212); the fake returns a three-value position observation per agent",
            "the upstream step returns a tuple of per-agent rewards and infos (sumo.py:188-192); the bridge's "
            "scalar reward is the sum of the two agents' reduced rewards, and the per-agent rewards are carried "
            "only in the info object",
            "the move_to_opp and push_opp shaping terms (sumo.py:168-184) are not modelled; the fake computes the "
            "win/loss/draw main reward and the control cost (agents.py:217-221)",
            "the per-motor bounds come from the fake's two Box spaces; the fake also rejects an out-of-range control "
            "itself, but the runtime refusal is the authoritative one",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (50 ms = 0.01 s "
            "model timestep times frame_skip 5) only",
            "snapshot and restore are not offered: the upstream class has set_state but no get_state pair for the "
            "bridge, and the fake exposes none",
        ],
    }
