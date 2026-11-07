OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Literal composition of a ROS endpoint, and the Webots demo sensed stop

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05, run
`ext-p5-sdk-names--literal-20261105`. This is unit part (1) of item p5-sdk-names only: gate G7 accepts a ROS
endpoint built from string literals joined by `+`, and `robots/jackymao1999__webots_demo` uses that for its
sensed stop. Parts (2) and (3), a name composed from a deployment value and a multi-element read-back, are
other units and are not in this tree. Not integrated. `reviewed_by` stays null. No hardware, ROS graph, Webots
process, network, install or human review is involved. The package evidence is fake `contract_checked` only.

## What was taken from the stopped attempts

A stopped Claude attempt at `development/p5-sdk-names/project` had an unfinished `ros_names.py` and a
`ros_check.py` edit. This unit took the literal-operand shape and the Webots concatenation
`ROBOT_NAME + "/" + std::string(motorNames) + std::string("/set_velocity")`, checked both against
`include/webots_ros.h:104`, `src/demo_2dnav_move.cpp:18` and `:21`, and rewrote the checker. Every initializer
in the cited span must include the declared literal, and the token on the other side of a newline still has to
bound the expression. The deployment-name half and the multi-element `where` edit in that `ros_check.py` were
not taken. The stopped Grok tree at `development/ext-p5-sdk-names.fast-stopped/project` had no file that
differed from its base manifest, so nothing was taken from it.

## Gate G7

`mhs.driver.ros_names` is internal. `mhs.driver.__all__` does not export it. A binding may declare `compose`,
a list of 2 to 8 operands. A literal operand has only `code`. A name operand has `code`, `value` and `ref`,
and may have `via` (1 to 4 citations). A `deployment` key is refused. The checker reads C, C++ and Python
only. It refuses escapes, f-strings and adjacent string literals that are not joined by `+`. ROS 1 cleaning
collapses repeated slashes and drops a trailing slash. ROS 2 rejects both and is not repaired. No leading
slash is added. The cleaned string must equal the binding's `source_name`. Omitting `source_name` compares
the absolute endpoint, so a relative composition does not match it.

`check_ros_surface` (`mhs/driver/ros_check.py`) calls `_composed_name` only when `compose` is present, and
that call replaces `_name_shown`. A binding without `compose` still needs the endpoint as one literal
(`G7.ROS_ENDPOINT_NOT_UPSTREAM`). One `G7.ROS_COMPOSED_NAME` is reported, the first problem. A citation that
`_source_text` already rejected is not reported again. Sensed-stop request steps and ordinary commands cannot
cite a companion (`companion_ok` is false).

The check does not prove that the literal defined at `ref` reaches the expression across a call, a member or
a loop index. The reviewer traces every `via` line. `MHS/sdk/docs/ros-driver.md` says this after the
`source_name` paragraph, and `MHS/handoff/REVIEW.md` item 5 says it after the ROS 1 latched-message sentence.

`compose` is gate evidence. `RosBridge._BINDING` accepts the key (`mhs/bridge/ros.py`) and the compiled
binding does not copy it. An unknown key is still refused.

Tests are `MHS/sdk/tests/driver/test_ros_composed_names.py` (20) plus the existing
`tests.driver.test_ros_gate` (24), which still pass with no `compose`. Mutants, each run against the compose
suite and then removed: `collapse_off` and `collapse_ros2` (ROS 1 cleaning and the ROS 2 refusal),
`any_definition` (one initializer is not enough), `skip_chain` and `skip_boundary` (a partial concatenation
is not the expression), `via_ignored`, `literal_unescape`, `ignore_value`, and `comment_counts` (comment text
tokenized as code). Each one failed at least one test. The tree was restored and the suite passed again.

## Package

