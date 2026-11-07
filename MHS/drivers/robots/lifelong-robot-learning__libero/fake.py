"""Fake backend of the LIBERO driver: a pure Python stand-in for ``libero.libero.envs.env_wrapper:OffScreenRenderEnv``.

The acceptance gate never imports the read-only clone and robosuite, mujoco, bddl and torch are not installed where
it runs, so this module cannot be the upstream environment.  It implements the public members that
``OffScreenRenderEnv`` inherits from ``ControlEnv`` (``step``, ``reset``, ``seed``, ``set_init_state``, ``get_sim_state``,
``set_state``, ``reset_from_xml_string``, ``regenerate_obs_from_state``, ``check_success`` and ``close``; gate G7 reads
those names from ``libero/libero/envs/env_wrapper.py`` at the pinned commit), and returns the same four-tuple from
``step`` and the same dictionary-shaped observation as the robosuite environment (``obs, reward, done, info``;
README.md:128-130).

What this is not: MuJoCo, robosuite or LIBERO.  The gripper and end-effector motion below is a placeholder first-order
update, not contact physics; the reward predicate, the object placements, the task success test, the camera images and
the full MuJoCo state are not modelled.  Every numeric choice in this file is test data and is marked ``# placeholder``;
none of it is a Fact, a Limit or a reference.  The differences are listed in the driver's fidelity ``gaps`` and in
RESULT.json, and no trajectory here was compared with the upstream simulator.
"""

import random

#: placeholder: the seven-element action the clone's README passes to env.step
_ACTION_DIM = 7
#: placeholder: metres of end-effector travel (or radians of orientation change) per unit of action
_STEP_GAIN = 0.01
#: placeholder: the fake's start end-effector position in metres
_START_POS = (0.0, 0.0, 1.0)
#: placeholder: the fake's start end-effector orientation as (x, y, z, w)
_START_QUAT = (0.0, 0.0, 0.0, 1.0)
#: placeholder: the fake's start gripper finger positions in metres
_START_GRIPPER = (0.04, 0.04)
#: placeholder: the fake's random placement jitter in metres
_PLACEMENT_JITTER = 0.01


class FakeOffScreenRenderEnv:
    """The public surface of ``ControlEnv``/``OffScreenRenderEnv`` without robosuite or MuJoCo.

    ``step`` returns ``(observation, reward, done, info)`` with ``done`` always false and the reward always 0.0, so
    the fake never reports the sparse task reward of ``bddl_base_domain.py:165-189``.  That is disclosed in the
    fidelity ``gaps``; it is not a claim about the upstream environment.
    """

    def __init__(self, bddl_file_name=None, **options):
        #: placeholder: the constructor keeps the clone's keyword name but the BDDL file is not parsed
        self.bddl_file_name = bddl_file_name
        self.options = dict(options)
        #: placeholder: seed used by the fake's placement draw
        self._seed = 0
        self._rng = random.Random(self._seed)
        #: placeholder: the fake's compact state (3 + 4 + 2 numbers), not the MuJoCo qpos layout
        self._eef_pos = list(_START_POS)
        self._eef_quat = list(_START_QUAT)
        self._gripper = list(_START_GRIPPER)
        #: placeholder: number of fake transitions since the last reset
        self._steps = 0
        self._xml = None
        self._closed = False

    # -- observation ---------------------------------------------------------
    def _observation(self):
        """The low-dimensional part of the robosuite observation the driver keeps (see bddl_base_domain.py:828)."""
        return {
            "robot0_eef_pos": list(self._eef_pos),
            "robot0_eef_quat": list(self._eef_quat),
            "robot0_gripper_qpos": list(self._gripper),
        }

    # -- ControlEnv members --------------------------------------------------
    def step(self, action):
        """Apply one placeholder action and return the clone's four-tuple."""
        values = [float(value) for value in action]
        if len(values) != _ACTION_DIM:
            raise AssertionError(f"the fake takes {_ACTION_DIM} action values, got {len(values)}")
        for index in range(3):
            self._eef_pos[index] += _STEP_GAIN * values[index]              # placeholder
        for index in range(3):
            self._eef_quat[index] += _STEP_GAIN * values[3 + index]         # placeholder
        self._gripper[0] += _STEP_GAIN * values[6]                          # placeholder
        self._gripper[1] += _STEP_GAIN * values[6]                          # placeholder
        self._steps += 1
        return self._observation(), 0.0, False, {}

    def reset(self):
        """Restore the fake's start state, drawn deterministically from its seed."""
        self._rng = random.Random(self._seed)
        jitter = [self._rng.uniform(-_PLACEMENT_JITTER, _PLACEMENT_JITTER) for _ in range(3)]  # placeholder
        self._eef_pos = [_START_POS[index] + jitter[index] for index in range(3)]                # placeholder
        self._eef_quat = list(_START_QUAT)                                                       # placeholder
        self._gripper = list(_START_GRIPPER)                                                     # placeholder
        self._steps = 0
        return self._observation()

    def seed(self, seed):
        """Set the seed of the fake's next reset draw (the clone delegates to ``np.random.seed``)."""
        self._seed = int(seed)
        self._rng = random.Random(self._seed)

    def get_sim_state(self):
        """The fake's compact state as a flat list (the clone flattens the MuJoCo state)."""
        return list(self._eef_pos) + list(self._eef_quat) + list(self._gripper)

    def set_state(self, mujoco_state):
        """Load the fake's compact state; the real method loads a flattened MuJoCo state."""
        values = [float(value) for value in mujoco_state]
        expected = len(_START_POS) + len(_START_QUAT) + len(_START_GRIPPER)
        if len(values) != expected:
            raise AssertionError(f"the fake takes {expected} state values, got {len(values)}")
        self._eef_pos = values[0:3]
        self._eef_quat = values[3:7]
        self._gripper = values[7:9]

    def set_init_state(self, init_state):
        """Set the state and return the observation of the resulting state."""
        return self.regenerate_obs_from_state(init_state)

    def regenerate_obs_from_state(self, mujoco_state):
        """Set the state and return the fake's observation (the clone forward-steps the MuJoCo model)."""
        self.set_state(mujoco_state)
        return self._observation()

    def reset_from_xml_string(self, xml_string):
        """Remember the XML string; the fake parses no MJCF."""
        self._xml = xml_string

    def check_success(self):
        """The fake models no task predicate, so it never reports success."""
        return False

    def close(self):
        """Mark the fake closed; the clone closes its robosuite environment."""
        self._closed = True
