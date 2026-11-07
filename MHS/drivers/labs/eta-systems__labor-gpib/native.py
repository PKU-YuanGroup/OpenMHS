"""Hardware backend: open a Prologix GPIB adapter and an NGMO2 through the upstream classes.

This module is used only with ``backend="hardware"`` and an explicit operator decision.  The acceptance gate never
imports it and the fake backend never calls it.  The package is model-authored, unreviewed and R2, so the loader
refuses its hardware backend until a human signs ``reviewed_by`` in ``driver.lock.json``.

The upstream clone is a src-layout project: ``interface.prologix_gpib`` and ``devices.rohde_schwarz_ngmo2`` live
under ``labs/eta-systems/labor-gpib/src``.  The operator can pass ``src_root``; by default the path is derived from
this package's location in this repository.  The upstream adapter imports ``visa`` (pyvisa), which the operator
installs; this package does not install or import it at gate time.

The upstream classes are never imported by the gate and no hardware was attached while this package was written.
``prologix_gpib.usb`` opens the VISA resource and sends ``++clr`` and ``++loc`` in its constructor
(src/interface/prologix_gpib.py:17-33); ``ngmo.device`` then builds the channel, display, format and status objects
(src/devices/rohde_schwarz_ngmo2.py:16-27).
"""


def connect(com="ASRL1::INSTR", baudrate=19200, timeout=2000, address=7, src_root=None, **options):
    """Open the GPIB adapter and return the upstream ``device`` object for ``address``.

    ``options`` (for example ``channel``) is consumed by the driver, not here.  ``com`` is the VISA resource of the
    Prologix adapter; the operator supplies it for the bench.  The constructor defaults are transport settings, not
    device bounds.
    """
    import sys
    from pathlib import Path

    if src_root is None:
        src_root = Path(__file__).resolve().parents[4] / "labs" / "eta-systems" / "labor-gpib" / "src"
    source = Path(src_root).resolve()
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

    import devices.rohde_schwarz_ngmo2 as ngmo
    import interface.prologix_gpib as prologix

    interface = prologix.usb(com=com, baudrate=int(baudrate), timeout=int(timeout))
    return ngmo.device(interface, int(address))
