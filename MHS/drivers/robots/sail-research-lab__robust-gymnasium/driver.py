"""OpenMHS driver for gh.sail-research-lab/robust-gymnasium: the CartPole-v1 simulation.

The upstream class is ``robust_gymnasium.envs.classic_control.cartpole:CartPoleEnv`` (entry symbol confirmed at the
card's file/line).  This is a Gymnasium family configuration: the class attributes name the environment and the
bridge derives ``cap.world.step.v1`` from the action and observation spaces, ``cap.world.reset.v1`` from ``reset`` and
``cap.world.seed.v1`` from the generator seed.  A step input is ``{ticks, action}`` with ``action`` = ``{index}``
bounded by ``Discrete(2)``; the device is simulated R0, so there is no hardware backend, no machine stop and no
operator-required limit.

The gate host has neither robust_gymnasium nor gymnasium, and package code never imports the read-only clone, so the
checked backend is the package's ``.fake:FakeCartPoleEnv``.  The bridge's unlisted ``sim`` path calls
``gymnasium.make`` (GymnasiumDriver.open_native), which opens the base Gymnasium distribution rather than this fork;
that path was not run and is not claimed here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002).  Every constant in the facts
below cites a line of the clone at the pinned commit.  This package is model-authored and unreviewed; only the fake
backend was exercised.
"""

from mhs.driver import Fact, GymnasiumDriver

CARTPOLE = "robust_gymnasium/envs/classic_control/cartpole.py"
ENVS = "robust_gymnasium/envs/__init__.py"


class RobustCartPole(GymnasiumDriver):
    device_id = "robust-cartpole"
    env_id = "CartPole-v1"
    native = "robust_gymnasium.envs.classic_control.cartpole:CartPoleEnv"
    backends = {"fake": ".fake:FakeCartPoleEnv"}
    action_space_ref = f"{CARTPOLE}:149"
    display_name = "robust-gymnasium CartPole-v1 (classic control)"
    vendor, model = "Safe RL Lab", "CartPole-v1"
    tags = ["cartpole", "classic-control", "robust-reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The action space is Discrete(2): the only valid actions are the integers 0 and 1",
             source="upstream_code", ref=f"{CARTPOLE}:149"),
        Fact("Action 1 applies a push of +force_mag and any other valid action applies -force_mag",
             source="upstream_code", ref=f"{CARTPOLE}:169"),
        Fact("The model constants are gravity 9.8, cart mass 1.0, pole mass 0.1, pole half-length 0.5, force "
             "magnitude 10.0, integration step 0.02 s and the euler integrator",
             source="upstream_code", ref=f"{CARTPOLE}:123-131"),
        Fact("The episode fails when the pole angle leaves 12 degrees or the cart position leaves 2.4",
             source="upstream_code", ref=f"{CARTPOLE}:134-135"),
        Fact("The observation bounds are twice the failure thresholds: cart position +-4.8, pole angle about "
             "+-0.418 rad, and the two velocity bounds are the float32 maximum",
             source="upstream_code", ref=f"{CARTPOLE}:134-150"),
        Fact("The observation has four elements: cart position, cart velocity, pole angle and pole angular "
             "velocity", source="upstream_code", ref=f"{CARTPOLE}:42-49"),
        Fact("step returns the state as a float32 numpy array", source="upstream_code",
             ref=f"{CARTPOLE}:232"),
        Fact("The episode terminates when the cart position or the pole angle crosses its threshold",
             source="upstream_code", ref=f"{CARTPOLE}:196-201"),
        Fact("The constructor's sutton_barto_reward default is False", source="upstream_code",
             ref=f"{CARTPOLE}:118-121"),
        Fact("When sutton_barto_reward is False every step pays 1.0, including the terminating step, and 0.0 "
             "after the episode; when it is True a non-terminal step pays 0.0 and a terminal or post-terminal "
             "step pays -1.0", source="upstream_code", ref=f"{CARTPOLE}:203-227"),
        Fact("CartPoleEnv.step always reports truncated=False; the episode length limit is the TimeLimit wrapper "
             "that make() adds", source="upstream_code", ref=f"{CARTPOLE}:231-232"),
        Fact("CartPole-v1 is registered with max_episode_steps=500", source="upstream_code", ref=f"{ENVS}:27-33"),
        Fact("reset() accepts options and uses the default bounds -0.05 and 0.05; it draws the four state values "
             "uniformly between low and high", source="upstream_code", ref=f"{CARTPOLE}:243-246"),
        Fact("The model is a cart on a frictionless track with an un-actuated pole joint; an action is a "
             "fixed-magnitude push", source="upstream_code", ref=f"{CARTPOLE}:25-35"),
    ]
    safe_state = ("the simulator stops advancing: after an e-stop no reset or step is accepted until "
                  "mhs.safety.reset clears the latch, while the last observation stays readable")
    #: The fidelity contract of this environment as deployed.  The bridge derives engine, determinism, timestep and
    #: clock defaults; the values are written out here so the whole claim is visible in the reference.
    fidelity = {
        "engine": "robust_gymnasium:CartPole-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 fix the next reset, and the dynamics are deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; the fake draws "
                     "initial states with Python's random.Random while upstream draws them with numpy's generator, "
                     "so the same seed need not give the same trajectory on the fake and upstream",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "frictionless point-mass cart-pole with an un-actuated joint: no contacts, friction, actuator dynamics, "
            "sensor model or measurement noise; the push is an ideal fixed-magnitude force",
            "no wall-clock pacing: realtime_factor 0, so ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was not validated against one",
            "the fake backend is a pure Python re-implementation using random.Random and Python floats instead of "
            "numpy's generator and float32 arrays; it was not compared with the upstream environment, and "
            "robust_gymnasium was not installed where the gate ran",
            "the bridge's unlisted sim backend calls gymnasium.make('CartPole-v1'), i.e. the base Gymnasium "
            "distribution, not robust_gymnasium.make; only the package fake is provided and checked",
            "snapshot and restore are not offered: CartPoleEnv exposes no get_state/set_state",
        ],
    }
