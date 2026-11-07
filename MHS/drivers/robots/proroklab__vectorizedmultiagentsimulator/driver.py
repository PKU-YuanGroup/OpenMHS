"""OpenMHS driver for gh.proroklab/vectorizedmultiagentsimulator: the VMAS balance scenario behind its Gymnasium wrapper.

VMAS is a vectorized multi-agent simulator (README.md:26) whose environment factory builds an ``Environment`` from a
scenario and can return it through one of its wrappers (vmas/make_env.py:80-101).  This package serves the
``vmas.simulator.environment.gym.gymnasium:GymnasiumWrapper`` (the card's second entry symbol) for the balance
scenario as a simulated R0 world: ``cap.world.step.v1`` takes ``{ticks, action}`` with a Dict action, one Box per
agent, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The bridge derives the
action limits from the environment's action space; the wrapper converts the VMAS spaces with shimmy
(vmas/simulator/environment/gym/gymnasium.py:43-44).

The gate cannot import the clone, torch, gymnasium or shimmy (see fake.py), so the ``fake`` backend is the package's
own pure Python balance stand-in.  A backend name ``backends`` does not list (``sim``) would be served by
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); no gymnasium environment with this id is registered, so that
path is not offered and was not run.  The package is model-authored and unreviewed; it is checked on the fake backend
only and its evidence is ``contract_checked``.

The ``fidelity`` attribute states what is and is not modelled.  The fake is not the upstream PyTorch engine, the world
step output carries one scalar reward where the wrapper returns one reward per agent, and the fake's transitions are
placeholder test data, so the level is F1 (rigid-body-like dynamics, no validated contact or actuator model).
"""

from mhs.driver import Fact, GymnasiumDriver

README = "README.md"
MAKE_ENV = "vmas/make_env.py"
WRAPPER = "vmas/simulator/environment/gym/gymnasium.py"
BALANCE = "vmas/scenarios/balance.py"
CORE = "vmas/simulator/core.py"
HOLONOMIC = "vmas/simulator/dynamics/holonomic.py"


class VMASBalance(GymnasiumDriver):
    device_id = "vmas-balance"
    env_id = "vmas:balance"
    native = "vmas.simulator.environment.gym.gymnasium:GymnasiumWrapper"
    backends = {"fake": ".fake:FakeVMASBalance"}
    display_name = "VMAS balance scenario behind the Gymnasium wrapper"
    vendor, model = "ProrokLab", "VMAS balance"
    tags = ["vmas", "multi-agent", "reinforcement-learning", "simulation", "gymnasium", "balance"]
    facts = [
        Fact("VMAS describes itself as a vectorized differentiable simulator designed for efficient MARL benchmarking",
             source="upstream_code", ref=f"{README}:26"),
        Fact("make_env loads the named scenario, constructs an Environment and returns the requested wrapper, or the "
             "Environment itself when wrapper is None", source="upstream_code", ref=f"{MAKE_ENV}:80-101"),
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
            "one scalar reward: GymnasiumWrapper.step returns one reward per agent, while cap.world.step.v1 carries "
            "a single number, so the fake returns the sum of its placeholder per-agent rewards",
            "action shape: the wrapper's step takes a list of per-agent actions, while the bridge sends the Dict "
            "action keyed by agent name; the fake accepts both",
            "reset: the wrapper calls Environment.reset_at(index=0) and sets the seed through Environment.seed; the "
            "fake resets its whole scalar state and has no vectorized batch dimension",
            "no rendering, no lidar, no communication channel and no snapshot/restore: the Environment exposes no "
            "get_state/set_state and the fake declares none",
            "the sim path was not run: torch, gymnasium and shimmy are not installed where the gate runs, and no "
            "gymnasium environment with the id vmas:balance is registered",
        ],
    }
