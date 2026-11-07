"""Hardware backend: load the upstream ``hardware.stage`` module and return it to the driver.

The upstream application imports its own packages as top-level names (``from hardware import
plc``, ``from utils.pycro import core``), so ``upstream_root`` must name the clone's inner
``WIL_Pycro_Control_App`` directory, which is put first on ``sys.path``.  Its generic package
names (``hardware``, ``utils``, ``models``, ``views``) can shadow, or be shadowed by, modules of
the same name already loaded in the server process.

The import is not passive (model review, 2026-11-05; the server opens the backend when it loads
the package):

* ``hardware/__init__.py:5-11`` sets the camera to its default mode (``camera.default_mode``:
  stop sequence acquisition, live mode off, trigger and acquire mode, exposure) and programs the
  PLC trigger circuit (``plc.init_plc_state``), suppressing ``GeneralHardwareException`` from both;
* ``utils/pycro.py:25-26`` constructs the pycromanager ``Studio`` and ``Core`` objects, so the
  Micro-Manager Java gateway and the devices must already be available;
* ``utils/__init__.py:1-5`` builds a ``Config`` from ``LSConfig.cfg`` in the current directory,
  which writes that file back (``utils/config_class.py:25-30``, ``117-125``), and
  ``utils/init_logger.py:11-16`` creates ``logs/`` there and calls ``logging.basicConfig`` with a
  DEBUG log file in it.

Every upstream hardware function prints a message to stdout when its second attempt fails
(``hardware/exceptions_handle.py:39-42``), at import as well; that output would corrupt an MHS
server that talks over stdio.

At R1 the loader does not require a human ``reviewed_by`` before it starts this backend; the
package is blocked because the clone has no stage stop (see ``driver.py``).  This deployment
path was never run here and the fake backend is the only backend this package has been checked
on.  The acceptance gate never imports this module and never opens hardware.
"""


def connect(upstream_root, **_options):
    """Return the upstream stage module from a deployed WIL_Pycro_Control_App checkout."""
    import sys
    from pathlib import Path

    root = Path(upstream_root).resolve()
    if not (root / "hardware" / "stage.py").is_file():
        raise RuntimeError(f"{root} is not the WIL_Pycro_Control_App package directory")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from hardware import stage

    return stage