`robots/jackymao1999__webots_demo` stays a repair. `authored_by` remains `deepseek-v4.1-flash:1017`, run
`ros-wave-c-130`. `reviewed_by` stays null. Before this repair the gate failed only `G6.ESTOP_FAILED`
(`HELPER_MISSING`), digest `sha256:402e83349ac7e1abde87e9e3f53914eb9e45b7ce813da70ee1eeb746c34a2e63`. That
digest was a blocked result, not a passing digest. After the repair the fake gate passes, evidence
`contract_checked`, digest `sha256:45eea84ece0fd8ee99414e8aa4691d756e292ef40c402903e2ee618bd2db1459`. G8
warns `SAFE014_NOT_APPLICABLE` because no actuating capability declares a numeric limit. The registry card
is still the blocked card until integration. This unit did not rebuild the registry and did not edit
`task.json` or `driver.lock.json`.

The stop is `safety_bindings.sensed_stop` on the simulated `RosDriver` (`driver.py`). It calls
`webots_ros/set_float` with value 0 on `/robot/left_motor/set_velocity` and
`/robot/right_motor/set_velocity`. `compose` is the expression at `include/webots_ros.h:104`. `ROBOT_NAME`
is the literal `"robot/"` at `src/demo_2dnav_move.cpp:18`. `motorNames` is `"left_motor"` and `"right_motor"`
at `:21`. The raw concatenation is `robot//<motor>/set_velocity`. ROS 1 cleans it to
`robot/<motor>/set_velocity`, and `source_name` is that relative name. `via` cites the constructor call
(`src/demo_2dnav_move.cpp:26`), the member assignment (`include/webots_ros.h:48-50`), the loop
(`src/demo_2dnav_move.cpp:34-36`) and the parameter (`include/webots_ros.h:101`). Those lines show the name.
They do not prove it is the same object as the literal. The C++ success test is `response.success == 1`
(`include/webots_ros.h:106`). `srv/set_float.srv:1-3` says the response field is `bool success`. The binding
compares boolean true.

The confirmation reads `point.x` and `point.z` of `/robot/gps/values` and `orientation.x`,
`orientation.y`, `orientation.z` and `orientation.w` of `/robot/inertial_unit/quaternion`. The GPS
source records `source_name` `gps/values`, the quoted literal inside `std::string("gps/values")` at
`src/robot_broadcaster_gmapping.cpp:126` (the cite is `:123-126`). The callback reads both fields at
`:85-89`. The inertial source records `source_name` `inertial_unit/quaternion`, the quoted literal at
`:135` (the cite is `:132-138`). The callback reads the four orientation components at `:100-103` and
does not read `angular_velocity`. `ROBOT_NAME` in that file is `"robot/"` at `:23`. The world's
`InertialUnit` node (`worlds/webots_map.wbt:20-22`) has no name field. The clone states no at-rest
bound and no unit, so the spans are `operator_required` and the fixture values `0.01` in
`fixtures/estop-confirmation.json` are placeholders. A quaternion span is the change of each component,
not a geodesic angle. The publishers, including their stamps, are not in the clone. The Webots `ros`
controller that applies `set_velocity` is not in the clone either. Position alone does not confirm an
in-place turn. The request is accepted under sensed confirmation on that basis, the same precedent as
an untraced simulator command whose effect the confirmation has to show.

`src/demo_2dnav_move.cpp:72-87` stores wheel speeds from `/cmd_vel` and does not clear them. The demo
subscribes at `:102` and does not publish `/cmd_vel`. `launch/amcl_demo.launch:60-66` starts move_base,
which publishes `/cmd_vel` (the remap is at `:66`). Either source, the stored speeds or that publisher,
leaves the confirmation unconfirmed. There is no unpause and no re-enable: nothing this package can send
clears a stored speed first (SAFE-042). The 0-value `time_step` request stays an ordinary action. It is
not the stop.
Risk is R2 (REVIEW item 12): a wheel-velocity command a physical robot could consume, even though
`device_kind` stays `world.sim` and the mode stays `simulated`. `estop_latency_ms` is 3500, the two 1000 ms
request budgets plus `confirm_within_ms` 1500. `publish_review` is still required. The licence tag is
`TODO` (`package.xml:16`, card NOASSERTION). The package may not be published.

