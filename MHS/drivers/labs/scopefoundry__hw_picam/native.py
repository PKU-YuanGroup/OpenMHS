"""Hardware backend: open the first PICam camera through the upstream ctypes wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R1: the loader's refusal of an unreviewed model-written hardware backend applies at R2 and R3
only, so it does not cover this package; nothing here ran on hardware.  The acceptance gate runs the fake backend
and never imports this module, the upstream package or the PICam DLL.

The upstream module loads the PICam shared library from the PICAM_DLL environment variable at import and overwrites
that variable with a fixed Windows path (picam.py:2, 13-14), so the hardware path is Windows-only and needs the
Princeton Instruments PICam runtime installed.  ``PiCAM()`` opens the first camera (picam.py:22-31).  The clone's
setup.py installs the modules as the package ScopeFoundryHW.picam (setup.py:1-17); the fallback import covers a
clone placed directly on sys.path.
"""


def connect(**_options):
    try:
        from ScopeFoundryHW.picam.picam import PiCAM
    except ImportError:
        from picam import PiCAM

    return PiCAM()
