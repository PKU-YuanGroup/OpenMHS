"""Exact bounded controlled-peer replay, not native SiLA transport evidence."""
from __future__ import annotations

import copy
import threading

from ..driver.sila2_config import canonical, keys, plain


class RecordingSila2Peer:
    def __init__(self, peer, *, max_records=4096):
        if type(max_records) is not int or not 1 <= max_records <= 4096:
            raise ValueError('finite recording bound required')
        self.peer, self.max_records = peer, max_records
        self.records = []
        self._lock = threading.Lock()

    def request(self, message, *, timeout_ms):
        plain(message, binary=True)
        with self._lock:
            if len(self.records) >= self.max_records: raise RuntimeError('recording budget exhausted')
            record = {'request': copy.deepcopy(message)}
            self.records.append(record)
        # No recorder lock surrounds the peer: protective requests remain
        # independent while an ordinary response is deliberately held.
        response = self.peer.request(message, timeout_ms=timeout_ms)
        plain(response, binary=True)
        with self._lock:
            record['response'] = copy.deepcopy(response)
        return response

    def close(self):
        self.peer.close()


class Sila2ReplayPeer:
    """Consume complete request/response pairs once, in recorded order.

    Only explicit local request, owner and bridge-generation UUIDs are rebound.
    Remote execution, stream and binary UUIDs remain exact. This synchronous
    replay does not model recorded concurrency, timing, transport errors or
    native work. An incomplete recording is refused before the first request.
    """
    def __init__(self, records):
        if type(records) is not list or not 1 <= len(records) <= 4096:
            raise ValueError('finite complete replay required')
        total = 0
        seen = set()
        for row in records:
            keys(row, {'request', 'response'}, {'request', 'response'}, 'record')
            plain(row, binary=True)
            total += len(canonical(row))
            if total > 16 * 1024 * 1024: raise ValueError('replay aggregate budget exceeded')
            request, response = row['request'], row['response']
            for key in ('request_id', 'owner_id', 'generation', 'feature', 'member', 'operation'):
                if canonical(request.get(key)) != canonical(response.get(key)):
                    raise ValueError('recorded response identity differs')
            if request['request_id'] in seen: raise ValueError('duplicate recorded request')
            seen.add(request['request_id'])
        self._records = copy.deepcopy(records)
        self._index = 0
        self._mapping = {'request_id': {}, 'owner_id': {}, 'generation': {}}
        self._lock = threading.Lock()
        self.closed = False

    def _bind(self, kind, old, new):
        mapping = self._mapping[kind]
        if old in mapping:
            if mapping[old] != new: raise ValueError('replay local identity changed')
        elif new in mapping.values():
            raise ValueError('replay local identities are not one-to-one')
        else:
            mapping[old] = new

    def request(self, message, *, timeout_ms):
        plain(message, binary=True)
        if type(timeout_ms) is not int or timeout_ms <= 0: raise ValueError('bounded request required')
        with self._lock:
            if self.closed or self._index == len(self._records): raise RuntimeError('replay closed or exhausted')
            row = self._records[self._index]
            expected = copy.deepcopy(row['request'])
            for key in ('request_id', 'owner_id', 'generation'):
                self._bind(key, expected[key], message[key]); expected[key] = message[key]
            for key in ('stream_owner', 'binary_owner'):
                if key in expected['payload']:
                    expected['payload'][key] = self._mapping['owner_id'].get(expected['payload'][key], expected['payload'][key])
            if canonical(expected) != canonical(message): raise ValueError('exact replay request differs; no placeholder matching')
            self._index += 1
            response = copy.deepcopy(row['response'])
            for key in ('request_id', 'owner_id', 'generation'): response[key] = message[key]
            if message['operation'] == 'observe' and 'payload' in response:
                response['payload']['retired_owners'] = [self._mapping['owner_id'].get(old, old)
                                                       for old in response['payload']['retired_owners']]
            return response

    @property
    def consumed(self):
        return self._index == len(self._records)

    def close(self):
        with self._lock:
            self.closed = True
