"""JSON Schema validation for the OpenMHS reference SDK (stdlib only).

Public API::

    from mhs.schema import validate, validate_file, Validator, SchemaStore

    errors = validate(instance, schema_dict)        # -> list[str]
    errors = validate_file(instance, "schema.json") # -> list[str]
    store  = SchemaStore()                          # $MHS_SCHEMA_DIR, mhs/_data or MHS/schema/
    errors = store.validate(instance, "device.schema.json")
    schema, base = store.resolve_public(ref)        # network-safe lookup of shipped schemas

The validator implements the JSON Schema 2020-12 subset used by MHS.  See
:mod:`mhs.schema.validator` for the keyword list and semantics.
"""

from __future__ import annotations

from .store import (
    KNOWN_SCHEMA_PREFIXES,
    SchemaStore,
    clear_default_store,
    default_store,
    find_schema_dir,
    mhs_schema_dir,
    packaged_data_dir,
    public_schema_name,
)
from .validator import (
    DEFAULT_MAX_DEPTH,
    SchemaError,
    Validator,
    resolve_pointer,
    validate,
    validate_file,
)

__all__ = [
    "DEFAULT_MAX_DEPTH",
    "KNOWN_SCHEMA_PREFIXES",
    "SchemaError",
    "SchemaStore",
    "Validator",
    "clear_default_store",
    "default_store",
    "find_schema_dir",
    "mhs_schema_dir",
    "packaged_data_dir",
    "public_schema_name",
    "resolve_pointer",
    "validate",
    "validate_file",
]
