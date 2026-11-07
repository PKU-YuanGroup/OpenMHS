# Contributing

Thank you for helping. This file covers the two common contributions: a **driver package** for one repository of the corpus,
and a change to the **SDK, spec or registry**. Be kind: see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report a safety
or security problem as described in [SECURITY.md](SECURITY.md), not in a public issue.

Licences: code, schemas, SDK, site generator and integrations are MIT ([LICENSE](LICENSE)); specification text and
registry data are CC-BY-4.0 ([LICENSE-docs](LICENSE-docs)). By contributing you license your work the same way.

## 1. Driver packages

The model-facing process is in [`MHS/handoff/`](MHS/handoff/README.md); a human contributor follows the same checklist. The
package for the card `MHS/registry/tasks/<track>/<owner>__<repo>.json` lives in `MHS/drivers/<track>/<owner>__<repo>/`.

Before you open the pull request, every item must hold:

- [ ] Keep changes focused and explain any SDK or schema changes needed by the adapted drivers. Related packages
      may be updated together; CI checks each changed package.
- [ ] `task.json` is the registry card, unchanged.
- [ ] `export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=MHS/sdk/src` and
      `python3 -m mhs.driver check <dir> --backend fake` exits 0 (gates G1 to G9).
- [ ] `python3 -m mhs.driver reference <dir>` was run after the last change to `driver.py`, and `reference.json` and
      `REFERENCE.md` are committed.
- [ ] Every `Limit` and `Fact` cites `source` (`vendor_doc` or `upstream_code`) and `ref` (`path/in/clone:LINE` at the pinned
      commit), and the cited line shows it. A bound nobody states is `Limit.operator_required(...)`, never a guess.
- [ ] `risk` is not below the card's `risk_floor`; a hardware driver has `@estop` and a `safe_state`; the fake uses only
      attributes and commands that exist upstream.
- [ ] `driver.lock.json` says who wrote it (`authored_by`) honestly and has `reviewed_by: null` until a human reviewer
      signs after [`MHS/handoff/REVIEW.md`](MHS/handoff/REVIEW.md).
- [ ] `python3 MHS/handoff/tools/collect.py <dir>` passes. Citation warnings remain visible for source review;
      they do not require an internal publication signature. Hardware activation keeps its operator controls.
- [ ] No generated `check-report.json`, no `__pycache__`, no copy of upstream code.
- [ ] `RESULT.json` states the truth (`pass`, `blocked` with codes, or `skip-proposed`).

CI re-runs the gate on every changed driver directory and never trusts a committed `RESULT.json` or report. A pass is
`contract_checked` evidence on a fake, nothing more.

Maintainers, after merging driver pull requests: `python3 MHS/registry/build_registry.py --jobs 8`, then
`python3 MHS/handoff/tools/prepare.py --sync`, then `python3 MHS/registry/validate.py --no-corpus` (without
`--allow-stale-cards`), and commit the refreshed cards and records. These generated updates may be included with the driver changes.

## 2. SDK, spec, schemas, registry

```sh
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=MHS/sdk/src python3 -m unittest discover -s MHS/sdk/tests -t MHS/sdk
python3 -m unittest discover -s MHS/registry/tests
PYTHONPATH=integration/openai4s:MHS/sdk/src:work/openai4s-src python3 -m unittest discover -s integration/openai4s/tests -t integration/openai4s
python3 MHS/site/check.py
```

- The SDK is Python 3.10+ and standard library only. Safety behaviour (limits, e-stop, reset, permits, receipts) changes
  only with a regression test that fails first.
- After a change to `MHS/schema/`, `MHS/spec/capabilities.json` or `MHS/spec/errors.json`, run
  `python3 MHS/sdk/tools/sync_data.py` and then with `--check`; regenerate the appendices with
  `python3 MHS/sdk/tools/gen_appendices.py`.
- After a change to the corpus-independent registry code, run `python3 MHS/registry/build_registry.py --jobs 8 --check` and
  `python3 MHS/registry/validate.py`.
- Write a line for [CHANGELOG.md](CHANGELOG.md) when behaviour changes.
