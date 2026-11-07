OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Complete controlled MCP Rigol fixture

This SDK-only synthetic fixture exercises all thirteen default tools from the pinned Rigol source. It does not author or accept the real repository package. Fake is a backend choice; the declared R0 hardware contract preserves numerical limits and full primary outputs. Native admission always refuses.

Use the stock loader/server/MCP projection. All selected operations, optional fields, six run actions, manual/track/off cursors, both complete returned waveform modes and the exact supported PNG screenshot are retained. JSON waveform/cursor primary results are scoped artifacts; small results remain inline. Raw SCPI is not exposed. See facts.md for source and remaining native limitations.

Sixteen finite bindings cover the thirteen tools. The three additional cursor bindings retain explicit time/amplitude positions and the source's omitted-type branch: enter manual mode, read the retained type, and apply only the matching seconds/volts candidates while omitting cursor_type. Fresh STOP readback is required before memory acquisition; ordinary stop is never inserted implicitly.

Stock fake G1-G9 passes with synthetic-card and unresolved-native warnings. This does not accept a real package, license, physical stop or family routing. The public server response boundary isolates returned receipt metadata; the controlled mutation witness also checks unchanged replay/store descriptors and no extra remote call.
