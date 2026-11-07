"""Hardware backend: opens a Thorlabs APT motor through the upstream Motor class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed.  It is R1, so the loader does not automatically refuse its hardware backend; an operator must review
the package and the site's stop arrangement before any hardware run.  The acceptance gate runs the fake backend and
never imports this module or the thorlabs_apt package.

Options of the backend: ``serial_number`` (required) is the integer serial number that ``list_available_devices()``
returns (README.md:44-48); it is passed to ``thorlabs_apt.Motor`` (thorlabs_apt/core.py:144-151).  The upstream
package loads APT.dll and calls APTInit at import time (thorlabs_apt/core.py:1346-1376), so the import below only
works on a Windows host with the Thorlabs APT software installed (README.md:7-16).
"""


def connect(serial_number):
    from thorlabs_apt import Motor

    return Motor(serial_number)
