"""Hardware backend: opens a Newport 1918-C through the upstream ctypes class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed; the acceptance gate runs the fake backend and never imports this module or the clone, and no hardware was
attached.  The card's install block is empty, so this package installs nothing.

The pinned upstream module newport_1918c.py is Python 2.7 source (README.md:12) and loads Newport's Windows usbdll.dll
through ctypes (README.md:8, newport_1918c.py:24-27).  A Python 3 interpreter cannot parse or import it, so the factory
refuses instead of trying; porting the clone is a change to the read-only upstream and is out of scope here.  On a
Python 2.7 interpreter with the clone root on sys.path the factory builds Newport_1918c with the optional LIBNAME and
product_id constructor arguments.  Those two arguments default to the 32-bit install path and product id 0xCEC7 in the
upstream constructor (newport_1918c.py:24-27); the defaults of the class are not a statement about another computer.
"""

import sys


def connect(libname=None, product_id=None, **options):
    """Open the upstream Newport_1918c; ``libname`` and ``product_id`` override its constructor defaults."""
    if sys.version_info[0] >= 3:
        raise RuntimeError(
            "the pinned upstream newport_1918c.py is Python 2.7 source (README.md:12, newport_1918c.py:1-30) and "
            "cannot be imported on Python 3; the hardware backend needs a Python 2.7 interpreter and Newport's "
            "usbdll.dll on Windows, and this package does not port or install either")
    from newport_1918c import Newport_1918c

    kwargs = dict(options)
    if libname is not None:
        kwargs["LIBNAME"] = libname
    if product_id is not None:
        kwargs["product_id"] = product_id
    return Newport_1918c(**kwargs)
