"""OpenMHS driver for gh.openai/multiagent-particle-envs: the simple particle world (a Gymnasium family driver).

The card's entry symbols are ``multiagent.envs:SimpleEnv`` and ``multiagent.envs:SimpleSpeakerListenerEnv``.  Those
names occur only in the two ``gym.register`` calls of ``multiagent/__init__.py``; the clone has no
``multiagent/envs.py`` module at the pinned commit, so the registered entry points cannot be imported.  The class the
documented factory ``make_env.py`` actually builds is ``multiagent.environment:MultiAgentEnv`` (``make_env.py:32-44``),
and that class is named as ``native`` so gate G7 can check the fake against the real surface.  The resulting
``G7.NOT_AN_ENTRY_SYMBOL`` warning is recorded in ``RESULT.json``.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  This package serves the single-agent ``simple.py`` scenario, i.e. the world
``MultiagentSimple-v0`` was meant to register: one movable, silent agent and one immovable landmark.  The action
space is ``Discrete(world.dim_p * 2 + 1)`` with ``world.dim_p = 2``, so ``cap.world.step.v1`` takes ``{ticks,
action}`` with ``action.index`` 0 to 4; ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required bound.

The upstream package imports the legacy gym and numpy (``multiagent/environment.py:1-5`` and ``setup.py:12``), neither
of which is installed where the acceptance gate runs, and package code never imports the clone.  The ``fake``
backend is therefore this package's pure Python re-implementation of the ``simple.py`` world in ``fake.py``; the
``sim`` path (``gymnasium.make(env_id)``) cannot resolve the card's registration because its module is absent, and it
was not run.  Every constant and rule in ``facts`` cites a line of the clone at the pinned commit
83ba4d1aeb00282f7c4acd6912435b3ca642c227.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = "multiagent/__init__.py"
ENVIRONMENT = "multiagent/environment.py"
CORE = "multiagent/core.py"
SIMPLE = "multiagent/scenarios/simple.py"
MAKE_ENV = "make_env.py"


class ParticleSimple(GymnasiumDriver):
    device_id = "multiagent-simple"
    env_id = "MultiagentSimple-v0"
    native = "multiagent.environment:MultiAgentEnv"
    backends = {"fake": ".fake:FakeSimpleEnv"}
    display_name = "OpenAI Multi-Agent Particle Environment (simple world)"
    vendor, model = "OpenAI", "MultiagentSimple-v0 (simple.py scenario)"
    tags = ["multiagent", "particle-environment", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The clone registers MultiagentSimple-v0 with entry point multiagent.envs:SimpleEnv and "
             "max_episode_steps=100", source="upstream_code", ref=f"{REGISTRATION}:9-15"),
        Fact("The clone registers MultiagentSimpleSpeakerListener-v0 with entry point "
             "multiagent.envs:SimpleSpeakerListenerEnv and max_episode_steps=100", source="upstream_code",
             ref=f"{REGISTRATION}:17-21"),
        Fact("make_env builds a MultiAgentEnv from a scenario's make_world, reset_world, reward and observation "
             "callbacks", source="upstream_code", ref=f"{MAKE_ENV}:32-44"),
        Fact("The simple scenario has one movable agent that is silent and does not collide, and one landmark "
             "that does not move or collide", source="upstream_code", ref=f"{SIMPLE}:9-19"),
        Fact("The world has two position dimensions, a 0.1 s timestep and damping 0.25", source="upstream_code",
             ref=f"{CORE}:90-96"),
        Fact("The physical action space of a movable agent is Discrete(world.dim_p * 2 + 1)",
             source="upstream_code", ref=f"{ENVIRONMENT}:43-49"),
        Fact("discrete_action_input defaults to False, whose comment describes the action as a one-hot "
             "N-dimensional vector", source="upstream_code", ref=f"{ENVIRONMENT}:30-31"),
        Fact("With discrete_action_input true, action 1 sets the x force to -1, 2 to +1, 3 sets the y force to "
             "-1 and 4 to +1", source="upstream_code", ref=f"{ENVIRONMENT}:164-167"),
        Fact("The physical action is multiplied by a sensitivity of 5.0 when agent.accel is None",
             source="upstream_code", ref=f"{ENVIRONMENT}:178-181"),
        Fact("A reset draws the agent and landmark positions uniformly from -1 to +1 and zeroes their velocities",
             source="upstream_code", ref=f"{SIMPLE}:32-39"),
        Fact("The observation concatenates the agent velocity with each landmark position relative to the agent",
             source="upstream_code", ref=f"{SIMPLE}:45-50"),
        Fact("The reward is the negative squared distance between the agent and the first landmark",
             source="upstream_code", ref=f"{SIMPLE}:41-43"),
        Fact("The world integrates velocity with damping and force/mass*dt, then position with velocity*dt",
             source="upstream_code", ref=f"{CORE}:158-169"),
        Fact("An agent's mass is 1.0, its motor noise is None and the world applies noise only when u_noise is set",
             source="upstream_code", ref=f"{CORE}:47-69"),
        Fact("MultiAgentEnv.step returns per-agent observation, reward and done lists plus an info dict",
             source="upstream_code", ref=f"{ENVIRONMENT}:80-104"),
        Fact("MultiAgentEnv.reset calls the scenario reset callback and returns a list of per-agent observations",
             source="upstream_code", ref=f"{ENVIRONMENT}:106-116"),
        Fact("A missing done callback makes every done flag False", source="upstream_code",
             ref=f"{ENVIRONMENT}:132-135"),
        Fact("The observation space is a Box from -inf to +inf with shape (obs_dim,) for each agent",
             source="upstream_code", ref=f"{ENVIRONMENT}:67-69"),
        Fact("make_env without benchmark passes no done callback to MultiAgentEnv", source="upstream_code",
             ref=f"{MAKE_ENV}:40-44"),
        Fact("The README says the code base is an archive and that the maintained version is PettingZoo",
             source="vendor_doc", ref="README.md:1-5"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym:MultiagentSimple-v0 (fake: simple.py single-agent world)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 fix the fake's initial state, after which its integration "
                     "is deterministic; upstream draws the initial positions from numpy's global generator "
                     "(simple.py:34-38) and has no env seed parameter, so one seed gives different trajectories on "
                     "the fake and upstream",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake serves the single-agent simple.py scenario only: one movable silent agent and one immovable "
            "landmark; communication, the speaker-listener registration and the other scenarios of the clone are "
            "not modelled",
            "the clone has no multiagent/envs.py, so the two registered ids cannot be constructed at the pinned "
            "commit; the fake stands in for make_env('simple') and the sim backend path was not run",
            "the upstream default discrete_action_input is False and its step expects a 5-element action vector, "
            "while its action_space is Discrete(5); the fake applies the discrete_action_input=True mapping of "
            "environment.py:164-167 so the declared integer action is meaningful",
            "the fake draws positions with Python's random.Random and integrates Python floats; upstream draws "
            "from numpy's global generator and returns float32 arrays, so one seed does not reproduce an upstream "
            "trajectory",
            "the fake returns the Gymnasium (observation, info) reset pair and a five-value step tuple; upstream "
            "returns a list of per-agent observations and a four-value step tuple, and the bridge normalizes both",
            "the class's reset options object is accepted but has no effect: the simple scenario's reset_world "
            "takes no options",
            "no rigid-body dynamics, contacts, friction, actuator, sensor or noise model: the fake integrates the "
            "simple momentum equations directly and the simple scenario disables collisions; the agent has no "
            "motor noise and the fake adds none",
            "no rendering, viewers, render.modes or PassiveEnvChecker, and no wall-clock pacing (realtime_factor 0)",
            "the fake was not compared with an upstream run: gym and numpy were not installed where the gate ran and "
            "the clone was never imported",
            "snapshot and restore are not offered: the upstream class and the fake expose no get_state/set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
