"""Hardware backend of the niscope-mcp driver: constructs the upstream DirectBackend.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The package is model-authored
and unreviewed and is R1, so the loader does not add a review gate here; no hardware was attached or driven by the
author of this package, and the acceptance gate runs the fake backend only.

The upstream hardware extra installs the niscope package (pyproject.toml:29) and the README states that the
package requires Windows and NI hardware (README.md:5).  DirectBackend opens the selected scope on demand with
``niscope.Session(resource_name, reset_device=False)`` (direct.py:57-64); the driver's setup selects the first
scope reported by ``scan_devices`` (direct.py:31-55) unless the ``resource_name`` option names one.  The driver
reads the other backend options (``channel``, and the hidden horizontal and trigger values) from ``self.options``.
"""


def connect(**_options):
    from niscope_mcp.backends.direct import DirectBackend

    return DirectBackend()
