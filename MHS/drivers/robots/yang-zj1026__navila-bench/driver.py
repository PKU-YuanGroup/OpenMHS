"""OpenMHS driver for gh.yang-zj1026/navila-bench: the go2_matterport_vision task (Gymnasium family driver).

The repository is an Isaac Lab benchmark for Visual Language Navigation (README.md:31).  ``go2_matterport_vision``
is registered at ``isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/__init__.py:20-28`` with the external
entry point ``omni.isaac.lab.envs:ManagerBasedRLEnv`` and the environment configuration
``Go2MatterportVisionCfg`` (the card's first entry symbol, ``go2_matterport_vision_cfg.py:163``).  The registered
environment class, its Gymnasium base and its action/observation spaces live in the external Isaac Lab package
(``go2_matterport_base_cfg.py:4``); the clone supplies the configuration only.  The card therefore names the
configuration class as ``native``, and this package uses it as the card's entry symbol.  A ``GymnasiumDriver`` is
configuration only: the bridge derives the ``cap.world.*`` contract from the environment spaces of the fake backend.

The task needs Isaac Sim 4.1.0 and Isaac Lab 1.1.0 with both extensions symlinked (README.md:55-69), a CUDA GPU
(README.md:45), the benchmark data and Matterport USD assets from Hugging Face (README.md:82), and an environment
configuration object passed to ``gym.make`` (``scripts/navila_eval.py:271``).  None of that is installed or present
where the gate runs, and package code never imports or runs the clone.  The package's ``fake`` backend is therefore a
pure Python interface stand-in (fake.py) for the registered environment, not the upstream simulator; the upstream-sim
mock path was not run.  It serves one environment, an unbounded 12-value joint-position action and three small
placeholder observation groups; the real camera is 512 x 512 RGB-D (``go2_matterport_base_cfg.py:301-307``), and
every reduction is listed in the fidelity ``gaps`` below and in RESULT.json.

The device is simulated (R0): no hardware backend, no machine to stop and no operator-required limit.  Every Fact
cites the clone at commit e9d2db12ce5788c0f987d734c0094100b6bc0d3a.  The package is model-authored and unreviewed:
it is checked on the fake backend only, and no hardware or simulator run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

VISION_CFG = "isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_vision_cfg.py"
BASE_CFG = "isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/go2_matterport_base_cfg.py"
GO2_INIT = "isaaclab_exts/omni.isaac.vlnce/omni/isaac/vlnce/config/go2/__init__.py"
EVAL = "scripts/navila_eval.py"


class Go2MatterportVision(GymnasiumDriver):
    """The go2_matterport_vision task of NaVILA-Bench, served through the package fake."""

    device_id = "navila-go2-matterport-vision"
    env_id = "go2_matterport_vision"
    native = "omni.isaac.vlnce.config.go2.go2_matterport_vision_cfg:Go2MatterportVisionCfg"
    backends = {"fake": ".fake:FakeGo2MatterportVisionEnv"}
    display_name = "NaVILA-Bench go2_matterport_vision (Isaac Lab / Isaac Sim 4.1 target)"
    vendor, model = "yang-zj1026", "NaVILA-Bench go2_matterport_vision"
    tags = ["navila-bench", "visual-language-navigation", "go2", "isaac-lab", "isaac-sim", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("The repository is a benchmark framework for evaluating Visual Language Navigation in Isaac Lab",
             source="vendor_doc", ref="README.md:31"),
        Fact("Isaac Sim 4.1.0 and Isaac Lab 1.1.0 are installed separately, and the omni.isaac.vlnce and "
             "omni.isaac.matterport extensions are symlinked into the Isaac Lab source tree",
             source="vendor_doc", ref="README.md:55-69"),
        Fact("The benchmark data and Matterport USD assets are downloaded from Hugging Face into the "
             "isaaclab_exts/omni.isaac.vlnce/assets directory", source="vendor_doc", ref="README.md:82"),
        Fact("go2_matterport_vision is registered with the external entry point omni.isaac.lab.envs:"
             "ManagerBasedRLEnv and the environment configuration Go2MatterportVisionCfg",
             source="upstream_code", ref=f"{GO2_INIT}:20-28"),
        Fact("The card entry symbol Go2MatterportVisionCfg is defined as a subclass of Go2MatterportBaseCfg",
             source="upstream_code", ref=f"{VISION_CFG}:163"),
        Fact("Go2MatterportBaseCfg extends ManagerBasedRLEnvCfg, so the registered environment base is external to "
             "the clone", source="upstream_code", ref=f"{BASE_CFG}:350"),
        Fact("ManagerBasedRLEnvCfg is imported from omni.isaac.lab.envs, the external Isaac Lab package",
             source="upstream_code", ref=f"{BASE_CFG}:4"),
        Fact("The Go2 robot is loaded from the external Isaac Lab asset {ISAACLAB_NUCLEUS_DIR}/Robots/Unitree/"
             "Go2/go2.usd", source="upstream_code", ref=f"{BASE_CFG}:70"),
        Fact("The action term is a JointPositionActionCfg over all robot joints (joint_names ['.*'])",
             source="upstream_code", ref=f"{BASE_CFG}:125"),
        Fact("The base post-initialization changes the joint-position action scale to 0.25",
             source="upstream_code", ref=f"{BASE_CFG}:372"),
        Fact("The simulation step is 0.005 s and the decimation is 4",
             source="upstream_code", ref=f"{BASE_CFG}:367-371"),
        Fact("The episode length is 200000.0 s", source="upstream_code", ref=f"{BASE_CFG}:369"),
        Fact("The rgbd camera is 512 by 512 and returns rgb and distance_to_image_plane data",
             source="upstream_code", ref=f"{BASE_CFG}:301-308"),
        Fact("The visualization camera is 512 by 512 and returns rgb data",
             source="upstream_code", ref=f"{BASE_CFG}:309-315"),
        Fact("The camera_obs group is the rgb measurement of the rgbd_camera and viz_camera_obs is the rgb "
             "measurement of the viz_rgb_camera", source="upstream_code", ref=f"{VISION_CFG}:100-115"),
        Fact("The vision configuration declares the observation groups policy, proprio, critic, camera_obs, "
             "viz_camera_obs and depth_obs", source="upstream_code", ref=f"{VISION_CFG}:133-139"),
        Fact("The policy observation group includes a last-action term",
             source="upstream_code", ref=f"{BASE_CFG}:144"),
        Fact("Termination is time_out, an illegal contact of the base above threshold 1.0 or a bad orientation "
             "with limit_angle 0.8", source="upstream_code", ref=f"{BASE_CFG}:230-245"),
        Fact("The only reward term is a termination penalty of -200.0 on is_terminated",
             source="upstream_code", ref=f"{BASE_CFG}:116-118"),
        Fact("The vision scene uses one environment with 2.5 spacing",
             source="upstream_code", ref=f"{VISION_CFG}:168"),
        Fact("The evaluation creates the environment with gym.make(task, cfg=env_cfg, render_mode=None), so the "
             "registered task needs an environment configuration object",
             source="upstream_code", ref=f"{EVAL}:271"),
        Fact("The evaluation reads camera_obs and viz_camera_obs and takes channel indices 0:3 of each frame",
             source="upstream_code", ref=f"{EVAL}:304-315"),
        Fact("The repository licence is MIT", source="vendor_doc", ref="LICENSE:1"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime's latch refuses every step, reset "
                  "and seed until mhs.safety.reset, and the last observation, tick and episode stay readable")
    #: The contract of the model as deployed on the fake backend (spec 05-fidelity).  The upstream task is an Isaac
    #: Sim rigid-body simulation, but this package ships no sim backend and the fake models no dynamics, so the level
    #: is F0 and the gaps carry every omission.  The 20 ms control step is sim.dt 0.005 s times decimation 4
    #: (base cfg:367-371).
    fidelity = {
        "engine": "mhs-fake:go2_matterport_vision (Isaac Lab 1.1.0 / Isaac Sim 4.1.0 target)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) and cap.world.seed.v1 seed the fake's own random.Random, and its step is "
                     "deterministic, so one seed repeats a fake trajectory.  The upstream reset is Isaac Sim state "
                     "(episode start position and rotation, Matterport scene, robot pose), was not run and is not "
                     "claimed to be reproducible here.",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an interface stand-in with no rigid-body dynamics, contacts, friction, actuator, sensor or "
            "noise model, no robot pose, no Matterport scene and no lidar or height scan; Isaac Sim 4.1.0 and Isaac "
            "Lab 1.1.0 (README.md:55-62) are not installed and no simulator run is claimed",
            "the real camera image is 512 x 512 (go2_matterport_base_cfg.py:301-307 and :309-315) with rgb and "
            "distance data; the fake returns an 8 x 8 x 3 placeholder image (192 values) and does not model depth, "
            "the 32-channel lidar (go2_matterport_vision_cfg.py:151-153) or the critic height scan",
            "the upstream observation is a dict of six groups (go2_matterport_vision_cfg.py:133-139); the fake "
            "represents policy as the 12 last-action values only, proprio as 6 placeholder base angular-velocity "
            "and rpy values only, and camera_obs as the small placeholder image; critic, viz_camera_obs and "
            "depth_obs are not represented, and velocity_commands, joint positions and joint velocities are absent",
            "the real action space is built by the external ManagerBasedRLEnv from JointPositionActionCfg "
            "(go2_matterport_base_cfg.py:125); the fake exposes an unbounded 12-value Box, its 12 is a placeholder "
            "for the joint count of the USD asset (go2_matterport_base_cfg.py:70), the upstream bounds were not "
            "inspected and nothing is clamped",
            "the fake returns reward 0.0 and never terminates or truncates; the upstream reward is a -200.0 "
            "termination penalty (go2_matterport_base_cfg.py:116-118), the termination terms are time_out, base "
            "contact and bad orientation (go2_matterport_base_cfg.py:230-245), and the 200000.0 s episode length "
            "(go2_matterport_base_cfg.py:369) is not modelled",
            "reset returns seeded placeholder values and ignores options; the upstream reset builds an Isaac Sim "
            "episode from the R2R data and Matterport assets (README.md:82), which are not present",
            "no snapshot or restore: the environment exposes no get_state/set_state and the fake offers none",
            "the fake was never compared with an Isaac Sim run, and no hardware or real-simulator evidence exists",
        ],
    }
