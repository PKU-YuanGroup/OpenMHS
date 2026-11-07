OpenMHS is an independent project, not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Preserve literal code in documentation search descriptions

The site generator removed underscore and asterisk characters from inline code while extracting a document's leading
description. The correctly spelled PointCloud2 capability became a different, nonexistent identifier in the generated
search index, causing the release site checker to fail. Lead extraction now removes inline-code delimiters while
preserving their literal content; prose emphasis still becomes plain text. No capability, SDK runtime or driver changes.

A regression uses the actual PointCloud2 guide and other literal code/link/emphasis examples. The unchanged assertion
fails on the old generator and passes after the fix. The complete release site build and freshness check must also pass;
the failed export and all its successful runtime-suite results remain retained separately.
