"""Hardware factory of the package. It refuses, and imports nothing.

The pinned upstream is a single-file MCP server. Its ``OscilloscopeConnection`` is
defined inside ``server.py``; importing that module executes the MCP imports, configures
a file logger in the clone and creates the module-level ``conn``. No reviewed native
profile owns that import, the SCPI socket or the server process, and the upstream
licence is NOASSERTION. A model-authored package therefore does not start a live
backend: this factory refuses before any import, socket or file write. The acceptance
gate uses the fake backend and never imports this module.
"""


def connect(**_options):
    raise RuntimeError(
        "native admission blocked: no reviewed transport, process ownership, stop readback or licence evidence "
        "for lxkang00/oscilloscope-mcp at 3eebcdfb3c339d7038b80a9a31573538bc84a331")
