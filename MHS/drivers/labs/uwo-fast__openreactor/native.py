"""Hardware backend: opens one RLHT heater slice through crumbs-i2c.

Used only with backend="hardware" and allow_hardware=True (an operator
decision).  This package is model-authored and unreviewed, and it is R2: the
loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package
must not claim it).  The acceptance gate runs the fake backend and never
imports this module or the openreactor package.

The factory builds the upstream ``DeviceConfig`` for one slice, opens the
Linux I2C bus, constructs ``CrumbsPort`` and ``RlhtSlice``, and calls
``RlhtSlice.start()`` -- the upstream safe start-up that sends the safe
state, arms the command watchdog and sets closed-loop mode
(src/openreactor/rlht.py:290-345).  It then runs the upstream ``Controller``
tick on its own thread, with the slice both polled and an actuator, because
the poll is what feeds the slice's watchdog and what refreshes the cached
state ``RlhtSlice.status`` reports (src/openreactor/controller.py:356-370,
src/openreactor/rlht.py:469-475).

The wrapper exposes exactly ``status``, ``set_setpoint`` and ``send_safe``,
so the driver still talks to the upstream surface.  Setpoint writes and
status reads run on the controller thread through ``Controller.call``;
``send_safe`` uses ``Controller.stop_all``, the upstream stop-all path.
The bus stays open for the life of the backend (the upstream closes it in
``opened_slices`` after stop-all; this factory has no close entry point).
"""


class _SliceChannel:
    """The upstream slice behind the controller thread."""

    def __init__(self, slice_, controller):
        self._slice = slice_
        self._controller = controller

    def status(self, why=None):
        return self._controller.call(lambda: self._slice.status(why)).result(timeout=5.0)

    def set_setpoint(self, output, deci):
        self._controller.call(lambda: self._slice.set_setpoint(output, deci)).result(timeout=10.0)

    def send_safe(self):
        events = self._controller.stop_all("mhs-estop").result(timeout=5.0)
        failed = [event for event in events if event.result != "ok"]
        if failed:
            raise RuntimeError(f"the safe state was not sent: {failed[0].result}")


def connect(
    bus,
    address,
    *,
    name="heater",
    watchdog_timeout_ms,
    poll_s,
    output1="jacket",
    output2="lid",
    tc1=1,
    tc2=2,
    allow_unprotected=False,
):
    """Open one RLHT slice and start supervising it.

    ``bus`` is a Linux i2c-dev path such as ``/dev/i2c-1``; ``address`` is
    the slice's 7-bit address.  ``watchdog_timeout_ms`` and ``poll_s`` are
    required because the board may be configured differently from the
    example file; both are operator settings, not device bounds.
    """
    from crumbs_i2c import LinuxBus
    from openreactor.config import ChannelConfig, DeviceConfig
    from openreactor.controller import Controller
    from openreactor.ezo import EzoReader
    from openreactor.rlht import CrumbsPort, RlhtSlice

    address_value = int(str(address), 0) if isinstance(address, str) else int(address)
    device = DeviceConfig(
        name=name,
        kind="rlht",
        bus=bus,
        address=address_value,
        channels=(
            ChannelConfig(name=output1, label=output1.replace("_", " ").title(), output=1, tc=tc1),
            ChannelConfig(name=output2, label=output2.replace("_", " ").title(), output=2, tc=tc2),
        ),
        allow_unprotected=allow_unprotected,
    )
    bus_object = LinuxBus(bus)
    slice_ = RlhtSlice(
        device,
        CrumbsPort(bus_object, address_value),
        watchdog_timeout_ms=watchdog_timeout_ms,
        poll_s=poll_s,
    )
    slice_.start()
    controller = Controller(
        EzoReader([]),
        actuators=[slice_],
        polled=[slice_],
        ezo_period_s=poll_s,
        auto_read=False,
    )
    controller.start()
    return _SliceChannel(slice_, controller)
