OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Finite controlled MCP clients

`McpClientDriver` declares a finite MCP tool contract over an injected controlled
peer. It reuses ordinary package loading, the resolved hardware model, limits,
permits, receipts, cancellation, and scoped artifact publication. It implements
no external MCP client. Every hardware constructor and the example native
factory refuse before an upstream import, server spawn or connection. Passing
the controlled fixture does not admit a real device or enable a registry family.

The SDK fixture `tests/fixtures/mcp_rigol` is the complete example. It exposes all
thirteen default operations in the pinned Rigol server, including configuration,
six acquisition actions, measurements, cursor variants, screen and memory
waveforms, and the PNG screenshot. The optional raw SCPI escape is unexposed.
Its three additional cursor bindings give the two source-dependent position
units explicit fields without dropping the omitted-type branch. It is a
synthetic SDK fixture, not an authored package for the upstream repository.

The registry family exemplar is the authored package
`MHS/drivers/labs/mattjax16__rigol-dho-mcp`: the same thirteen tools of the same pinned
source, with the real task card and clone, `x-cap.mattjax16.*` ids, an example operator
overlay and repository tests through the stock loader and server. It passes the fake
gate and is fake-only for the reasons below; it adds no native admission.

## Declaration and authority

Declare `mcp_config`, explicit `Action` objects, finite `commands`, optional
read-only `reads`, and a controlled fake factory. The compiler accepts concrete,
bounded JSON only. Every selected tool has a closed input schema, complete
output schema or PNG contract, literal optional defaults, an effect flag, and a
reference into one exact source file and commit. Every tool must have a primary
command. Numeric action inputs require source-backed or operator-required limits;
the fixture's broad overlay is a test range, not a hardware limit. Protocol
configuration writes in an R0 acquisition profile do not alone imply an actuator
hazard. Resolved risk and permit enforcement remain stock SDK responsibilities.

Discovery must match the locally declared tool names and input schemas exactly.
Names, descriptions, annotations and `readOnlyHint` never grant authority. The
only supported remote methods are `tools/list` and the declared `tools/call`
operations. No caller-supplied executable, endpoint, tool name, credential, code,
SCPI program, filesystem path or follow-up URL is accepted. Native factories
remain blocked even for an R0 package; unsigned R2/R3 admission also retains the
stock loader's review requirement.

Ordinary command arguments pass through unchanged by default. A finite argument
map may rename action fields or supply literal constants. It cannot reinterpret
a source-declared unit or change a value's concrete schema. A source-cited
selection can perform one constant preparation and one read-only observation,
then choose one of at most eight declared argument maps. It cannot evaluate an
expression or choose an undeclared tool. A malformed selector after preparation
leaves the effect unconfirmed.

The Rigol retained-cursor-type binding first enters manual mode, as the pinned
handler does, reads the retained type, and applies only that axis's supplied
positions. Time candidates use seconds and amplitude candidates use volts. It
omits `cursor_type` in the final call; candidates for the other axis are not
applied. Separate bindings set an explicit TIME or AMPLitude type. Manual, track
and off paths remain available. Memory waveform acquisition also preserves the
source's STOP prerequisite: a fresh status check must pass before acquisition;
the helper does not silently issue an ordinary stop on the caller's behalf.

## Ownership and stopping

An injected peer implements `exchange(message, timeout_ms=..., lane=...)` and may
implement owned `close()`. The message carries a unique JSON-RPC identity. The
peer must return a concrete response object; wrong IDs, protocol errors,
`isError`, declared normal-text errors, incomplete data, and conflicting primary
representations are refused. Local timeout does not prove that an external
request ended. Its worker and identity remain owned until actual retirement;
an unknown effect is never automatically resubmitted.

Ordinary transactions serialize so local configuration cannot interleave between
a declared prerequisite and its effect. A separate protective lane never waits
for that ordinary mutex. A declared protective command plus fresh observation
can establish only the controlled peer's state after older requests retire.
There is at most one bounded protective retry after a superseded observation.
The proof's generation and pending owners are checked and committed together;
reset revalidates the exact current proof. A later contrary observation revokes
it. A successful-looking response, RPC cancellation, local flag, transport
disconnect, or closing a worker is not physical-stop evidence.

Close prohibits new calls and publication immediately, retains pending workers,
and invokes owned peer cleanup after retirement. Thread-start failure before
startup removes an owner that never ran; failure after real startup retains it.
A cleanup worker that never starts can be retried by another close. A peer that
ignores its timeout can remain owned indefinitely; native transport retirement
and deployment-wide quiescence remain unresolved admission requirements.

