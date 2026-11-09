"""Complete SDK-contained controlled Rigol MCP surface; native stays refused.

Pinned source is read as text only. Synthetic values and operator overlay are
test choices, not vendor bounds, measurements, physical stop or package review.
"""
from mhs.driver import Action, Field, Limit, McpClientDriver

SOURCE = 'rigol_dho_mcp/server.py'
PIN = 'f9ac7191869845ae46ca714de69a877c388b2530'
SHA = 'c2daec52a875c1eb910606695dab71af6d160d731ac7a14dc1437911e5651190'
MEASUREMENTS = ['VMAX','VMIN','VPP','VTOP','VBASe','VAMP','VAVG','VRMS','OVERshoot','PREShoot',
    'MARea','MPARea','PERiod','FREQuency','RTIMe','FTIMe','PWIDth','NWIDth','PDUTy','NDUTy','TVMAX',
    'TVMIN','PSLewrate','NSLewrate','VUPPer','VMID','VLOWer','VARiance','PVRMS','PPULses','NPULses','PEDGes','NEDGes']
BETWEEN = ['RRDelay','RFDelay','FRDelay','FFDelay','RRPHase','RFPHase','FRPHase','FFPHase']
CURSOR_SOURCES = ['CHAN1','CHAN2','CHAN3','CHAN4','MATH1','MATH2','MATH3','MATH4']
TRIGGER_SOURCES = ['CHAN1','CHAN2','CHAN3','CHAN4','EXT','ACL'] + ['D'+str(i) for i in range(16)]
CAPS = {name: 'x-cap.sdk-fixture.' + name + '.v1' for name in (
    'identify','get_status','run_control','configure_channel','configure_timebase','configure_trigger_edge',
    'configure_acquisition','configure_cursors','get_cursor_values','get_measurement','measure_between',
    'get_waveform','get_screenshot')}


def text(**kwargs): return Field('string', max_length=256, **kwargs)
def strings(names): return {name: text() for name in names.split()}
def optional_enum(values): return Field('string', enum=values, required=False, nullable=True)
def numeric(unit=None, integer=False):
    return Field('integer' if integer else 'number', unit=unit, required=False, nullable=True,
        limit=Limit.operator_required('The pinned signature gives no enforceable physical envelope; select an operator-approved finite range. Cursor coordinates depend on the selected axis.'))
def channel(line, required=False):
    return Field('integer', unit='1', required=required, limit=Limit(1,4,source='upstream_code',ref=SOURCE+':'+str(line)))
def schema(fields):
    properties={name:f.to_schema() for name,f in fields.items()}
    for name,field in fields.items():
        if field.nullable and field.enum is not None: properties[name]['enum'].append(None)
    return {'type':'object','properties':properties,
            'required':[name for name,f in fields.items() if f.required is not False], 'additionalProperties':False}


CHANNEL = {'enabled':Field('boolean'), **{name:text(required=False) for name in (
    'scale_V_per_div','offset_V','coupling','probe_ratio','bandwidth_limit')}}
STATUS = {**strings('trigger_status sample_rate_Sa_per_s memory_depth acquisition_type timebase_scale_s_per_div timebase_offset_s'),
    'trigger':Field('object',properties=strings('mode sweep')),
    'channels':Field('object',properties={'CH'+str(ch):Field('object',properties=CHANNEL,required=False) for ch in range(1,5)})}
