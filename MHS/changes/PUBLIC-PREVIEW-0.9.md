OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# First public preview: specification 0.9, SDK 0.9.0.dev0 (2026-11-06)

The owner decided on 2026-11-06 to publish a first public preview with the current version numbers (specification 0.9,
SDK `0.9.0.dev0`, wire revision 1); raising the SDK to 0.9.0 is later work, because the SDK version is part of every
gate's stable digest. The preview contains the specification, the JSON Schemas, the standard-library SDK, the
conformance suite, the capability catalogue, the registry and the driver corpus: 842 done cards (746 passing packages,
85 blocked records with their reasons in `MHS/handoff/BLOCKED.md`, 11 proposed skips).

The owner states that the publication review of the packages marked `publish_review: required` (218, mostly with an
upstream licence that is undeclared, copyleft, proprietary or noncommercial) is complete and approved publishing them
with the rest. Driver packages import upstream code in their hardware backends and never copy it.

Nothing in the preview is a safety certification or a hardware approval: every package's evidence is fake
`contract_checked`, no package was run on hardware, and `reviewed_by` is null everywhere, so a hardware backend still
needs a human reviewer before any use. The name stays OpenMHS; the schema namespace `https://openmhs.invalid/` remains a
placeholder until a release names a real one.
