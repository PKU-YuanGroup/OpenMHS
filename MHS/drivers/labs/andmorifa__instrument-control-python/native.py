"""Hardware backend: open the TCP socket of a Red Pitaya SCPI server through the upstream client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The gate and the fake backend
never import this module.  ``ip`` and ``port`` are required options because the driver does not assume a device
address; any other option (for example ``timeout``) is passed to the upstream constructor unchanged.  ``connect``
opens the socket and raises when the connection fails (src/redpitaya_client.py:26-39).
"""


def connect(ip, port, **options):
    from redpitaya_client import RedPitayaClient

    client = RedPitayaClient(ip=ip, port=port, **options)
    client.connect()
    return client
