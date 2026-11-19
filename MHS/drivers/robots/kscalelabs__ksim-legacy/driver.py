"""OpenMHS driver for gh.kscalelabs/ksim-legacy: the Stompy humanoid MJCF (a MuJoCo family driver).

The card's entry symbol is ``ksim.mjx_gym.envs.stompy_env.stompy:StompyEnv`` (``stompy.py:21``), a brax
``PipelineEnv`` that builds the MJCF path ``MODEL_DIR + "/stompy/stompy.xml"`` (``stompy.py:33``), loads it with
``mujoco.MjModel.from_xml_path`` (``stompy.py:34``), converts it with ``brax.io.mjcf.load_model`` (``stompy.py:39``)
and runs it on the MJX backend (``stompy.py:43``).  That class is not a raw ``mujoco`` model/data pair and is not a
Gymnasium environment; this package serves the card's model ``ksim/assets/stompy/stompy.xml`` through
``MujocoDriver``, the card's helper, exactly as other MJX/card-family packages do.

A ``MujocoDriver`` is configuration only: the bridge loads the MJCF, derives the step action from ``data.ctrl`` (31
motors, each bounded by the model's ``actuator_ctrlrange`` of -200 to 200, ``stompy.xml:230-262``), and derives the
world state from the model and data arrays.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [31 numbers]}}``
and runs ``mj_step`` once per tick; ``cap.world.reset.v1`` runs ``mj_resetData`` + ``mj_forward`` and restores the
model defaults.  The integration step is the model's own 0.001 s (``stompy.xml:16``).

The device is simulated (R0, ``world.sim``): there is no hardware backend, no physical stop and no operator-required
limit.  MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF for the root
slide/ball joints, the hinge and finger slide joints, the 31 motor actuators, their ctrlrange and the option time step,
but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` library and loads the same file; that path was not run
here.

The upstream environment's own reset noise, reward, healthy termination, observation assembly and four-physics-step
control period (``stompy.py:41``) are not exposed: this package serves the raw ``cap.world.step.v1`` /
``cap.world.reset.v1`` contract of the model the environment loads.  Every Fact cites a line of the clone at commit
c1b92feabeab90ad1ecd2c7ff8b6beb4b7a30652.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "ksim/assets/stompy/stompy.xml"
ENV = "ksim/mjx_gym/envs/stompy_env/stompy.py"
ENVS = "ksim/mjx_gym/envs/__init__.py"
README = "README.md"
REQUIREMENTS = "ksim/requirements.txt"
SETUP = "setup.py"
#: The card model, relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/kscalelabs/ksim-legacy/" + MODEL


class Stompy(MujocoDriver):
    device_id = "stompy"
    model_path = MODEL_PATH
    native = "ksim.mjx_gym.envs.stompy_env.stompy:StompyEnv"
    backends = {"fake": FakeMujoco}
    display_name = "K-Scale Stompy humanoid (MJCF model)"
    vendor, model = "K-Scale Labs", "Stompy"
    tags = ["humanoid", "kscale", "locomotion", "mujoco", "mjx", "simulation", "stompy", "world", "robot"]
    facts = [
        Fact("The repository describes itself as a library for training humanoid locomotion in MJX and MuJoCo",
             source="vendor_doc", ref=f"{README}:17"),
        Fact("The environment registry maps the name stompy to StompyEnv", source="upstream_code", ref=f"{ENVS}:9"),
        Fact("get_env registers the selected class with brax and returns a brax environment", source="upstream_code",
             ref=f"{ENVS}:12-14"),
        Fact("StompyEnv is a brax PipelineEnv subclass", source="upstream_code", ref=f"{ENV}:21"),
        Fact("StompyEnv builds its MJCF path as MODEL_DIR plus /stompy/stompy.xml", source="upstream_code",
             ref=f"{ENV}:33"),
        Fact("StompyEnv loads the model with mujoco.MjModel.from_xml_path and converts it with brax.io.mjcf.load_model",
             source="upstream_code", ref=f"{ENV}:34-39"),
        Fact("The environment declares four physics steps per control step and selects the mjx backend",
             source="upstream_code", ref=f"{ENV}:41-43"),
        Fact("The initial qpos is read from the model keyframe named default, and the reward function is built from "
             "the reward parameters and the environment time step", source="upstream_code", ref=f"{ENV}:53-55"),
        Fact("reset(rng) splits the key into three generators and adds uniform noise of plus or minus "
             "reset_noise_scale to the keyframe qpos and to the zero qvel before pipeline_init", source="upstream_code",
             ref=f"{ENV}:57-72"),
        Fact("step takes a brax State, advances it with pipeline_step, computes the reward and sets done to "
             "1 - is_healthy when terminate_when_unhealthy is true", source="upstream_code", ref=f"{ENV}:89-119"),
        Fact("The model compiles in radians with autolimits enabled", source="upstream_code", ref=f"{MODEL}:3"),
        Fact("The model option sets a 0.001 s timestep, 50 iterations, the PGS solver and gravity 0 0 -9.81",
             source="upstream_code", ref=f"{MODEL}:16"),
        Fact("The root body carries three slide joints (root_x, root_y, root_z) and one ball joint (root_ball)",
             source="upstream_code", ref=f"{MODEL}:61-64"),
        Fact("The left shoulder pitch joint declares range -3.14159 to 3.14159, actuatorfrcrange -80 to 80 "
             "and ref -0.534", source="upstream_code",
             ref=f"{MODEL}:69"),
        Fact("The actuator section declares 31 motor actuators, each with ctrllimited true and ctrlrange -200 200",
             source="upstream_code", ref=f"{MODEL}:230-262"),
        Fact("The model declares a keyframe named default with a qpos vector", source="upstream_code",
             ref=f"{MODEL}:360-361"),
        Fact("The runtime stack lists brax, jax and mujoco-mjx", source="upstream_code", ref=f"{REQUIREMENTS}:3-7"),
        Fact("The package requires Python 3.11 or newer", source="upstream_code", ref=f"{SETUP}:35"),
    ]
    safe_state = ("bridge-owned lockstep integration stops; no step or world reset is accepted while latched. "
                  "The integration state, velocities and controls are retained and readable. mhs.safety.reset "
                  "only clears the latch; a new step is required and a step without action reuses retained controls")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, time step, determinism kind and
    #: lockstep clock; the members below make the whole contract readable in one place.
    fidelity = {
        "engine": "mujoco:stompy",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "the bridge publishes no seed control for this engine: reset restores the model defaults with "
                     "mj_resetData and the stand-in is a deterministic replay of the caller's control sequence, but "
                     "that is not the upstream MJX environment, whose reset draws JAX random noise around the "
                     "keyframe default pose",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the root "
            "slide/ball joints, the hinge and finger slide joints, the 31 motor actuators, their -200..200 ctrlrange "
            "and the 0.001 s option step, then gives each actuated hinge or slide a placeholder velocity proportional "
            "to its control value and holds the root joints fixed; it computes no inertia, torque, gravity, contact, "
            "friction, damping, armature, constraint or actuator dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision, contact, equality, tendon or "
            "sensor; the 32 mesh assets and the plane floor are not applied",
            "the upstream StompyEnv MJX environment is not exposed: its keyframe-default initial pose plus uniform "
            "reset noise, reward, healthy termination, observation assembly and metrics stay upstream; this package "
            "serves the raw cap.world.step.v1/cap.world.reset.v1 contract of the MJCF the environment loads",
            "the environment runs four physics steps per control step (stompy.py:41) and selects the mjx backend "
            "(stompy.py:43); this package's bridge advances the model by one 0.001 s mj_step per requested tick and "
            "does not implement that control period or the MJX implementation",
            "StompyEnv overwrites the XML solver with CG and sets iterations and ls_iterations to 6 "
            "(stompy.py:35-37); the raw-model bridge does not apply these overrides, and the fake models no solver",
            "the environment resolves its model through MODEL_DIR (stompy.py:33); this package points model_path at "
            "the card model in the read-only clone and never sets or requires MODEL_DIR",
            "the bridge's basic checkpoint profile restores only time/qpos/qvel/act/ctrl for the stand-in, not the "
            "full integration state, so snapshot_restore is declared false",
            "MuJoCo itself and the JAX/MJX stack were not importable where the gate ran, so no trajectory of this "
            "package was compared with the real engine and the sim backend was not run",
            "no physical Stompy is modelled by this package and nothing was validated against hardware",
        ],
    }
    fidelity_by_backend = {
        "fake": {"engine": "analytic:stompy", "fidelity_level": "F0"},
    }
