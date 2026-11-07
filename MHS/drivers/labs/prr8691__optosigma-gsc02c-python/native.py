"""Hardware backend: opens a GSC-02C controller over its RS-232 serial line with the upstream GSC02C class.

The acceptance gate never imports this module and never calls it: this package is model-authored and unreviewed, and
no hardware was attached while it was written.  The gate serves the fake backend only.

Options of the backend:
    port       serial port name (required), for example "COM7" or "/dev/ttyUSB0" (controller.py:72-81)
    axis       1 or 2 (default 1) (controller.py:83-84)
    baudrate   default 9600 (controller.py:86-87)
    timeout    seconds to wait for a reply, default 2.0 (controller.py:89-90)
    any other keyword goes to StageConfig: um_per_pulse, min_position_mm and max_position_mm
               (controller.py:22-40)

The upstream connect() opens the port with 9600 baud, 8 data bits, no parity, 1 stop bit and RTS/CTS handshaking
(controller.py:139-149).
"""


def connect(port, axis=1, baudrate=9600, timeout=2.0, **config):
    from optosigma_gsc02c.controller import GSC02C, StageConfig

    device = GSC02C(port=port, axis=axis, baudrate=baudrate, timeout=timeout,
                    config=StageConfig(**config) if config else StageConfig())
    device.connect()
    return device
