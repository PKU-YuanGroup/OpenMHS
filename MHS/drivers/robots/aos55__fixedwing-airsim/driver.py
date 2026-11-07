"""OpenMHS driver for gh.aos55/fixedwing-airsim: the SingleObservation fixed-wing Gym environment.

The card calls this a Gymnasium family configuration, and the upstream class is a ``gym.Env``: ``step(action)``
returns ``(observation, reward, done, info)`` and ``reset()`` returns an observation.  ``GymnasiumDriver`` derives
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from that environment.  The action space is a
``Box`` over heading and pitch in degrees, so the step input is ``{"ticks": n, "action": {"values": [heading,
pitch]}}`` with the bounds the upstream constructor declares.

The upstream environment is a bridge between JSBSim and AirSim, not a registered Gymnasium environment: it has no
``gym.register`` call and its constructor eagerly builds ``Simulation`` (which needs the AirSim runtime and a JSBSim
root).  ``env_id`` therefore stays unset and the bridge's ``gymnasium.make`` path is not offered.  The gate runs the
package's own ``fake`` backend (``fake.py``), a protocol stand-in that implements the same public environment methods
without importing the clone.

Every Fact cites a line of the clone at the pinned commit c5054486fb05dc67668b123c7789e399c8d4ce02.  The fidelity
contract describes the model as deployed (spec 05-fidelity FID-002): JSBSim rigid-body dynamics with AirSim/Unreal
collision information.  The package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "src/envs/single_observation.py"
SIM = "src/jsbsim_simulator.py"
IMAGES = "src/image_processing.py"
README = "README.md"


class FixedwingAirsim(GymnasiumDriver):
    device_id = "fixedwing-airsim"
    #: The clone registers no Gymnasium environment id; the class is reached directly (src/envs/single_observation.py:13).
    env_id = None
    native = "envs.single_observation:SingleObservation"
    backends = {"fake": ".fake:FakeSingleObservation"}
    action_space_ref = f"{ENV}:62-68"
    display_name = "Fixedwing-Airsim SingleObservation (JSBSim + AirSim)"
    vendor, model = "AOS55", "Fixedwing-Airsim x8"
    tags = ["fixed-wing", "jsbsim", "airsim", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("SingleObservation is the OpenAI Gym environment class of the package (a gym.Env subclass)",
             source="upstream_code", ref=f"{ENV}:13"),
        Fact("The action space is Box(2): heading from -45 to +45 degrees and pitch from -30 to 0 degrees",
             source="upstream_code", ref=f"{ENV}:62-68"),
        Fact("The action space is built as spaces.Box(min_angle, max_angle, dtype=np.float32) from the four angle "
             "attributes", source="upstream_code", ref=f"{ENV}:66-68"),
        Fact("The observation space is spaces.Box(low=0, high=255) with the shape and dtype of the first AirSim "
             "Scene image", source="upstream_code", ref=f"{ENV}:69-71"),
        Fact("An AirSim Scene image is reshaped to (3, image_response.height, image_response.width); the resolution "
             "comes from the AirSim response at runtime", source="upstream_code", ref=f"{IMAGES}:41-50"),
        Fact("The step reads the Scene image before the physics update and reports done=True when AirSim reports "
             "collision_info.has_collided", source="upstream_code", ref=f"{ENV}:88-100"),
        Fact("The reward is 1 when the collided object_name is 'airport' and 0 otherwise", source="upstream_code",
             ref=f"{ENV}:93-100"),
        Fact("A step advances JSBSim once and returns (observation, reward, done, info)", source="upstream_code",
             ref=f"{ENV}:104-113"),
        Fact("A reset reinitialises the Simulation and returns a new Scene image", source="upstream_code",
             ref=f"{ENV}:121-130"),
        Fact("The seed method forwards to gym.utils.seeding.np_random and returns [seed]", source="upstream_code",
             ref=f"{ENV}:81-83"),
        Fact("The environment uses airsim_frequency_hz 48.0, jsbsim_frequency_hz 240.0 and airspeed 50.0, and "
             "constructs Simulation with the JSBSim frequency", source="upstream_code", ref=f"{ENV}:49-58"),
        Fact("The environment's default aircraft is the x8 model", source="upstream_code",
             ref=f"{ENV}:52"),
        Fact("Simulation sets sim_dt = 1.0 / sim_frequency_hz and passes it to the FDM", source="upstream_code",
             ref=f"{SIM}:85-87"),
        Fact("The AirSim pose update runs when relative_update = airsim_frequency_hz / jsbsim_frequency_hz makes the "
             "integer graphics tick increase", source="upstream_code", ref=f"{ENV}:76-105"),
        Fact("The constructor computes max_updates = max_sim_time * jsbsim_frequency_hz, but step never compares id "
             "with max_updates, so the environment code has no episode time limit", source="upstream_code",
             ref=f"{ENV}:75-113"),
        Fact("The default initial conditions are basic_ic.xml; minimal_ic.xml is used only when init_conditions is "
             "not None", source="upstream_code", ref=f"{SIM}:139-148"),
        Fact("Simulation.reinitialise resets the FDM to its initial conditions", source="upstream_code",
             ref=f"{SIM}:165-176"),
        Fact("The JSBSim FDM root is the hardcoded Windows path c:\\Users\\quessy\\Dev\\jsbsim", source="upstream_code",
             ref=f"{SIM}:76"),
        Fact("wall_clock_dt starts as None, so the simulation is not wall-clock paced", source="upstream_code",
             ref=f"{SIM}:89"),
        Fact("run() advances the FDM once and sleeps only when wall_clock_dt is set", source="upstream_code",
             ref=f"{SIM}:178-187"),
        Fact("The AirSim client is a VehicleClient that calls confirmConnection()", source="upstream_code",
             ref=f"{SIM}:225-233"),
        Fact("The README lists AirSim and JSBSim as separate installs and requires moving the x8 directory and "
             "electric800w.xml into the JSBSim aircraft and engine directories", source="vendor_doc",
             ref=f"{README}:6-10"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind, timestep and lockstep clock from the environment; they are written out so the whole contract
    #: reads in one place.  Every constant cites a line of the clone at the pinned commit.
    fidelity = {
        "engine": "jsbsim+airsim",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) is accepted and cap.world.seed.v1 fixes the seed of the next reset, but "
                     "SingleObservation only stores it in gym's np_random; reset always reinitialises from "
                     "basic_ic.xml and the initial state does not depend on the seed.  JSBSim is deterministic for "
                     "a fixed state and command sequence; AirSim scene rendering and collision timing are not "
                     "claimed bit-identical, and the fake is exact for its own placeholder state.",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "The clone implements neither the flight dynamics nor the collision response: JSBSim's x8 FDM "
            "supplies the rigid-body dynamics and AirSim/Unreal supplies contact and scene rendering "
            "(src/jsbsim_simulator.py:83, src/envs/single_observation.py:93-100).  The fake backend reproduces "
            "neither; its motion and collision are placeholder test data.",
            "No actuator, sensor, wind, turbulence or noise model is declared: the autopilot receives heading, "
            "pitch and airspeed commands and JSBSim applies them.  Contact and actuator fidelity are therefore "
            "not validated.",
            "No wall-clock pacing: wall_clock_dt is None (src/jsbsim_simulator.py:89) and realtime_factor is 0; "
            "ticks advance simulated time by timestep_ms only.",
            "The fake's observation is a 3 x 8 x 8 placeholder array.  The clone takes (3, height, width) from the "
            "AirSim image response at runtime (src/image_processing.py:49) and fixes no default resolution for "
            "SingleObservation; the 480 x 832 values in src/segmentation/config.py:22-23 belong to the separate "
            "segmentation pipeline, not to this environment.",
            "The seed does not change the reset state: reset reinitialises from basic_ic.xml (src/jsbsim_simulator.py:"
            "139-148 and 165-176) and SingleObservation.seed only seeds gym's np_random (src/envs/single_observation."
            "py:81-83).  Repeatability comes from the fixed initial state and deterministic JSBSim arithmetic, not "
            "from the seed.",
            "Snapshot and restore are not offered: the environment exposes no get_state/set_state pair.",
            "The hardcoded Windows JSBSim root (src/jsbsim_simulator.py:76) and the separate AirSim/JSBSim installs "
            "(README.md:6-10) mean the upstream environment was not run here; only the fake backend is checked.",
        ],
    }
