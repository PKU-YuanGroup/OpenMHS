"""OpenMHS driver for gh.google-deepmind/mujoco_mpc: the Free-Floating Fingers MJCF task (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model (``models[0]``,
``mjpc/tasks/fingers/task.xml``) and the bridge derives the whole contract from the model it loads.  The step action
is ``{ticks, action: {ctrl: [...]}}``: the bridge checks each control against the model's ``actuator_ctrlrange``
(six ``intvelocity`` actuators, ``-.99`` to ``.99``) before it writes ``data.ctrl`` and calls ``mj_step`` ``ticks``
times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state
is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The upstream repository is MuJoCo MPC (MJPC), an interactive application and framework for real-time predictive
control with MuJoCo (README.md:14-16).  The Fingers task is one of its registered example tasks
(``mjpc/tasks/tasks.cc:54``); its C++ task class loads this MJCF (``fingers.cc:25-28``) and computes a residual from
the finger/object positions, the object/target site distances and the control values (``fingers.cc:34-54``).  This
package serves the MJCF world, not the C++ task, the planner or the GUI: the fidelity ``gaps`` say so.

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and never
imported).  MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py): it reads the same MJCF text for the actuator count, the control ranges and the qpos/qvel
dimensions, but its integration is a placeholder, not MuJoCo's physics.  A backend name that ``backends`` does not
list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

Every Fact cites a line of the clone at commit ff572a21e7c2bf9fda62e1862a758da7e9a8719b.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and no hardware run is claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

TASK = "mjpc/tasks/fingers/task.xml"
FINGERS = "mjpc/tasks/fingers/fingers.cc"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/google-deepmind/mujoco_mpc/" + TASK


class Fingers(MujocoDriver):
    device_id = "mujoco-mpc-fingers"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "MuJoCo MPC Free-Floating Fingers (simulation)"
    vendor, model = "Google DeepMind", "Free-Floating Fingers"
    tags = ["mujoco", "mujoco-mpc", "simulation", "manipulation", "fingers", "world-sim"]
    facts = [
        Fact("MJPC is an interactive application and software framework for real-time predictive control with "
             "MuJoCo, developed by Google DeepMind", source="vendor_doc", ref="README.md:14-16"),
        Fact("MJPC supports multiple shooting-based planners: iLQG and Gradient Descent are derivative-based and "
             "Predictive Sampling is derivative-free", source="vendor_doc", ref="README.md:18-21"),
        Fact("An MJPC task needs an MJCF file that describes the simulated model and the task parameters and a C++ "
             "file that implements the residual", source="vendor_doc", ref="docs/OVERVIEW.md:108-111"),
        Fact("The Fingers task loads fingers/task.xml from XmlPath and is named FreeFingers", source="upstream_code",
             ref=f"{FINGERS}:25-28"),
        Fact("The Fingers task is registered in the MJPC task list", source="upstream_code",
             ref="mjpc/tasks/tasks.cc:54"),
        Fact("The task XML's root model is named 'Free-Floating Fingers'", source="upstream_code", ref=f"{TASK}:1"),
        Fact("The task XML includes ../common.xml, the shared visual assets and materials", source="upstream_code",
             ref=f"{TASK}:2"),
        Fact("The model integrates with timestep 0.001 s, an elliptic friction cone, five noslip iterations and the "
             "implicit integrator", source="upstream_code", ref=f"{TASK}:4"),
        Fact("The object and target bodies each have a free joint and a box geom; the object's collision default "
             "class sets mass 0.2 and its visual class mass 0.001", source="upstream_code", ref=f"{TASK}:43-68"),
        Fact("The finger_a and finger_b bodies each have three slide joints along x, y and z", source="upstream_code",
             ref=f"{TASK}:73-84"),
        Fact("The six intvelocity actuators A_x, A_y, A_z, B_x, B_y and B_z each have ctrlrange -.99 to .99, "
             "ctrllimited true and kp 1000; the x and y actranges are -1 to 1 and the z actranges 0 to 1.4",
             source="upstream_code", ref=f"{TASK}:93-100"),
        Fact("The home keyframe holds 20 qpos values (two free joints of 7 and six slides) and 6 act values",
             source="upstream_code", ref=f"{TASK}:20-34"),
        Fact("The sensors are the user sensors Reach (dim 6), Bring (dim 3) and Control (dim 6), plus framepos "
             "sensors for both fingers, the object and the six sites", source="upstream_code", ref=f"{TASK}:101-114"),
        Fact("The Fingers residual subtracts each finger's position from the object's, writes the distance of three "
             "object sites to their target sites, and copies data->ctrl for each of model->nu actuators",
             source="upstream_code", ref=f"{FINGERS}:34-54"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:Free-Floating Fingers",
        "fidelity_level": "F1",
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF for the six "
            "actuator control ranges, the qpos/qvel dimensions and the 0.001 s step, but it integrates a placeholder "
            "first-order motion of each actuated slide joint toward its control target and resolves no contact, "
            "friction, inertia, equality, tendon, actuator or sensor dynamics",
            "the two free bodies (object and target) are not integrated and no mesh or texture is loaded by the "
            "stand-in; the floor, the box geoms and the site geometry are not resolved",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the MJPC task layer is not served: the C++ Fingers residual (fingers.cc:34-54), the custom task "
            "settings of task.xml:7-18, the planners and the GUI are outside this driver, which exposes the raw "
            "ctrl vector and the MuJoCo integration state",
            "the bridge's reset calls mj_resetData, so the model defaults are restored, not the home keyframe of "
            "task.xml:20-34",
            "the stand-in implements no mj_getState/mj_setState, so a snapshot uses the bridge's fallback "
            "time/qpos/qvel/act/ctrl copy rather than the full integration state; it was not compared with the "
            "engine",
            "no rendering, camera or image is produced, and no physical device is modelled or was validated",
        ],
    }
