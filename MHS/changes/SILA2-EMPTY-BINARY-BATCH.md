# Preserve unknown Binary ownership after an empty sample batch

OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

A controlled observable Binary request could allocate a transfer and return an empty sample batch. The caller rejected the missing sample, but the ownership collector treated the empty batch as complete identification and removed its request debt. A later stock Stop and reset could therefore succeed while the peer still retained an unidentified transfer.

An empty batch now retains its original allocation debt regardless of the stream end flag. Known streams may still close, but their cleanup and execution-retirement observations do not prove that the missing Binary transfer was retired. No returned value, operation cardinality, finite resource bound, Stop/reset predicate or native-admission rule is relaxed.

Three stock Driver/server/permit/MCP regression methods cover both empty-batch end flags, missing batch/sample controls and the complete 72-byte PNG result. The two empty-batch subcases fail against unchanged predecessor code; all three methods and ten existing resource methods pass after the repair. Full composed validation and independent review remain separate evidence requirements. The observable-property declaration is controlled test coverage for the generic helper, not a change to Phenix's pinned unary property or a claim of native compatibility.
