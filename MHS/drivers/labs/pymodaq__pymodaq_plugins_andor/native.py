"""Hardware backend: opens an Andor SDK3 camera through the upstream ``AndorCamera`` class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed.  It is R1, so the loader's ``reviewed_by`` refusal for unreviewed
model-written packages (which applies at R2 and R3 only) does not cover it: nobody has run this module,
and it must not be run without a human reviewing the package and the camera setup first.  The
acceptance gate runs the fake backend and never imports this module or the upstream package.

Options of the backend: ``cam_num`` (default 0) is the index the SDK3 enumeration gives the camera, and
``nbuffer`` (default 1) is the number of acquisition buffers passed to ``AndorCamera``.  The upstream
viewers open a camera with ``AndorCamera(index)`` and then call ``init_camera()``
(daq_2Dviewer_AndorSCMOS.py:399-402); the same two steps are done here.  The vendor SDK (the Andor
library behind the ctypes bindings) must be installed separately; this module does not install it.
"""


def connect(cam_num=0, nbuffer=1, **_options):
    from pymodaq_plugins_andor.hardware.andor_sdk3.api import AndorCamera

    camera = AndorCamera(cam_num, nbuffer)
    camera.init_camera()
    return camera
