"""Analytic stand-in for the environment that ``robopianist.suite.load`` returns (gate and package tests only).

The upstream factory returns a dm_control composer ``Environment`` (a class of the external ``mujoco_utils``
library) wrapping the ``PianoWithShadowHands`` task.  This fake keeps the part of that object's dm_env interface the
SDK's dm_env adapter uses (``reset``, ``step``, ``action_spec``, ``observation_spec``, ``control_timestep``,
``close``) and nothing else: no MuJoCo physics, no piano, no hands, no MIDI and no sound.

The action spec copies the shape and per-element bounds of the default task configuration (two Shadow Hands with
the two default forearm degrees of freedom, then the sustain pedal); the sources of every number are the facts of
driver.py.  The numbers of the episode itself (its length, the reward, the observation values) are placeholders.
"""

from collections import namedtuple

#: The step types of dm_env (FIRST, MID, LAST), as the dm_env adapter reads them (exact integers).
FIRST, MID, LAST = 0, 1, 2
TimeStep = namedtuple("TimeStep", ["step_type", "reward", "discount", "observation"])

#: ctrlrange of the Shadow Hand position actuator classes (right_hand.xml and left_hand.xml of the menagerie
#: submodule, lines 16, 20, 27, 31, 35, 39, 43, 49, 53, 57 and 61).
_WRIST_Y = (-0.523599, 0.174533)
_WRIST_X = (-0.698132, 0.488692)
_THBASE = (-1.0472, 1.0472)
_THPROXIMAL = (0.0, 1.22173)
_THHUB = (-0.20944, 0.20944)
_THMIDDLE = (-0.698132, 0.698132)
_THDISTAL = (-0.261799, 1.5708)
_METACARPAL = (0.0, 0.785398)
_KNUCKLE = (-0.349066, 0.349066)
_PROXIMAL = (-0.261799, 1.5708)
_MIDDLE_DISTAL = (0.0, 3.1415)
#: the 20 actuators of one hand in the order of the XML's <actuator> block (right_hand.xml:323-344)
_HAND_ACTUATORS = (_WRIST_Y, _WRIST_X, _THBASE, _THPROXIMAL, _THHUB, _THMIDDLE, _THDISTAL,
                   _KNUCKLE, _PROXIMAL, _MIDDLE_DISTAL,            # first finger
                   _KNUCKLE, _PROXIMAL, _MIDDLE_DISTAL,            # middle finger
                   _KNUCKLE, _PROXIMAL, _MIDDLE_DISTAL,            # ring finger
                   _METACARPAL, _KNUCKLE, _PROXIMAL, _MIDDLE_DISTAL)  # little finger
#: Half the piano's width: the base geom's size[1] is BASE_WIDTH / 2 = PIANO_LENGTH / 2 with PIANO_LENGTH
#: = 52 * 0.0225 + 51 * 0.001 (piano_constants.py:22-28, 34-36, 47-48; piano_mjcf.py:104; piano.py:93-94).
_HALF_PIANO = (52 * 0.0225 + 51 * 0.001) / 2
#: forearm_tx spans the piano offset by the hand's y position (base.py:34, 36, 160-164, 188-194); forearm_ty is 0 to
#: 0.06 (shadow_hand.py:50-51); _add_dofs appends both after the XML actuators before they are collected
#: (shadow_hand.py:85, 138-141, 161, 303-309).  Rounded to 10 decimals: the sum has no exact binary value.
_RIGHT_FOREARM = ((round(-_HALF_PIANO - 0.15, 10), round(_HALF_PIANO - 0.15, 10)), (0.0, 0.06))
_LEFT_FOREARM = ((round(-_HALF_PIANO + 0.15, 10), round(_HALF_PIANO + 0.15, 10)), (0.0, 0.06))
#: the sustain pedal (piano_with_shadow_hands.py:230-236)
_SUSTAIN = ((0.0, 1.0),)
_BOUNDS = _HAND_ACTUATORS + _RIGHT_FOREARM + _HAND_ACTUATORS + _LEFT_FOREARM + _SUSTAIN

#: goal: (n_steps_lookahead + 1) x (88 keys + sustain) with the default lookahead of one step
#: (piano_with_shadow_hands.py:53, 380-383)
_GOAL_SIZE = 2 * 89
_EPISODE_STEPS = 8          # placeholder: the real episode lasts as many control steps as the MIDI has frames
_CONTROL_TIMESTEP = 0.05    # base.py:31


class Array:
    """A dm_env ``specs.Array`` stand-in: shape, dtype and name."""

    def __init__(self, shape, dtype, name):
        self.shape, self.dtype, self.name = tuple(shape), dtype, name


class BoundedArray(Array):
    """A dm_env ``specs.BoundedArray`` stand-in with per-element minimum and maximum."""

    def __init__(self, shape, dtype, minimum, maximum, name):
        super().__init__(shape, dtype, name)
        self.minimum, self.maximum = list(minimum), list(maximum)

    def validate(self, value):
        values = value.tolist() if hasattr(value, "tolist") else list(value)
        if len(values) != self.shape[0]:
            raise ValueError(f"{self.name}: expected {self.shape[0]} values, got {len(values)}")
        for index, item in enumerate(values):
            if not self.minimum[index] <= float(item) <= self.maximum[index]:
                raise ValueError(f"{self.name}[{index}] = {item} is outside "
                                 f"[{self.minimum[index]}, {self.maximum[index]}]")
        return value


class FakePianoEnvironment:
    """The dm_env interface of the composer environment the factory returns; analytic, no physics."""

    def __init__(self):
        self._action_spec = BoundedArray((len(_BOUNDS),), "float64", [low for low, _high in _BOUNDS],
                                         [high for _low, high in _BOUNDS], "action")
        self._t = 0
        self._started = False
        self._closed = False
        self._last_action = None

    # -- dm_env interface ---------------------------------------------------------
    def action_spec(self):
        return self._action_spec

    def observation_spec(self):
        return {"goal": Array((_GOAL_SIZE,), "float64", "goal")}

    def control_timestep(self):
        return _CONTROL_TIMESTEP

    def reset(self):
        if self._closed:
            raise RuntimeError("the environment is closed")
        self._t = 0
        self._started = True
        self._last_action = None
        return TimeStep(FIRST, None, None, self._observation())

    def step(self, action):
        if self._closed:
            raise RuntimeError("the environment is closed")
        if not self._started:
            raise RuntimeError("step before reset")
        self._action_spec.validate(action)
        self._last_action = [float(item) for item in (action.tolist() if hasattr(action, "tolist") else action)]
        self._t += 1
        if self._t >= _EPISODE_STEPS:
            self._started = False
            # The song's last frame ends the episode with discount 1.0 (piano_with_shadow_hands.py:193, 209-216).
            return TimeStep(LAST, 0.0, 1.0, self._observation())   # placeholder reward
        return TimeStep(MID, 0.0, 1.0, self._observation())          # placeholder reward

    def close(self):
        self._closed = True

    # -- helpers --------------------------------------------------------------------
    def _observation(self):
        goal = [0.0] * _GOAL_SIZE   # placeholder: no MIDI is loaded
        if self._t < _EPISODE_STEPS:
            goal[self._t % 88] = 1.0   # placeholder: one key per frame
        return {"goal": goal}
