"""Hardware backend: opens a Tecan FluentControl instrument through the upstream HTTP client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the upstream package.

Options: ``base_url`` (required unless ``FLUENT_CONTROL_URL`` is set) is the instrument URL, and ``username``,
``password``, ``api_key`` and ``timeout`` go to the upstream constructor (fluent_control_automation.py:86-113).  The
upstream ``post_transfer_session`` takes a list of ``TransferParameters`` dataclasses (fluent_control_automation.py:
190-210); this factory wraps the client so the driver can pass the same fields as plain dictionaries.
"""

import os


class _FluentControl:
    """The upstream client with dictionary transfer parameters; it keeps every public client method."""

    def __init__(self, client):
        self._client = client

    def get_instrument_status(self):
        return self._client.get_instrument_status()

    def get_deck_layout(self):
        return self._client.get_deck_layout()

    def post_transfer_session(self, transfers):
        from fluent_control_automation import TransferParameters

        parameters = [TransferParameters(**dict(transfer)) for transfer in transfers]
        return self._client.post_transfer_session(parameters)

    def start_transfer_session(self, session_id):
        return self._client.start_transfer_session(session_id)

    def get_transfer_status(self, session_id):
        return self._client.get_transfer_status(session_id)

    def cancel_transfer_session(self, session_id):
        return self._client.cancel_transfer_session(session_id)


def connect(base_url=None, username=None, password=None, api_key=None, timeout=None, **options):
    from fluent_control_automation import FluentControlClient

    url = base_url or options.pop("url", None) or os.environ.get("FLUENT_CONTROL_URL")
    if not url:
        raise ValueError("the FluentControl hardware backend needs base_url (or FLUENT_CONTROL_URL)")
    kwargs = {"base_url": url, "username": username, "password": password, "api_key": api_key}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if options:
        raise TypeError(f"unknown FluentControl backend options: {sorted(options)}")
    return _FluentControl(FluentControlClient(**kwargs))
