"""OpenMHS driver for gh.spiglerg/tavis: the TAVIS simulated humanoid-torso benchmark.

TAVIS composes an embodiment, a task and an optional scene with IsaacLab-Arena into an Isaac Lab
``ManagerBasedRLEnv`` and returns it wrapped in ``CanonicalFrameWrapper`` (make_env.py:14-22 and :90-100).  The
result is a Gymnasium environment: the bridge serves ``cap.world.step.v1`` (a batched 19-D Box action on the
GR1T2 embodiment, gr1t2.py:8-10), ``cap.world.reset.v1`` (``seed``/``options``) and ``cap.world.seed.v1``.
``cap.world.step.v1`` returns the observation, reward, terminal flags, tick and state hash; the observation is the
environment's policy group, a Dict of observation terms including a camera image.

There is no fixed ``env_id`` to ``gym.make``: ``make_tavis_env`` composes an ``IsaacLabArenaEnvironment`` named
``tavis_env`` and registers it at build time (make_env.py:56-61 and :72-75), so the family's configured
``gym.make(env_id)`` path cannot reproduce it from class attributes alone.  This package therefore ships only the
package fake backend.  The upstream simulator path needs Isaac Sim, Isaac Lab, IsaacLab-Arena, a Linux NVIDIA RTX
machine and USD assets downloaded from Hugging Face (README.md:38-49); it was not run here.

The card's ``make_tavis_env`` entry symbol is a function, and G7 resolves ``native`` as a class, so ``native`` names
the GR1T2 embodiment class, the card entry symbol for the reference robot of the benchmark (the Reachy 2 class is
the second embodiment entry symbol).  The composed environment itself is Isaac Lab's ``ManagerBasedRLEnv`` outside
the clone.  The fake therefore stands in for the registered environment while the gate compares its Gymnasium
interface with the embodiment class, whose base ``EmbodimentBase`` is also outside the clone; those interface names
are reported as ``G7.MAYBE_ABSENT`` warnings by design.  This package is simulated R0, model-authored and
unreviewed: its evidence is ``contract_checked`` on the fake backend, never an MHS-Device level, a hardware run or a
statement that a human reviewed it.

Every constant and rule cites a line of the clone at the pinned commit
a114648a0db232a1a8d4b142c65251b29afa795a.
"""

from mhs.driver import Fact, GymnasiumDriver

MAKE_ENV = "tavis/make_env.py"
GR1T2 = "tavis/robots/gr1t2.py"
REACHY2 = "tavis/robots/reachy2.py"
WRAPPER = "tavis/wrappers/canonical_frame_wrapper.py"


