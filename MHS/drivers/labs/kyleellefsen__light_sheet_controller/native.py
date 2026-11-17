"""Hardware backend: constructs the upstream LightSheetDriver on the two NI USB-6001 boards.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed and is R2: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json.  The acceptance gate runs the fake backend and never imports this module,
the clone or the vendor SDK; nothing in this package was run against a board, a laser or Qt.

Deployment assumptions:

* the clone root (the directory that contains ``light_sheet_controller.py``) is placed on ``sys.path``; the
  repository has no setup.py and the card's install block is empty, so this factory accepts ``clone_root`` and
  inserts it.  The module imports PyDAQmx, qtpy, pyqtgraph, numpy and scipy (light_sheet_controller.py:15-31,
  calc_waveforms.py:1-3);
* a Qt application exists because LightSheetDriver subclasses QtWidgets.QWidget and calls ``self.hide()``
  (light_sheet_controller.py:118-131); this factory creates one with the offscreen platform if the deployment
  provides no display;
* the upstream constructor starts both analog-output tasks from saved settings before MHS can enforce an
  envelope (light_sheet_controller.py:73-92,120-147). The later ``gotozero`` does not prevent this initial
  actuation and computes laser TTL from the saved laser flags (190-218); it does not establish laser-off;
* NI MAX must name the two USB-6001 boards Dev1 and Dev2 (light_sheet_controller.py:7, 46-57).  The factory
  does not call ``check_if_NI_devs_are_present`` because that function opens modal warning dialogs; a missing
  board instead raises from PyDAQmx when the task is created;
* the clone has no documented hardware e-stop and no readback of the output voltage or laser emission.  The
  zeroing request is a software operation, not a safe-state action. The stop path uses DAQ writes with
  timeout -1 (190-218), and waveform clamps may open modal dialogs (calc_waveforms.py:80-87). This adapter
  remains blocked until a bounded construction and a source-backed laser-off stop are available.
"""

import os
import sys

_APP = None


def connect(clone_root=None, **options):
    global _APP
    if clone_root:
        sys.path.insert(0, os.path.abspath(os.fspath(clone_root)))
    os.environ.setdefault("QT_QPA_PLATFORM", options.pop("qt_qpa_platform", "offscreen"))
    from qtpy import QtWidgets
    from light_sheet_controller import LightSheetDriver, Settings

    _APP = QtWidgets.QApplication.instance()
    if _APP is None:
        _APP = QtWidgets.QApplication([])
    device = LightSheetDriver(Settings())
    device.gotozero()
    return device
