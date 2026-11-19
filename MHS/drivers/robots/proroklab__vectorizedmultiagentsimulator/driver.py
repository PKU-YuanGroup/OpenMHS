"""OpenMHS driver for gh.proroklab/vectorizedmultiagentsimulator: the VMAS balance scenario behind its Gymnasium wrapper.

VMAS is a vectorized multi-agent simulator (README.md:26) whose environment factory builds an ``Environment`` from a
scenario and can return it through one of its wrappers (vmas/make_env.py:80-101).  This package serves the
``vmas.simulator.environment.gym.gymnasium:GymnasiumWrapper`` (the card's second entry symbol) for the balance
scenario as a simulated R0 world: ``cap.world.step.v1`` takes ``{ticks, action}`` with a Dict action, one Box per
agent, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The bridge derives the
action limits from the environment's action space; the wrapper converts the VMAS spaces with shimmy
(vmas/simulator/environment/gym/gymnasium.py:43-44).

The gate cannot import the clone, torch or gym where the fake runs (see fake.py), so the ``fake`` backend is the
package's own pure Python balance stand-in.  Nothing in the clone calls ``gym.register`` or ``gymnasium.register``:
``vmas.make_env`` builds the ``Environment`` and, when ``wrapper`` is None, returns that object
(vmas/make_env.py:80-101).  ``gym.make('vmas:balance')`` therefore raises ``NameNotFound``.  The ``sim`` backend is
``_build_sim_env``, which calls ``vmas.make_env`` for the balance scenario and returns that ``Environment``.
``Environment.step`` accepts a dict keyed by agent name (vmas/simulator/environment/environment.py:354-366).  The
published Box has shape ``(action_size,)`` (environment.py:487) while ``step`` requires ``(num_envs, action_size)``
(environment.py:376-384); with ``num_envs=1`` the wrapper adds that leading 1 and does not change the numbers or the
keys.  The balance reward is the same tensor for every agent (vmas/scenarios/balance.py:223-241); the wrapper returns
that one number.  ``GymnasiumWrapper.step`` is not used: it requires a sequence (vmas/simulator/environment/gym/base.py:94-109).
The import stays inside the factory, so the fake backend never loads the clone.  The sim entry is a callable, so the
lock's string map (fake only) is still what G2 compares.  The package is model-authored and unreviewed; this workspace
checks the fake backend, and the orchestrator's ``--backend sim`` run is the evidence for the real environment.

The ``fidelity`` attribute states what is and is not modelled.  The fake is not the upstream PyTorch engine, the world
step output carries one scalar reward where the wrapper returns one reward per agent, and the fake's transitions are
placeholder test data, so the level is F1 (rigid-body-like dynamics, no validated contact or actuator model).
"""

from mhs.driver import Fact, GymnasiumDriver

README = "README.md"
INIT = "vmas/__init__.py"
MAKE_ENV = "vmas/make_env.py"
ENV = "vmas/simulator/environment/environment.py"
BASE = "vmas/simulator/environment/gym/base.py"
WRAPPER = "vmas/simulator/environment/gym/gymnasium.py"
BALANCE = "vmas/scenarios/balance.py"
CORE = "vmas/simulator/core.py"
HOLONOMIC = "vmas/simulator/dynamics/holonomic.py"


def _one_env_batch(value):
    """``(action_size,)`` to ``(1, action_size)``.  The values are not changed.

    ``get_agent_action_space`` publishes a Box of shape ``(action_size,)`` (environment.py:487).  ``Environment.step``
    requires ``(num_envs, action_size)`` (environment.py:376-384).  This factory builds ``num_envs=1``.
    """
    shape = getattr(value, "shape", None)
    if shape is not None and len(shape) == 1:
        return value.reshape((1, int(shape[0])))
    return value


def _python_number(value):
    """One element of a length-1 tensor, as a Python number.  A plain number is returned unchanged."""
    item = getattr(value, "item", None)
    if callable(item):
        try:
            value = item()
        except (TypeError, ValueError):
            pass
    return value