`safe_state` is one sentence under 500 characters. The competing-publisher limit, the missing controller
and the fact that the 0 `time_step` request is not the stop are in the docstring, `facts.md` and the
`RESULT.json` review, not in that sentence.

The author's `RESULT.json` notes were shortened, at a word boundary, with ` [...]`, so the notes stay within
8000 characters. The earlier model-review paragraph is unchanged. One paragraph was appended, headed
`MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null):`.

## Round 1

A review blocked three gate holes and three false sentences. `shows_definition` now requires the complete
`#define` replacement. Adjacent string literals concatenate, so `#define ROBOT_NAME "robot/" "different"`
is `robot/different` and does not define `robot/`. A function-like macro, a backslash continuation or any
other token does not match. A C or C++ parenthesized comma expression is not an initializer list. A
parenthesized single literal still is, and a brace list still is. `find_chain` rejects a match whose
grouping parentheses have a `+` outside them, on either side. A call, a comma argument and an assignment
still bound the expression, so `include/webots_ros.h:104` and the Python parenthesized assignment still
match. C tokens keep a newline, and a C initializer ends at `;` rather than at that newline.

The sensed stop no longer treats an in-place turn as rest. Besides the GPS spans it requires
`orientation.x`, `orientation.y`, `orientation.z` and `orientation.w` from the gmapping broadcaster's
inertial callback. The fake's `pure_rotation` flag acknowledges a 0-velocity request and does not apply
it, keeps the GPS point fixed, and advances the quaternion. The estop is then `SAFE_STATE_UNREACHED`
(`not_confirmed`) and the reset is `RESET_REFUSED` while that flag persists. `facts.md` no longer lists
the wheel-velocity services as out of scope: the stop commands them, and `SetMotorsPositon`'s
`/set_position` (`include/webots_ros.h:90`) stays uncovered. `demo_2dnav_move` subscribes to `/cmd_vel`
and stores speeds. move_base is the publisher.

`test_ros_composed_names.py` is 23 tests. The 12 mutants, each run against that suite and then removed,
are the original nine plus `macro_first_only`, `paren_comma_is_list` and `larger_concat_off`. Each failed
at least one test. `via_ignored` fails `test_a_via_line_must_show_the_name`. The comment test fails too,
because that mutant makes `shows_name` true for every name; the comment test does not itself exercise
`via`. The package suite is 18 tests. `tests.driver.test_ros_gate` is still 24. The fake gate passes.
Its stable digest is unchanged, `sha256:45eea84ece0fd8ee99414e8aa4691d756e292ef40c402903e2ee618bd2db1459`,
because the report's findings are the same pass with the `G8.SAFE014_NOT_APPLICABLE` note. Evidence remains
fake `contract_checked`. `reviewed_by` stays null.

`python3 MHS/handoff/tools/collect.py --strict` over the 730 packages whose `RESULT.json` status is pass
exited 1. 726 of 730 pass. Five packages have warnings. Zero `RESULT_DIGEST_STALE`. No other passing digest
moved. This package passed again with the same digest and the `G8.SAFE014_NOT_APPLICABLE` note. The four
gate failures and the MCM3000 `UNVERIFIABLE_CITATION` warning are outside this patch.

## Round 2

G7 still accepted an enclosing expression whose value is not the cited concatenation.
`std::string("other/") + std::string(ROBOT_NAME + std::string("/set_velocity"))` compiles to a name that
starts with `other/`: the conversion hid the `+` from the parenthesis walk.
`(ROBOT_NAME + std::string("/set_velocity"), std::string("different"))` is a comma expression whose value
is `different`. `(false ? ROBOT_NAME + std::string("/set_velocity") : std::string("different"))` selects
`different`. Both shapes passed for an ordinary command and for a sensed-stop request.

