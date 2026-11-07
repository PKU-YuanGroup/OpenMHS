"""Hardware backend: opens the LASAF CAM socket through the upstream client class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
no human has reviewed it.  The loader refuses the hardware backend of such a package only at R2 and above; this one is
R1, so nothing stops an operator from enabling it: run it first with a person at the microscope
(MHS/handoff/REVIEW.md, section 1).  The acceptance gate runs the fake backend and never imports this module or the
leicacam package.

Options of the backend: ``host`` and ``port`` of the CAM server, 127.0.0.1 and 8895 by default
(src/leicacam/cam.py:45-46).  ``CAM()`` connects in its constructor and receives the welcome message
(src/leicacam/cam.py:110-121), so the factory returns a connected client.
"""


def connect(host="127.0.0.1", port=8895, **_options):
    from leicacam import CAM

    return CAM(host=host, port=port)