class _BalanceEnv:
    """The real balance ``Environment``, with the two conversions the bridge needs.

    ``Environment.step`` takes a dict of actions keyed by agent name (environment.py:354-366) and, when
    ``terminated_truncated`` is set, returns obs, rewards, terminated, truncated and infos (environment.py:300-303).
    Rewards are a dict of the same tensor for every agent (balance.py:223-241).  ``cap.world.step.v1`` carries one
    number and reads terminated and truncated with ``bool``.  The action dict is not rebuilt as a list: each value
    only gains the leading batch axis of 1 that ``step`` requires.  Observations and info are the objects
    ``Environment.step`` returned.
    """

    def __init__(self, env):
        self._env = env

    def __getattr__(self, name):
        return getattr(self._env, name)

    def reset(self, **kwargs):
        return self._env.reset(**kwargs)

    def step(self, action):
        batched = {name: _one_env_batch(value) for name, value in action.items()}
        obs, rews, terminated, truncated, info = self._env.step(batched)
        shared = rews[self._env.agents[0].name]
        return obs, float(_python_number(shared)), bool(_python_number(terminated)), bool(_python_number(truncated)), info


def _build_sim_env(**_options):
    """Build the balance ``Environment`` for the ``sim`` backend.

    The import is inside the factory so the fake backend never imports VMAS.  ``vmas/__init__.py:32`` lists
    ``balance``.  ``make_env`` loads that scenario, constructs an ``Environment`` and returns it when ``wrapper`` is
    None (vmas/make_env.py:80-101).  ``device`` defaults to ``"cpu"`` and ``continuous_actions`` to True
    (vmas/make_env.py:17-18).  ``dict_spaces`` defaults to False, which publishes a Tuple (environment.py:432-435);
    True publishes the Dict keyed by agent name (environment.py:437-441) that ``step`` accepts.  ``num_envs`` is 1
    so the added batch axis matches ``Environment.step`` (environment.py:378-380).  ``terminated_truncated`` defaults
    to False (vmas/make_env.py:26); True makes ``step`` return the five-tuple (environment.py:300-303).  No render
    call is made: pyglet is imported only inside ``Environment.render`` (environment.py:823).
    """
    from vmas import make_env

    env = make_env(
        scenario="balance",
        num_envs=1,
        device="cpu",
        continuous_actions=True,
        dict_spaces=True,
        terminated_truncated=True,
        wrapper=None,
    )
    return _BalanceEnv(env)