`larger_concat` now follows a one-argument `std::string`, `string` or `str` conversion and then looks
outside it. A comma beside the match is an argument separator only when the enclosing parenthesis is a
call. A grouping comma is a comma expression and does not match. A `?:` conditional does not match, on
either branch. A call, a call's comma argument, an assignment, and `std::string` around the whole
concatenation still match, including `include/webots_ros.h:104`.

`test_ros_composed_names.py` is 25 tests. The new tests are
`test_a_conversion_a_comma_expression_and_a_conditional_are_not_the_endpoint` and
`test_a_wrapped_concat_a_comma_expression_and_a_conditional_are_refused`. The second refuses those three
shapes for an ordinary command and for a sensed-stop request. The 15 mutants are the previous 12 plus
`conversion_ignored`, `comma_expression_ignored` and `conditional_ignored`. Each was run against that
suite and then removed, and each failed at least one test. `tests.driver.test_ros_gate` is still 24.
The fake gate passes with the same digest,
`sha256:45eea84ece0fd8ee99414e8aa4691d756e292ef40c402903e2ee618bd2db1459`, and the
`G8.SAFE014_NOT_APPLICABLE` note. Evidence remains fake `contract_checked`. `reviewed_by` stays null.

`python3 MHS/handoff/tools/collect.py --strict` over the 730 packages whose `RESULT.json` status is pass
exited 1. 726 of 730 pass. Five packages have warnings. Zero `RESULT_DIGEST_STALE`. No other passing digest
moved. This package passed again with the same digest. The four gate failures and the MCM3000
`UNVERIFIABLE_CITATION` warning are outside this patch.

## Round 3

G7 still accepted an enclosing expression whose compiled value is not the cited concatenation.
`std::string(ROBOT_NAME + std::string("/set_velocity"), 1)` keeps the characters from position 1.
`std::string(...).substr(1)` and `.insert(0, "other/")` do the same kind of rewrite. A lambda
`return (concatenation, std::string("different"))` returns `different`. The checker treated `return`
as a call head, so the comma looked like an argument separator, and it treated every `std::string(...)`
as a one-argument conversion. A postfix after that conversion was outside the span the walk checked.

`conversion_arity` now requires one argument. Any other count is a different value. `postfix_expression`
rejects `.`, `->`, `[`, a call `(`, `++` and `--` immediately after the span, including after a peeled
conversion or a grouping parenthesis. `call_head` does not treat a keyword as a function name, so
`return (span, other)` is a comma expression. Each peel checks the surrounding tokens again. A call, a
call's comma argument, an assignment, a one-argument conversion, and `return (span)` still match,
including `include/webots_ros.h:104`.

`test_ros_composed_names.py` is 27 tests. The new tests are
`test_a_multi_argument_conversion_a_postfix_and_a_keyword_are_not_the_endpoint` and
`test_a_multi_argument_conversion_a_postfix_and_a_keyword_are_refused`. The second refuses the
multi-argument conversion, `.substr`, `.insert` and the `return` comma expression for an ordinary
command and for a sensed-stop request, and it accepts `return` of the concatenation itself. The 18
mutants are the previous 15 plus `conversion_arity_one`, `postfix_ignored` and `keyword_is_call`.
Each was run against that suite and then removed, and each failed at least one test.
`tests.driver.test_ros_gate` is still 24. The author line of this record names the model `grok-4.7`.

