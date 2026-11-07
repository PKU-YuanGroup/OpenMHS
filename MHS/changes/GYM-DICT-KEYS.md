OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# GYM-DICT-KEYS — preserve literal native keys through bounded action fields

Gymnasium Dict action keys such as `action.left_arm` previously became the limit
path `action.action.left_arm`. The limit engine interpreted the dots as nested
fields, although the native environment expected one literal key. A literal key
could also collide with a genuinely nested Dict member.

The Gymnasium bridge now maps each non-identifier native key to a short
`mhs_key_N` input field. Existing identifier keys retain their spelling and
reserve that name; aliases are assigned in sorted native-key order. Field
descriptions name the exact native key. The same mapping builds the schema and
limits and restores the original native dictionary immediately before
`env.step`. Nested Dicts use the same rule independently at each level. Native
spaces and native keys are unchanged. Non-string action keys are refused rather
than coerced into ambiguous strings.

The limit-path grammar, schema files and ordinary identifier inputs are unchanged.
Aliases describe the current environment space; changing that space requires a
new manifest. Existing direct adapters, including RoboCasa packages that already
restore their own native keys, have not been migrated by this SDK change.

## Validation

- Seven new cases cover literal/nested collisions, reserved names, deterministic
  aliases, punctuation and Unicode, nested reconstruction, rejection before any
  reset/step, and the stock server's limit enforcement and exact native arguments.
- All 56 focused new and existing simulator/family tests passed in the isolated
  development copy. An earlier invocation named a nonexistent test module; the
  corrected run and its log are retained.
- In-memory regeneration of all 251 Gymnasium references in the 582-package
  baseline produced byte-identical JSON and Markdown with the original and
  changed bridge. No package files were rewritten by that comparison.
- Full integrated SDK, corpus and clean-export validation remain pending for the
  combined completion work. No upstream simulator or hardware ran.

Source changes: `MHS/sdk/src/mhs/bridge/gymnasium.py` and the new
`MHS/sdk/tests/bridges/test_gym_dict_keys.py`. Preserved originals, comparison
captures, tests and integration hashes are under the private
`work/handoff-runs/mhs-build-20261102/development/dict-key-aliases/` directory.
