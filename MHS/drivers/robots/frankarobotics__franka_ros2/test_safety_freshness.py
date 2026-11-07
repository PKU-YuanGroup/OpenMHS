"""Stock package/server with source-shaped pending callbacks; no ROS/hardware."""
import threading
import time
import unittest
from pathlib import Path
from mhs.adapter import load_driver
from mhs.driver import build_server,close_server,DriverFailed
from mhs.client import MHSClient,InProcessTransport

HERE=Path(__file__).resolve().parent
MOVE='x-cap.frankarobotics.spine_move.v1'
HALT='x-cap.frankarobotics.spine_halt.v1'
OFF='x-cap.frankarobotics.spine_switch_off.v1'
INPUT={'position':0.2,'velocity':0.1,'acceleration':0.2,'deceleration':0.2}

class SourceSafetyCases(unittest.TestCase):
    def setup_endpoint(self):
        driver=load_driver(HERE,'fake')
        server=build_server(driver,site_limits=HERE/'site-limits.example.json')
        self.addCleanup(close_server,server)
        client=MHSClient(InProcessTransport(server));client.hello()
        device=next(iter(server.devices));client.open_session([device],mode='simulated')
        return driver,server,client,device

    def test_cancel_rearms_before_terminal_but_never_before_achieved_receipt(self):
        driver,server,client,device=self.setup_endpoint();peer=driver.native
        peer.hold_move=True;receipts={};errors=[]
        def move():
            try:receipts['move']=client.invoke(MOVE,INPUT,device_id=device)
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=move,daemon=True);thread.start()
        self.assertTrue(peer.goal_received.wait(1))
        operation=next(iter(server._operations.values()))
        # The e-stop of this device (it declares a re-enable) answers only once the commands in flight settled and
        # the stop path ran again (CORE-086), so it is sent from its own thread while the cancel path plays out.
        stops=[]
        stopper=threading.Thread(target=lambda:stops.append(client.estop('cancel pending move',device_id=device,
                                                                         deadline_ms=1000)),daemon=True)
        try:
            stopper.start()
            self.assertTrue(peer.cancel_received.wait(1))
            self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
            self.assertNotEqual(client.reset(device_id=device).get('result',{}).get('status'),'completed')
            peer.rearm_cancelled_motion()
            self.assertEqual(peer.state,'SwitchedOn')
            self.assertFalse(operation.done.is_set())
            self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])
            self.assertEqual(stops,[])                     # no e-stop answer before the terminal
            safe_action=client.invoke(OFF,{},device_id=device)
            self.assertNotEqual(safe_action['status'],'completed')
            self.assertEqual(peer.state,'SwitchedOff')  # independent stop did dispatch
            peer.finish_cancelled_motion()
            operation.thread.join(2);thread.join(2);stopper.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            self.assertEqual(peer.state,'SwitchedOff')
            self.assertTrue(driver.inner.safety_status()['safe_state']['achieved'])
            self.assertEqual(client.get_operation(operation.operation_id)['status'],'cancelled')
            self.assertEqual(len(stops),1)
            if stops[0]['output']['safe_state_achieved']:  # claimed only after the terminal and a fresh stop
                self.assertEqual(peer.state,'SwitchedOff')
        finally:
            if peer.pending_goal is not None:
                peer.rearm_cancelled_motion();peer.finish_cancelled_motion()
            thread.join(2);stopper.join(3)

    def test_halt_rearm_clears_prior_safe_stamp_through_stock_command(self):
        driver,server,client,device=self.setup_endpoint()
        self.assertEqual(client.invoke(OFF,{},device_id=device)['status'],'completed')
        self.assertTrue(driver.inner.safety_status()['safe_state']['achieved'])
        self.assertEqual(client.invoke(HALT,{},device_id=device)['status'],'completed')
        self.assertEqual(driver.native.state,'SwitchedOn')
        self.assertFalse(driver.inner.safety_status()['safe_state']['achieved'])

    def test_disabled_spine_rejects_move_without_rearming(self):
        driver,server,client,device=self.setup_endpoint()
        self.assertEqual(client.invoke(OFF,{},device_id=device)['status'],'completed')
        receipt=client.invoke(MOVE,INPUT,device_id=device)
        self.assertEqual(receipt['status'],'failed',receipt)
        self.assertEqual(driver.native.state,'SwitchedOff')
        self.assertEqual(driver.native.position,0.25)

