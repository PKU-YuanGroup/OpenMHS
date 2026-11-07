# Facts and tags for gh.martinhjelmare/leicacam

Every Fact cites its source at commit `5c33a0d6daa179377390eccf40f1fc3e584b2dad`: `upstream_code` for a code or
comment line of the clone, `vendor_doc` for documentation text (README.md, COMMANDS.md). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| CAM messages are /key:value pairs joined by spaces, for example b'/cmd:val /cmd2:val2' | upstream_code | src/leicacam/cam.py:364-370 |
| Every message carries the client prefix /cli:python-leicacam /app:matrix | upstream_code | src/leicacam/cam.py:49-54 |
| start_scan sends /cmd:startscan and waits for the reply that carries cmd | upstream_code | src/leicacam/cam.py:210-214 |
| stop_scan sends /cmd:stopscan and waits for the reply that carries cmd | upstream_code | src/leicacam/cam.py:216-220 |
| autofocus_scan sends /cmd:autofocusscan and waits for the reply that carries cmd | upstream_code | src/leicacam/cam.py:222-226 |
| pause_scan sends /cmd:pausescan and waits for the reply that carries cmd | upstream_code | src/leicacam/cam.py:228-232 |
| enable sends /cmd:enable with slide, wellx, welly, fieldx, fieldy and value true | upstream_code | src/leicacam/cam.py:243-251 |
| disable sends the same /cmd:enable command with value false | upstream_code | src/leicacam/cam.py:264-272 |
| enable_all sends /cmd:enableall value true and disable_all sends the same command with value false | upstream_code | src/leicacam/cam.py:276-286 |
| get_information sends /cmd:getinfo /dev:<about> and waits for the reply that carries cmd | upstream_code | src/leicacam/cam.py:339-343 |
| wait_for waits timeout minutes (60 by default) and returns an empty OrderedDict when it is reached | upstream_code | src/leicacam/cam.py:171-198 |
| A reply is parsed into an OrderedDict keyed by the /key:value field names | upstream_code | src/leicacam/cam.py:408-436 |
| The CAM socket connects to 127.0.0.1 port 8895 by default | upstream_code | src/leicacam/cam.py:45-46 |
| COMMANDS.md documents startscan as start matrix scan, stopscan as stop matrix scan, pausescan as toggle pause of matrix scan and autofocusscan as start matrix focus scan | vendor_doc | COMMANDS.md:31-34 |
| COMMANDS.md documents enable as enable single scan field and disable as disable single scan field | vendor_doc | COMMANDS.md:37-38 |
| COMMANDS.md documents getinfo as information about the stage, z-drive, COR-ring, job list, pattern list, scan status, experiment, position, load position and autofocus mode and position | vendor_doc | COMMANDS.md:41 |
| The README connects with CAM() and prints the reply of cam.start_scan() | vendor_doc | README.md:56-61 |

Limits: the five indices of `enable` and `disable` (slide, wellx, welly, fieldx, fieldy) are
`Limit.operator_required`. No text of the clone states a range for any of them; the defaults of the upstream method
(src/leicacam/cam.py:234-241) are not bounds. `site-limits.example.json` shows the overlay that supplies them, and until
an operator does, both actions are refused `MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop and the safe-state action `x-cap.martinhjelmare.stop_matrix_scan.v1` both send the CAM `stopscan`
command (src/leicacam/cam.py:216-220). The e-stop sends it without waiting for the acknowledgement, because `wait_for`
allows 60 minutes (src/leicacam/cam.py:171-198); the action uses the upstream `stop_scan`, which waits. No line of the
clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. The driver is R1, below the R2
floor that SAFE-045 applies to.

Tags: microscope, leica, lasaf, cam, matrix scan, autofocus
