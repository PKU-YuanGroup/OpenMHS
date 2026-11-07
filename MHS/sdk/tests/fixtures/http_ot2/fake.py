"""Controlled HTTP peer, never a server emulator or native client.

The pinned client supplies the HTTP routes/body shapes. Response fields,
remote retirement and protocol interpretation below are fixture behavior.
No Opentrons, requests, networking or protocol execution is imported.
"""
import base64
import copy
import hashlib
import json
import threading


class FakeOT2:
    def __init__(self, *, auto_complete=True, log_padding=0):
        self.auto_complete = auto_complete
        self.log_padding = log_padding
        self.requests = []
        self.uploads = {}
        self.runs = {}
        self.closed = False
        self.close_calls = 0
        self.close_error = False
        self.close_entered = threading.Event()
        self.close_release = None
        self.started = threading.Event()
        self._lock = threading.RLock()
        self.blocks = {}
        self.mutators = {}
        self.stop_state = 'stopped'
        self.late_play_after_stop = False

    def block(self, role):
        entered, release = threading.Event(), threading.Event()
        self.blocks[role] = (entered, release)
        return entered, release

    def role(self, message):
        path = message['path']
        if path == '/protocols': return 'upload'
        if path == '/runs': return 'create' if message['method'] == 'POST' else 'list'
        if path.endswith('/commands'): return 'commands'
        if path.endswith('/actions'): return message['json']['data']['actionType']
        return 'status'

    def request(self, message, *, timeout_ms):
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError('finite timeout is required')
        role = self.role(message)
        with self._lock:
            if self.closed: raise RuntimeError('closed fixture peer')
            self.requests.append(copy.deepcopy(message))
        blocker = self.blocks.get(role)
        if blocker:
            blocker[0].set()
            blocker[1].wait(10)  # Test release is bounded even after assertion failures.
        with self._lock:
            if role == 'upload':
                upload = message['multipart']
                data = base64.b64decode(upload['data_base64'], validate=True)
                if upload['field'] != 'files' or len(data) != upload['size_bytes'] or hashlib.sha256(data).hexdigest() != upload['sha256']:
                    raise ValueError('invalid fixture upload')
                ident = 'protocol-' + str(len(self.uploads) + 1)
                self.uploads[ident] = data
                body, status = {'data': {'id': ident}}, 201
            elif role == 'create':
                protocol = message['json']['data']['protocolId']
                if protocol not in self.uploads: raise ValueError('unknown protocol')
                ident = 'run-' + str(len(self.runs) + 1)
                self.runs[ident] = {'id': ident, 'protocolId': protocol, 'status': 'idle', 'current': True}
                body, status = {'data': {'id': ident}}, 201
            elif role == 'list':
                body, status = {'data': list(self.runs.values())}, 200
            else:
                ident = message['path'].split('/')[2]
                run = self.runs[ident]
                if role == 'play':
                    if run['status'] != 'stopped' or self.late_play_after_stop:
                        run['status'] = 'running'
                    self.started.set()
                    body, status = {'data': {'actionType': 'play'}}, 201
                elif role == 'pause':
                    run['status'] = 'paused'
                    body, status = {'data': {'actionType': 'pause'}}, 201
                elif role == 'stop':
                    run['status'] = self.stop_state
                    body, status = {'data': {'actionType': 'stop'}}, 201
                elif role == 'commands':
                    body, status = {'data': [{'id': 'command-1', 'commandType': 'aspirate',
                                               'status': 'succeeded', 'fixture_payload': 'x' * self.log_padding}],
                                    'meta': {'cursor': 0, 'totalLength': 1}}, 200
                elif role == 'status':
                    if self.auto_complete and run['status'] == 'running': run['status'] = 'succeeded'
                    body, status = {'data': dict(run)}, 200
                else:
                    raise ValueError('unsupported controlled route')
            raw = {'request_id': message['request_id'], 'status': status,
                   'headers': {'Content-Type': 'application/json'},
                   'body': json.dumps(body, separators=(',', ':'))}
        mutate = self.mutators.get(role)
        return mutate(raw, message) if mutate else raw

    def close(self):
        self.close_entered.set()
        if self.close_release is not None: self.close_release.wait(10)
        self.close_calls += 1
        self.closed = True
        if self.close_error: raise RuntimeError('fixture close failed')


def connect(**options):
    return FakeOT2(**options)
