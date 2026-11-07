"""Hardware backend: opens a Thorlabs camera through the upstream PyMoDAQ pylablib viewer class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed: it is R1, so the loader's ``reviewed_by`` refusal of an unreviewed model-written hardware backend
(which applies at R2 and R3 only) does not cover it.  Nobody has run this module, and it must not be run without a
human reviewing the package and the camera setup first.  The acceptance gate runs the fake backend and never
imports this module, the upstream package or pylablib.

The upstream class is a PyMoDAQ 2D viewer built on the DAQ_Viewer_base Qt module
(daq_2Dviewer_ThorlabsPLL.py:7-29).  Its camera work lives in inherited methods that only touch
``self.controller`` and ``self.settings`` (daq_2Dviewer_GenericPylablibCamera.py:114-122, 229-244, 326-330), so
this factory constructs the class without the PyMoDAQ dashboard: it sets the settings mapping the viewer's
``init_controller`` reads (daq_2Dviewer_ThorlabsPLL.py:24-29) and lets that method open the pylablib camera.  The
Qt-only members of the viewer (its callback thread and its parameter tree) are not created; the driver does not
use them.  This headless construction is the part that was never executed, and the pylablib / PyMoDAQ stack and a
Thorlabs camera are required at run time.  ``serial`` is the Thorlabs serial number the viewer's camera list
reports; when it is omitted the viewer's first enumerated camera is used.
"""


class _HeadlessSettings(dict):
    """The little of the viewer's parameter tree that init_controller reads: settings['camera_list']."""


class _HeadlessStatus:
    """The fields the viewer's close() clears on its DAQ status object (daq_2Dviewer_GenericPylablibCamera.py:315-321)."""

    def __init__(self):
        self.initialized = True
        self.controller = None
        self.info = ""


def _make_viewer_class():
    from pymodaq_plugins_pylablib_camera.daq_viewer_plugins.plugins_2D.daq_2Dviewer_ThorlabsPLL import (
        DAQ_2DViewer_ThorlabsPLL)

    class HeadlessThorlabsViewer(DAQ_2DViewer_ThorlabsPLL):
        """The upstream viewer without its Qt/PyMoDAQ construction; the driver uses the camera-facing members."""

        def __init__(self, serial):
            self.camera_list = [serial]
            self.settings = _HeadlessSettings(camera_list=serial)
            self.status = _HeadlessStatus()
            self.controller = None
            self.roi_pos_size = None
            self.axes = []
            self.data_shape = "Data2D"
            self.pixel_width = None
            self.last_tick = 0.0
            self.fps = 0.0
            self.controller = self.init_controller()   # the upstream method (daq_2Dviewer_ThorlabsPLL.py:24-29)

        def emit_status(self, command):
            """The Qt status signal is not part of the headless use."""

        def _prepare_view(self):
            """The viewer's Qt data emission is not part of the headless use."""

    return HeadlessThorlabsViewer


def connect(serial=None, **_options):
    viewer_class = _make_viewer_class()
    selected = serial if serial is not None else (viewer_class.camera_list[0] if viewer_class.camera_list else None)
    return viewer_class(selected)
