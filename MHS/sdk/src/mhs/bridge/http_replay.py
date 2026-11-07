"""Versioned finite HTTP exchange replay for controlled fixtures only.

Wire fields match exactly, including origin, version header, query and complete
JSON/multipart bytes. A fresh local request UUID is explicitly rebound to the
one consumed recorded request; recorded response identity must already match.
Remote run/protocol IDs are never guessed or rewritten. This does not accept
legacy header-less ReplayHttp records or establish native server retirement.
"""
from __future__ import annotations

import copy
import threading

from ..driver.http_config import encoded

FORMAT = 'mhs-http-exchange-v1'
MAX_EXCHANGES = 1024
MAX_TRANSCRIPT_BYTES = 32 * 1024 * 1024


def _identity(value):
    return type(value) is str and len(value) == 32 and all(c in '0123456789abcdef' for c in value)


def _request(value):
    encoded(value)
    required={'format','request_id','origin','method','path','headers','query'}
    if (type(value) is not dict or set(value)-required-{'json','multipart'} or required-set(value)
            or value['format'] != 'mhs-http-request-v1' or not _identity(value['request_id'])
            or value['headers'] != {'Opentrons-Version':'2'}):
        raise ValueError('incomplete or unsupported HTTP replay request')
    return {key:item for key,item in value.items() if key!='request_id'}


def exchange_record(request, response):
    """Validate one complete response pairing; no I/O or implicit legacy upgrade."""
    _request(request);encoded(response)
    if (type(response) is not dict or set(response)!={'request_id','status','headers','body'}
            or response['request_id']!=request['request_id']):
        raise ValueError('recorded HTTP response is not paired with its request')
    return copy.deepcopy({'format':FORMAT,'request':request,'response':response})


class ReplayHttpExchange:
    """One finite ordered controlled transcript with unique per-replay UUIDs."""
    def __init__(self, records):
        if type(records) is not list or not 1<=len(records)<=MAX_EXCHANGES:
            raise ValueError('HTTP replay requires 1..1024 complete exchanges')
        copied=[];size=0;identities=set()
        for record in records:
            if type(record) is not dict or set(record)!={'format','request','response'} or record['format']!=FORMAT:
                raise ValueError('unsupported HTTP exchange record version')
            item=exchange_record(record['request'],record['response'])
            size+=len(encoded(item))
            if size>MAX_TRANSCRIPT_BYTES or item['request']['request_id'] in identities:
                raise ValueError('HTTP transcript exceeds bounds or repeats a request identity')
            identities.add(item['request']['request_id']);copied.append(item)
        self._records=copied
        self._position=0
        self._seen=set()
        self._lock=threading.Lock()
        self.closed=False

    def request(self, message, *, timeout_ms):
        if type(timeout_ms) is not int or not 0<timeout_ms<=60000:
            raise ValueError('HTTP replay requires a finite request budget')
        current=_request(message)
        with self._lock:
            if self.closed or self._position>=len(self._records):
                raise ValueError('HTTP replay is closed or exhausted')
            recorded=self._records[self._position]
            if message['request_id'] in self._seen or current!=_request(recorded['request']):
                raise ValueError('HTTP replay request differs from the complete recorded exchange')
            self._seen.add(message['request_id']);self._position+=1
            result=copy.deepcopy(recorded['response'])
            result['request_id']=message['request_id']
            return result

    def close(self):
        with self._lock:
            self.closed=True
