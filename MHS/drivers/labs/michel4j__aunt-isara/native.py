"""Hardware backend: opens one ISARA controller through the upstream AuntISARAApp.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses this backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the upstream package.

The upstream application is a Soft IOC: its constructor opens the two TCP links of the controller
(auntisara/ioc.py:561-585) but Twisted serves them only while the reactor runs.  The factory therefore starts the
reactor in a daemon thread.  Options: ``device_name`` (the PV prefix), ``address`` (the controller IP), the optional
``command_port`` (default 1000) and ``status_port`` (default 10000), and ``positions`` (the position file name,
resolved by the application against its working directory).  These defaults are the upstream constructor's; an
operator sets the ports of the unit.  The hardware path was never run in this package.
"""

import threading


def connect(device_name, address, command_port=1000, status_port=10000, positions="positions", **options):
    from auntisara.ioc import AuntISARAApp
    from twisted.internet import reactor

    app = AuntISARAApp(device_name, address, command_port=command_port, status_port=status_port,
                       positions=positions, **options)
    thread = threading.Thread(target=reactor.run, kwargs={"installSignalHandlers": False}, daemon=True,
                              name="isara-reactor")
    thread.start()
    return app