INPUTS = {
    'identify':{}, 'get_status':{},
    'run_control':{'action':Field('string',enum=['run','stop','single','autoset','clear','force_trigger'])},
    'configure_channel':{'channel':channel(230,True),'enabled':Field('boolean',required=False,nullable=True),
        'scale':numeric('V'),'offset':numeric('V'),'coupling':optional_enum(['AC','DC','GND']),
        'probe_ratio':numeric(),'bandwidth_limit':optional_enum(['OFF','20M']),
        'invert':Field('boolean',required=False,nullable=True)},
    'configure_timebase':{'scale':numeric('s'),'offset':numeric('s')},
    'configure_trigger_edge':{'source':optional_enum(TRIGGER_SOURCES),'slope':optional_enum(['POSitive','NEGative','RFALl']),
        'level':numeric('V'),'sweep':optional_enum(['AUTO','NORMal','SINGle'])},
    'configure_acquisition':{'memory_depth':optional_enum(['AUTO','1k','10k','100k','1M','5M','10M','25M','50M']),
        'acq_type':optional_enum(['NORMal','AVERages','PEAK','ULTRa']),'averages':numeric(integer=True)},
    'configure_cursors':{'mode':Field('string',enum=['OFF','MANual','TRACk'],required=False),
        'cursor_type':optional_enum(['TIME','AMPLitude']),'source':optional_enum(CURSOR_SOURCES),
        'position_a':numeric(),'position_b':numeric(),'track_source_a':optional_enum(CURSOR_SOURCES),
        'track_source_b':optional_enum(CURSOR_SOURCES)},
    'get_cursor_values':{},
    'get_measurement':{'item':Field('string',enum=MEASUREMENTS),'channel':channel(443)},
    'measure_between':{'item':Field('string',enum=BETWEEN),'source_a':channel(478),'source_b':channel(479)},
    'get_waveform':{'channel':channel(512),'mode':Field('string',enum=['screen','memory'],required=False),
        'max_points':Field('integer',required=False,limit=Limit(10,10000,source='upstream_code',ref=SOURCE+':517')),
        'include_data':Field('boolean',required=False)}, 'get_screenshot':{},
}
# Source conditionals are not dimensionless quantities. The raw MCP schema is
# kept below; public coordinate bindings use seconds or volts explicitly.
DESCRIPTIONS={
    'action':'Acquisition action: run, stop, single, autoset, clear, or force trigger.',
    'channel':'Analog channel index, 1 through 4.', 'enabled':'Enable or disable this analog channel.',
    'scale':'Scale in the stated voltage/time unit per display division.', 'offset':'Offset in the stated voltage or time unit.',
    'coupling':'Analog input coupling.', 'probe_ratio':'Dimensionless probe attenuation ratio.',
    'bandwidth_limit':'Source bandwidth-limit token; OFF or 20M.', 'invert':'Set channel inversion; the source returns no inversion readback.',
    'source':'Declared analog/digital trigger or cursor source token.', 'slope':'Source trigger edge slope token.',
    'level':'Trigger level in volts.', 'sweep':'Source acquisition trigger sweep token.',
    'memory_depth':'Declared source acquisition-memory depth token.', 'acq_type':'Acquisition type token.',
    'averages':'Average count; descriptions are not a verified device range and an operator limit is required.',
    'mode':'Explicit cursor mode or waveform mode as indicated by the finite enum.',
    'cursor_type':'Manual cursor axis: TIME means seconds; AMPLitude means volts. Omission retains the source type.',
    'position_a':'Cursor A native coordinate; raw source meaning depends on retained or selected cursor type.',
    'position_b':'Cursor B native coordinate; raw source meaning depends on retained or selected cursor type.',
    'track_source_a':'Waveform followed by track cursor A.', 'track_source_b':'Waveform followed by track cursor B.',
    'item':'Exact source measurement item. Values use source SI units, except phase differences in degrees.',
    'source_a':'First analog-channel index, 1 through 4.', 'source_b':'Second analog-channel index, 1 through 4.',
    'max_points':'Source decimation target, 10 through 10000; floor decimation can return more points.',
    'include_data':'Include every returned time/voltage sample; false retains the complete source statistics-only variant.',
}
for fields in INPUTS.values():
    for key,field in fields.items():
        field.description=DESCRIPTIONS[key]
        if key in ('probe_ratio','averages','max_points'):field.unit='1'
OUTPUTS = {
    'identify':{'text':text()}, 'get_status':STATUS, 'run_control':{'text':text()},
    'configure_channel':{'channel':Field('integer'),'enabled':Field('boolean'),
        **strings('scale_V_per_div offset_V coupling probe_ratio bandwidth_limit')},
    'configure_timebase':strings('scale_s_per_div offset_s'),
    'configure_trigger_edge':strings('mode source slope level_V sweep status'),
    'configure_acquisition':strings('memory_depth type averages sample_rate_Sa_per_s'),
    'configure_cursors':strings('mode'),
    'get_cursor_values':{'artifact_ref':text(),'media_type':Field('string',enum=['application/json'])},
    'get_measurement':{'item':Field('string',enum=MEASUREMENTS),'channel':Field('integer'),
        'value':Field('number'),'invalid':Field('boolean')},
    'measure_between':{'item':Field('string',enum=BETWEEN),'source_a':Field('integer'),'source_b':Field('integer'),
        'value':Field('number'),'invalid':Field('boolean')},
    'get_waveform':{'artifact_ref':text(),'media_type':Field('string',enum=['application/json'])},
    'get_screenshot':{'image_ref':text(),'media_type':Field('string',enum=['image/png']),
        'width':Field('integer'),'height':Field('integer')},
}
CURSOR_VALUES = strings('ax ay bx by delta_x delta_y inverse_delta_x')
CURSOR_SCHEMA = {'anyOf':[
    schema({'mode':Field('string',enum=['MANual']),**strings('type source'),**CURSOR_VALUES}),
    schema({'mode':Field('string',enum=['TRACk']),**strings('source_a source_b'),**CURSOR_VALUES}),
    schema({'mode':Field('string',enum=['OFF']),'note':text()}),
]}
WAVE_BASE = {'channel':Field('integer'),'mode':Field('string',enum=['screen','memory']),
    'points_captured':Field('integer'),'dt_s':Field('number'),'t0_s':Field('number'),
    'sample_rate_Sa_per_s':Field('number',nullable=True),
    'stats':Field('object',properties={key:Field('number') for key in ['vmin_V','vmax_V','vpp_V','vavg_V','vrms_V']})}
