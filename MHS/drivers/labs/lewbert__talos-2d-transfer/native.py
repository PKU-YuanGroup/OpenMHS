"""Hardware backend: opens a Zolix ZC300 XYR stage through the upstream Modbus-RTU driver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream
``talos`` package.

``port`` (required) is the serial port of the ZC300 controller's USB virtual COM port.  The other keyword options
are the upstream's configuration keys (talos/hal/devices/zolix.py:102-120, 194): ``slave_address``,
``timeout_s``, ``um_per_pulse_xy``, ``um_per_pulse_r``, ``slow_speed_pps``, ``fast_speed_pps``, ``slow_speed_r``,
``fast_speed_r``, ``accel_pps2``, ``stop_mode`` and ``rotation_enabled``.  An option left out takes its upstream
default (talos/hal/devices/zolix.py:104-117; for example 0.625 micrometres per pulse, ``accel_pps2`` 10_000_000 and the
immediate stop).  Those are the upstream application's deployment defaults, not facts about a given bench or a
statement of any limit, so a site passes the values of its own controller.  The serial line settings themselves
are fixed by the upstream connect() (115200 8N1), as the clone documents (docs/DESIGN.md:47).

Opening this backend changes the controller: the upstream connect() writes 0x01 to the enable register and
``accel_pps2`` to the acceleration register of every axis in use (X, Y and, unless ``rotation_enabled`` is false, R)
and reads the acceleration back (talos/hal/devices/zolix.py:136-164).  It writes no motion opcode.
"""


def connect(port, slave_address=1, **options):
    from talos.hal.devices.zolix import ZolixXYRStage

    config = {"port": port, "slave_address": slave_address}
    config.update(options)
    device = ZolixXYRStage(config)
    device.connect()                    # opens the port, writes each axis's enable and acceleration registers
    return device
