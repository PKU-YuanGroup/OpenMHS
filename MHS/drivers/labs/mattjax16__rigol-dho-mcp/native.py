"""Hardware factory of the package. It refuses, and imports nothing.

McpClientDriver already refuses every non-fake backend before it resolves this factory.
This module refuses too, so a direct call cannot start the upstream server, open its SCPI
socket or import an MCP library. A native profile needs reviewed evidence first: the
FastMCP wire envelope (pydantic-generated discovery schemas, structuredContent on string
results), ownership of a stdio or HTTP server process, whole-tool retirement and an
instrument-level stop readback. None of it exists for this pin.
"""


def connect(**_options):
    raise RuntimeError('MCP native admission blocked: no reviewed transport, retirement or device-stop evidence '
                       'for rigol-dho-mcp at f9ac7191869845ae46ca714de69a877c388b2530')
