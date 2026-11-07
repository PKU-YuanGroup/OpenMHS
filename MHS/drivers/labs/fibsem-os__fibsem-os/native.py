"""Hardware backend: connects to the fibsem device server that serves a remote fluorescence microscope.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate runs the fake
backend and never imports this module or fibsem.  This package is model-authored and unreviewed; the loader refuses
the hardware backend of an unreviewed model-authored package at R2 and R3 only, and this driver is R1, so the
hardware backend remains an explicit operator choice rather than a guarded one.

Options: ``host`` and ``port`` are required; they name the device server on the FM's computer.  ``parent``, ``client``
and ``offline`` are passed to RemoteFluorescenceMicroscope.connect (fibsem/fm/remote.py:35-52): ``offline=True``
builds the FM unbound and lets it come online when the server starts (fibsem/fm/remote.py:44-48).  The connection is
HTTP over the device server, so the upstream ``requests`` and ``psygnal`` dependencies are needed as installed by the
card.
"""


def connect(host, port, **options):
    from fibsem.fm.remote import RemoteFluorescenceMicroscope

    return RemoteFluorescenceMicroscope.connect(host, port, **options)
