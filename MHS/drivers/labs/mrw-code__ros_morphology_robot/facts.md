# Facts and tags for gh.mrw-code/ros_morphology_robot

Every fact cites its source at commit `bdff1da251c4671dcbe94d7b6fa2d24e22459380`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same entries are in `driver.py`.

| fact | source | ref |
|---|---|---|
| README.md names v2_robot as the final version and robot/ as legacy code kept for completeness. | vendor_doc | README.md:5 |
| portConnection sets the pyserial port and baudrate from the GUI fields and opens the port. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:384-388 |
| Closing the port through portConnection clears portConnectStatus and sets systemCalibrate to False. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:401-414 |
| The control window sets the relative-move speed string to `F50\n`. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:268 |
| The manual step-size spin box is bounded by setMinimum(0.0) and setMaximum(100.0). | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:152-153 |
| A manual relative move writes `$J=G21G91` plus the axis, the spin box's textFromValue of the step value divided by 100.0 and speed_rel to the serial port, then sleeps 0.1 s. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:296-302 |
| Calibration writes `$X\n` and `G10 P0 L20 X0 Y0 Z0\n` to an open serial port and sets the systemCalibrate software flag. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:367-380 |
| HOME writes `G90 G0 X0 Y0\n` only when the port is open and systemCalibrate is true; it does not home Z. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:356-365 |
| getMonitorSystemValues only prints `@GETALLPOS` to stdout; it writes nothing to the port and reads no reply. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:270-274 |
| quitSystem calls explorationThread.stop(), closes the serial port and closes the window; it writes no command to the controller. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:454-457 |
| The exploration stop() sets ThreadActive to false, joins the subscriber thread with timeout 0 and calls quit(); it writes nothing to the serial port. | upstream_code | v2_robot/src/robot_v2/scripts/src/exploration.py:151-155 |
| The exploration run loop busy-waits in `while config.pictureSaved == False` and `while not self.shall_i_move` without checking ThreadActive. | upstream_code | v2_robot/src/robot_v2/scripts/src/exploration.py:90-94 |
| After its row loops the exploration run writes `G90 G0 X0 Y0` to the port. | upstream_code | v2_robot/src/robot_v2/scripts/src/exploration.py:138-140 |
| The v2 ROS subscriber calls rospy.Subscriber on the relative name do_inference_topic (String) and rospy.Publisher on the relative name ready_move (Bool), then rospy.spin(). | upstream_code | v2_robot/src/robot_v2/scripts/subscriber.py:13-19 |
| QtCapture creates a publisher on the relative topic do_inference_topic, initialises the anonymous ROS node inference_trigger and opens the camera with cv2.VideoCapture(0). | upstream_code | v2_robot/src/robot_v2/scripts/src/capture.py:41-51 |
| The exploration thread subscribes to the relative topic ready_move; its callback stores the Boolean in shall_i_move. | upstream_code | v2_robot/src/robot_v2/scripts/src/exploration.py:50-57 |
| The ControlWindow constructor prints every serial port device it lists. | upstream_code | v2_robot/src/robot_v2/scripts/src/control.py:49-52 |

Tags: `microscope`, `morphology`, `stage`, `gcode`, `serial`, `ros1`, `simulated`.

## Scope and limits of this package

- The v2 robot is a PyQt5 desktop application with a pyserial G-code channel. The ROS 1 nodes are an auxiliary
  inference trigger (`do_inference_topic` -> `ready_move`), not the motion controller.
- The driver exposes the manual single-axis relative moves, calibration and the X/Y home command. It does not expose
  the camera/JPG capture path, the exploration loop or the ROS inference handshake.
- The upstream has no position feedback: `getMonitorSystemValues` only prints a request and returns None. The
  `calibration_flag` read is the upstream software flag, not sensed stage position.
- The upstream has no stop command. `quitSystem()` (control.py:454-457) stops the exploration thread, closes the
  serial port and the window, and writes nothing to the controller; `explorationThread.stop()` clears a flag that
  the busy-waits at exploration.py:90-94 do not check. Since the model review of 2026-11-05 the `@estop` runs that
  Exit path and then raises `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held, and `close_command_channel` is an
  ordinary action, not a safe-state action: closing a transport is not a stop. The gate fails G6.ESTOP_FAILED and
  G8 SAFE-028, and the package is blocked (`NO_HARDWARE_FREE_PATH`).
- The device is a real Arduino G-code stage with a camera, not a simulator; the card's `simulated` mode comes from
  the registry record. Reopening the port through the upstream toggle clears the calibration flag (control.py:
  401-414), so the stage must be calibrated again. The upstream window needs a Qt display and prints to stdout.
- The fake formats the divided step with `%g`; the upstream QDoubleSpinBox.textFromValue uses the spin box's decimals
  and locale (Qt, outside the clone), so the exact G-code strings asserted in the tests are fake-only.
- The fake is F0: it records one-way G-code writes and changes placeholder GUI/state values. It does not run G-code,
  move a motor, capture an image or contact ROS.
- No hardware backend, ROS graph or live device was used. `driver.lock.json` keeps `reviewed_by: null`.
