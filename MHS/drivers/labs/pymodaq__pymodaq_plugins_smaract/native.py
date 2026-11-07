"""Hardware backend: opens a SmarAct MCS2 controller through the upstream wrapper.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator
decision).  The upstream wrapper needs the SmarAct MCS2 SDK library installed
(README.rst:52-53); this module imports it only inside ``connect`` and the
acceptance gate never imports this module or the pymodaq package.

Options of the backend:

* ``controller_locator`` (required) is the locator of the controller, for
  example ``usb:sn:00000667``: the number is the serial number printed on the
  device (MCS2_wrapper.py:17-26).
* ``configuration`` is passed to ``open_communication`` (unused upstream,
  MCS2_wrapper.py:66-72).
* other options (for example ``channel_index``, which the driver reads) are
  accepted and ignored here; the wrapper takes only the locator.

This package is model-authored and unreviewed.  It is R1: the loader refuses the
hardware backend of an unreviewed model-written package only at R2 and R3, so a
human review and a ``reviewed_by`` signature still have to happen before any
hardware use; the ``reviewed_by`` field in driver.lock.json is null.
"""


def connect(controller_locator, configuration="", **options):
    from pymodaq_plugins_smaract.hardware.mcs2.MCS2_wrapper import SmarActMCS2Wrapper

    wrapper = SmarActMCS2Wrapper()
    wrapper.open_communication(controller_locator, configuration=configuration)
    return wrapper