## Complete outputs and limits

Small complete results remain inline. Large JSON results use `artifact_ref`;
supported screenshots use `image_ref`, width, height and media type. The stock
artifact transaction supplies principal/session ownership, digest, size, TTL,
replay and resource retrieval. An immutable per-result descriptor records the
tool, request identity, source digest and `complete_returned_result` coverage.
Publication checks cancellation, close and the stop epoch before and after
staging; the server commits it with the final receipt. Store preflight occurs
before acquisition. No remote resource or local-path fallback is followed.

The concrete JSON envelope is bounded to 16 MiB, depth 16, 262144 nodes, arrays
of at most 65536 elements, and exact integers within ±(2^53−1). Each declared
message/output adds its own finite byte bound. The Rigol fixture uses a 1 MiB
waveform JSON bound and a 1 MiB PNG bound. A requested `max_points` is not a result
budget: the upstream floor-decimation can return more points. Every returned
time/voltage element, count, statistic and source rounding is retained; this is
not a claim to all raw memory samples. `include_data=false` preserves its
complete statistics-only source variant. Malformed arrays or an undeclared
summary cannot substitute for the selected primary result.

PNG validation checks base64, format, pixel and byte limits and decoder
completion while preserving exact supported bytes. It does not prove an image
is a full sensor frame, fresh, calibrated or synchronized. Other encodings and
device-specific screenshot variants require separate evidence. The controlled
3×2 PNG and synthetic waveform arrays are test data, not real Rigol captures.

## Source and integration boundaries

G7 checks exact source bytes and pin, literal tool registration, function
arguments/defaults and source ranges without importing upstream code. Recorded
requests must stay inside the finite names, arguments, lanes, deadlines and
identities. This is a necessary source/wire check, not a semantic proof of every
effect or output. G3 preloads and fingerprints the compiler, checker, bridge and
driver, including their policy containers and compiled regular expressions.

The selected source is `rigol_dho_mcp/server.py` at
`f9ac7191869845ae46ca714de69a877c388b2530`. Source facts and MIT notice are retained
in the fixture. Status can contain fewer channels; invert has no invented
readback; measurement and waveform selectors remain effects. Native MCP
framing, authentication, dependencies, whole-operation timeouts, request
retirement, concurrent protective transport, actual PNG compatibility and
device stopping are unresolved. Microscope, LumiPy and Siglent source assessments
remain separate; this fixture implements none of those packages and resolves no
publication or license requirement for them.

The public server response boundary copies decoded results before returning them.
Caller mutation of nested receipt metadata cannot alter the retained receipt or
its later replay. The controlled artifact witness checks the original receipt,
unchanged store descriptor and absence of a new remote call; separate standard
SDK tests cover nested ordinary output, errors and operation lookup. These
in-process ownership checks do not authenticate native device measurements.

## SDK-owned controlled stdio

`mhs.bridge.mcp_stdio.OwnedStdioTransport` adds a concrete POSIX test transport
for the SDK's own `tests/fixtures/mcp_stdio_peer.py`. The peer executes the
existing complete controlled Rigol fixture. This is a controlled checkout
facility, not a launcher for arbitrary MCP servers: no parameter selects an
executable, module, shell command, endpoint or credential. Native Driver and
factory entrypoints still refuse before any import, spawn or connection.

The caller supplies an existing private directory owned by its user (mode
0700). Construction validates that directory but starts nothing. Stock fake
loading may inject the concrete object as `native=peer`; the first admitted
exchange starts the fixed child. Its source digest is verified before execution
and those exact bytes execute in the same interpreter with `-I -S -B -u`, an
explicit minimal environment, closed inherited descriptors and a new process
group. Isolated mode ignores Python environment flags, so `-B` is explicit.
The fixed peer consumes bounded test data from the private directory; it does
not execute supplied code, import upstream MCP/device modules, or open sockets.

Initialization selects only MCP `2025-11-25`, advertises no optional client
capabilities, checks the correlated initialization result and tools capability,
then writes `notifications/initialized` before any tool request. Only
`tools/list` and `tools/call` are admitted by the exchange API. Remote
instructions remain inert diagnostic data. Ping receives a bounded reply;
other inbound requests receive method-not-found, and notifications receive no
reply. Fixed discovery changes permanently fence the owner. Discovery retains
the existing exact local schema check and never expands local tool authority.

