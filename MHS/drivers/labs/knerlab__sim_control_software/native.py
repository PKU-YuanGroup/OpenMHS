"""Hardware backend: opens the knerlab motorized polarizer through the upstream A8MRU class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed.  It is R1, so the loader does not refuse the hardware backend on review grounds (that refusal is for R2
and R3 only); the backend was never executed and no hardware run is claimed.

The upstream class is ``motorized_pol_v2.A8MRU``.  The clone is a script bundle with no packaging metadata, so the
deployment must make ``motorized_pol_v2`` importable: pass ``clone_root`` (the clone directory) or put it on
PYTHONPATH.  The module also needs two things that are not Python code of the clone (motorized_pol_v2.py:14-20):

* the external ``pol_rotator_p35`` package, which provides ``Mot_pol_params`` (the ctypes structures); pass
  ``params_root`` or put it on PYTHONPATH;
* ``USMCDLL.dll``, loaded by its bare name.  On Windows that directory (the clone root contains the DLL) must be on
  PATH or be the working directory.

The upstream application enables the motor with ``MotorOn`` after constructing the class
(microscope_p35.py:67-68); this factory does the same.  The constructor itself powers the motor off (ResetD=1,
motorized_pol_v2.py:142).  No speed is set: the class default applies and this package does not expose a speed write.
"""


def connect(clone_root=None, params_root=None, **_options):
    """Open the USMC controller and return the upstream A8MRU object with its motor enabled."""
    import sys

    for root in (params_root, clone_root):
        if root not in (None, "") and str(root) not in sys.path:
            sys.path.insert(0, str(root))
    from motorized_pol_v2 import A8MRU

    device = A8MRU()
    device.MotorOn()
    return device
