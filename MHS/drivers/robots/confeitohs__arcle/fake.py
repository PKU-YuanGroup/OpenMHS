"""Fake backend of the ARCLE driver: a pure Python stand-in for ``arcle.envs.arcenv:RawARCEnv``.

Why a fake: the acceptance gate runs without the upstream package (it needs gymnasium, numpy and pygame,
``pyproject.toml``), and package code never imports the clone.  This module re-implements the public behaviour of
``RawARCEnv`` that the Gymnasium bridge uses -- ``reset``, ``step`` and the two spaces -- with the same action and
observation shapes.  Every structural number below is either the upstream constructor default or synthetic test
data; the synthetic grids are marked ``# placeholder`` and are never used as evidence in a Fact or a Limit.

What this is not: the upstream environment.  The upstream ``reset`` asks ``ARCLoader`` for a problem and its
``np_random`` picks the sub-problem; this fake uses a small synthetic table selected by ``random.Random``.  There is
no numpy array, no pygame window, no ANSI renderer and no ``PassiveEnvChecker`` or ``OrderEnforcing`` wrapper.
"""

import random

# placeholder: the fake models the upstream constructor defaults of arcenv.py:17 -- a 30x30 grid, 10 colors,
# max_trial -1 and the 12 operations built by RawARCEnv.create_operations (arcenv.py:26-41).  These are test-data
# configuration of the fake, not device bounds.
HEIGHT = 30
WIDTH = 30
COLORS = 10
MAX_TRIAL = -1
OPERATIONS = 12

# placeholder: the synthetic 3x3 example/test problems the fake draws from.  They are test data: no value below
# is cited by a Fact, a Limit or the reference file.
EXAMPLE_PROBLEMS = [
    ([[1, 2, 3], [4, 5, 6], [7, 8, 9]], [[9, 8, 7], [6, 5, 4], [3, 2, 1]]),
    ([[0, 1, 0], [1, 2, 1], [0, 1, 0]], [[2, 2, 2], [1, 1, 1], [0, 0, 0]]),
]
TEST_PROBLEMS = [
    ([[1, 1, 1], [2, 2, 2], [3, 3, 3]], [[3, 3, 3], [2, 2, 2], [1, 1, 1]]),
    ([[0, 2, 0], [2, 0, 2], [0, 2, 0]], [[2, 0, 2], [0, 2, 0], [2, 0, 2]]),
]


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape, dtype="int8"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"


class MultiBinary:
    """Duck-typed ``gymnasium.spaces.MultiBinary``: ``n`` binary values."""

    def __init__(self, n):
        self.n = int(n)
        self.shape = (self.n,)
        self.dtype = "int8"


def _copy_grid(grid):
    return [[int(value) for value in row] for row in grid]


def _pad(grid, height, width):
    """Zero-pad a grid to ``height x width`` (base.py:161-165 pads the input and the grid the same way)."""
    out = [[0] * width for _ in range(height)]
    for row_index, row in enumerate(grid):
        if row_index >= height:
            break
        for column_index, value in enumerate(row):
            if column_index >= width:
                break
            out[row_index][column_index] = int(value)
    return out


def _flat_selection(selection):
    """The bridge sends a Box action as a flat list; a nested list is accepted too."""
    if selection and isinstance(selection[0], (list, tuple)):
        return [int(value) for row in selection for value in row]
    return [int(value) for value in selection]


def _paint(grid, selection, color, height, width):
    """``gen_color`` (arcle/actions/color.py:62-77): paint every selected cell with ``color``."""
    index = 0
    for row in range(height):
        for column in range(width):
            if index < len(selection) and selection[index]:
                grid[row][column] = int(color)
            index += 1


def _resize_to_answer(state, answer, height, width):
    """``resize_to_answer`` (arcenv.py:31-35): set the visible size to the answer and zero everything outside."""
    answer_height, answer_width = len(answer), len(answer[0])
    state["grid_dim"] = [answer_height, answer_width]
    for row in range(height):
        for column in range(width):
            if row >= answer_height or column >= answer_width:
                state["grid"][row][column] = 0


def _matches_answer(state, answer):
    """The comparison ``RawARCEnv.reward`` makes (arcenv.py:51-58)."""
    height, width = state["grid_dim"]
    if (height, width) != (len(answer), len(answer[0])):
        return False
    for row in range(height):
        for column in range(width):
            if state["grid"][row][column] != answer[row][column]:
                return False
    return True


