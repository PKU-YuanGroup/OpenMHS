"""Hardware backend: opens a Zaber stage through the upstream ``zaber_device`` package.

The acceptance gate never imports this module, and no hardware run was made.  This package is model-authored and
unreviewed.  It is R1, so the SDK's review refusal for a model-written package applies at R2 and R3, not here: the
loader does not block this factory by itself, and an operator decides whether to use it.

Options of the backend:
  * ``serial_number`` (required): the serial number of the Zaber device the axes are configured on;
  * ``x_alias``, ``y_alias`` and ``z_alias`` (required): the actuator aliases of the three axes on that device;
  * any other option (for example ``use_ports``) is passed to ``ZaberStage`` -> ``ZaberDevices`` -> ``ZaberDevice``;
    without ``use_ports`` the upstream class searches the serial ports itself
    (``zaber_device/zaber_device.py:100-134``).

The driver serves one device wired as an xyz stage; all three aliases are required so that no axis is left
unconfigured.  The axis mapping is the upstream stage's own API: ``set_x_axis``, ``set_y_axis`` and ``set_z_axis``
select an actuator by its alias (``zaber_device/zaber_device.py:826-849``).
"""


def connect(serial_number, x_alias, y_alias, z_alias, **options):
    from zaber_device import ZaberStage

    stage = ZaberStage(**options)
    stage.set_x_axis(int(serial_number), int(x_alias))
    stage.set_y_axis(int(serial_number), int(y_alias))
    stage.set_z_axis(int(serial_number), int(z_alias))
    return stage