class VMASBalance(GymnasiumDriver):
    device_id = "vmas-balance"
    env_id = "vmas:balance"
    native = "vmas.simulator.environment.gym.gymnasium:GymnasiumWrapper"
    #: ``fake`` is this package's stand-in.  ``sim`` calls ``vmas.make_env`` (vmas/make_env.py:80-101) and returns
    #: the real balance ``Environment``.  The sim entry is a callable, so the lock's string entry (``fake`` only)
    #: is still what G2 compares.
    backends = {"fake": ".fake:FakeVMASBalance", "sim": _build_sim_env}
    display_name = "VMAS balance scenario behind the Gymnasium wrapper"
    vendor, model = "ProrokLab", "VMAS balance"
    tags = ["vmas", "multi-agent", "reinforcement-learning", "simulation", "gymnasium", "balance"]
    facts = [
        Fact("VMAS describes itself as a vectorized differentiable simulator designed for efficient MARL benchmarking",
             source="upstream_code", ref=f"{README}:26"),
        Fact("make_env loads the named scenario, constructs an Environment and returns the requested wrapper, or the "
             "Environment itself when wrapper is None", source="upstream_code", ref=f"{MAKE_ENV}:80-101"),
        Fact("The published scenario list includes the name balance", source="upstream_code", ref=f"{INIT}:32"),
        Fact("make_env defaults device to cpu and continuous_actions to True", source="upstream_code",
             ref=f"{MAKE_ENV}:17-18"),
        Fact("make_env defaults dict_spaces to False and terminated_truncated to False", source="upstream_code",
             ref=f"{MAKE_ENV}:22-26"),
        Fact("get_action_space returns a Tuple of per-agent spaces when dict_spaces is false and a Dict keyed by "
             "agent name when dict_spaces is true", source="upstream_code", ref=f"{ENV}:431-441"),
        Fact("A continuous agent action space is a Box whose shape is the agent's action size", source="upstream_code",
             ref=f"{ENV}:474-488"),
        Fact("Environment.step accepts a dict of actions keyed by agent name", source="upstream_code",
             ref=f"{ENV}:354-366"),
        Fact("Environment.step requires each action tensor to have shape (num_envs, action_size)",
             source="upstream_code", ref=f"{ENV}:376-384"),
        Fact("With terminated_truncated set, the step result is obs, rewards, terminated, truncated and infos",
             source="upstream_code", ref=f"{ENV}:300-303"),
        Fact("The balance reward returns the same ground_rew + pos_rew tensor for every agent",
             source="upstream_code", ref=f"{BALANCE}:223-241"),
        Fact("GymnasiumWrapper.step converts its action with _action_list_to_tensor, which requires one action per "
             "agent in a sequence", source="upstream_code", ref=f"{BASE}:94-109"),
        Fact("The Gymnasium wrapper requires gymnasium and shimmy and raises ImportError when either is absent",
             source="upstream_code", ref=f"{WRAPPER}:14-23"),
        Fact("The Gymnasium wrapper serves one vectorized environment only: it asserts num_envs == 1 and "
             "terminated_truncated", source="upstream_code", ref=f"{WRAPPER}:36-42"),
        Fact("GymnasiumWrapper.reset(seed, options) seeds the wrapped Environment and resets environment 0; options is "
             "accepted and not used", source="upstream_code", ref=f"{WRAPPER}:65-75"),
        Fact("GymnasiumWrapper.step converts the per-agent action list, steps the wrapped Environment and returns "
             "obs, rewards, terminated, truncated and info", source="upstream_code", ref=f"{WRAPPER}:51-63"),
        Fact("GymnasiumWrapper converts the wrapped Environment's observation and action spaces with shimmy's "
             "_convert_space", source="upstream_code", ref=f"{WRAPPER}:43-44"),
        Fact("The balance scenario defaults to 3 agents and constructs agent_0, agent_1 and agent_2 with "
             "u_multiplier=0.7", source="upstream_code", ref=f"{BALANCE}:17-39"),
        Fact("An Agent uses Holonomic dynamics by default and takes its action size from the dynamics' "
             "needed_action_size", source="upstream_code", ref=f"{CORE}:929-937"),
        Fact("Holonomic.needed_action_size is 2, so each balance agent has a two-value action", source="upstream_code",
             ref=f"{HOLONOMIC}:9-12"),
        Fact("The default Agent action range u_range is 1.0", source="upstream_code", ref=f"{CORE}:851"),
        Fact("The balance observation concatenates agent position, velocity, package-relative position, "
             "line-relative position, package-goal offset, package velocity, line velocity, line angular velocity and "
             "line rotation", source="upstream_code", ref=f"{BALANCE}:245-256"),
        Fact("World's default simulation timestep dt is 0.1 s", source="upstream_code", ref=f"{CORE}:1095"),
        Fact("The balance scenario constructs the World with gravity (0.0, -0.05) and y_semidim 1 and does not "
             "override dt", source="upstream_code", ref=f"{BALANCE}:33"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    fidelity = {
        "engine": "vmas:balance",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the fake's Python random generator and repeats a start state; the upstream "
                     "wrapper calls Environment.seed, which seeds torch, numpy and Python random, so the same seed "
                     "does not reproduce the upstream trajectory in this fake",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no contact or actuator model: the placeholder transition ignores VMAS's collision response, gravity, "
            "friction and joint forces, and applies the action as an ideal velocity increment",
            "the fake is not the upstream PyTorch rigid-body engine: its start states, integration and rewards are "
            "placeholder test data and were never compared with a VMAS run",
            "one scalar reward: the balance reward is the same tensor for every agent (balance.py:241), while "
            "cap.world.step.v1 carries a single number; the sim backend returns that shared number, and the fake "
            "returns the sum of its placeholder per-agent rewards",
            "action shape: GymnasiumWrapper.step takes a list of per-agent actions, while the bridge sends the Dict "
            "action keyed by agent name; the fake accepts both, and the sim backend keeps the Dict and adds a "
            "leading batch axis of 1",
            "reset: the wrapper calls Environment.reset_at(index=0) and sets the seed through Environment.seed; the "
            "fake resets its whole scalar state and has no vectorized batch dimension",
            "no rendering, no lidar, no communication channel and no snapshot/restore: the Environment exposes no "
            "get_state/set_state and the fake declares none",
            "the sim backend calls vmas.make_env(scenario='balance', wrapper=None); each Dict action gains a leading "
            "batch axis of 1 and the shared reward is returned as one number; this authoring workspace did not "
            "install or run VMAS, torch or gym, so the fake was not compared with an upstream trajectory",
        ],
    }
