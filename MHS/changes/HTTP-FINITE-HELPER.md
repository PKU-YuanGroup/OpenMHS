OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Finite HTTP workflow helper

This change adds a config-only `HttpDriver` and an `ot2-run-v1`
request profile. A controlled injected peer executes the complete selected
upload/create/play/poll/pause/resume/cancel workflow, owned-run observations and
bounded log artifacts. The helper validates finite requests and responses, keeps
late requests and IDs owned after local timeouts, reserves an independent stop
lane, and defers transport cleanup until retained requests return. No native
HTTP transport exists, and native construction refuses before any factory or
upstream import.

The generic artifact publisher accepts an explicit `artifact_ref` output while
keeping `image_ref` as its default. MCP resource registration preserves the
existing session, principal, TTL, byte-size and digest checks. Exact log bytes
can be retrieved without labelling a log as an image. Ambiguous output
references and failed or cancelled publication abort staged resources.

The compiler, source/wire checker and bridge join the existing gate-integrity
boundary. Source proof is restricted to the exact pinned OT2 client file and
does not establish a server schema, physical effect envelope or retirement
guarantee. Exchange replay checks the complete request and explicitly rebinds
each new local request UUID to one validated consumed record.

The author repair invalidates stop evidence across older normal request
completion, performs at most one bounded protective retry with fresh
observations, and cooperatively stops an owned run on operation cancellation.
Unconfirmed retirement remains unknown. A FIFO cannot block before opened-file
validation; a worker that never starts releases its registration, while an
exception after a real start retains ownership. The same distinction records
cleanup startup failures and allows explicit retry only before any cleanup
thread started. The generated SDK interface is
regenerated without changing its assertions.

Stop proof validation and safety commitment share one critical section. Reset
rechecks current owned-job safety before latch release. A newer active
observation remains effective after either commit and revokes the old job's
settlement, including after reset; it cannot admit a replacement workflow.

Author validation: 166 focused combined SDK tests pass, including existing
image, QCoDeS and Ophyd controls. Applying the cumulative 23-path SDK patch to
the recorded baseline produces the same 407-file SDK; all 64 HTTP tests and
two interface tests pass there
with no production `MHS/drivers` directory. Seven selected full-workflow tests
pass in the separate private OT2 package. All six final unchanged independent
v1/v2 reproducer scripts and the post-reset ownership probe pass against v3,
including both late-play schedules. A separately mapped validation composition
with the accepted core cancellation fix also passes 78 HTTP/interface/core
controls; the HTTP patch contains no server change.

The package's full gate still fails G6 and G8. Empty local ownership cannot
prove remote quiescence, and a finite visible-run list cannot prove deployment
exclusivity. Missing stateful prerequisites and generic positive controls that
omit permits are recorded separately; no gate waiver is introduced. G9 remains
skipped, human signatures remain null, and the package awaits independent
different-model review. No registry family, package, native backend, hardware
run or physical stopping claim is accepted by this change record.

This narrowly versioned OT2 workflow is not general support for the five
waiting HTTP repositories. Common contract dispatch, bounded response handling,
request ownership and artifact grants are reusable; OT2 fields/roles and the
pinned request-shape profile remain protocol specific. Other profiles and
ADPT-030's declaration boundary require separate design and source evidence.

Independent SDK review: 176 focused tests and seven unchanged adversarial scripts pass in a separate tree composed with the accepted ROS reader-close and core cancellation fixes. The 23 SDK paths are accepted for the controlled injected profile. The separate native package remains blocked.

Post-integration validation on 2026-11-04 completed 2,763 SDK tests (five skipped), with every executed test passing and all 409 SDK inputs and 1,034 dependency files unchanged. All 587 existing passing packages pass their complete fake gates with matching stable RESULT digests; strict collection still reports the unchanged, unaccepted MCM3000 binary-PDF citation. The isolated ROS simulator regression passes all four stages and 101 native frames, including shared image-artifact retrieval, with 167 runtime inputs unchanged and clean shutdown. The subsequent regex-lifetime fixture isolation changes one test only; an explicit composition check confirms the package and simulator runtime evidence is unchanged. These checks do not exercise a native HTTP service or establish hardware safety.