WAVE_ARRAYS = {'decimation_factor':Field('integer'),'points_returned':Field('integer'),
    'time_s':Field('array',items=Field('number'),max_items=20000),
    'voltage_V':Field('array',items=Field('number'),max_items=20000)}
WAVE_SCHEMA = {'anyOf':[schema(WAVE_BASE),schema({**WAVE_BASE,**WAVE_ARRAYS})]}
LINES = dict(zip(CAPS,[148,158,199,229,269,287,316,345,396,441,476,511,593]))
EFFECTS = set(CAPS) - {'identify','get_status','get_cursor_values','get_screenshot'}
DEFAULTS = {name:{key:None for key,field in fields.items() if field.required is False} for name,fields in INPUTS.items()}
DEFAULTS['configure_cursors']['mode']='MANual'
DEFAULTS['get_measurement']={'channel':1}
DEFAULTS['measure_between']={'source_a':1,'source_b':2}
DEFAULTS['get_waveform']={'channel':1,'mode':'screen','max_points':1000,'include_data':True}
EXAMPLES = {name: {} for name in CAPS}
EXAMPLES.update(run_control={'action':'stop'},configure_channel={'channel':1},
    get_measurement={'item':'VPP'},measure_between={'item':'RRDelay'})
TOOLS = {}
for name in CAPS:
    output = {'kind':'json','schema':schema(OUTPUTS[name]),'max_bytes':65536}
    if name in ('identify','run_control'):
        output = {'kind':'text','max_bytes':4096}
        if name == 'run_control': output['success_prefixes']=['Sent :']
    elif name == 'get_cursor_values': output.update(schema=CURSOR_SCHEMA,artifact=True)
    elif name == 'get_waveform':
        output.update(schema=WAVE_SCHEMA,artifact=True,max_bytes=1024*1024,
            array_counts={'time_s':'points_returned','voltage_V':'points_returned'},arrays_if='include_data')
    elif name == 'get_screenshot': output={'kind':'png','max_bytes':1024*1024,'max_pixels':2097152}
    TOOLS[name]={'input':schema(INPUTS[name]),'output':output,'effectful':name in EFFECTS,
        'source_ref':SOURCE+':'+str(LINES[name]),'defaults':DEFAULTS[name],'error_prefixes':['ERROR','Error:']}
for name,fields in {'configure_channel':['channel'],'get_measurement':['item','channel'],
                    'measure_between':['item','source_a','source_b'],'get_waveform':['channel','mode']}.items():
    TOOLS[name]['result_matches']={field:field for field in fields}
TOOLS['get_waveform']['prerequisite']={'when':{'argument':'mode','equals':'memory'},
    'observe':'get_status','path':'trigger_status','equals':'STOP','source_ref':SOURCE+':518-525'}
# The stock G6 gate instruments both the stop and its fresh read-back and still
# enforces its independent two-second end-to-end bound. Allow those two worker
# exchanges 1.5 seconds here; adversarial timeout tests set their own budgets.
CONFIG = {'tools':TOOLS,'source':{'path':SOURCE,'sha256':SHA,'commit':PIN,'receiver':'mcp'},
    'safety':{'command':'run_control','arguments':{'action':'stop'},'observe':'get_status','path':'trigger_status','equals':'STOP'},
    'request_timeout_ms':3000,'stop_timeout_ms':1500,'max_message_bytes':4*1024*1024,'owned_transport':True}

CURSOR_TIME='x-cap.sdk-fixture.configure_cursors_time.v1'
CURSOR_AMPLITUDE='x-cap.sdk-fixture.configure_cursors_amplitude.v1'
CURSOR_CURRENT='x-cap.sdk-fixture.configure_cursors_current.v1'
CURSOR_BASE={k:v for k,v in INPUTS['configure_cursors'].items() if k not in ('position_a','position_b')}
def coordinates(unit):
    return {key:Field('number',unit=unit,required=False,nullable=True,
        description='Manual cursor '+letter+' coordinate in '+('seconds' if unit=='s' else 'volts')+'.',
        limit=Limit.operator_required('Operator approves the cursor coordinate range in its declared physical unit.'))
        for key,letter in [('position_a','A'),('position_b','B')]}