class InFlightMoveCases(unittest.TestCase):
    """CORE-086: the e-stop of a device with a declared re-enable waits for every command in flight.

    An e-stop during a running move cancels it; the upstream cancel path quick-stops, waits for the motion worker
    and then re-arms the drive with switch-on before the cancelled result (spine_controller.py:404-434; the fake's
    rearm_cancelled_motion and finish_cancelled_motion barriers).  Here that re-arm lands after the e-stop's first
    switch-off: the attempt is held at its safe-state read (only its first one) while the cancel path finishes.

    Two kinds of guard meet here.  The SDK rule holds the e-stop answer until the commands in flight settled and
    runs the stop path again.  The ROS bridge has its own: a goal still pending, or native activity after a stop,
    leaves the safe state unconfirmed, so the background retry stops the drive again.  The counterfactual removes
    the SDK rule only; the bridge then still ends with the drive switched off, but the e-stop answers before the
    move settled.  The SDK-level counterfactual (tests/safety, a decorated driver without such bridge rules) shows a
    stop confirmed while the device is enabled.
    """

    def run_race(self, *, sdk_rule=True):
        driver = load_driver(HERE, 'fake')
        server = build_server(driver, site_limits=HERE / 'site-limits.example.json')
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server)); client.hello()
        device = next(iter(server.devices)); client.open_session([device], mode='simulated')
        self.assertIs(server.devices[device].bridge, driver)
        peer = driver.native
        peer.hold_move = True
        moved = threading.Thread(target=lambda: client.invoke(MOVE, INPUT, device_id=device), daemon=True)
        moved.start()
        self.addCleanup(moved.join, 2)
        self.assertTrue(peer.goal_received.wait(1))
        operation = next(iter(server._operations.values()))
        original, reached, release, held = driver.safety_status, threading.Event(), threading.Event(), []

        def gated():
            name = threading.current_thread().name
            if not held and name.startswith('mhs-estop-') and not name.startswith(('mhs-estop-native',
                                                                                   'mhs-estop-retry')):
                held.append(name); reached.set(); release.wait(5)
            return original()

        driver.safety_status = gated
        self.addCleanup(release.set)
        if not sdk_rule:
            # The same device without the declaration: the endpoint then treats it as one whose stop does not
            # leave it disabled and keeps the single run of the stop path.
            self.assertEqual(server.devices[device].safety.estop.pop('reenable'),
                             'x-cap.frankarobotics.spine_switch_on.v1')
        stop = client.estop('stop during a running move', device_id=device, deadline_ms=1000)
        self.assertTrue(reached.wait(5))                   # the first run switched off and is held
        self.assertTrue(peer.cancel_received.wait(1))
        peer.rearm_cancelled_motion(); peer.finish_cancelled_motion()   # the cancel path re-arms, then ends
        operation.thread.join(2); moved.join(2)
        self.assertEqual(peer.state, 'SwitchedOn')
        mark = len(peer.sent)
        release.set()
        end = time.monotonic() + 8
        while time.monotonic() < end and server._estop_state[device].get('confirmed') is not True:
            time.sleep(0.02)
        self.assertIs(server._estop_state[device].get('confirmed'), True)
        offs = [m for m in peer.sent[mark:] if m.get('op') == 'call_service'
                and m.get('service') == '/franka_spine_node/switch_off']
        return stop, peer, offs

    def test_the_second_stop_after_the_cancel_rearm_leaves_the_drive_switched_off(self):
        stop, peer, offs = self.run_race()
        self.assertEqual(stop['status'], 'failed', stop)
        self.assertEqual(stop['error']['details']['reason'], 'command_in_flight', stop)
        self.assertTrue(offs)                              # the stop path ran again after the re-arm
        self.assertEqual(peer.state, 'SwitchedOff')

    def test_counterfactual_without_the_sdk_rule_the_estop_answers_before_the_move_settled(self):
        # A device that declares no re-enable keeps the single run of the stop path: the e-stop answers while the
        # cancelled move is still running, and only the ROS bridge's own rules make the background retry stop the
        # drive again after the re-arm.
        stop, peer, offs = self.run_race(sdk_rule=False)
        self.assertNotEqual(stop.get('error', {}).get('details', {}).get('reason'), 'command_in_flight', stop)
        self.assertNotIn('awaiting_operations', stop.get('error', {}).get('details', {}))
        self.assertTrue(offs)
        self.assertEqual(peer.state, 'SwitchedOff')

if __name__=='__main__':unittest.main()
