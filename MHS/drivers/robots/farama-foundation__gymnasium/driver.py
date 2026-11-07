"""OpenMHS driver for gh.farama-foundation/gymnasium: the CartPole-v1 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by
``Discrete(2)`` (0 or 1), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import gymnasium (see fake.py), so the ``fake`` backend is the package's own pure Python CartPole.  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver
.open_native); that path needs the upstream package (Python 3.11 or newer, numpy) and was not run here (README.md).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (d77197c284406e6094c9d1a74d4988a8749ce849).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

CARTPOLE = "gymnasium/envs/classic_control/cartpole.py"


class CartPole(GymnasiumDriver):
    device_id = "cartpole"
    env_id = "CartPole-v1"
    native = "gymnasium.envs.classic_control.cartpole:CartPoleEnv"
    backends = {"fake": ".fake:FakeCartPoleEnv"}
    action_space_ref = f"{CARTPOLE}:151"
    display_name = "Gymnasium CartPole-v1 (classic control)"
    vendor, model = "Farama Foundation", "CartPole-v1"
    tags = ["cartpole", "classic-control", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The action space is Discrete(2): the integer action 0 or 1", source="upstream_code",
             ref=f"{CARTPOLE}:151"),
        Fact("Action 1 pushes the cart with +force_mag and any other action with -force_mag", source="upstream_code",
             ref=f"{CARTPOLE}:171"),
        Fact("The physics constants are gravity 9.8, masscart 1.0, masspole 0.1, length 0.5 (half the pole's "
             "length), force_mag 10.0 and tau 0.02 s between state updates, integrated with the euler scheme",
             source="upstream_code", ref=f"{CARTPOLE}:125-133"),
        Fact("The failure thresholds are 12 degrees for the pole angle and 2.4 for the cart position",
             source="upstream_code", ref=f"{CARTPOLE}:136-137"),
        Fact("The episode terminates when the cart position or the pole angle passes its threshold",
             source="upstream_code", ref=f"{CARTPOLE}:199-204"),
        Fact("The observation is [cart position, cart velocity, pole angle, pole angular velocity] with the bounds "
             "+-4.8, +-inf, about +-0.418 rad (24 degrees) and +-inf", source="upstream_code",
             ref=f"{CARTPOLE}:44-51"),
        Fact("The reward is +1 for every step, including the step that terminates the episode, and 0 after it",
             source="upstream_code", ref=f"{CARTPOLE}:206-221"),
        Fact("CartPole-v1 is registered with max_episode_steps=500", source="upstream_code",
             ref="gymnasium/envs/__init__.py:26-32"),
        Fact("CartPoleEnv.step never truncates: the time limit is the TimeLimit wrapper that gymnasium.make adds",
             source="upstream_code", ref=f"{CARTPOLE}:226"),
        Fact("A reset draws the four state values uniformly from (-0.05, 0.05)", source="upstream_code",
             ref=f"{CARTPOLE}:238-243"),
        Fact("The reset option low or high replaces a bound of that draw (low must not exceed high)",
             source="upstream_code", ref="gymnasium/envs/classic_control/utils.py:35-44"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:CartPole-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial state and the dynamics are deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; this package's fake "
                     "draws initial states with Python's random.Random and upstream with numpy's generator, so a "
                     "seed gives different trajectories on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body equations of motion of a cart and a pole on a frictionless track: no contacts, no friction "
            "and no actuator, sensor or noise model; the push is an ideal step force of fixed size",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (tau 0.02 s) only",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend re-implements the dynamics in pure Python floats and was not compared with the "
            "upstream environment (gymnasium was not importable where the gate ran): trajectories can differ from "
            "upstream's float32 observations and numpy random stream",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