One reader reconstructs newline-delimited UTF-8 JSON across pipe chunks. LF and
CRLF are accepted; banners, blank lines, Content-Length framing, batches,
duplicate keys, nonfinite values, wrong-typed/unknown/duplicate response IDs,
and ambiguous result/error envelopes are rejected. Result objects are not
heuristically unwrapped. Bounded protocol errors and tool errors remain complete
diagnostic evidence and never become success or retirement proof.

`StdioBudget` can reduce, but cannot increase, these software ceilings:

| Resource | Ceiling |
| --- | --- |
| One incoming JSON frame | 16 MiB |
| Aggregate retained response, decoding and partial wire bytes | 32 MiB |
| Outgoing JSON / initialization result | 64 KiB each |
| One control frame / retained stderr tail | 4 KiB / 64 KiB |
| Handshake / complete-frame write | 2000 ms / 100 ms |
| Graceful / TERM / KILL observation stages | 250 / 250 / 500 ms |
| Lifetime identity ledger | 4096 entries, with four final protective exchanges reserved |
| Control traffic | 64 frames per second and 1024 per pending request |

Wire budgets are logical byte reservations, not an operating-system RSS limit.
The existing depth, node, array and exact-number bounds apply independently to
decoded values. Handshake diagnostic storage and the stderr tail have their
separate finite ceilings. JSON frame sizes exclude the terminating newline;
partial-buffer reservation is conservative and includes received delimiters.
The finite writer queue reserves capacity for control and protective traffic.
An ordinary and a protective request may be pending together; frames never
interleave. A partially written ordinary frame cannot be preempted with another
JSON frame, so its finite write deadline fences the peer instead. Parsing and
stderr draining do not own the writer lock. None of these limits is a physical
instrument bound or a hard real-time guarantee.

IDs are never reused during the owner's lifetime. Caller timeout or cancellation
returns an unknown outcome through the bridge while its worker and request ID
remain retained through confirmed software retirement. At most one best-effort
`notifications/cancelled` is sent for a completely issued ordinary/tool request;
none is sent for initialization or an unissued request. Cancellation replies,
late success, EOF and child exit do not prove device quiescence. There is no
automatic retry, reconnect or respawn. A valid late result cannot create a
grant for an abandoned operation.

Terminal health is sticky. Idle EOF and non-effectful exchange or semantic
result failures revoke a cached controlled safety proof. The concrete bridge
and owner use one consistent lock order to check the live owner epoch and
commit stop/reset proof atomically. A later loss revokes current status while
historical receipts remain unchanged. Healthy controlled peers can still
settle older work using a fresh bounded stop/read attempt; legacy in-process
controlled peers retain their existing behavior. Once this stdio owner is
fenced, reset cannot reopen it or clear uncertainty by observing process exit.

Close is nonblocking and immediately revokes proof. A supervisor closes stdin,
then uses bounded TERM/KILL stages for its process group, drains/closes owned
streams and reaps its child. A missing cleanup observation leaves the bounded
owner `RETIREMENT_UNCONFIRMED`; it neither reports completion nor admits another
child. Request and cleanup threads that actually started remain owned even if
their startup acknowledgement raises. A failed notification cannot strand
process retirement.

The library installs no host-wide signal handler. Tests that interrupt cleanup
explicitly install a **caller-owned deferring policy that keeps the host alive**.
That is not evidence for default SIGTERM, SIGKILL, interpreter crash or abrupt
host death: an in-process supervisor cannot survive those events. Abrupt-host
cleanup and Windows process ownership remain unsupported. Killing the owned
group cleans software resources; it cannot reverse an already delivered SCPI
command or establish instrument quiescence.

## Native compatibility remains a separate decision

The static source assessment pinned MCP Python SDK v1.29.0 and the
`2025-11-25` protocol. The selected Rigol source defaults to stdio at its console
entrypoint, but its container defaults to HTTP. Its synchronous FastMCP tool
body can block the event loop and therefore does not establish an independent
native protective lane. SCPI locks/timeouts do not prove whole-tool retirement
or exclusive ownership against another instrument client.

The source-derived native discovery also differs from this fixture's closed
schema. FastMCP string returns can contain both text and
`structuredContent={"result": ...}`. This controlled profile rejects that dual
representation and the incompatible discovery without stripping wrappers or
dropping primary data. A native envelope profile and upstream/device retirement
contract need separate review. Complete controlled 13-tool/16-binding pipe,
loader, server and MCP tests establish no native Rigol admission, physical stop,
package qualification, registry enablement or publication clearance.