`python3 MHS/handoff/tools/collect.py --strict` over the 730 packages whose `RESULT.json` status is pass
exited 1 after 3306.70s. 729 of 730 pass. Two packages have warnings. Zero `RESULT_DIGEST_STALE`. No
passing digest moved. This package passed again with the same digest,
`sha256:45eea84ece0fd8ee99414e8aa4691d756e292ef40c402903e2ee618bd2db1459`, and the
`G8.SAFE014_NOT_APPLICABLE` note. `lightwheelai__lw-benchhub` failed G1, and
`amsikking__thorlabs_mcm3000` kept its `UNVERIFIABLE_CITATION` warning. Both are outside this patch.
`mattjax16__rigol-dho-mcp`, `misterblue__ros2_raspicam_node` and `christianrauch__raspicam2_node` passed
this run, and their gate digests match the recorded `RESULT.json` digests. This unit did not edit them.

## Round 4

G7 still accepted a brace conversion and a conversion whose argument count could not be proven.
`std::string{ROBOT_NAME + std::string("/set_velocity"), 1}` keeps the characters from position 1.
`std::string{...}.substr(1)` rewrites the same string after the braces.
`std::string{...} + std::string("/extra")` and `std::string("other/") + std::string{...}` add text outside
the braces. `std::string(concatenation, 1 < 2)` is the substring constructor, because the comparison is
true. The checker treated `<` as an unclosed template, got no argument count, and then treated that
unknown count as safe. `{` and `}` were boundaries, so the brace conversion never entered the arity check.

`brace_layer` peels a one-argument `std::string{span}`, `string{span}` or `str{span}` and checks the
tokens outside those braces again. A brace conversion whose count is not one, including a count that
cannot be proven, does not match. A brace list that is not that conversion does not match. A compound
statement's braces are not a list. `unproven_conversion` is true when a parenthesized string conversion's
argument count cannot be proven, and that case does not match. `std::string(span, (1 < 2))` still has a
proven count of two. A call, a call's comma argument, an assignment, a one-argument conversion written
with `()` or `{}`, and `return (span)` still match, including `include/webots_ros.h:104`.

`test_ros_composed_names.py` is 29 tests. The new tests are
`test_a_brace_conversion_and_an_unproven_arity_are_not_the_endpoint` and
`test_a_brace_conversion_and_an_unproven_arity_are_refused`. The second accepts `std::string{span}` and
refuses the brace substring, the brace postfix, the brace prefix, the brace suffix, and
`std::string(span, 1 < 2)`, for an ordinary command and for a sensed-stop request. The 20 mutants are the
previous 18 plus `brace_ignored` and `unproven_arity_open`. Each was run against that suite and then
removed, and each failed at least one test. `tests.driver.test_ros_gate` is still 24. The package suite
is still 18. The fake gate passes with the same digest,
`sha256:45eea84ece0fd8ee99414e8aa4691d756e292ef40c402903e2ee618bd2db1459`, and the
`G8.SAFE014_NOT_APPLICABLE` note. Both G7 holes are closed, so this package is not held for them.
`reviewed_by` stays null. Evidence remains fake `contract_checked`. The author line of this record names
the model `grok-4.7`.

`python3 MHS/handoff/tools/collect.py --strict` over the 730 packages whose `RESULT.json` status is pass
exited 1 after 3002.24s. 729 of 730 pass. Two packages have warnings. Zero `RESULT_DIGEST_STALE`. No
passing digest moved. This package passed again with the same digest,
`sha256:45eea84ece0fd8ee99414e8aa4691d756e292ef40c402903e2ee618bd2db1459`, and the
`G8.SAFE014_NOT_APPLICABLE` note. `lightwheelai__lw-benchhub` failed G1, and
`amsikking__thorlabs_mcm3000` kept its `UNVERIFIABLE_CITATION` warning. Both are outside this patch.
`mattjax16__rigol-dho-mcp`, `misterblue__ros2_raspicam_node` and `christianrauch__raspicam2_node` passed
this run, and their gate digests match the recorded `RESULT.json` digests. This unit did not edit them.
## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-06 while composing the phase-5 units onto snapshot-8 (ext-integrator-C). `reviewed_by` stays null. No simulator or hardware run is claimed. OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

