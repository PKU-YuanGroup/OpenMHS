# Controlled fixture source facts

OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

The complete thirteen default registrations are in rigol_dho_mcp/server.py:148-601 at f9ac7191869845ae46ca714de69a877c388b2530; source SHA c2daec52a875c1eb910606695dab71af6d160d731ac7a14dc1437911e5651190. These source files are AST/text inputs, never imported.

Channel range 1..4: server.py:230,443,478-479,512. Waveform max_points 10..10000: server.py:517. Other numerical signature descriptions are not verified physical bounds; limits require an operator overlay. The fixture overlay is a synthetic test range only.

Complete waveform return values retain source floor-decimation, statistics and rounded time/voltage arrays (server.py:527-585), including returned count exceeding max_points. This is the complete returned result, not complete raw memory. Screen and memory selector writes remain effects. Memory STOP is a documented precondition that the upstream handler does not enforce (server.py:511-543); the finite declaration requires fresh status before that request and does not implicitly stop a running peer.

Cursor position units depend on the current/manual type (server.py:354-355,375-389). Explicit TIME and AMPLitude bindings use seconds and volts. The omitted-type binding retains source mode-entry/read-current-type order and omits cursor_type in its final request; only the selected axis's typed candidates are applied. OFF and TRACk remain separate complete source branches. This is local request sequencing, not proof against independent native clients.

Configuration invert has no returned readback (server.py:255-265); get_status can stop channel enumeration at the first query error (server.py:174-190). Manual/track/off cursor variants remain complete (server.py:396-433). Measurement invalid/string edge cases are refused if they cannot satisfy finite numeric output (server.py:456-462,494-500). Phase values are degrees; delays seconds (server.py:481-489).

The controlled peer owns all requests and its synthetic STOP state. Native exclusive ownership, server lifecycle/cancellation, transport versions, device stop/readback/late effect ordering, real PNG variants and deployment envelopes remain unproved. Native factories refuse before external import/spawn/connect; no physical stopping claim, device or registry acceptance follows from a fake gate. MIT source notice retained under vendor/LICENSE.
