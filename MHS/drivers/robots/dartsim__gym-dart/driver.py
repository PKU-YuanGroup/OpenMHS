"""OpenMHS driver for gh.dartsim/gym-dart: the DartCartPole-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{"values": [v]}``
bounded by the 1-D ``Box(-5, 5)`` action space (``gym_dart/envs/dart_cartpole_env.py:59-66``),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import or run the clone, and ``dartpy`` is not installed here, so the ``fake`` backend is this
package's own pure-Python stand-in (fake.py).  The upstream class as committed cannot be served by the gymnasium
bridge: ``step()`` still returns the legacy 3-tuple (``gym_dart/envs/dart_cartpole_env.py:74-80``) and ``reset()``
takes no seed (``:70-72``), while the bridge requires the 5-tuple and passes ``seed=``.  That defect is recorded in
the fidelity ``gaps``; the ``sim`` backend (``gymnasium.make("DartCartPole-v0")``) was not run.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (bf915eaa3baa70a3a4d0fd42e024694e7825d5fe).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_dart/envs/dart_cartpole_env.py"
REGISTER = "gym_dart/__init__.py"


class DartCartPole(GymnasiumDriver):
    device_id = "dart-cartpole"
    env_id = "DartCartPole-v0"
    native = "gym_dart.envs:DartCartPoleEnv"
    backends = {"fake": ".fake:FakeDartCartPoleEnv"}
    action_space_ref = 'gym_dart/envs/dart_cartpole_env.py:59-66'
    display_name = "gym-dart DartCartPole-v0 (DART cart-pole)"
    vendor, model = "dartsim", "DartCartPole-v0"
    tags = ["cartpole", "dart", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("DartCartPole-v0 is registered with entry point gym_dart.envs:DartCartPoleEnv, max_episode_steps=200 "
             "and reward_threshold=195.0", source="upstream_code", ref=f"{REGISTER}:8-14"),
        Fact("The observation space is Box(-high, high) with high = [x_threshold * 2, float32 max, "
             "theta_threshold_radians * 2, float32 max], where x_threshold is 2.4 and theta_threshold_radians is "
             "12 degrees in radians", source="upstream_code", ref=f"{ENV}:13-33"),
        Fact("The action space is a one-element Box from -5 to 5 with dtype float32", source="upstream_code",
             ref=f"{ENV}:59-66"),
        Fact("The world timestep is set to 0.01 s and gravity to (0, 0, -9.8) after the skeleton is loaded",
             source="upstream_code", ref=f"{ENV}:35-36"),
        Fact("get_state returns [pole angle, pole angular velocity, cart position, cart velocity]",
             source="upstream_code", ref=f"{ENV}:91-94"),
        Fact("The initial state limits are +-0.1 in all four dimensions", source="upstream_code",
             ref=f"{ENV}:47-50"),
        Fact("The public reset takes no seed and returns only the observation (no info dict)",
             source="upstream_code", ref=f"{ENV}:70-72"),
        Fact("reset draws the four state values uniformly from the initial state limits and applies them to the "
             "cart and pole positions and velocities", source="upstream_code", ref=f"{ENV}:133-139"),
        Fact("The reset draw uses numpy's global np.random.uniform", source="upstream_code",
             ref=f"{ENV}:133-135"),
        Fact("step sets the cart velocity to the action, clipped into the action-space bounds, and advances the "
             "world one timestep", source="upstream_code", ref=f"{ENV}:158-168"),
        Fact("step returns the legacy 3-tuple (observation, reward, done), not the gymnasium 5-tuple",
             source="upstream_code", ref=f"{ENV}:74-80"),
        Fact("The episode is done when the absolute pole angle exceeds theta_threshold_radians, the absolute cart "
             "position exceeds 1.0, or current_step reaches max_time_steps", source="upstream_code",
             ref=f"{ENV}:175-186"),
        Fact("max_time_steps is 10000", source="upstream_code", ref=f"{ENV}:40"),
        Fact("The reward is (theta_threshold - |pole angle|) / theta_threshold + exp(-cart position) while the "
             "angle is below theta_threshold, otherwise 0.0", source="upstream_code",
             ref=f"{ENV}:144-156"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym_dart:DartCartPole-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the packaged fake reseeds its own uniform draw from reset(seed) or cap.world.seed.v1, and "
                     "its dynamics are deterministic, so one seed plus one action sequence repeats a trajectory; "
                     "the upstream reset() has no seed parameter and draws from numpy's global random state "
                     "(dart_cartpole_env.py:129-139), so the sim path cannot repeat a trajectory from a seed",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the packaged fake is a pure-Python stand-in: one damped pendulum equation plus the cart velocity the "
            "action sets, with no cart-pole inertia coupling, contact, friction, actuator or sensor model; it is "
            "not DART and was never compared with the upstream environment (dartpy is not installed here)",
            "no contact or actuator fidelity: the action directly sets the cart velocity as the upstream step does "
            "(dart_cartpole_env.py:162-163), so there is no motor, gearbox, track friction or measurement noise",
            "the upstream class returns the legacy 3-tuple from step() (dart_cartpole_env.py:74-80) and its "
            "reset() takes no seed (dart_cartpole_env.py:70-72); the gymnasium bridge requires the 5-tuple and "
            "passes seed=..., so the upstream environment cannot be served on the sim backend as committed. The "
            "fake returns (observation, reward, terminated, truncated, info) and accepts reset(seed, options)",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
            "the fake applies the registration's 200-step truncation itself (gym_dart/__init__.py:12); the "
            "upstream step() only stops at its internal 10000-step limit (dart_cartpole_env.py:40), because the "
            "TimeLimit wrapper is what gymnasium.make adds",
            "the fake accepts and ignores reset options; the upstream reset() has no options parameter",
        ],
    }
