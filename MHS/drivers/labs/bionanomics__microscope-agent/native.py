"""Hardware backend of the Baumer camera: the upstream GenICam class.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", ...)``); it is then the only code that imports
``acquisition.backends.baumer_genicam`` and, through that module, ``harvesters``, ``genicam``, ``cv2`` and
``PIL``.  The upstream package is not installed in this workspace and was never imported or run here.

The upstream ``BaumerGenICam`` constructor takes no arguments.  It finds a GenTL producer through
``GENICAM_GENTL64_PATH`` and the two fallback directories the clone records (``baumer_genicam.py:46-70``), so a
deployment must provide one of those producer paths and a camera that is not already held by another GenICam
consumer.  The capture directory is chosen by ``acquisition.paths`` at import time; set ``CONFOCAL_MCP_DATA_DIR``
before this module is imported when the operator wants captures outside the process working directory.  Nothing here
was run against a camera.
"""


def connect(**options):
    """Build the upstream ``BaumerGenICam``; the upstream constructor accepts no options."""
    if options:
        raise TypeError("BaumerGenICam takes no constructor options; configure its data root with "
                        "CONFOCAL_MCP_DATA_DIR before loading the hardware backend")
    from acquisition.backends.baumer_genicam import BaumerGenICam

    return BaumerGenICam()
