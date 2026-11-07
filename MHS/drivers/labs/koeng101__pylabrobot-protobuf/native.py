"""Hardware backend: opens the pylabrobot-protobuf client against a deployed STAR service.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate
runs the fake backend and never imports this module or the client package.  This package is
model-authored and unreviewed and is R2, so the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json.

``base_url`` is the URL of the deployed STAR service (the upstream README example is
http://localhost:8080, README.md:41).  The client package is not installed here; the import is
deliberately inside ``connect`` so the fake and the gate never need it.  The driver's ``setup`` awaits
the service's Setup RPC after this factory returns.
"""


def connect(base_url="http://localhost:8080", **_options):
    from pylabrobot_protobuf_client.star import RemoteSTARBackend

    return RemoteSTARBackend.connect(base_url)