The final Codex verdict is `fix_needed`. One open high finding concerns `MHS/sdk/src/mhs/driver/ros_names.py:201`: G7 treats C/C++ character arithmetic as string concatenation. The package decision for `MHS/drivers/robots/jackymao1999__webots_demo` is `block` (`SDK_BUG`), not `accept`. Only this change record is merged. The snapshot-8 text of the record is in `DEV/originals/`. The unit text before this section is in `DEV/originals/before-integration-section/`.

Left out:

- `MHS/sdk/src/mhs/driver/ros_names.py`, `ros_check.py`, and `MHS/sdk/src/mhs/bridge/ros.py`. The open high is the checker itself.
- `MHS/sdk/tests/driver/test_ros_composed_names.py`, `MHS/sdk/docs/ros-driver.md`, `MHS/handoff/REVIEW.md`, and `CHANGELOG.md`. Those files describe or test the unlanded checker.
- The whole `jackymao1999__webots_demo` directory. The decision is `block`.

`ros.py`, `ros_check.py`, `ros-driver.md`, and `REVIEW.md` also changed in `p5-sdk-stampless--all`. That SDK was installed and then removed, because it moves three snapshot-8 passing digests whose package decisions are `block`. Those paths are the snapshot-8 bytes, not this unit's text and not the stampless text.
Round 1 review (Codex, gpt-6.1-sol, a model and not a human, 2026-11-06; reviewed_by stays null) says this delta was built before `collect.py --strict` had zero problems. The two rows are `gh.lightwheelai/lw-benchhub` (`G1.CLONE_MODIFIED` on `lw_benchhub/utils/X7S/urdf/X7S/X7S.usd`) and `gh.amsikking/thorlabs_mcm3000` (`UNVERIFIABLE_CITATION` on `MCM3000_Direct_Serial_Communication.pdf:2`). The reviewer's control run reproduces both on snapshot-8 with the current clone inputs. The orchestrator disposed of this same pair when applying delta B: environment and pre-existing, not a regression (`review/ORCHESTRATOR-DECISIONS.md`). `MHS/handoff/tools/collect.py` keeps `UNVERIFIABLE_CITATION` as a warning until a human signs `reviewed_by`, and `CONTRIBUTING.md` says the same. `MHS/sdk/src/mhs/driver/check.py` says the clone is read-only and that an operator restores it. Neither package is in this delta. Their `RESULT.json` files stay as recorded. `reviewed_by` stays null.
Round 2 review (Codex, gpt-6.1-sol, a model and not a human, 2026-11-06; reviewed_by stays null) keeps the zero-problem `collect.py --strict` prerequisite unmet. logs/collect-r2.log line 1285 is `-- 749 of 750 package(s) pass the gate; 2 with warnings`. Line 1286 is `COLLECT_EXIT 1`. `gh.amsikking/thorlabs_mcm3000` warns `UNVERIFIABLE_CITATION` at line 36. `gh.lightwheelai/lw-benchhub` is `RESULT_UNTRUSTED` at line 844 (`G1.CLONE_MODIFIED` on `lw_benchhub/utils/X7S/urdf/X7S/X7S.usd`). The stage C brief still requires 0 problems before the delta is built. Clearing the citation needs a human signature on `reviewed_by`. Clearing the clone means writing a read-only clone. This rebuild records that the strict collect still exits 1. The medium finding is fixed for `gh.qdeyna/ur10e_2f140_topic_based_ros2_control`: the package page and its explorer row were regenerated from the composed index. The page shows ring 1, Contract Checked, and no declared capability classes. The explorer row is ring 1, 0 capabilities, evidence `contract_checked`, adapter `runnable`. The sketch still lists `cap.device.describe.v1`. The home page, the about page, the search index, and the explorer ring counts were left as they were. A full `site/build.py` was not run. No hardware or simulator run is claimed. `reviewed_by` stays null.
