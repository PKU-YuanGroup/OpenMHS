"""Live backend factory: ``robopianist.suite.load``, imported and called only when the sim backend opens.

Nothing is imported at module import time (the gate never opens this backend), and this route has never been run.
Deployment requirements, none of which the package can establish or the gate checks:

* robopianist installed from the pinned clone as its README says (README.md:59-78: ``git submodule init && git
  submodule update``, ``bash scripts/install_deps.sh``, ``pip install -e ".[dev]"``), with dm_control,
  dm_env_wrappers, mujoco and mujoco_utils (setup.py:37-40);
* the soundfont ``TimGM6mb.sf2``, which install_deps.sh downloads (scripts/install_deps.sh:60-76): importing
  robopianist raises FileNotFoundError without it (robopianist/__init__.py:48-58), and the import reads
  ``~/.robopianistrc`` when it exists (robopianist/__init__.py:31-44);
* the Shadow Hand XML that install_deps.sh copies from the menagerie submodule after checking it out at
  1afc8be (scripts/install_deps.sh:78-88; robopianist/models/hands/shadow_hand_constants.py:18-19, 51-53).

Constructing the task prints to standard output when the MIDI file has no fingering
(robopianist/suite/tasks/piano_with_shadow_hands.py:136-141); this factory sends Python's ``sys.stdout`` to standard
error while it imports and builds the environment, so that text never reaches a stdio protocol stream (the SDK's stdio
servers write to the stream they captured at start).  Native libraries that write to file descriptor 1 directly are
not redirected.
"""

import contextlib
import sys

from mhs.driver import DriverDefinitionError

#: The suite README's quickstart environment (robopianist/suite/README.md:18), one of the debug pieces whose MIDI
#: the clone builds in code (robopianist/music/library.py:544-553); the PIG repertoire files are not in the clone.
DEFAULT_ENVIRONMENT = "RoboPianist-debug-TwinkleTwinkleLittleStar-v0"
_OPTIONS = frozenset({"environment_name", "seed"})


def make_env(**options):
    """``robopianist.suite.load(environment_name, seed=seed)`` with the default task arguments (driver.py facts)."""
    unknown = sorted(set(options) - _OPTIONS)
    if unknown:
        raise DriverDefinitionError(f"the RoboPianist live route takes only {sorted(_OPTIONS)}, not {unknown} "
                                    "(midi_file and task_kwargs change the action space the package declares)")
    name = options.get("environment_name", DEFAULT_ENVIRONMENT)
    seed = options.get("seed")
    if not isinstance(name, str) or not name.startswith("RoboPianist-") or len(name) > 200:
        raise DriverDefinitionError("environment_name must be a RoboPianist suite name (robopianist.suite.ALL)")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 32):
        raise DriverDefinitionError("seed must be an integer in [0, 2**32) or omitted")
    with contextlib.redirect_stdout(sys.stderr):
        from robopianist import suite

        return suite.load(environment_name=name, seed=seed)