class FakeRawARCEnv:
    """``RawARCEnv`` without numpy, gymnasium or a data loader; only the public members the upstream class has."""

    def __init__(self, data_loader=None, max_grid_size=(HEIGHT, WIDTH), colors=COLORS, max_trial=MAX_TRIAL,
                 render_mode=None, render_size=None):
        if render_mode is not None:
            raise ValueError("the fake RawARCEnv cannot render; use render_mode=None")
        del data_loader, render_size
        self.H, self.W = int(max_grid_size[0]), int(max_grid_size[1])
        self.colors = int(colors)
        self.max_trial = int(max_trial)
        self.description = None
        self.truncated = False
        self.submit_count = 0
        self.last_action = None
        self.last_action_op = None
        self.last_reward = 0
        self.action_steps = 0
        self.current_state = None
        self.info = {}
        self._rng = random.Random()
        cells = self.H * self.W
        # The clone's selection space is spaces.Box(0, 1, (H, W)) (base.py:134-138): one uniform 0/1 bound for
        # every cell.  Storing one pair (not one pair per cell) keeps the bridge-derived limit scalar; the runtime
        # applies a scalar bound to every element of the array.
        self.action_space = Dict({
            "selection": Box([0], [1], (self.H, self.W)),
            "operation": Discrete(OPERATIONS),
        })
        self.observation_space = Dict({
            "trials_remain": Box([self.max_trial], [self.max_trial], (1,)),
            "terminated": MultiBinary(1),
            "input": Box([0] * cells, [self.colors] * cells, (self.H, self.W)),
            "input_dim": Box([1, 1], [self.H, self.W], (2,)),
            "grid": Box([0] * cells, [self.colors] * cells, (self.H, self.W)),
            "grid_dim": Box([1, 1], [self.H, self.W], (2,)),
        })

    def reset(self, seed=None, options=None):
        """Draw a synthetic problem and build the initial state (base.py:69-118)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self.truncated = False
        self.submit_count = 0
        self.last_action = None
        self.last_action_op = None
        self.last_reward = 0
        self.action_steps = 0
        self.prob_index = None
        self.subprob_index = None
        self.adaptation = True
        self.reset_on_submit = False
        self.options = options
        if options is not None:
            self.prob_index = options.get("prob_index")
            self.subprob_index = options.get("subprob_index")
            adaptation = options.get("adaptation")
            self.adaptation = True if adaptation is None else bool(adaptation)
            reset_on_submit = options.get("reset_on_submit")
            self.reset_on_submit = False if reset_on_submit is None else reset_on_submit
        if self.prob_index is not None and int(self.prob_index) != 0:
            raise IndexError(f"the fake has one problem group, not {self.prob_index!r}")
        table = EXAMPLE_PROBLEMS if self.adaptation else TEST_PROBLEMS
        if self.subprob_index is None:
            self.subprob_index = self._rng.randrange(len(table))
        input_grid, answer_grid = table[int(self.subprob_index)]
        self.input_ = _copy_grid(input_grid)
        self.answer = _copy_grid(answer_grid)
        self.description = f"synthetic fake problem {int(self.subprob_index)}"
        self.init_state(self.input_)
        self.info = self.init_info()
        return self.current_state, self.info

    def init_state(self, initial_grid, options=None):
        """The state document of ``AbstractARCEnv.init_state`` (base.py:155-166)."""
        del options
        input_height, input_width = len(self.input_), len(self.input_[0])
        grid_height, grid_width = len(initial_grid), len(initial_grid[0])
        self.current_state = {
            "trials_remain": [self.max_trial],
            "terminated": [0],
            "input": _pad(self.input_, self.H, self.W),
            "input_dim": [input_height, input_width],
            "grid": _pad(initial_grid, self.H, self.W),
            "grid_dim": [grid_height, grid_width],
        }

    def init_info(self):
        """The info document of ``AbstractARCEnv.init_info`` plus RawARCEnv's steps (base.py:145-153; arcenv.py:46-49)."""
        input_height, input_width = len(self.input_), len(self.input_[0])
        answer_height, answer_width = len(self.answer), len(self.answer[0])
        return {
            "input": _pad(self.input_, self.H, self.W),
            "input_dim": [input_height, input_width],
            "answer": _pad(self.answer, self.H, self.W),
            "answer_dim": [answer_height, answer_width],
            "steps": 0,
        }

    def reward(self, state):
        """1 only when the last operation is submit and the visible grid equals the answer (arcenv.py:51-58)."""
        if self.last_action_op != OPERATIONS - 1:
            return 0
        return 1 if _matches_answer(state, self.answer) else 0

    def step(self, action):
        """Apply one operation and return the five-tuple of ``RawARCEnv.step`` (arcenv.py:60-76)."""
        operation = int(action["operation"])
        self.last_action_op = operation
        self.last_action = action
        state = self.current_state
        if 0 <= operation <= 9:
            _paint(state["grid"], _flat_selection(action["selection"]), operation, self.H, self.W)
        elif operation == 10:
            _resize_to_answer(state, self.answer, self.H, self.W)
        elif operation == OPERATIONS - 1:
            if state["trials_remain"][0] != 0:
                state["trials_remain"][0] -= 1
                self.submit_count += 1
                if _matches_answer(state, self.answer):
                    state["terminated"][0] = 1
                if self.reset_on_submit:
                    self.init_state(self.input_)
            if state["trials_remain"][0] == 0:
                state["terminated"][0] = 1
        else:
            raise IndexError(f"operation {operation} is outside the fake's {OPERATIONS} operations")
        reward = self.reward(state)
        self.last_reward = reward
        self.action_steps += 1
        self.info["steps"] = self.action_steps
        return self.current_state, reward, bool(state["terminated"][0]), self.truncated, self.info
