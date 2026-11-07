"""OpenMHS driver for gh.intelligent-control-lab/bricksim: the state-based Lego assemble-brick environment.

BrickSim is an Isaac Lab task package: it registers Gymnasium environments whose entry point is the external
``isaaclab.envs.ManagerBasedRLEnv`` and whose ``env_cfg_entry_point`` is the in-tree ``AssembleBrickEnvCfg``
(``python/bricksim/envs/assemble_brick/__init__.py:7-14``).  This is a ``GymnasiumDriver``, so it is configuration
only: ``env_id`` names the registration and the bridge derives the contract from the environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values: [7 floats]}`` from the arm and gripper
action terms, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The card's entry symbol is the config class, not an environment class: the actual environment is Isaac Lab's
``ManagerBasedRLEnv``, which lives outside this repository and is not importable where the gate runs.  ``native`` is
therefore ``AssembleBrickEnvCfg``, the card's first entry symbol, and the ``fake`` backend is this package's own pure
Python stand-in for the environment that class configures.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
fact cites a line of the clone at the pinned commit ``cbd5de3238e6ac12f44ef699e1507a9f16bdafc3``.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and neither Isaac Sim nor Isaac Lab was run.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "python/bricksim/envs/assemble_brick/env.py"
REGISTRY = "python/bricksim/envs/assemble_brick/__init__.py"
PYPROJECT = "python/pyproject.toml"


class BrickAssembleEnv(GymnasiumDriver):
    device_id = "lego-assemble-brick"
    env_id = "Lego-AssembleBrick-v0"
    native = "bricksim.envs.assemble_brick.env:AssembleBrickEnvCfg"
    backends = {"fake": ".fake:FakeAssembleBrickEnv"}
    display_name = "BrickSim state-based Lego assemble-brick environment (Isaac Lab)"
    vendor, model = "Intelligent Control Lab", "BrickSim 0.1.0 / Lego-AssembleBrick-v0"
    tags = ["brick-assembly", "gymnasium", "isaac-lab", "isaac-sim", "lego", "manipulation",
            "reinforcement-learning", "simulation"]
    facts = [
        Fact("The assemble-brick package registers Lego-AssembleBrick-v0 with entry point "
             "isaaclab.envs:ManagerBasedRLEnv and env_cfg_entry_point <this package>.env:AssembleBrickEnvCfg",
             source="upstream_code", ref=f"{REGISTRY}:7-14"),
        Fact("The same package registers Lego-AssembleBrick-RGB-v0 and Lego-AssembleBrick-RGBD-v0 with the RGB and "
             "RGB-D configuration classes", source="upstream_code", ref=f"{REGISTRY}:16-32"),
        Fact("The Python package requires Python 3.11 or newer and depends on gymnasium 1.2.0",
             source="upstream_code", ref=f"{PYPROJECT}:5-8"),
        Fact("The isaacsim and isaaclab optional extras pin isaacsim[all,extscache]==5.1.0 and isaaclab==2.3.2.post1",
             source="upstream_code", ref=f"{PYPROJECT}:17-19"),
        Fact("BrickSim requires an x86-64 Linux platform and an NVIDIA driver compatible with Isaac Sim",
             source="vendor_doc", ref="README.md:32-37"),
        Fact("AssembleBrickBaseEnvCfg extends isaaclab.envs.ManagerBasedRLEnvCfg",
             source="upstream_code", ref=f"{ENV}:468-469"),
        Fact("The scene runs one environment instance with an environment spacing of 5.0",
             source="upstream_code", ref=f"{ENV}:472"),
        Fact("Each control step applies 6 simulation steps of 1/60 s and an episode is 12.0 s long",
             source="upstream_code", ref=f"{ENV}:492-494"),
        Fact("AssembleBrickEnvCfg removes the hand, front and side cameras and the image observation group, so the "
             "state-based environment returns no images", source="upstream_code", ref=f"{ENV}:506-516"),
        Fact("The arm action is a differential inverse-kinematics relative pose command",
             source="upstream_code", ref=f"{ENV}:278-290"),
        Fact("The arm action is scaled per axis by (0.2, 0.2, 0.2, 1.0, 1.0, 1.0)",
             source="upstream_code", ref=f"{ENV}:90"),
        Fact("The gripper action opens the fingers to 0.04 m above the 0.2 threshold and closes them to 0.0 m below "
             "the -0.2 threshold", source="upstream_code", ref=f"{ENV}:292-300"),
        Fact("The ActionsCfg docstring tells callers to send finite actions in [-1, 1]",
             source="upstream_code", ref=f"{ENV}:274"),
        Fact("The policy observation group is end-effector pose, gripper width, gripper speed, brick pose and target "
             "pose", source="upstream_code", ref=f"{ENV}:323-332"),
        Fact("The privileged observation group adds brick_grasped, connection_created and brick_dimensions and sets "
             "concatenate_terms to False", source="upstream_code", ref=f"{ENV}:334-342"),
        Fact("The termination terms are a timeout, a formed target connection with the gripper open, a non-target "
             "connection and a brick dropped below its height threshold", source="upstream_code", ref=f"{ENV}:458-465"),
        Fact("A reset applies a Gaussian joint offset with mean 0.0 and standard deviation 0.02",
             source="upstream_code", ref=f"{ENV}:417-425"),
        Fact("A reset places the brick uniformly over x 0.36 to 0.56 m, y 0.16 to 0.32 m and yaw 0 to 2*pi",
             source="upstream_code", ref=f"{ENV}:427-439"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "gymnasium:Lego-AssembleBrick-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial brick gap; the dynamics are "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions.  The "
                     "fake draws with Python's random.Random; upstream Isaac Lab seeds its own torch/numpy "
                     "generators through the manager-based environment, and the two were never compared",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body physics, contacts, friction, actuators and sensors are Isaac Sim's, configured by this "
            "package but implemented outside it (python/pyproject.toml:17-19); the gate cannot import, install or "
            "run Isaac Sim or Isaac Lab, so nothing here was executed against them",
            "the state-based configuration is served; the RGB and RGB-D camera variants return 720x1280 RGB and "
            "depth images, which this driver does not declare, and no image array is produced",
            "the fake backend is a pure Python kinematic stand-in, not Isaac Sim: it has no contact, friction, "
            "actuator, sensor or camera model, and its reward is a placeholder, not the weights of env.py:446-455",
            "the fake keeps a scalar gap to the brick instead of the full articulation; its observation keeps the "
            "structure of the policy and privileged groups but the policy group is 23 numbers and the RGB/RGB-D "
            "image groups of the other configurations are absent",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the fake environment exposes no get_state or set_state",
        ],
    }
