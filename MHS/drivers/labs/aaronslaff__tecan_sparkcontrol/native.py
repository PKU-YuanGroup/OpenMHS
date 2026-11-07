"""Hardware backend: opens a Tecan SparkControl instrument through the upstream HTTP client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the upstream package.

Options: ``base_url`` (required unless ``SPARK_CONTROL_URL`` is set) is the instrument URL; ``username``,
``password``, ``api_key`` and ``timeout`` go to the upstream constructor
(spark_control_automation.py:113-140).  The upstream client keeps a requests session and sends JSON over HTTP
(spark_control_automation.py:142-177); the client is imported only here, never by the gate.
"""

import os


def connect(base_url=None, username=None, password=None, api_key=None, timeout=None, **options):
    from spark_control_automation import SparkControlClient

    url = base_url or options.pop("url", None) or os.environ.get("SPARK_CONTROL_URL")
    if not url:
        raise ValueError("the SparkControl hardware backend needs base_url (or SPARK_CONTROL_URL)")
    kwargs = {"base_url": url, "username": username, "password": password, "api_key": api_key}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if options:
        raise TypeError(f"unknown SparkControl backend options: {sorted(options)}")
    return SparkControlClient(**kwargs)