class Tavis(GymnasiumDriver):
    device_id = "tavis"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    #: No fixed environment id exists in the clone: make_tavis_env registers the composed IsaacLab-Arena
    #: environment under the name it builds (make_env.py:56-61 and :72-75).  Only the package fake is provided.
    env_id = None
    #: G7 resolves ``native`` as a class; the card's factory is a function (make_env.py:14), so this is the
    #: GR1T2 embodiment, the card entry symbol for the reference robot of the benchmark (gr1t2.py:400).
    native = "tavis.robots.gr1t2:GR1T2Embodiment"
    backends = {"fake": ".fake:FakeTavisEnv"}
    display_name = "TAVIS humanoid-torso active-vision benchmark (Isaac Lab-Arena)"
    vendor, model = "TAVIS benchmark", "TAVIS (Fourier GR1T2 / Pollen Reachy 2)"
    tags = ["tavis", "isaac-lab", "isaac-sim", "isaaclab-arena", "humanoid", "active-vision",
            "imitation-learning", "simulation", "gymnasium"]
    facts = [
        Fact("TAVIS is a benchmark for egocentric active-vision imitation learning on humanoid torsos with eight "
             "simulated manipulation tasks across the Fourier GR1T2 and Pollen Reachy 2 robots",
             source="vendor_doc", ref="README.md:7-10"),
        Fact("The same tasks run on both humanoid torsos with a canonical 19-D action layout",
             source="vendor_doc", ref="README.md:27-30"),
        Fact("make_env.py is described as the single environment-construction entry point",
             source="vendor_doc", ref="README.md:252"),
        Fact("make_tavis_env composes an embodiment, a task and an optional scene, and defaults to 1 environment, "
             "cameras enabled, a 20 Hz robot control rate and 100 s episodes",
             source="upstream_code", ref=f"{MAKE_ENV}:14-22"),
        Fact("make_tavis_env builds an IsaacLabArenaEnvironment named tavis_env",
             source="upstream_code", ref=f"{MAKE_ENV}:56-61"),
        Fact("make_tavis_env builds and registers the environment with ArenaEnvBuilder.build_registered",
             source="upstream_code", ref=f"{MAKE_ENV}:72-75"),
        Fact("make_tavis_env creates the environment with gym.make(name, cfg=cfg).unwrapped and resets it once",
             source="upstream_code", ref=f"{MAKE_ENV}:90-93"),
        Fact("make_tavis_env wraps the environment in CanonicalFrameWrapper before returning it",
             source="upstream_code", ref=f"{MAKE_ENV}:99-100"),
        Fact("CanonicalFrameWrapper extends gymnasium.Wrapper so downstream wrappers see a Gymnasium Env",
             source="upstream_code", ref=f"{WRAPPER}:58"),
        Fact("CanonicalFrameWrapper.step adds the embodiment's canonical-frame offset to the left and right arm IK "
             "position targets before stepping the wrapped environment",
             source="upstream_code", ref=f"{WRAPPER}:86-92"),
        Fact("GR1T2Embodiment is the GR1T2 robot embodiment with Robotiq 2F-85 grippers and NullspaceIK control",
             source="upstream_code", ref=f"{GR1T2}:400-401"),
        Fact("The GR1T2 action space is 19-D: left and right arm IK (7 each), head roll (1), head pitch and yaw (2) "
             "and one gripper command per hand (1 each)",
             source="upstream_code", ref=f"{GR1T2}:8-10"),
        Fact("GR1T2Embodiment.modify_env_cfg sets the simulation timestep to 1/60 s",
             source="upstream_code", ref=f"{GR1T2}:461-465"),
        Fact("Reachy2Embodiment is the Reachy 2 robot embodiment with NullspaceIK control",
             source="upstream_code", ref=f"{REACHY2}:596-597"),
        Fact("Simulation, data collection and evaluation need an NVIDIA GPU with ray-tracing support, and RTX is "
             "required at rendering time", source="vendor_doc", ref="README.md:47-49"),
        Fact("The installer bootstraps the pinned stack into a conda environment on Python 3.11",
             source="vendor_doc", ref="README.md:57-59"),
        Fact("The package requires Python >=3.10", source="vendor_doc", ref="pyproject.toml:11"),
        Fact("isaacsim, isaaclab and isaaclab-arena must be installed separately and are not on PyPI",
             source="vendor_doc", ref="pyproject.toml:32"),
        Fact("Plain pip install -e . will not install correctly; pyproject.toml instructs uv pip install -e .",
             source="vendor_doc", ref="pyproject.toml:34"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "tavis:make_tavis_env",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) or cap.world.seed.v1 and its "
                     "kinematic update is deterministic; upstream reset(seed) controls Isaac Lab's generators, "
                     "and the fake was not compared with the upstream environment because that stack was not run",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no Isaac Sim physics, contacts, IK, actuator, sensor, noise or rendering "
            "model; the fake adds a fixed fraction of each action to one coordinate per joint per tick",
            "the real action space is the batched Box of Isaac Lab's action manager, 19 wide for the GR1T2 "
            "embodiment (7 + 7 arm IK, 1 head roll, 2 head pitch/yaw and 2 grippers), transformed by "
            "CanonicalFrameWrapper; num_envs defaults to 1 but can be larger, while the MHS bridge drives one "
            "environment and the fake uses a single 19-element action Box and no canonical-frame conversion",
            "the real observation is the environment's Dict of observation groups, including the head-mounted "
            "camera images (image_or_zeros handles disabled cameras); the fake publishes one policy group of 19 "
            "numbers and no image, so the real arrays are larger",
            "timestep_ms is the default control period of 50 ms (robot_ctrl_rate 20 Hz, make_env.py:20); the "
            "fake advances one integer tick per step and models no simulated time, while the upstream decimation "
            "is computed from the simulator's 60 Hz step and robot_ctrl_rate can change both",
            "episode_length_s defaults to 100 s and is passed to the task (make_env.py:21 and :48); the fake has "
            "no episode limit and no task success or reward model",
            "there is no fixed env_id to gym.make: make_tavis_env registers the composed environment as tavis_env "
            "at build time, so only the package fake backend is provided and the upstream simulator path is not "
            "configured",
            "the upstream stack (Isaac Sim, Isaac Lab, IsaacLab-Arena, Python 3.11 per README.md:59 and an NVIDIA "
            "RTX GPU per README.md:47-49) requires USD assets downloaded from Hugging Face and was never started "
            "here",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep",
        ],
    }
