"""Project identifiers for OpenMHS, defined in exactly one place.

Every name, version, namespace and prefix that identifies this project lives
here so that a rename (for example once the project has its own organisation
and domain) is a one-line change followed by regeneration.  Code, tools, the
site generator and the registry generator import these values; they never
spell them out.

* ``SPEC_VERSION`` is the specification line (``0.9``); ``SDK_VERSION`` is the
  distribution version.
* ``WIRE_VERSION`` is the value of ``mhs_version`` on the wire.  ``"1.0"``
  means *wire revision 1*; it is unchanged so existing endpoints, clients and
  reports keep interoperating.
* ``SCHEMA_BASE`` is a placeholder on the reserved ``.invalid`` top-level
  domain until the project picks an organisation.  It must stay a
  hierarchical ``https`` URL because the schemas use relative ``$ref``.
* ``LEGACY_SCHEMA_PREFIX`` is accepted by :mod:`mhs.schema.store` for reading
  only, so documents written before the rename keep validating.  It is
  scheduled for removal in 0.10 and must not be used to write new documents.
"""

from __future__ import annotations

__all__ = [
    "ADAPTER_ID_PREFIX",
    "DIST_NAME",
    "LEGACY_SCHEMA_PREFIX",
    "NON_AFFILIATION",
    "PROJECT_NAME",
    "REGISTRY_ID",
    "SCHEMA_BASE",
    "SDK_VERSION",
    "SPEC_VERSION",
    "WIRE_VERSION",
]

PROJECT_NAME = "OpenMHS"
DIST_NAME = "openmhs"
SPEC_VERSION = "0.9"
SDK_VERSION = "0.9.0.dev0"
WIRE_VERSION = "1.0"
SCHEMA_BASE = "https://openmhs.invalid/schema/0.9/"
LEGACY_SCHEMA_PREFIX = "https://modelhardwarestandard.com/schema/"
REGISTRY_ID = "openmhs-registry"
ADAPTER_ID_PREFIX = "openmhs:"
NON_AFFILIATION = (
    "OpenMHS is an independent open-source project, not affiliated with or "
    "endorsed by Anthropic, and not a reimplementation or compatible dialect "
    "of Anthropic's MHS research preview."
)
