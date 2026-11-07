OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Local image artifacts

Image capabilities can now return a primary image that the calling MCP session can retrieve. The endpoint owns
an explicitly enabled, bounded temporary store; drivers stage bytes through their execution context and return
the corresponding image reference. Successful output validation and evidence recording publish the grant and
retained receipt together. Failed, cancelled, expired or invalid executions cannot expose staged bytes. Replaying
a command reuses its original receipt and grant without capturing another frame or extending retention.

ROS Image bindings convert supported 8-bit color/mono and unsigned 16-bit mono/depth samples to lossless PNG,
preserving sample values, byte order and row-padding semantics. The optional compressed-image path normalizes
supported decoded pixels to PNG. It does not claim archival validation of every original JPEG entropy byte.
Unsupported encodings, metadata/chunk forms, malformed data and excessive dimensions or byte sizes are refused.
Source-backed non-ROS adapters may publish opaque vendor raw bytes with a truthful MIME type, without invented
endianness, calibration or preview support.

Retrieval requires the original live session, endpoint principal and device/capability/resource grant. MCP also
checks its session ownership and current host policy. There is no arbitrary file/URL fetch or remote transport
fallback. The default store permits 2 MiB per image, 32 MiB total and 128 grants for 300 seconds; an explicit setting
can raise one image to 16 MiB. Only an authenticated registered artifact response receives a correspondingly
larger MCP output allowance, capped at 24 MiB. Other responses and every inbound frame retain the 4 MiB ceiling.
The store is ephemeral, with no persistent index or recovery after process failure.

Independent review rejected the first publication/codec candidate and then found that creating or aborting an
unused publisher could block a safe-state action behind image evidence I/O. The integrated third version creates
publishers lazily and avoids the store lock for empty preparation/cleanup. Production regressions hold image
publication while proving native stop dispatch, a completed client receipt and operation completion before release.
Direct emergency-stop coverage alone had not exercised that path.

Validation: 172 combined tests pass on the integrated SDK. The independent review ran 54 image/artifact cases with
the optional decoder and no skips, reproduced the prior publication/codec defects, and verified a controlled
10,027,008-byte uint16 frame through a 13,376,397-byte actual MCP stdio response with exact reconstructed samples
and digest. Oversized ordinary responses and inbound requests remain refused. These controlled fixtures do not
establish physical camera or corpus-driver compatibility. Real ROS deployment validation is recorded separately;
full SDK, corpus collection and export remain separate checkpoints.

Usage and representation limits are in [Local image artifacts](../sdk/docs/image-artifacts.md). Hardware signatures,
native camera lifecycle correctness, source-backed bounds and publication decisions remain independent requirements.

The acceptance gate now supplies a fresh store with the unchanged default bounds only when the opened fake endpoint binds an image capability. It closes the store on construction and teardown failures, including strict hardware-view checks that still use an unarmed fake. Nine added gate tests pass on actual sources, including full CLI G1-G9, MCP authorization/retrieval and cleanup. The Thorlabs full gate now passes G6 and fails only G8 with the unchanged TSAFE-001 and SAFE-014 terminal-reset findings. No gate waiver or lifecycle reopening was introduced.
