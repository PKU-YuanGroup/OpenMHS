"""Hardware backend of the ARI M1 mirror-section driver: the upstream ophyd Device over EPICS Channel Access.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend; it imports
``ari_sxn_common.ari_ophyd`` and constructs the upstream ``M1`` class (src/ari_sxn_common/ari_ophyd.py:38), which
creates the mirror motors, the ``_VacuumDevices`` child, the ``BaffleSlit`` child and the ``Diagnostic`` child.  It
then waits once for the Device's connection, with the operator's timeout.

Deployment notes, not device facts:

* ``prefix`` is the EPICS prefix of the installed M1 section.  The vacuum child additionally carries the literal
  prefix ``ARI_M1:`` in its ``_AriSxnC`` Component (ari_ophyd.py:34), so the operator must confirm that this matches
  the installed IOC before a live load.
* ``locations_data`` is the optional mapping for the parent ``locations`` signal; the class itself configures the
  ``slits`` and ``diag`` location mappings (ari_ophyd.py:112-140).  The package reads the parent location flags and
  does not write them.
* The upstream module imports ``common_ophyd`` as a top-level module (ari_ophyd.py:1).  This factory first tries the
  normal installed import path and, only when that fails on ``common_ophyd``, makes the package's own directory
  importable for the duration of the import.  It never modifies the clone and never changes upstream source.
* Waiting for the whole Device also connects Components this package does not read (for example the diagnostic
  camera and the ``gv`` shutter).  Whether every configured PV exists is a deployment check.
* Construction writes to the IOC: each ``ID29EM`` (``slits.currents`` and ``diag.currents``) puts ``EM180`` into the
  ``nd_array_port`` of its current1 to current4 plugins while it is constructed (common_ophyd.py:212-224), eight
  Channel Access puts before the driver serves anything.
* The package no longer calls ``M1.trigger()`` (model review): its children are ophyd ``SingleTrigger``/``NSLS_EM``
  detectors that the package never stages.

Nothing here was run: the package has never connected to an EPICS IOC.
"""

import math


def _m1_class():
    """Import the upstream M1 class, tolerating its top-level ``common_ophyd`` import during deployment.

    The pinned ``ari_ophyd.py`` imports ``common_ophyd`` as a top-level module (ari_ophyd.py:1).  An installation
    that exposes only the ``ari_sxn_common`` package cannot resolve that import; the fallback adds the package's own
    directory to ``sys.path`` for the import only.  It never modifies the clone and never changes upstream source.
    """
    try:
        from ari_sxn_common.ari_ophyd import M1
        return M1
    except ModuleNotFoundError as exc:
        if exc.name != "common_ophyd":
            raise
        import sys
        from pathlib import Path

        import ari_sxn_common

        package_dir = str(Path(ari_sxn_common.__file__).resolve().parent)
        sys.path.insert(0, package_dir)
        try:
            from ari_sxn_common.ari_ophyd import M1
        finally:
            sys.path.remove(package_dir)
        return M1


def connect(*, prefix="", name="m1", connection_timeout_s=10.0, locations_data=None):
    if not isinstance(prefix, str):
        raise ValueError("prefix must be a string (the installed M1 EPICS prefix)")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if isinstance(connection_timeout_s, bool) or not isinstance(connection_timeout_s, (int, float)) \
            or not math.isfinite(connection_timeout_s) or connection_timeout_s <= 0:
        raise ValueError("connection_timeout_s must be a positive finite number of seconds")
    if locations_data is not None and not isinstance(locations_data, dict):
        raise ValueError("locations_data must be a mapping of location names to member mappings")

    M1 = _m1_class()
    options = {"prefix": prefix, "name": name}
    if locations_data is not None:
        options["locations_data"] = locations_data
    device = M1(**options)
    device.wait_for_connection(timeout=connection_timeout_s)
    return device
