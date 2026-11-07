"""OpenMHS driver for gh.avisingh599/roboverse: the Widow250Grasp-v0 PyBullet simulation (a Gymnasium family driver).

The upstream repository is a legacy Gym 0.12.1 / PyBullet simulation of a WidowX 250 arm (README.md:2,
requirements.txt:1-2).  ``roboverse.make(id)`` is a thin wrapper over ``gym.make`` (roboverse/envs/registration.py:1035-1037)
and the main environment is ``roboverse.envs.widow250:Widow250Env`` (roboverse/envs/widow250.py:30).  The card's
``GymnasiumDriver`` expresses that interface: ``env_id`` names the registered environment and the bridge derives the
``cap.world.step.v1`` action contract from the environment's ``gym.spaces.Box`` action space and serves
``cap.world.reset.v1`` / ``cap.world.seed.v1``.  The bridge also accepts the legacy four-value ``step`` result and a
``reset()`` without ``seed`` (roboverse/envs/widow250.py:182-192 and :272-275).

The device is simulated and R0: there is no hardware backend and no physical effect.  The ``fake`` backend is this
package's own pure-Python stand-in (fake.py); package code never imports or runs the read-only upstream clone.
The gate runs the fake only.  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package with legacy gym and PyBullet
and was not run here.

``fidelity`` describes the model as deployed in the checked package, the kinematic fake: it is F0 (no rigid-body
dynamics or contacts), seeded, lockstep at the upstream 1/240 s physics step, with the omissions listed in ``gaps``.
Every constant and rule cites a line of the clone at the pinned commit a443f79af67529158ba409889fd7b8006b1d3f88.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

WIDOW250 = "roboverse/envs/widow250.py"


class RoboverseWidow250(GymnasiumDriver):
    device_id = "widow250"
    env_id = "Widow250Grasp-v0"
    native = "roboverse.envs.widow250:Widow250Env"
    backends = {"fake": ".fake:FakeWidow250Env"}
    action_space_ref = 'roboverse/envs/widow250.py:332-335'
    display_name = "Roboverse Widow250Grasp-v0 (PyBullet WidowX 250 simulation)"
    vendor, model = "avisingh599/roboverse", "WidowX 250 (Widow250Grasp-v0)"
    tags = ["roboverse", "widow250", "widowx-250", "pybullet", "gym", "reinforcement-learning", "simulation"]
    env_kwargs = {
        "reward_type": "grasping",
        "control_mode": "discrete_gripper",
        "target_object": "beer_bottle",
        "load_tray": True,
        "xyz_action_scale": 0.2,
    }
    facts = [
        Fact("roboverse is a set of environments that use PyBullet to simulate robotic manipulation tasks",
             source="vendor_doc", ref="README.md:2"),
        Fact("The documented use is env = roboverse.make('Widow250DoubleDrawerOpenNeutral-v0', gui=True), then "
             "env.reset() and env.step(env.action_space.sample())", source="vendor_doc", ref="README.md:7-11"),
        Fact("The requirements pin gym 0.12.1 (the legacy Gym API) and pybullet 2.7.9", source="upstream_code",
             ref="requirements.txt:1-2"),
        Fact("roboverse.make is gym.make and the environments are registered with gym.register", source="upstream_code",
             ref="roboverse/envs/registration.py:1024-1037"),
        Fact("Widow250Grasp-v0 is registered with entry_point roboverse.envs.widow250:Widow250Env and "
             "control_mode discrete_gripper", source="upstream_code", ref="roboverse/envs/registration.py:8-16"),
        Fact("The action vector is eight-dimensional: ACTION_DIM = 8", source="upstream_code", ref=f"{WIDOW250}:27"),
        Fact("The action space is a gym.spaces.Box with one bound per action dimension, built from act_bound 1 (so "
             "every entry is in -1..1)", source="upstream_code", ref=f"{WIDOW250}:331-335"),
        Fact("step reads action[:3] as an end-effector position action, action[3:6] as an orientation action, "
             "action[6] as the gripper action and action[7] as the neutral action", source="upstream_code",
             ref=f"{WIDOW250}:203-206"),
        Fact("xyz_action_scale defaults to 0.2 and abc_action_scale to 20.0", source="upstream_code",
             ref=f"{WIDOW250}:57-59"),
        Fact("The target end-effector position is the current position plus xyz_action_scale times the xyz action, "
             "and the target orientation adds abc_action_scale times the abc action", source="upstream_code",
             ref=f"{WIDOW250}:214-217"),
        Fact("ee_pos_low defaults to (0.4, -0.2, -0.34) and ee_pos_high to (0.8, 0.4, -0.1)", source="upstream_code",
             ref=f"{WIDOW250}:61-62"),
        Fact("The target end-effector position is clipped between ee_pos_low and ee_pos_high before the action is "
             "applied", source="upstream_code", ref=f"{WIDOW250}:244-245"),
        Fact("num_sim_steps defaults to 10, num_sim_steps_reset to 50 and num_sim_steps_discrete_action to 75",
             source="upstream_code", ref=f"{WIDOW250}:46-48"),
        Fact("The default grasp thresholds are object height -0.25 and object-gripper distance 0.1",
             source="upstream_code", ref=f"{WIDOW250}:50-52"),
        Fact("check_grasp succeeds only when the object height is above the height threshold and the distance from "
             "the end effector to the object is below the distance threshold", source="upstream_code",
             ref="roboverse/bullet/object_utils.py:46-56"),
        Fact("get_observation returns a dictionary with the keys object_position, object_orientation, state and "
             "image; state concatenates the end-effector position (3), quaternion (4), gripper joints (2) and the "
             "gripper-open flag (1)", source="upstream_code", ref=f"{WIDOW250}:277-297"),
        Fact("The image observation is the rendered image flattened and divided by 255 into float32 values",
             source="upstream_code", ref=f"{WIDOW250}:284-286"),
        Fact("observation_img_dim defaults to 48", source="upstream_code", ref=f"{WIDOW250}:35"),
        Fact("The observation_space declares an image whose length is observation_img_dim squared times 3 and a "
             "10-entry state bounded by +/-100", source="upstream_code", ref=f"{WIDOW250}:337-347"),
        Fact("reset() resets the simulation, loads the meshes, resets the robot joints and returns "
             "get_observation()", source="upstream_code", ref=f"{WIDOW250}:182-192"),
        Fact("step returns (observation, reward, done, info) and done is always False, so the environment never "
             "terminates on its own", source="upstream_code", ref=f"{WIDOW250}:272-275"),
        Fact("The reward for reward_type grasping is the target object's grasp-success flag as a float",
             source="upstream_code", ref=f"{WIDOW250}:299-304"),
        Fact("The physics step is 1/240 s with 150 solver iterations and gravity -10", source="upstream_code",
             ref="roboverse/bullet/core.py:30-35"),
        Fact("connect_headless calls p.connect(p.DIRECT) when gui is false", source="upstream_code",
             ref="roboverse/bullet/core.py:5-11"),
        Fact("Widow250Env connects to PyBullet in its constructor through bullet.connect_headless(self.gui)",
             source="upstream_code", ref=f"{WIDOW250}:102"),
        Fact("The WidowX 250 URDF wx250s.urdf is loaded at base position [0.6, 0, -0.4]", source="upstream_code",
             ref="roboverse/envs/objects.py:34-41"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed in the checked package (the kinematic fake).  The bridge derives
    #: engine, determinism kind and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:Widow250Grasp-v0 (roboverse)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws object positions with random.Random(seed) and applies every action "
                     "deterministically, so a seed and an action sequence repeat a trajectory; upstream reset() "
                     "takes no seed and draws object positions from numpy's global generator "
                     "(roboverse/bullet/object_utils.py:114-120), so the same seed does not reproduce an upstream "
                     "trajectory unless numpy is seeded globally as well",
        },
        "timestep_ms": 41.6667,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic point model: the end-effector position changes by xyz_action_scale times the "
            "action and is clipped to the upstream ee_pos bounds; there are no rigid-body dynamics, contacts, "
            "friction, gravity or inverse kinematics, and the abc action only accumulates a tracked orientation",
            "no image rendering: the real observation image is a 48x48x3 float32 vector of 6912 values "
            "(roboverse/envs/widow250.py:339-341); the fake returns a 12-value stand-in (test data)",
            "no PyBullet: the upstream environment connects to p.DIRECT (roboverse/bullet/core.py:5-11); the fake "
            "never imports or runs it and was not compared with it",
            "no wall-clock pacing: realtime_factor 0; one environment step advances 10 PyBullet steps of 1/240 s "
            "(41.6667 ms) by default, but a discrete gripper toggle advances 75 steps (312.5 ms) "
            "(roboverse/envs/widow250.py:46-48), so the declared fixed timestep covers the common 10-step case and "
            "the fake applies one action per tick without sub-stepping",
            "snapshot and restore are not offered: Widow250Env exposes no get_state or set_state",
            "the fake models only the target object and has no tray, table, link collision or camera; the upstream "
            "step is legacy Gym with done always False and no truncation, which the fake mirrors",
        ],
    }
