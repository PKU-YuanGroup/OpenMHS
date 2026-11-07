"""Test package bootstrap: isolate OpenAI4S state and make sibling trees importable.

The tests are stdlib ``unittest`` and need no environment variables:

    python3 -m unittest discover -s integration/openai4s/tests -t integration/openai4s -v

``sys.path`` only reaches this process.  The tests also start child processes
(``python -m mhs.reference``, the ``mhs.mcp`` connectors that OpenAI4S's
``MCPConnection`` spawns, the crash and ledger helpers), so the same source
trees are exported on ``PYTHONPATH`` and ``PYTHONDONTWRITEBYTECODE=1`` keeps every
process of the run from writing ``__pycache__`` into them.  OpenAI4S starts MCP
connectors with a least-privilege environment; those children get both
variables from their connector row's ``env``
(``host_remediation_support.connector_env``).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve()
_OPENAI4S_INTEGRATION = _HERE.parents[1]
_REPO_ROOT = _HERE.parents[3]

#: The trees the tests import from; the last one wins on ``sys.path``.
SOURCE_TREES = (
    _OPENAI4S_INTEGRATION,
    _REPO_ROOT / "work" / "openai4s-src",
    _REPO_ROOT / "MHS" / "sdk" / "src",
)

for _path in SOURCE_TREES:
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)


def _export_pythonpath() -> str:
    """Put the source trees on ``PYTHONPATH`` in ``sys.path`` order; keep other entries."""
    parts = [str(path) for path in reversed(SOURCE_TREES)]
    for entry in str(os.environ.get("PYTHONPATH") or "").split(os.pathsep):
        if entry and entry not in parts:
            parts.append(entry)
    os.environ["PYTHONPATH"] = os.pathsep.join(parts)
    return os.environ["PYTHONPATH"]


_export_pythonpath()
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

#: Never touch the developer's real ~/.openai4s store during tests.  These are
#: forced (not setdefault) so a developer's exported posture cannot make the
#: suite pass or fail for the wrong reason.
os.environ["OPENAI4S_DATA_DIR"] = tempfile.mkdtemp(prefix="openai4s-mhs-test-")
#: HostDispatcher's permission broker fails closed when headless.  The native
#: path tests exercise the MHS-level permit gate instead, so opt into the
#: documented unattended policy for this isolated test process.
os.environ["OPENAI4S_UNATTENDED_APPROVAL"] = "allow"
os.environ["OPENAI4S_SECRET_STORE"] = "plaintext"
#: Likewise, a developer's own MHS settings never reach the tests.
for _name in ("MHS_CONFIG", "MHS_ENABLED", "MHS_ENDPOINTS"):
    os.environ.pop(_name, None)