TIME_FIELDS={'source':INPUTS['configure_cursors']['source'],**coordinates('s')}
AMPLITUDE_FIELDS={'source':INPUTS['configure_cursors']['source'],**coordinates('V')}
CURRENT_FIELDS={'source':INPUTS['configure_cursors']['source'],
    **{'time_'+key:field for key,field in coordinates('s').items()},
    **{'voltage_'+key:field for key,field in coordinates('V').items()}}
def projected(axis, prefix=''):
    args={'mode':{'const':'MANual'},'source':{'input':'source'},
          'position_a':{'input':prefix+'position_a'},'position_b':{'input':prefix+'position_b'}}
    if not prefix:args['cursor_type']={'const':axis}
    return args
CURRENT_CASES={axis:{'arguments':projected(axis,prefix)}
    for axis,prefix in [('TIME','time_'),('AMPLitude','voltage_')]}
CURRENT_SELECT={'observe':{'prepare':{'tool':'configure_cursors','arguments':{'mode':'MANual'}},
    'tool':'get_cursor_values','path':'type','source_ref':SOURCE+':375-389'},'cases':CURRENT_CASES}
for key,field in CURRENT_FIELDS.items():
    if field.type=='number':field.description='Cursor '+key[-1].upper()+(' seconds candidate; used only for retained TIME.' if key.startswith('time_') else ' volts candidate; used only for retained AMPLitude.')


class Driver(McpClientDriver):
    device_id='controlled_rigol'
    device_kind='instrument'
    mode,risk='hardware','R0'
    native='rigol_dho_mcp.scpi:ScpiClient'
    backends={'fake':'.fake:connect','hardware':'.native:connect'}
    safe_state='Only the controlled endpoint STOP observation after request retirement is confirmed; native acquisition/device stopping remains unproved.'
    mcp_config=CONFIG
    parameters={'trigger_status':text()}
    reads={'trigger_status':{'tool':'get_status','path':'trigger_status'}}
    commands={cap:{'tool':name} for name,cap in CAPS.items()}
    commands[CAPS['configure_cursors']]={'tool':'configure_cursors','arguments':{key:{'input':key} for key in CURSOR_BASE}}
    commands[CURSOR_TIME]={'tool':'configure_cursors','arguments':projected('TIME')}
    commands[CURSOR_AMPLITUDE]={'tool':'configure_cursors','arguments':projected('AMPLitude')}
    commands[CURSOR_CURRENT]={'tool':'configure_cursors','select':CURRENT_SELECT}
    actions={CAPS[name]:Action(name=name,risk='R0',exclusive=False,
        long_running=name in ('get_waveform','get_screenshot'),cancellable=name in ('get_waveform','get_screenshot'),
        max_duration_ms=1000 if name in ('get_waveform','get_screenshot') else None,
        input=INPUTS[name],output=OUTPUTS[name],examples=[EXAMPLES[name]],
        description='Complete selected pinned MCP tool; source results preserved and native admission blocked.') for name in CAPS}
    actions[CAPS['configure_cursors']]=Action(name='configure_cursors',risk='R0',exclusive=False,input=CURSOR_BASE,
        output=OUTPUTS['configure_cursors'],examples=[{}],description='Set source cursor modes, type and sources. Typed coordinate bindings preserve both explicit and omitted-type branches.')
    for cap,name,fields,example in [(CURSOR_TIME,'configure_cursors_time',TIME_FIELDS,{}),
            (CURSOR_AMPLITUDE,'configure_cursors_amplitude',AMPLITUDE_FIELDS,{}),
            (CURSOR_CURRENT,'configure_cursors_current',CURRENT_FIELDS,{})]:
        actions[cap]=Action(name=name,risk='R0',exclusive=False,input=fields,output=OUTPUTS['configure_cursors'],examples=[example],
            description='Typed manual coordinates. Current variant enters MANual, reads retained type, applies that axis candidate and omits cursor_type. Supply both candidates for either type. Unknown readback leaves the mode change unresolved.')


def overlay():
    rules={}
    for cap,action in Driver.actions.items():
        fields=action.input or {}
        chosen={key:{'min':-1000000,'max':1000000,'source':'operator'} for key,field in fields.items()
                if any(limit.is_operator_required for limit in field.limits)}
        if chosen: rules[cap]=chosen
    return {'openmhs':'0.9','site':'controlled-fixture','issued_by':{'id':'operator:fixture'},
            'issued_at':'2026-11-04T00:00:00Z','devices':{'mhs://localhost/controlled_rigol':rules}}
