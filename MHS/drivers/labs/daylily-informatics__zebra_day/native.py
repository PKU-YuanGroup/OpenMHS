"""Hardware backend factory for the zebra_day driver.

Used only with backend="hardware" and allow_hardware=True, after a human sets ``reviewed_by`` in driver.lock.json:
this package is model-authored and R2, so the loader refuses the hardware backend of an unreviewed package.  The
factory imports the pinned upstream class and constructs it; the clone is never imported by the gate, and the fake
backend never touches this module.

Options: ``ip_address`` (required) is the printer's IPv4 address or hostname; ``port`` defaults to the upstream
constructor's 9100 and ``buffer_size`` to its 4096.  The upstream class opens one TCP connection per command
(zebra_day/cmd_mgr.py:26-41).
"""


def connect(ip_address, port=9100, buffer_size=4096, **_options):
    from zebra_day.cmd_mgr import ZebraPrinter

    return ZebraPrinter(ip_address, port=port, buffer_size=buffer_size)
