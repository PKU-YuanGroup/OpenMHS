"""OpenMHS driver for gh.tau-intelligence/mujoco-drones-gym: the HoverAviary MuJoCo environment.

A GymnasiumDriver is configuration only: the bridge derives the ``cap.world.*`` contract from the environment's
spaces.  ``HoverAviary`` is a single-drone hover task (``multi_drone_mujoco/envs/hover_aviary.py:15``).  Its action
space is a 4-element Box of normalized RPM commands in [-1, 1] (``hover_aviary.py:51-53``) and its observation is the
12 values position, roll-pitch-yaw, linear velocity and angular velocity (``hover_aviary.py:68-73``).
``cap.world.step.v1`` therefore takes ``{ticks, action: {values}}`` with four bounded elements, ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no
hardware backend, no stop path to a machine and no operator-required limit.

The ``multi_drone_mujoco.envs`` package re-exports the environment classes
(``multi_drone_mujoco/envs/__init__.py:1-7``) and the upstream README constructs ``HoverAviary`` directly
(``README.md:67``); no registered Gymnasium id is used, so ``env_id`` is left None.
The ``fake`` backend is this package's pure Python stand-in (fake.py); it is checked because the gate does not install
MuJoCo or import the clone.  The upstream model would run through ``gymnasium.make`` only after the package is
installed; that path was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit ca170dc6760d422e47ef46fb3af46f8cd20410eb.  This
package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

HOVER = "multi_drone_mujoco/envs/hover_aviary.py"
BASE = "multi_drone_mujoco/envs/base_aviary.py"


class HoverAviary(GymnasiumDriver):
    device_id = "hover-aviary"
    env_id = None
    native = "multi_drone_mujoco.envs.hover_aviary:HoverAviary"
    backends = {"fake": ".fake:FakeHoverAviary"}
    action_space_ref = f"{HOVER}:51-53"
    display_name = "MuJoCo multi-drone gym HoverAviary (single-drone hover)"
    vendor, model = "tau-intelligence", "HoverAviary"
    tags = ["mujoco", "quadcopter", "hover", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("HoverAviary is the single-drone hover task: hover at height 1.0 and remain stable",
             source="upstream_code", ref=f"{HOVER}:3"),
        Fact("The action is a 4-element normalized RPM command in [-1, 1]", source="upstream_code",
             ref=f"{HOVER}:5"),
        Fact("The action space is a Box with low -1 and high 1 for each of the 4 motors", source="upstream_code",
             ref=f"{HOVER}:51-53"),
        Fact("The observation is 12 values: position (3), roll-pitch-yaw (3), linear velocity (3) and angular "
             "velocity (3)", source="upstream_code", ref=f"{HOVER}:68-73"),
        Fact("The default simulation frequency is 240 Hz and the default control frequency is 48 Hz",
             source="upstream_code", ref=f"{HOVER}:22-23"),
        Fact("The control period is 1/ctrl_freq and the physics step is 1/sim_freq; the environment runs "
             "sim_freq/ctrl_freq physics sub-steps per control step", source="upstream_code",
             ref=f"{BASE}:350-354"),
        Fact("The default initial position is [0.0, 0.0, 0.1]", source="upstream_code",
             ref=f"{HOVER}:33-34"),
        Fact("EPISODE_LEN_SEC is 10 s", source="upstream_code", ref=f"{HOVER}:32"),
        Fact("The episode truncates when step_counter / SIM_FREQ reaches the episode length",
             source="upstream_code", ref=f"{HOVER}:113-115"),
        Fact("The episode terminates when the altitude is below 0 or above 3 m, or when the absolute roll or pitch "
             "exceeds pi/2", source="upstream_code", ref=f"{HOVER}:105-110"),
        Fact("The reward is -(height error) - 0.1*(xy error) - 0.05*|velocity| - 0.05*(|roll| + |pitch|), plus 1 "
             "when both errors are below 0.05 and -100 when terminated", source="upstream_code",
             ref=f"{HOVER}:83-95"),
        Fact("The info dict reports the position and the absolute height error", source="upstream_code",
             ref=f"{HOVER}:117-121"),
        Fact("reset(seed, options) delegates the seed to the Gymnasium base class, restores the initial position and "
             "orientation, zeroes step_counter and last_clipped_action, and returns the observation and info",
             source="upstream_code", ref=f"{BASE}:490-524"),
        Fact("step preprocesses the action, runs the physics sub-steps, increments step_counter by "
             "SIM_STEPS_PER_CTRL and returns observation, reward, terminated, truncated and info",
             source="upstream_code", ref=f"{BASE}:528-598"),
        Fact("With the MuJoCo physics mode each simulation sub-step advances the model with mujoco.mj_step",
             source="upstream_code", ref=f"{BASE}:577-579"),
        Fact("The package's runtime dependencies are gymnasium>=0.29.0, mujoco>=3.0.0 and numpy>=1.21.0; no "
             "hardware transport is declared", source="upstream_code", ref="setup.py:13-15"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The upstream environment is a MuJoCo rigid-body world with
    #: contacts and an RPM-to-thrust/torque actuator; the fake backend is a pure Python stand-in (see the gaps).
    fidelity = {
        "engine": "mujoco:HoverAviary",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) records the seed and the hover start pose is fixed, so one action sequence repeats "
                     "from a reset; the fake is deterministic as well and makes no random draw",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python kinematic stand-in, not MuJoCo: it integrates placeholder "
            "accelerations and angular-rate gains, has no contacts, thrust/torque actuator, ground effect, drag, "
            "downwash, wind, obstacles or sensors, and was not compared with the upstream environment",
            "the upstream F1 model has rigid-body MuJoCo contacts and an RPM-to-thrust/torque actuator; it was not "
            "run here because the gate neither installs MuJoCo nor imports the clone",
            "no wall-clock pacing: realtime_factor 0, ticks advance the lockstep environment only",
            "timestep_ms is the physics step (1/240 s); one cap.world.step.v1 tick is one control step of 5 physics "
            "sub-steps (1/48 s, base_aviary.py:350-354, 585)",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }
