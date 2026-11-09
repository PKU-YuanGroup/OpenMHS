# Release preparation: portable image tests and host boundaries

## Changes

- Support the maintained Pillow 12.3 line on Python 3.10 alongside Pillow 13,
  with the same strict image validation and truncated-image refusal.
- Give controlled stdio fixtures enough startup time on hosted runners; keep
  cancellation and late-publication assertions. The image deadline test keeps
  its conversion barrier held past the separate execution budget.
- Add `inherit_env=False` to the Python stdio client for hosts supplying an
  isolated child environment. The compatibility default still inherits.
- Refuse model-supplied filesystem paths in the native OpenAI4S evidence tool.
  Export returns the bundle; saving it uses the host's governed file tools.

## Validation

- Python 3.10 with Pillow 12.3: 85 image, artifact and client tests passed.
- Controlled stdio regressions: 11 tests passed, including the complete CLI gate.
- OpenAI4S integration suite: 130 tests, OK (3 skipped).
- Full SDK regression is running; no hardware execution or human qualification is claimed.
