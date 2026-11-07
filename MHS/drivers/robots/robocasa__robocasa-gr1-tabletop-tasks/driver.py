"""OpenMHS driver for gh.robocasa/robocasa-gr1-tabletop-tasks: the GR-1 Tabletop Gymnasium environments.

A GymnasiumDriver is configuration only: ``env_id`` names one registered task and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where ``action`` is a ``spaces.Dict``
of controller parts (each a ``Box`` in ``[-1, 1]``; the fake drops the upstream ``action.`` key prefix so the bridge's
limit paths resolve, see the fidelity gaps), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The gate cannot import the upstream stack (robosuite, MuJoCo 3.2.6, the downloaded tabletop assets), so the ``fake``
backend is the package's own pure Python stand-in for ``GrootRoboCasaEnv`` (see fake.py).  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path
needs the upstream package installed and its ids registered by importing ``robocasa.utils.gym_utils`` first, and was not
run here.  The ``fidelity`` attribute describes the model as deployed (the analytic fake), not the upstream MuJoCo
model; its ``gaps`` say what the fake omits.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

TASK = "gr1_unified/PnPCupToDrawerClose_GR1ArmsAndWaistFourierHands_Env"
BASIC = "robocasa/utils/gym_utils/gymnasium_basic.py"
GROOT = "robocasa/utils/gym_utils/gymnasium_groot.py"
ROBOTS = "robocasa/models/robots/__init__.py"
GR1_ROBOT = "robocasa/models/robots/manipulators/gr1_robot.py"
TABLETOP = "robocasa/environments/tabletop/tabletop.py"


class RoboCasaGR1Tabletop(GymnasiumDriver):
    device_id = "robocasa-gr1-tabletop"
    env_id = TASK
    native = "robocasa.utils.gym_utils.gymnasium_groot:GrootRoboCasaEnv"
    backends = {"fake": ".fake:FakeRoboCasaEnv"}
    #: The upstream wrapper builds a headless robosuite environment when this is False (gymnasium_basic.py:40, :63,
    #: :66).
    env_kwargs = {"enable_render": False}
    display_name = "RoboCasa GR-1 Tabletop task (Gymnasium GrootRoboCasaEnv)"
    vendor, model = "RoboCasa", "GR-1 Tabletop Tasks"
    tags = ["robocasa", "gr1", "humanoid", "tabletop", "manipulation", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("The repository is the official release of simulation environments for the GR-1 Tabletop Tasks",
             source="vendor_doc", ref="README.md:7"),
        Fact("The package is a RoboCasa fork that adds environments, assets and tooling for the GR-1 Tabletop tasks",
             source="vendor_doc", ref="README.md:13"),
        Fact("The first task id in the README's list of 24 tabletop task names is "
             "gr1_unified/PnPCupToDrawerClose_GR1ArmsAndWaistFourierHands_Env", source="vendor_doc",
             ref="README.md:99"),
        Fact("The simulation dependency is pinned to mujoco==3.2.6", source="upstream_code", ref="setup.py:21"),
        Fact("GrootRoboCasaEnv extends RoboCasaEnv", source="upstream_code", ref=f"{GROOT}:22"),
        Fact("RoboCasaEnv is a gymnasium.Env subclass", source="upstream_code", ref=f"{BASIC}:77"),
        Fact("The wrapper creates its underlying environment with robosuite.make", source="upstream_code",
             ref=f"{BASIC}:73"),
        Fact("The wrapper passes ignore_done=True to the robosuite environment", source="upstream_code",
             ref=f"{BASIC}:64"),
        Fact("The per-part controller action Box is bounded by min -1 and max 1", source="upstream_code",
             ref=f"{BASIC}:140"),
        Fact("A hybrid mobile base adds a Discrete(2) base_mode action", source="upstream_code", ref=f"{BASIC}:149"),
        Fact("The GR-1 arms-and-waist key converter maps action.left_hand, action.right_hand, action.left_arm, "
             "action.right_arm and action.waist to the robosuite controllers", source="upstream_code",
             ref=f"{ROBOTS}:312-320"),
        Fact("The key converter derives each action space key by prefixing the mapped name with 'action.' and bounds "
             "each Box by -1 and 1", source="upstream_code", ref=f"{ROBOTS}:203-213"),
        Fact("The GR1 arms-and-waist initial joint vector is 17 values, with a seven-value right arm at indices 3:10 "
             "and a seven-value left arm at 10:17, leaving the first three values before the right arm",
             source="upstream_code", ref=f"{GR1_ROBOT}:49-53"),
        Fact("The Fourier hand action selection keeps the six values at indices 0, 1, 4, 6, 8 and 10",
             source="upstream_code", ref=f"{ROBOTS}:24-25"),
        Fact("reset(seed, options) seeds numpy with the seed and resets the wrapped robosuite environment; the options "
             "argument is not used", source="upstream_code", ref=f"{BASIC}:213-215"),
        Fact("step takes a dict of per-robot actions and calls the wrapped environment's step", source="upstream_code",
             ref=f"{BASIC}:225-242"),
        Fact("The wrapper reports truncated=False on every step", source="upstream_code", ref=f"{BASIC}:246"),
        Fact("The Groot observation image resolution is 256 x 256", source="upstream_code", ref=f"{GROOT}:19"),
        Fact("The Groot image observation is a uint8 Box of shape 256 x 256 x 3", source="upstream_code",
             ref=f"{GROOT}:29"),
        Fact("The Groot language annotation is a Text field of max_length 256", source="upstream_code",
             ref=f"{GROOT}:38-39"),
        Fact("The gr1_unified id prefix is used for the GR-1 arms, waist and Fourier hands registration",
             source="upstream_code", ref=f"{GROOT}:163-167"),
        Fact("Tabletop is the base class of the tabletop environments", source="upstream_code", ref=f"{TABLETOP}:90"),
        Fact("Tabletop's default control_freq is 20 control signals per second", source="upstream_code",
             ref=f"{TABLETOP}:278"),
        Fact("Tabletop's default horizon is 1000 timesteps", source="upstream_code", ref=f"{TABLETOP}:279"),
        Fact("Tabletop steps the model at the model timestep rate until the control period elapses",
             source="upstream_code", ref=f"{TABLETOP}:1069-1071"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is analytic and was never
    #: compared with the upstream MuJoCo environment; the gaps say what is not modelled.
    fidelity = {
        "engine": f"analytic:fake/GrootRoboCasaEnv for {TASK} (upstream simulator: robosuite with MuJoCo)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) re-seeds the fake's Python random generator and the same seed plus the same actions "
                     "repeats a trajectory; the upstream wrapper seeds numpy and resets the robosuite environment "
                     "(gymnasium_basic.py:214-215), and the two were never compared",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic: no rigid-body dynamics, contacts, actuators, sensors, noise or rendering; one "
            "action is applied per tick through a placeholder first-order filter, so this is an F0 model and the "
            "upstream MuJoCo physics (setup.py:21) is not represented",
            "timestep_ms is 0 because the clone states no physics timestep; tabletop.py:278 declares control_freq=20 "
            "(a 50 ms control period) and tabletop.py:1069-1071 decimates the robosuite model timestep, whose value "
            "this clone does not state",
            "the action and observation dimensions are the default GR-1 sizes named by the clone (seven per arm, "
            "three for the waist, six per Fourier hand); a different robosuite composite controller configuration at "
            "run time can change them and the fake does not model the controller",
            "the image observation is a 2 x 2 x 3 stand-in for the upstream 256 x 256 x 3 uint8 frame "
            "(gymnasium_groot.py:19, :29) and the language annotation is always the empty string",
            "the fake does not model task success: reward is always 0 and terminated/truncated are always false, while "
            "the upstream task subclasses define success through _check_success and reward (tabletop.py:1580-1603)",
            "the fake's action keys drop the upstream 'action.' prefix: the wrapper names the parts action.left_hand, "
            "action.right_hand, action.left_arm, action.right_arm and action.waist (robocasa/models/robots/"
            "__init__.py:312-320), but the Gymnasium bridge addresses a Dict member as action.<key>, so a dotted key "
            "gives an unresolvable limit path; the fake exposes the same five parts as left_hand, right_hand, "
            "left_arm, right_arm and waist, while the sim backend would use the upstream names and was not run",
            "the fake was never compared with the upstream environment and the sim backend (gymnasium.make of the "
            "registered id) was not run; the ids are only registered when robocasa.utils.gym_utils is imported",
            "snapshot and restore are not offered: the wrapper exposes no get_state/set_state pair",
        ],
    }
