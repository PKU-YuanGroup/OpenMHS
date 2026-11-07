"""OpenMHS driver for gh.ussoftware1/mujoco-planar-reach-rl-demo: the planar two-link reach MJCF as a simulated world.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's ``models[0]``,
``mujoco_planar_reach_rl/assets/planar_reach.xml``, and the bridge loads it with the MuJoCo engine and derives the whole
contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [2 numbers]}}``: ``ctrl`` is
``data.ctrl`` of the model's two motors, bounded per actuator by ``actuator_ctrlrange`` (-1 to 1, planar_reach.xml:8
and :48-49), and the bridge writes it before running ``mj_step`` for ``ticks``.  ``cap.world.reset.v1`` calls
``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``), with two hinge coordinates (``shoulder`` and ``elbow``).

The device is simulated (R0): there is no hardware backend and no physical robot is driven.  The MJCF is read from the
read-only clone at the pinned commit and is not copied into this package.  MuJoCo is not installed where the acceptance
gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py), which reads the model shape
from the same MJCF but integrates a placeholder motion instead of the engine's physics; the fidelity ``gaps`` below
state every difference.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module
and loads the same file; that path was not run here.

Every Fact cites a line of the clone at commit 863bd473bc478e93cb05bbef22fcbf5905fb977d.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical arm.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "mujoco_planar_reach_rl/assets/planar_reach.xml"
ENV = "mujoco_planar_reach_rl/env.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/ussoftware1/mujoco-planar-reach-rl-demo/" + MODEL


class PlanarReach(MujocoDriver):
    device_id = "planar-reach"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "MuJoCo planar reach (two-link arm)"
    vendor, model = "ussoftware1", "MuJoCo Planar Reach RL Demo"
    tags = ["mujoco", "planar-arm", "two-link", "robot-arm", "reinforcement-learning", "simulation"]
    facts = [
        Fact("The card's model is the MJCF 'planar_reach', whose root element is '<mujoco model=\"planar_reach\">'",
             source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model is compiled with angles in radians and autolimits enabled", source="upstream_code",
             ref=f"{MODEL}:2"),
        Fact("The model integrates with the RK4 integrator at a 0.002 s timestep under gravity 0 0 -9.81",
             source="upstream_code", ref=f"{MODEL}:3"),
        Fact("The default joint attributes are armature 0.01, damping 0.8 and limited true; the default motor is "
             "ctrl-limited with ctrlrange -1 to 1", source="upstream_code", ref=f"{MODEL}:5-9"),
        Fact("The shoulder joint turns about the +z axis with the range -3.1416 to 3.1416 rad", source="upstream_code",
             ref=f"{MODEL}:27"),
        Fact("The elbow joint turns about the +z axis with the range -3.1416 to 3.1416 rad", source="upstream_code",
             ref=f"{MODEL}:32"),
        Fact("The arm is two links of 0.25 m: the link bodies sit 0.25 m apart and each capsule spans -0.25 to "
             "0.25 m", source="upstream_code", ref=f"{MODEL}:30-36"),
        Fact("The end effector is the site ee_site at the tip of link2, 0.25 m from the elbow", source="upstream_code",
             ref=f"{MODEL}:37"),
        Fact("The target is the mocap body target_body, placed at 0.45 0.10 0.045; it is not a joint of the arm",
             source="upstream_code", ref=f"{MODEL}:42"),
        Fact("The actuator section declares two motors: shoulder_motor with gear 2.0 and elbow_motor with gear 1.5, "
             "both with ctrlrange -1 to 1", source="upstream_code", ref=f"{MODEL}:47-50"),
        Fact("The environment loads the MJCF with mujoco.MjModel.from_xml_path and creates its state with "
             "mujoco.MjData", source="upstream_code", ref=f"{ENV}:76-77"),
        Fact("The environment's observation is 12 numbers: cos and sin of both joint positions, both joint "
             "velocities, the end-effector xy, the target xy and the target delta", source="upstream_code",
             ref=f"{ENV}:49-51"),
        Fact("The environment's action is the two shoulder and elbow torque commands in [-1, 1]",
             source="upstream_code", ref=f"{ENV}:53-54"),
        Fact("The environment defaults to frame_skip 10, max_episode_steps 250 and a success_threshold of 0.035 m",
             source="upstream_code", ref=f"{ENV}:33-35"),
        Fact("The target is sampled at an angle uniform in -pi to pi and at a radius uniform in 0.18 to 0.48 m",
             source="upstream_code", ref=f"{ENV}:195-198"),
        Fact("A reset draws both joint positions uniformly from -0.35 to 0.35 rad and both joint velocities from a "
             "normal distribution with scale 0.02", source="upstream_code", ref=f"{ENV}:116-117"),
        Fact("Each control step applies the action to data.ctrl and advances frame_skip (10) MuJoCo steps",
             source="upstream_code", ref=f"{ENV}:132-135"),
        Fact("The episode succeeds when the end-effector distance to the target is at or below the success "
             "threshold and truncates at max_episode_steps", source="upstream_code", ref=f"{ENV}:144-146"),
        Fact("The package requires Python 3.10 or newer and depends on mujoco 3.2.0 or newer, gymnasium 1.0.0 or "
             "newer and numpy 1.26 or newer", source="upstream_code", ref="pyproject.toml:10-16"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the integration state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:planar_reach",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no random "
                     "element, so the same ctrl sequence and tick count repeat the trajectory.  The bridge takes no "
                     "seed input: a reset restores the model defaults and no seed selects a different start.  The "
                     "package's fake backend is deterministic too, but its placeholder motion is not the engine's "
                     "physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses planar_reach.xml for the "
            "2 ms step, the two hinge coordinates and the two motor ctrlranges and gears, then moves each joint "
            "toward gear * ctrl; it resolves no inertia, contact, friction, damping, armature or RK4 integration, "
            "so no trajectory here is a MuJoCo result",
            "the bridge's reset calls mj_resetData and starts from the model defaults (zero qpos and qvel), not "
            "from the upstream environment's reset: env.py:116-117 draws both joint positions from -0.35 to 0.35 rad "
            "and both velocities from a normal distribution with scale 0.02, and env.py:195-206 samples and writes "
            "a target that the bridge never moves",
            "the upstream environment's 12-number observation (env.py:49-51), its reward shaping "
            "(env.py:227-235) and its 0.035 m success threshold (env.py:35, :144) are not served: "
            "cap.world.step.v1 returns the bridge's {time, qpos, qvel} observation and the world state "
            "{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's 2 ms step only; "
            "the environment's render_fps 50 (env.py:57) is a rendering rate, not the integration rate",
            "no rendering, camera, viewer or sensor publication is served, only the integration state",
            "the model is a simulation asset for a two-link planar arm: no physical robot is modelled or controlled "
            "and nothing here was validated against hardware",
        ],
    }
