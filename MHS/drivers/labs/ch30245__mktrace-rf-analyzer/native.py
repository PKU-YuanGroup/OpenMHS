"""Hardware backend of the MKTrace package: the pinned upstream ``pna.NaClient``.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend; it imports
the pinned clone's root module ``pna`` (and through it ``touchstone``), so the clone root must be on ``PYTHONPATH``:
the repository has no installable package and the card's install command only installs the requirements
(``requirements.txt``).  The driver's ``setup`` creates the capture directory the native writes Touchstone files into;
``capture_dir`` is therefore consumed by the driver and not by the upstream constructor, whose only arguments are the
host and port (pna.py:236-241).  Nothing in this package has run this factory against an analyzer.
"""


def connect(host, port=5025, **options):
    """Return a ``pna.NaClient`` for ``host`` and ``port``; other options are the driver's deployment settings."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be the non-empty address of the analyzer")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536:
        raise ValueError("port must be an integer in 1..65535")
    from pna import NaClient

    return NaClient(host.strip(), port)
