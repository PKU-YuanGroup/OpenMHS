"""OpenMHS driver for gh.chauby/coppeliasimrl: the CoppeliaSim cart-pole environment (a Gymnasium family driver).

The upstream class is ``CartPole.CartPoleEnv:CartPoleEnv`` (``CartPole/CartPoleEnv.py:13``), a legacy ``gym.Env``
that drives a cart-pole scene in CoppeliaSim through the remote API on port 19997 and supports a discrete action
space of three actions (``:37-38``) and a continuous force action (``:40``).  The demo configuration deployed by
the repository uses the discrete actions (``examples/demo_cart_pole_learning.py:19``), so this package serves that
configuration: ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.index`` 0, 1 or 2, and
``cap.world.reset.v1``/``cap.world.seed.v1`` control the seeded start draw (``CartPole/CartPoleEnv.py:46-47,
70-72,129-134``).  The device is simulated (R0): there is no hardware backend, no machine to stop and no
operator-required limit.

The gate cannot run CoppeliaSim (the clone's own simulator needs the CoppeliaSim application, the scene
``cart_pole.ttt`` and the platform remoteApi library; ``README.md:16,27`` and ``VREP_RemoteAPIs/sim.py:14-20``), so
the ``fake`` backend is this package's own pure Python stand-in (fake.py) for the class.  Its dynamics are
placeholders, not a CoppeliaSim reproduction; the fidelity ``gaps`` say so.  The backend name ``sim`` is not
declared and the local ``env_id`` is not a registered gymnasium environment, so no second path is claimed or was
run.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit 8eb98b8a42b515b61eae5ffebcc9f228e2f5fdd1.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

CLONE = "8eb98b8a42b515b61eae5ffebcc9f228e2f5fdd1"
ENV = "CartPole/CartPoleEnv.py"
MODEL = "CartPole/CartPoleSimModel.py"


class CoppeliaSimCartPole(GymnasiumDriver):
    """The discrete-action cart-pole environment of the clone, served through the gymnasium bridge."""

    device_id = "coppeliasim-cartpole"
    #: A package-local label: the clone's environment is not registered with gymnasium, so this id does not make
    #: ``gymnasium.make`` work; the fake backend is the only backend this package declares.
    env_id = "coppeliasim-cartpole"
    native = "CartPole.CartPoleEnv:CartPoleEnv"
    backends = {"fake": ".fake:FakeCartPoleEnv"}
    action_space_ref = f"{ENV}:38"
    display_name = "CoppeliaSim cart-pole (chauby/coppeliasimrl)"
    vendor, model = "chauby/coppeliasimrl", "CartPoleEnv"
    tags = ["cartpole", "coppeliasim", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The repository describes itself as a reinforcement learning workspace for CoppeliaSim (VREP) "
             "simulation environments", source="vendor_doc", ref="README.md:3"),
        Fact("The environment setup lists CoppeliaSim 4.2 and the legacy Gym package as required software",
             source="vendor_doc", ref="README.md:16-18"),
        Fact("The cart-pole demo is started after CoppeliaSim is running and cart_pole.ttt has been imported",
             source="vendor_doc", ref="README.md:27"),
        Fact("CartPoleEnv is a gym.Env subclass", source="upstream_code", ref=f"{ENV}:13"),
        Fact("The constructor builds a Discrete(3) action space when action_type is 'discrete' and a Box(-1.0, "
             "1.0) action space when it is 'continuous'", source="upstream_code", ref=f"{ENV}:17-40"),
        Fact("The cart-pole demo instantiates CartPoleEnv with action_type='discrete'", source="upstream_code",
             ref="examples/demo_cart_pole_learning.py:19"),
        Fact("In the discrete action mapping action 0 applies zero force, action 1 applies +1.0 and action 2 "
             "applies -1.0", source="upstream_code", ref=f"{ENV}:84-90"),
        Fact("For a continuous action the push force is action*2.0, so the action range -1.0 to 1.0 maps to "
             "-2.0 to 2.0", source="upstream_code", ref=f"{ENV}:91-92"),
        Fact("The failure thresholds are a cart position of 0.8 and a pole angle of 40*pi/360 rad",
             source="upstream_code", ref=f"{ENV}:24-25"),
        Fact("The episode ends when the cart position reaches +-0.8 or the pole angle leaves +-40*pi/360 rad",
             source="upstream_code", ref=f"{ENV}:99"),
        Fact("The observation is [cart position, pole angle, cart linear velocity, pole angular velocity]",
             source="upstream_code", ref=f"{ENV}:119-121"),
        Fact("Joint velocities are computed by dividing the position change by a 0.005 s interval",
             source="upstream_code", ref=f"{ENV}:119-120"),
        Fact("A reset draws the four state values uniformly from -0.05 to 0.05", source="upstream_code",
             ref=f"{ENV}:133"),
        Fact("Every step that is not done pays reward 1.0; the first step after done pays 1.0 and later steps pay "
             "0.0", source="upstream_code", ref=f"{ENV}:102-117"),
        Fact("The reset stops and restarts the CoppeliaSim simulation and sets the joint torque to zero",
             source="upstream_code", ref=f"{ENV}:136-141"),
        Fact("The environment connects to the remote API server at 127.0.0.1 on port 19997 and runs it in "
             "synchronous mode", source="upstream_code", ref=f"{ENV}:52-64"),
        Fact("Each step triggers one synchronous simulation advance and waits for its ping time",
             source="upstream_code", ref=f"{ENV}:124-125"),
        Fact("The joint driver sets the prismatic joint target velocity to +-1000 and its maximum force to "
             "abs(torque)", source="upstream_code", ref=f"{MODEL}:57-63"),
        Fact("Joint positions are read from the prismatic and revolute joints through the remote API buffer mode",
             source="upstream_code", ref=f"{MODEL}:43-51"),
        Fact("The remote API wrapper loads a platform-specific remoteApi library (remoteApi.so, .dll or .dylib) "
             "next to sim.py", source="upstream_code", ref="VREP_RemoteAPIs/sim.py:14-20"),
        Fact("CartPoleEnv.close stops the simulation and finishes all remote API connections", source="upstream_code",
             ref=f"{ENV}:149-152"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "coppeliasim",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the environment seeds a numpy generator and draws the start state from it; the fake uses "
                     "Python's random.Random, so one seed does not give the same trajectory on the two, and the "
                     "CoppeliaSim scene itself was never run here",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the physics lives in the binary cart_pole.ttt scene and the CoppeliaSim engine: mass, inertia, "
            "friction, contact and actuator parameters are not stated in the clone and were not read",
            "the remote API sets a prismatic target velocity and a maximum force (CartPole/CartPoleSimModel.py:"
            "57-63); the resulting actuator dynamics, contacts and friction are not modelled by this package",
            "the scene's actual simulation step is not stated in the clone: 5 ms is the interval the upstream "
            "velocity computation assumes (CartPole/CartPoleEnv.py:119-120), not a scene setting read here",
            "the fake backend replaces the engine with placeholder displacement constants and was never compared "
            "with a running CoppeliaSim; its initial draw uses Python's random.Random, not numpy's generator",
            "the upstream reset draws a start state but does not push it into the simulation; the fake keeps the "
            "drawn cart and pole positions as its own state",
            "the fake advances the positions before returning them, while upstream reads the joints before it "
            "triggers the next synchronous step, so the reported state lags the applied action by one tick",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
