"""OpenMHS driver for gh.qlan3/gym-games: the NChain-v1 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{index}`` bounded by ``Discrete(2)`` (0 moves left, 1 moves right), ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate runs without gymnasium, numpy or the upstream package (package code never imports the clone), so the
``fake`` backend is the package's own pure Python NChain.  A backend name that ``backends`` does not list
(``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream
package and its dependencies and was not run here (fake.py, facts.md).

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The
bridge derives the engine, the determinism kind and the lockstep clock; this package overrides only the gaps so
they name the omissions of a discrete chain.  Every fact cites a line of the clone at the pinned commit
0220815982456a20f02887b20a7d9a5fbeeedd55.  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

NCHAIN = "gym_exploration/envs/nchain.py"


class NChain(GymnasiumDriver):
    device_id = "nchain"
    env_id = "NChain-v1"
    native = "gym_exploration.envs.nchain:NChainEnv"
    backends = {"fake": ".fake:FakeNChainEnv"}
    action_space_ref = f"{NCHAIN}:17"
    display_name = "gym-games NChain-v1 (exploration chain)"
    vendor, model = "qlan3", "NChain-v1"
    tags = ["nchain", "exploration", "reinforcement-learning", "simulation", "gymnasium"]
    #: The episode of NChainEnv is short (n + 8 steps), so the bridge continues with a fresh episode after a
    #: terminal or truncated step instead of refusing every later step.  The upstream environment itself does
    #: not auto-reset; the gap below says so, and reset()/terminated flags stay observable.
    autoreset = True
    facts = [
        Fact("NChainEnv is a chain of n states and the agent always starts in state s2", source="upstream_code",
             ref=f"{NCHAIN}:9-10"),
        Fact("In state s1 the reward is 0.001 and in state sN it is 1", source="upstream_code",
             ref=f"{NCHAIN}:12"),
        Fact("The action space is Discrete(2): the integer actions 0 and 1", source="upstream_code",
             ref=f"{NCHAIN}:17"),
        Fact("Action 1 moves right (the state is incremented) and any other action moves left (the state is "
             "decremented); the state stays at the ends of the chain", source="upstream_code",
             ref=f"{NCHAIN}:49-54"),
        Fact("The reward is computed from the state before the transition", source="upstream_code",
             ref=f"{NCHAIN}:48"),
        Fact("The reward is 1.0 when the state is n-1 and the action is 1, 0.001 when the state is 0 and the "
             "action is 0, and 0 otherwise", source="upstream_code", ref=f"{NCHAIN}:36-42"),
        Fact("The observation is the vector (v <= state), as uint8: 1 for the states up to and including the "
             "current state and 0 for the rest", source="upstream_code", ref=f"{NCHAIN}:25-26"),
        Fact("The observation is evaluated over v = arange(n) in reset and step", source="upstream_code",
             ref=f"{NCHAIN}:31"),
        Fact("The observation space is Box(low=0, high=1, shape=(n,), dtype=uint8)", source="upstream_code",
             ref=f"{NCHAIN}:22"),
        Fact("The step limit is max_steps = n + 8", source="upstream_code", ref=f"{NCHAIN}:23"),
        Fact("The episode terminates when the step counter reaches max_steps", source="upstream_code",
             ref=f"{NCHAIN}:55-59"),
        Fact("A reset sets the state to 1 and the step counter to 0 and returns the initial observation",
             source="upstream_code", ref=f"{NCHAIN}:28-34"),
        Fact("reset calls super().reset(seed=seed) to seed np_random; NChainEnv draws no random numbers, so the "
             "seed changes nothing in the chain", source="upstream_code", ref=f"{NCHAIN}:29-30"),
        Fact("NChain-v1 is registered with entry_point gym_exploration.envs:NChainEnv", source="upstream_code",
             ref="gym_exploration/__init__.py:9-12"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F0"
    #: The bridge derives engine, determinism, timestep, clock, reset and snapshot_restore (GymnasiumDriver
    #: ._derived_fidelity); the gaps name what the model does not contain, as FID-002 requires.
    fidelity = {
        "gaps": [
            "the environment is a discrete Markov chain: no continuous dynamics, forces, contacts, actuators, "
            "sensors or noise model",
            "no fixed physics timestep: a tick is one discrete transition, so timestep_ms is 0 (an event-driven "
            "analytic model) and realtime_factor 0 means the chain is not wall-clock paced",
            "the bridge auto-resets a fresh episode after a terminal or truncated step (autoreset=True); the "
            "upstream NChainEnv itself does not auto-reset, and the step receipt still reports the terminal flags",
            "the fake backend re-implements the chain in pure Python and was not compared with the upstream "
            "environment (gymnasium and numpy were not importable where the gate ran); the fake returns lists of "
            "Python ints where upstream returns numpy uint8 arrays",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
