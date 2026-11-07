"""OpenMHS driver for gh.navneet-nmk/hierarchical-meta-reinforcement-learning: the TabularMDP-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by
``Discrete(5)`` (0 to 4), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): it is a tabular Markov decision process, there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The upstream environment uses the legacy Gym API (``gym.Env``, maml_rl/envs/mdp.py:3-7) and neither ``gym`` nor
``gymnasium`` is importable where the gate runs.  The ``fake`` backend is therefore the package's own pure Python
``TabularMDPEnv`` (fake.py); it is not the upstream simulator and was not compared with it.  A backend name that
``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` (GymnasiumDriver.open_native), which needs the
upstream package and its registration module; that path was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002): the
model is analytic (F0), has no physics timestep (0 ms), no wall-clock pacing, full resets and no snapshot.  Every
constant and rule cites a line of the clone at the pinned commit (4ef92cebfa11760d9de55d54fc8e827271982a63).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

MDP = "maml_rl/envs/mdp.py"
REGISTRATION = "maml_rl/envs/__init__.py"


class TabularMDP(GymnasiumDriver):
    device_id = "tabularmdp"
    env_id = "TabularMDP-v0"
    native = "maml_rl.envs.mdp:TabularMDPEnv"
    backends = {"fake": ".fake:FakeTabularMDPEnv"}
    display_name = "MAML-RL TabularMDP-v0 (tabular MDP)"
    vendor, model = "navneet-nmk", "TabularMDP-v0"
    tags = ["tabular-mdp", "meta-reinforcement-learning", "reinforcement-learning", "simulation", "gymnasium", "gym"]
    facts = [
        Fact("The TabularMDP-v0 registration fixes num_states=10 and num_actions=5", source="upstream_code",
             ref=f"{REGISTRATION}:19"),
        Fact("The TabularMDP-v0 registration sets max_episode_steps=10", source="upstream_code",
             ref=f"{REGISTRATION}:20"),
        Fact("The environment uses the legacy Gym API: it imports gym and gym.spaces and subclasses gym.Env",
             source="upstream_code", ref=f"{MDP}:3-7"),
        Fact("The action space is Discrete(num_actions), so a step action is an integer action index",
             source="upstream_code", ref=f"{MDP}:27"),
        Fact("The observation space is Box(0.0, 1.0, shape=(num_states,), dtype=float32)", source="upstream_code",
             ref=f"{MDP}:28-29"),
        Fact("The default task has uniform transition probabilities 1/num_states and zero mean rewards",
             source="upstream_code", ref=f"{MDP}:31-35"),
        Fact("seed replaces the environment's random generator and returns [seed]", source="upstream_code",
             ref=f"{MDP}:39-41"),
        Fact("sample_tasks draws transition rows from a Dirichlet(1) distribution and mean rewards from a "
             "Normal(1, 1) distribution", source="upstream_code", ref=f"{MDP}:43-50"),
        Fact("reset_task replaces the transition tensor and the mean rewards from a task dictionary",
             source="upstream_code", ref=f"{MDP}:52-55"),
        Fact("reset starts every episode in state 0 and returns a one-hot observation of length num_states",
             source="upstream_code", ref=f"{MDP}:57-63"),
        Fact("step draws the reward from a Normal(mean, 1) distribution, samples the next state from the "
             "transition row and returns the next one-hot observation", source="upstream_code", ref=f"{MDP}:65-75"),
        Fact("step always returns done=False, so the environment class itself never terminates an episode",
             source="upstream_code", ref=f"{MDP}:75"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:TabularMDP-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "a reset with a seed, or cap.world.seed.v1 followed by a reset, reseeds the generator; the "
                     "transition table and the mean rewards are fixed per task, so one implementation repeats a "
                     "trajectory for the same seed and actions. The clone draws from numpy's generator and this "
                     "package's fake from Python's random.Random, so one seed gives different trajectories on the "
                     "two. The clone's reset() takes no seed and does not consume the generator (mdp.py:57-63); the "
                     "bridge seeds the legacy environment through seed() before reset()",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic tabular MDP: a finite state transition table and a Normal reward, not a physical model; there "
            "are no dynamics, contacts, actuators, sensors or noise model beyond the reward distribution",
            "the environment has no physics timestep: one step is one MDP transition and the class takes no time "
            "argument, so timestep_ms is 0 and ticks count transitions, not simulated time (FID-015)",
            "no wall-clock pacing: realtime_factor 0, the state advances only when a command arrives",
            "no physical device is modelled and the model was never validated against one",
            "the registered TabularMDP-v0 adds gym's TimeLimit of 10 steps (maml_rl/envs/__init__.py:20); the fake "
            "models the environment class, whose step always returns done=False (mdp.py:75), so it does not truncate "
            "at 10 steps",
            "the fake backend re-implements the tabular MDP in pure Python and was not compared with the upstream "
            "environment (neither gym nor gymnasium is importable where the gate runs): trajectories can differ from "
            "upstream's float32 arrays and numpy random stream",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
