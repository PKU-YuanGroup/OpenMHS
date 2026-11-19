"""OpenMHS driver for gh.renforce-dynamics/trackerlab: the G1 23-DoF tracking environment (Gymnasium family).

The card's entry symbol is ``trackerLab.tracker_env:ManagerBasedTrackerEnv`` (manager_based_tracker_env.py:9), a
concrete Isaac Lab ``ManagerBasedRLEnv`` subclass that adds the motion manager to ``step`` and ``reset``
(manager_based_tracker_env.py:35-49).  This package serves the registered environment
``TrackerLab-Tracking-Unitree-G1-23D-Walk`` (g1/__init__.py:3-12), whose config ``G1TrackingWalk`` is a G1 23-DoF
joint-position tracking task (g1_23d_tracking_env_cfg.py:193-200).

The Gymnasium family uses ``env_id`` to name the environment and the bridge derives the whole
``cap.world.*`` contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the
action derived from the space (a Box -> ``{values: [...]}``), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated R0: no hardware backend; raw action values require an
operator envelope.  The example envelope is illustrative fake data, not a sourced robot bound.
The e-stop is the runtime's software latch; there is no native stop on the environment.

The upstream environment needs Isaac Lab, Isaac Sim, torch and a GPU (README.md:58-59, docs/tutorial_en.md:17), so
the gate cannot open it and package code never imports the clone.  The ``fake`` backend is this package's own pure
Python analytic stand-in (fake.py), never compared with an Isaac Lab run.  Only that backend is declared.  The
inherited ``gymnasium.make(env_id)`` fallback is not a supported live adapter: it lacks application bootstrap,
task registration, a cfg and torch/batch adaptation.  No external Isaac Sim pause or stop is provided.

The raw action space is built by Isaac Lab's action manager outside the clone and was not observed here, so the fake
uses an unbounded 23-element Box and declares action.values operator_required.  The configured joint-position clip
(-6.0 to 6.0) is not evidence of a raw input bound.  The fake uses a zero-offset target approximation with scale and
clip, and applies the configured angular-velocity and joint-velocity observation scales; it claims no physics.
Every Fact cites a line of the clone at commit 1e5ccc062b445712a0aa7308cfb99edd7296cc88.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Action, Fact, GymnasiumDriver, Limit

from .adapter import TrackerContractBridge

REGISTER = "source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/__init__.py"
ENV = "source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/manager_based_tracker_env.py"
BASE_CFG = ("source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/"
            "manager_based_tracker_env_cfg/tracking_env_base.py")
CONFIGS = ("source/trackerLab/trackerLab/tracker_env/manager_based_tracker_env/"
           "manager_based_tracker_env_cfg/configs.py")
G1_CFG = ("source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/"
          "g1_23d_tracking_env_cfg.py")
HUMANOID_CFG = "source/trackerTask/trackerTask/trackerLab/tracking/humanoid/tracking_humanoid_env_cfg.py"
ALIGN = ("source/trackerTask/trackerTask/trackerLab/tracking/humanoid/robots/g1/"
         "motion_align_cfg.py")


class TrackerLabG1(GymnasiumDriver):
    device_id = "trackerlab-g1-23d-walk"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "TrackerLab-Tracking-Unitree-G1-23D-Walk"
    native = "trackerLab.tracker_env:ManagerBasedTrackerEnv"
    backends = {"fake": ".fake:FakeTrackerEnv"}
    display_name = "TrackerLab Unitree G1 23-DoF motion tracking (Isaac Lab simulation)"
    vendor, model = "Renforce Dynamics", "TrackerLab / Unitree G1 23-DoF"
    tags = ["trackerlab", "isaac-lab", "humanoid", "unitree-g1", "motion-tracking", "reinforcement-learning",
            "simulation", "gymnasium"]
    actions = {
        "cap.world.step.v1": Action(name="step", limits={
            "action.values": Limit.operator_required(
                "The raw action space has no verified finite bound in this clone; bound all 23 raw values "
                "for the deployment. The configured processed-target clip is not an input envelope; "
                "site-limits.example.json contains illustrative fake data only")
        }),
    }

    def make_bridge(self, native):
        return TrackerContractBridge(env=native, env_id=self.env_id, device_id=self.device_id,
                                     seed=self.seed, autoreset=self.autoreset, max_ticks=self.max_ticks,
                                     env_origin="the fake backend .fake:FakeTrackerEnv")

    facts = [
        Fact("TrackerLab-Tracking-Unitree-G1-23D-Walk is registered with entry point "
             "trackerLab.tracker_env:ManagerBasedTrackerEnv and the training config "
             "g1_23d_tracking_env_cfg:G1TrackingWalk", source="upstream_code", ref=f"{REGISTER}:3-12"),
        Fact("ManagerBasedTrackerEnv extends ManagerBasedRLEnv and its constructor takes cfg, an optional "
             "render_mode and keyword arguments", source="upstream_code", ref=f"{ENV}:3-12"),
        Fact("step(action) calls the parent step, updates the motion manager and returns the observation, reward, "
             "terminated, timeout and extras buffers", source="upstream_code", ref=f"{ENV}:35-39"),
        Fact("reset(seed, env_ids, options) forwards to the parent reset and returns the observation buffer and "
             "extras", source="upstream_code", ref=f"{ENV}:41-49"),
        Fact("The action configuration is a joint-position action over all robot joints with scale 0.5, the default "
             "joint offset and a configured clip of -6.0 to 6.0", source="upstream_code", ref=f"{CONFIGS}:154-159"),
        Fact("The G1 23-DoF tracking task selects the 23-joint motion alignment, sets the action scale to 0.5, "
             "enables a 5-step policy observation history and sets the episode length to 20.0 s",
             source="upstream_code", ref=f"{G1_CFG}:166-186"),
        Fact("G1_23D_MOTION_ALIGN_CFG lists 23 gym joint names for the G1 23-DoF tracking task",
             source="upstream_code", ref=f"{ALIGN}:1-16"),
        Fact("The policy observation group is the dof-position command, root-velocity command, base linear "
             "velocity, base angular velocity, projected gravity, relative joint position, relative joint velocity "
             "and last action", source="upstream_code", ref=f"{CONFIGS}:171-188"),
        Fact("set_no_scanner removes the height scanner and the height_scan policy observation",
             source="upstream_code", ref=f"{BASE_CFG}:75-78"),
        Fact("The G1 23-DoF tracking task calls set_no_scanner", source="upstream_code", ref=f"{G1_CFG}:167"),
        Fact("The base configuration uses 4 physics steps of 0.005 s per environment step",
             source="upstream_code", ref=f"{BASE_CFG}:40-43"),
        Fact("The G1 23-DoF tracking task sets the episode length to 20.0 s and disables the base-contact "
             "termination", source="upstream_code", ref=f"{G1_CFG}:185-186"),
        Fact("The termination terms are a base height below 0.2 m and a bad orientation beyond 0.8 rad",
             source="upstream_code", ref=f"{HUMANOID_CFG}:20-21"),
        Fact("The reset events sample base pose x and y in -2.5 to 2.5, yaw in -3.14 to 3.14, base velocity x, y "
             "and z in -1.0 to 1.0, roll, pitch and yaw in -0.5 to 0.5 and the joint velocity scale in -1.0 to 1.0",
             source="upstream_code", ref=f"{G1_CFG}:126-149"),
        Fact("The environment config sets sim.physx.gpu_max_rigid_patch_count to 10 * 2**15",
             source="upstream_code", ref=f"{BASE_CFG}:46"),
        Fact("TrackerLab extends IsaacLab and requires IsaacLab and its dependencies to be installed",
             source="vendor_doc", ref="README.md:58-59"),
        Fact("The setup guide includes Isaac Sim installation and Python environment setup",
             source="vendor_doc", ref="docs/tutorial_en.md:17"),
    ]
    safe_state = ("the declared analytic fake stops advancing and retains its cached observation, target, tick "
                  "and episode; no step or world reset is accepted while latched. mhs.safety.reset releases "
                  "only the latch and advances no ticks. No pause or stop of an external Isaac Sim application "
                  "is provided; a live adapter is outside this package")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  It describes the analytic fake,
    #: not Isaac Sim's PhysX: level F0 says no dynamics are claimed and the gaps name what is missing.
    fidelity = {
        "engine": "analytic:trackerlab-g1-23d-walk-stand-in (Isaac Lab target)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 reseeds Python's random.Random, and the analytic update is "
                     "deterministic, so one seed repeats a trajectory; the upstream Isaac Lab reset uses its own "
                     "random generators and domain randomisation, and the two were not compared",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic F0 stand-in: no Isaac Sim or PhysX, no rigid-body dynamics, contacts, friction, actuator, "
            "sensor, terrain, noise or rendering model; the fake sets relative joint positions from an approximate "
            "zero-offset target, reports reward 0 and never terminates on height, orientation or contact. The "
            "upstream config enables default joint offsets; its processing implementation is outside the clone",
            "the raw action space is built by Isaac Lab's action manager outside the clone and was not observed here; "
            "the fake exposes an unbounded Box of 23 action values, so action.values is operator_required at the "
            "endpoint. site-limits.example.json supplies illustrative fake bounds only; the configured clip of "
            "-6.0 to 6.0 does not establish a raw action-space bound",
            "the fake returns the policy observation group as one 104-value vector (23 dof-position command, 3 "
            "root-velocity command, 3 base linear velocity, 3 base angular velocity, 3 projected gravity, 23 relative "
            "joint positions, 23 relative joint velocities and 23 last actions); the upstream group is assembled by "
            "Isaac Lab and the task enables a 5-step history (g1_23d_tracking_env_cfg.py:183), so the real flattened "
            "observation is larger and its exact shape was not observed",
            "the fake applies the task's angular-velocity observation scale 0.25 and joint-velocity observation "
            "scale 0.05 in its analytic observations (g1_23d_tracking_env_cfg.py:174-179); initial joint "
            "velocities remain independent placeholder samples, not the upstream reset_joints_by_scale result",
            "the upstream environment is vectorised over 4096 environments (g1_23d_tracking_env_cfg.py:163) and "
            "returns torch tensors; the MHS Gymnasium bridge drives one environment and the fake uses Python lists",
            "the fake does not model the termination terms (base height below 0.2 m and bad orientation beyond "
            "0.8 rad, tracking_humanoid_env_cfg.py:20-21) or any reward term; its own episode budget is 1000 "
            "control steps and it does not model Isaac Lab's in-step episode resets",
            "the upstream stack (Isaac Lab, Isaac Sim, PhysX, torch and a GPU) was not installed or run where the "
            "gate runs; only fake is declared. The generic gymnasium.make fallback is not a supported live "
            "adapter: the upstream constructor requires cfg (manager_based_tracker_env.py:11), and the scripts "
            "bootstrap AppLauncher, import task registrations and parse cfg before gym.make. The native returns "
            "vectorised torch buffers; no torch/batch conversion or application lifecycle adapter is provided",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep; 20.0 ms is one environment control step "
            "(4 physics steps of 0.005 s, tracking_env_base.py:40-43), not an integration performed by the fake",
            "no rendering, video, checkpoint or exact snapshot/restore is offered: the environment exposes no "
            "get_state/set_state and the fake has none",
        ],
    }
