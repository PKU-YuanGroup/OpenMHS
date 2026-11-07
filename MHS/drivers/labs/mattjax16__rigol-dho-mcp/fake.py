"""Controlled MCP peer for the thirteen selected rigol-dho-mcp tools.

Local test code: it imports neither the upstream server nor an MCP library and opens no
socket. It answers JSON-RPC tools/list and tools/call with the declared schemas and the
tool behaviour of rigol_dho_mcp/server.py (which settings each tool changes, what it
returns). Every number below is test data, not a Rigol measurement or bound.

The envelope is the SDK's controlled profile, not FastMCP's: a FastMCP server
lists pydantic-generated input schemas and can add structuredContent to string results,
both of which the McpClientDriver bridge refuses. See RESULT.json notes.
"""
import base64
import copy
import json
import math
import struct
import threading
import zlib

from .driver import CONFIG, DEFAULTS


def png():
    """A complete 3 x 2 RGB PNG (placeholder pixels, not a screen capture)."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b'\0\xff\x00\x00\x00\xff\x00\x00\x00\xff\0\x11\x22\x33\x44\x55\x66\x77\x88\x99'  # placeholder
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 3, 2, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


class ControlledPeer:
    """One controlled oscilloscope endpoint; ``exchange`` is the only transport method."""

    def __init__(self, **_options):
        self.lock = threading.RLock()
        self.calls = []
        self.closed = False
        self.close_calls = 0
        self.trigger_status = 'STOP'  # placeholder
        self.channels = {ch: {'enabled': ch == 1, 'scale_V_per_div': '1.0', 'offset_V': '0.0', 'coupling': 'DC',
                              'probe_ratio': '1.0', 'bandwidth_limit': 'OFF'} for ch in range(1, 5)}  # placeholder
        self.invert = {ch: False for ch in range(1, 5)}
        self.channel_count = 4  # placeholder: get_status stops listing at the first failing channel query
        self.timebase = {'scale_s_per_div': '0.001', 'offset_s': '0.0'}  # placeholder
        self.trigger = {'mode': 'EDGE', 'source': 'CHAN1', 'slope': 'POSitive', 'level_V': '0.0',
                        'sweep': 'AUTO'}  # placeholder
        self.acquisition = {'memory_depth': 'AUTO', 'type': 'NORMal', 'averages': '2',
                            'sample_rate_Sa_per_s': '1000000'}  # placeholder
        self.cursor = {'mode': 'OFF', 'type': 'TIME', 'source': 'CHAN1', 'source_a': 'CHAN1', 'source_b': 'CHAN2',
                       'ax': '0.0', 'ay': '0.0', 'bx': '0.000001', 'by': '1.0'}  # placeholder
        self.raw_screen = bytes((i * 37 + 11) % 256 for i in range(1031))  # placeholder samples
        self.raw_memory = bytes((i * 53 + 7) % 256 for i in range(20001))  # placeholder samples
        self.screenshot = png()
        self.measurement_value = 1.25  # placeholder
        self.last_selector = None
        # Test hooks: called before a request is answered and after the response is built.
        self.before = None
        self.after = None
        self.discovery = None

    def status(self):
        channels = {}
        for ch in range(1, self.channel_count + 1):
            value = self.channels[ch]
            channels['CH' + str(ch)] = copy.deepcopy(value) if value['enabled'] else {'enabled': False}
        return {'trigger_status': self.trigger_status,
                'sample_rate_Sa_per_s': self.acquisition['sample_rate_Sa_per_s'],
                'memory_depth': self.acquisition['memory_depth'], 'acquisition_type': self.acquisition['type'],
                'timebase_scale_s_per_div': self.timebase['scale_s_per_div'],
                'timebase_offset_s': self.timebase['offset_s'],
                'trigger': {key: self.trigger[key] for key in ('mode', 'sweep')}, 'channels': channels}

    def tool(self, name, arguments):
        a = {**DEFAULTS[name], **arguments}
        if name == 'identify':
            return 'RIGOL TECHNOLOGIES,CONTROLLED-DHO,FAKE,0'  # placeholder identity
        if name == 'get_status':
            return self.status()
        if name == 'run_control':
            action = a['action']
            if action in ('run', 'autoset'):
                self.trigger_status = 'RUN'  # placeholder status word
            elif action == 'single':
                self.trigger_status = 'WAIT'  # placeholder status word
            elif action == 'stop':
                self.trigger_status = 'STOP'
            commands = {'run': ':RUN', 'stop': ':STOP', 'single': ':SINGle', 'autoset': ':AUToset',
                        'clear': ':CLEar', 'force_trigger': ':TFORce'}
            return 'Sent ' + commands[action] + '. Trigger status: ' + self.trigger_status
        if name == 'configure_channel':
            value = self.channels[a['channel']]
            for src, dst in {'enabled': 'enabled', 'scale': 'scale_V_per_div', 'offset': 'offset_V',
                             'coupling': 'coupling', 'probe_ratio': 'probe_ratio',
                             'bandwidth_limit': 'bandwidth_limit'}.items():
                if a[src] is not None:
                    value[dst] = a[src] if src == 'enabled' else str(a[src])
            if a['invert'] is not None:
                self.invert[a['channel']] = a['invert']
            return {'channel': a['channel'], **copy.deepcopy(value)}
        if name == 'configure_timebase':
            for src, dst in {'scale': 'scale_s_per_div', 'offset': 'offset_s'}.items():
                if a[src] is not None:
                    self.timebase[dst] = str(a[src])
            return self.timebase.copy()
        if name == 'configure_trigger_edge':
            self.trigger['mode'] = 'EDGE'
            for src, dst in {'source': 'source', 'slope': 'slope', 'level': 'level_V', 'sweep': 'sweep'}.items():
                if a[src] is not None:
                    self.trigger[dst] = str(a[src])
            return {**self.trigger, 'status': self.trigger_status}
        if name == 'configure_acquisition':
            for src, dst in {'memory_depth': 'memory_depth', 'acq_type': 'type', 'averages': 'averages'}.items():
                if a[src] is not None:
                    self.acquisition[dst] = str(a[src])
            return self.acquisition.copy()
        if name == 'configure_cursors':
            self.cursor['mode'] = a['mode']
            if a['mode'] == 'MANual':
                if a['cursor_type'] is not None:
                    self.cursor['type'] = a['cursor_type']
                if a['source'] is not None:
                    self.cursor['source'] = a['source']
                axis = 'x' if self.cursor['type'] == 'TIME' else 'y'
                if a['position_a'] is not None:
                    self.cursor['a' + axis] = str(a['position_a'])
                if a['position_b'] is not None:
                    self.cursor['b' + axis] = str(a['position_b'])
            elif a['mode'] == 'TRACk':
                for src, dst in {'track_source_a': 'source_a', 'track_source_b': 'source_b'}.items():
                    if a[src] is not None:
                        self.cursor[dst] = a[src]
            return {'mode': self.cursor['mode']}
        if name == 'get_cursor_values':
            mode = self.cursor['mode']
            if mode == 'OFF':
                return {'mode': mode, 'note': 'Cursors are off. Call configure_cursors first.'}
            values = {key: self.cursor[key] for key in ('ax', 'ay', 'bx', 'by')}
            dx = float(values['bx']) - float(values['ax'])
            dy = float(values['by']) - float(values['ay'])
            values.update(delta_x=str(dx), delta_y=str(dy), inverse_delta_x=str(1 / dx if dx else 0))
            fields = ('type', 'source') if mode == 'MANual' else ('source_a', 'source_b')
            return {'mode': mode, **{key: self.cursor[key] for key in fields}, **values}
        if name in ('get_measurement', 'measure_between'):
            self.last_selector = copy.deepcopy(a)
            value = self.measurement_value
            invalid = isinstance(value, float) and (not math.isfinite(value) or abs(value) > 9e37)
            return {**a, 'value': value, 'invalid': invalid}
        if name == 'get_waveform':
            self.last_selector = {'channel': a['channel'], 'mode': a['mode'], 'format': 'BYTE'}
            # Like the pinned handler, no STOP check here: the binding's prerequisite does that.
            raw = self.raw_memory if a['mode'] == 'memory' else self.raw_screen
            if not raw:
                return {'error': 'No waveform data returned. Is the channel enabled and acquiring?'}
            volts = [(byte - 125 - 2) * 0.02 for byte in raw]  # placeholder preamble: yorigin 125, yref 2, yinc 0.02
            n = len(volts)
            result = {'channel': a['channel'], 'mode': a['mode'], 'points_captured': n, 'dt_s': 1e-6,
                      't0_s': -0.001, 'sample_rate_Sa_per_s': 1e6,  # placeholder preamble: xinc 1e-6, xorig -0.001
                      'stats': {'vmin_V': round(min(volts), 6), 'vmax_V': round(max(volts), 6),
                                'vpp_V': round(max(volts) - min(volts), 6), 'vavg_V': round(sum(volts) / n, 6),
                                'vrms_V': round(math.sqrt(sum(v * v for v in volts) / n), 6)}}
            if a['include_data']:
                step = max(1, n // a['max_points'])
                indices = range(0, n, step)
                result.update(decimation_factor=step, points_returned=len(indices),
                              time_s=[round(-0.001 + i * 1e-6, 12) for i in indices],
                              voltage_V=[round(volts[i], 6) for i in indices])
            return result
        if name == 'get_screenshot':
            return self.screenshot
        raise ValueError('undeclared controlled tool')

    def exchange(self, message, *, timeout_ms, lane):
        with self.lock:
            if self.closed:
                raise RuntimeError('controlled transport closed')
            self.calls.append(copy.deepcopy({'message': message, 'timeout_ms': timeout_ms, 'lane': lane}))
        if self.before:
            self.before(message, lane)
        with self.lock:
            if message['method'] == 'tools/list':
                result = copy.deepcopy(self.discovery) if self.discovery is not None else {'tools': [
                    {'name': name, 'inputSchema': spec['input'], 'description': 'Untrusted remote description.'}
                    for name, spec in CONFIG['tools'].items()]}
            else:
                name = message['params']['name']
                value = self.tool(name, message['params']['arguments'])
                if name == 'get_screenshot':
                    result = {'content': [{'type': 'image', 'mimeType': 'image/png',
                                           'data': base64.b64encode(value).decode()}]}
                elif isinstance(value, str):
                    result = {'content': [{'type': 'text', 'text': value}]}
                else:
                    result = {'content': [{'type': 'text',
                                           'text': json.dumps(value, allow_nan=False, separators=(',', ':'))}]}
            response = {'jsonrpc': '2.0', 'id': message['id'], 'result': result}
        if self.after:
            changed = self.after(message, response, lane)
            if changed is not None:
                response = changed
        return response

    def close(self):
        with self.lock:
            self.close_calls += 1
            self.closed = True


def connect(**options):
    return ControlledPeer(**options)
