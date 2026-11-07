"""OpenMHS driver for gh.openai/multiagent-competition: the run-to-goal-ants-v0 environment.

The upstream package is ``gym-compete``, a legacy ``gym`` 0.9.1 / MuJoCo 1.31 multi-agent environment.  The card
chooses the gymnasium family, and this package uses ``GymnasiumDriver``: ``env_id`` names the registered environment
and the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the environment's
Tuple action space and Tuple observation space.  The driver is configuration only; it declares the environment, its
provenance and its fidelity contract.  The device is simulated (R0): there is no hardware backend and no
operator-required limit.

Two translations are specific to this legacy multi-agent environment (both are disclosed in the fidelity ``gaps``):

* upstream ``reset`` returns a bare tuple of per-agent observations, but the bridge reads a reset two-tuple as
  ``(observation, info)``; the fake therefore returns ``(observations, {})``;
* upstream ``_step`` returns a tuple of per-agent rewards and a tuple of per-agent dones, but
  ``cap.world.step.v1`` carries one scalar reward and one scalar terminal flag; the fake sums the rewards, reports
  termination when any agent is done and keeps the per-agent values in ``info``.

The gate cannot import the clone (it needs gym 0.9.1, mujoco-py 0.5.7 and MuJoCo 1.31, ``README.md:9-11``), so the
``fake`` backend is the package's own pure Python kinematic stand-in (``fake.py``).  A backend name that ``backends``
does not list (``sim``) is served by ``gym.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the
legacy stack and was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend
only.

Every fact and fidelity claim cites a line of the clone at the pinned commit
b2e081a192429913b7d21a89525901d59c85e7f3.  The observation is 122 values per ant on the upstream environment; the
fake uses that size, derived in ``fake.py`` from the same lines.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = "gym-compete/gym_compete/__init__.py"
ENV = "gym-compete/gym_compete/new_envs/multi_agent_env.py"
SCENE = "gym-compete/gym_compete/new_envs/multi_agent_scene.py"
AGENT = "gym-compete/gym_compete/new_envs/agents/agent.py"
ANT = "gym-compete/gym_compete/new_envs/agents/ant.py"
ANT_XML = "gym-compete/gym_compete/new_envs/assets/ant_body.xml"
WORLD_XML = "gym-compete/gym_compete/new_envs/assets/world_body.ant_body.ant_body.xml"


class MultiAgentCompetition(GymnasiumDriver):
    device_id = "gym-compete-ants"
    env_id = "run-to-goal-ants-v0"
    native = "gym_compete.new_envs:MultiAgentEnv"
    backends = {"fake": ".fake:FakeMultiAgentEnv"}
    display_name = "OpenAI gym-compete run-to-goal-ants-v0 (two ants)"
    vendor, model = "OpenAI", "gym-compete run-to-goal-ants-v0"
    risk = "R0"
    tags = ["multi-agent", "ants", "mujoco", "gym", "reinforcement-learning", "simulation"]
    facts = [
        Fact("run-to-goal-ants-v0 is registered with entry point gym_compete.new_envs:MultiAgentEnv, two ant "
             "agents, the ant scene XML and the initial positions [(-1, 0, 0.75), (1, 0, 0.75)]",
             source="upstream_code", ref=f"{REGISTRATION}:4-15"),
        Fact("MultiAgentEnv builds observation_space and action_space as a Tuple with one entry per agent",
             source="upstream_code", ref=f"{ENV}:103-111"),
        Fact("MultiAgentEnv._step advances the scene, collects per-agent rewards, dones and infos, and returns a "
             "tuple of per-agent observations", source="upstream_code", ref=f"{ENV}:135-157"),
        Fact("MultiAgentScene.simulate concatenates the per-agent actions and calls do_simulation with the scene's "
             "frame_skip", source="upstream_code", ref=f"{SCENE}:16-18"),
        Fact("MultiAgentScene constructs gym's MuJoCo environment with frame_skip 5", source="upstream_code",
             ref=f"{SCENE}:12"),
        Fact("The ant scene XML sets the MuJoCo timestep to 0.01 s", source="upstream_code", ref=f"{WORLD_XML}:4"),
        Fact("Agent.set_action_space builds each agent's Box from the XML actuator ctrlrange and falls back to "
             "infinite bounds when no range is found", source="upstream_code", ref=f"{AGENT}:50-75"),
        Fact("The ant XML declares eight motors with ctrlrange -1.0 to 1.0", source="upstream_code",
             ref=f"{ANT_XML}:56-64"),
        Fact("The ant observation concatenates its qpos, qvel, clipped external contact forces and the other "
             "agent's qpos", source="upstream_code", ref=f"{ANT}:48-61"),
        Fact("The ant observation space is Box(-inf, inf) with the observation size computed from that "
             "observation", source="upstream_code", ref=f"{ANT}:63-68"),
        Fact("MultiAgentEnv._seed delegates seeding to the scene", source="upstream_code", ref=f"{ENV}:165-166"),
        Fact("MultiAgentEnv.dt returns the scene's dt", source="upstream_code", ref=f"{ENV}:176-178"),
        Fact("MultiAgentEnv.reset_model resets the scene and every agent and returns the per-agent observations",
             source="upstream_code", ref=f"{ENV}:186-191"),
        Fact("The tested stack is gym 0.9.1 with MuJoCo 1.31 and mujoco-py 0.5.7 on Python 3.6", source="vendor_doc",
             ref="README.md:9-11"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and clock from the backend; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym-compete:run-to-goal-ants-v0 (legacy gym 0.9.1 + MuJoCo 1.31 on the sim backend; the fake "
                  "backend is an analytic kinematic stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "seed() or reset(seed) fixes the fake's initial joint offsets and the kinematic update is "
                     "deterministic, so one seed and one action sequence repeat a state-hash trajectory; the "
                     "upstream MuJoCo scene uses gym's and MuJoCo's generators, and this fake uses Python's "
                     "random.Random, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic: no MuJoCo rigid-body integration, contact solver, actuator, sensor or "
            "noise model is implemented, and its external contact forces are reported as zero",
            "one environment step is 50 ms: the MuJoCo timestep in the ant scene XML is 0.01 s (world XML:4) and "
            "MultiAgentScene passes frame_skip 5 (multi_agent_scene.py:12), so the contract exposes the 50 ms "
            "control-step period as timestep_ms and one step contains five 10 ms integrations",
            "the upstream MultiAgentEnv returns a tuple of per-agent rewards and a tuple of per-agent dones; "
            "cap.world.step.v1 carries one scalar reward and one scalar terminal flag, so the fake sums the "
            "rewards, terminates when any agent is done and keeps the per-agent values in info",
            "the upstream legacy gym reset returns a bare observation tuple; the bridge reads a reset two-tuple as "
            "(observation, info), so the fake returns (observations, {})",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time only",
            "the fake has no goal, fall, arena or rendering logic, no per-agent policies and no demo policies; it "
            "was never compared with the upstream MuJoCo environment",
            "the sim backend (gym.make of the legacy environment) needs gym 0.9.1, mujoco-py 0.5.7 and MuJoCo "
            "1.31 and was not run",
        ],
    }
