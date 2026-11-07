"""Conservative pinned-source proof for classic Ophyd Component Signals.

The initial proof accepts direct, literal Component declarations on the selected
class. Nested/dynamic components remain unsupported, even if get/set names exist.
No upstream code is imported. External classic Signal API is a named profile,
not a claim that arbitrary similarly named objects are Signals.
"""
from __future__ import annotations
import ast
from .ophyd_config import signal_specs
from .upstream import parse_ref


# Same identity/storage boundary as the independently reviewed QCoDeS v4
# grammar. Component shape is distinct; no QCoDeS implementation is imported.
_IDENTITY_MEMBERS = {"__getattribute__", "__getattr__", "__setattr__", "__delattr__",
    "__dict__", "__class__", "__slots__", "__new__", "__init_subclass__", "__mro_entries__",
    "__bases__", "__base__", "__mro__", "__prepare__", "__get__", "__set__", "__delete__", "__call__"}
_REFLECTION = {"getattr", "setattr", "delattr", "hasattr"}


class UnresolvedIdentity(ValueError):
    """Declaration exists, but the supported grammar cannot prove its lifetime."""


def _path(node):
    if isinstance(node, ast.Name):return node.id
    if isinstance(node, ast.Attribute):
        parent=_path(node.value)
        return parent+'.'+node.attr if parent else None
    return None


def _scope(scope):
    stack=list(scope.body)
    while stack:
        node=stack.pop();yield node
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _bindings(scope):
    result={}
    def add(name,node):
        if name:result.setdefault(name,[]).append(node)
    for node in _scope(scope):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            for alias in node.names:add(alias.asname or alias.name.split('.')[0],node)
        elif isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):add(node.name,node)
        elif isinstance(node,(ast.Name,ast.Attribute)) and isinstance(node.ctx,(ast.Store,ast.Del)):
            path=_path(node);add(path.split('.')[0] if path else None,node)
        elif isinstance(node,ast.ExceptHandler):add(node.name,node)
        elif isinstance(node,(ast.MatchAs,ast.MatchStar)):add(node.name,node)
        elif isinstance(node,ast.MatchMapping):add(node.rest,node)
        elif isinstance(node,(ast.Global,ast.Nonlocal)):
            for name in node.names:add(name,node)
    return result


def _module(tree,path,cache):
    if path not in cache:
        text=tree.read_text(path)
        if text is None:raise ValueError('source file absent from pin')
        if len(cache)>=32 or len(text.encode())>1048576:raise ValueError('source proof exceeds 32 files / 1 MiB per file')
        cache[path]=ast.parse(text)
    return cache[path]


def _imports(module):
    bindings=_bindings(module);out={}
    for node in module.body:
        if isinstance(node,ast.ImportFrom) and node.level==0:
            for alias in node.names:
                local=alias.asname or alias.name
                if bindings.get(local)==[node]:out[local]=(node.module,alias.name)
    return out


def _targets(node):
    return node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []


def _related(path,wanted):
    return path and (path==wanted or path.startswith(wanted+'.') or wanted.startswith(path+'.'))


def _identity_uses(module,name,kind,component_names=()):
    """Reject constructor aliases/escapes instead of following arbitrary Python."""
    parents={child:parent for parent in ast.walk(module) for child in ast.iter_child_nodes(parent)}
    for node in _scope(module):
        if isinstance(node,(ast.Attribute,ast.Subscript)) and isinstance(node.ctx,(ast.Store,ast.Del)):
            raise ValueError('module member/index mutation is outside the Component proof')
    for node in ast.walk(module):
        if isinstance(node,ast.Attribute) and node.attr in _IDENTITY_MEMBERS | _REFLECTION:
            raise UnresolvedIdentity('explicit identity/storage/reflection member access needs a separate source profile')
        if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id in _REFLECTION:
            raise UnresolvedIdentity('reflection is outside the direct Component profile')
        if isinstance(node,ast.ImportFrom) and node.module=='builtins' and any(a.name in _REFLECTION or a.name=='*' for a in node.names):
            raise UnresolvedIdentity('imported reflection builtins are outside the Component profile')
        if isinstance(node,ast.Name) and node.id in {'eval','exec','globals','locals','vars','__import__','__builtins__'}:
            raise ValueError('dynamic namespace access is outside the Component proof')
        if not isinstance(node,ast.Name) or node.id!=name or not isinstance(node.ctx,ast.Load):continue
        parent=parents.get(node)
        if isinstance(parent,ast.ClassDef) and node in parent.bases:continue
        if isinstance(parent,ast.Call) and parent.func is node:continue
        if (kind=='signal' and isinstance(parent,ast.Call) and _path(parent.func) in component_names
                and parent.args and parent.args[0] is node):continue
        if (isinstance(parent,ast.Call) and _path(parent.func) in {'isinstance','issubclass'}
                and len(parent.args)==2 and parent.args[1] is node and _path(parent.func) not in _bindings(module)):continue
        cursor=node
        while cursor in parents and isinstance(parents[cursor],(ast.Subscript,ast.BinOp,ast.Tuple,ast.Attribute)):
            cursor=parents[cursor]
        container=parents.get(cursor)
        if ((isinstance(container,ast.AnnAssign) and container.annotation is cursor)
                or (isinstance(container,ast.arg) and container.annotation is cursor)
                or (isinstance(container,(ast.FunctionDef,ast.AsyncFunctionDef)) and container.returns is cursor)):
            continue
        raise ValueError(f'constructor {name!r} escapes the supported declaration/type/base grammar')


def _class_body(cls,selector,component_names):
    for node in cls.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Pass)):continue
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):continue
        if isinstance(node,(ast.Assign,ast.AnnAssign)) and all(isinstance(t,ast.Name) for t in _targets(node)):
            value=node.value
            if value is None:continue
            if isinstance(value,ast.Call) and _path(value.func) in component_names:continue
            if isinstance(value,ast.Name) and value.id.upper()==value.id:continue
            try:ast.literal_eval(value);continue
            except (ValueError,TypeError):pass
        raise ValueError('class executable/alias body is outside the Component declaration grammar')
    bindings=_bindings(cls)
    if _IDENTITY_MEMBERS.intersection(bindings):
        raise UnresolvedIdentity('identity/storage class bindings are unsupported regardless of their value')
    if any(name in bindings for name in ('__new__','__init_subclass__','__mro_entries__')):
        raise ValueError('dynamic instance/subclass construction is unsupported')


def prove_signal(tree,surface,item,cache=None):
    cache={} if cache is None else cache
    selector=item['signal']
    if '.' in selector:raise ValueError('nested Component paths need a separate full segment proof; unsupported')
    if not surface.classes:raise ValueError('selected source class is unresolved')
    selected_path,selected_name=surface.classes[0].rsplit(':',1)
    ref=parse_ref(item['source_ref'])
    if ref.path!=selected_path:raise ValueError('Component citation must be in the selected class file')
    selected=_module(tree,selected_path,cache)
    classes=[node for node in selected.body if isinstance(node,ast.ClassDef) and node.name==selected_name]
    if len(classes)!=1:raise ValueError('selected class needs one unconditional definition')
    owner=classes[0]
    candidates=[node for node in owner.body if isinstance(node,(ast.Assign,ast.AnnAssign))
                and any(_path(target)==selector for target in _targets(node))]
    if len(candidates)!=1 or len(_targets(candidates[0]))!=1:raise ValueError('Signal needs a unique direct Component assignment')
    node=candidates[0]
    if not node.lineno<=ref.line<=ref.end<=getattr(node,'end_lineno',node.lineno):
        raise ValueError('citation does not identify the exact Component assignment')
    call=node.value;imports=_imports(selected)
    if not isinstance(call,ast.Call) or imports.get(_path(call.func)) not in {
            ('ophyd','Component'),('ophyd.device','Component')}:
        raise ValueError('selector must use the unshadowed classic Ophyd Component import')
    if _path(call.func) in _bindings(owner):raise ValueError('Component import is shadowed in class body')
    # The exact imported Signal type of each explicit profile; EpicsSignalRO only
    # for the get-only classic_epics_ro_v1 profile (signal_specs refuses its set).
    if item['profile']=='classic_epics_v1':
        expected={('ophyd','EpicsSignal'),('ophyd.signal','EpicsSignal')}
    elif item['profile']=='classic_epics_ro_v1' and item['set'] is False:
        expected={('ophyd','EpicsSignalRO'),('ophyd.signal','EpicsSignalRO')}
    elif item['profile']=='classic_soft_v1':
        expected={('ophyd','Signal'),('ophyd.signal','Signal')}
    else:
        expected=set()
    if not call.args or imports.get(_path(call.args[0])) not in expected:
        raise ValueError('Component Signal type does not match the explicit classic profile')
    if _path(call.args[0]) in _bindings(owner):raise ValueError('Signal type import is shadowed in class body')
    _identity_uses(selected,_path(call.func),'component')
    _identity_uses(selected,_path(call.args[0]),'signal',{_path(call.func)})
    if len(call.args)>2 or (len(call.args)==2 and not isinstance(call.args[1],ast.Constant)):
        raise ValueError('Component suffix must be a literal, not a factory/formatted expression')
    if len(call.args)==2 and not isinstance(call.args[1].value,str):raise ValueError('Component suffix must be text')
    for keyword in call.keywords:
        if keyword.arg is None:raise ValueError('expanded Component keywords are unsupported')
        try:ast.literal_eval(keyword.value)
        except (ValueError,TypeError):raise ValueError('Component keywords must be literal data') from None
    wanted='self.'+selector
    for entry in surface.classes:
        path,name=entry.rsplit(':',1);module=_module(tree,path,cache);bindings=_bindings(module)
        local=[n for n in module.body if isinstance(n,ast.ClassDef) and n.name==name]
        if len(local)!=1 or bindings.get(name)!=local:raise ValueError('class identity is rebound or conditional')
        cls=local[0]
        _identity_uses(module,name,'class')
        component_names={key for key,value in _imports(module).items() if value in {('ophyd','Component'),('ophyd.device','Component')}}
        _class_body(cls,selector,component_names)
        class_bindings=_bindings(cls)
        initializers=class_bindings.get('__init__',[])
        if initializers and (len(initializers)!=1 or not isinstance(initializers[0],ast.FunctionDef) or initializers[0] not in cls.body):
            raise ValueError('initializer is rebound, conditional or not a direct method')
        if cls.decorator_list or cls.keywords:raise ValueError('class decorators/metaclasses need separate proof')
        for base in cls.bases:
            key=(_path(base) or '').split('.')[0];definitions=bindings.get(key,[])
            if key=='object' and not definitions:
                continue
            if len(definitions)!=1 or definitions[0] not in module.body or not isinstance(definitions[0],(ast.Import,ast.ImportFrom,ast.ClassDef)):
                raise ValueError('class ancestry binding is shadowed, dynamic or unsupported')
            definition=definitions[0]
            if isinstance(definition,ast.ImportFrom):
                imported=_imports(module).get(key)
                local_ids=set()
                for identity in surface.classes:
                    local_path,local_name=identity.rsplit(':',1)
                    module_path=local_path.removesuffix('.py').replace('/','.')
                    local_ids.add((module_path,local_name))
                    for prefix in ('src.','lib.','python.','py.'):
                        if module_path.startswith(prefix):local_ids.add((module_path[len(prefix):],local_name))
                if imported not in local_ids and imported not in {('ophyd','Device'),('ophyd.device','Device'),
                        ('ophyd.positioner','PositionerBase'),('abc','ABC')}:
                    raise UnresolvedIdentity('external/dynamic ancestry needs a source-bound reviewed profile')
            elif isinstance(definition,ast.ClassDef):
                if path+':'+definition.name not in surface.classes:
                    raise UnresolvedIdentity('local ancestry was not fully resolved')
            else:
                raise UnresolvedIdentity('qualified external ancestry needs a separate source profile')
        # Imported component/signal symbols may not be rebound through attributes
        # or compound module statements. _imports already checks their full scope.
        for method in cls.body:
            if not isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            if isinstance(method,ast.AsyncFunctionDef):
                raise UnresolvedIdentity('async methods require a separate source profile')
            for decorator in method.decorator_list:
                if (_path(decorator) not in {'property','staticmethod'} or _path(decorator) in _bindings(module)
                        or _path(decorator) in class_bindings):
                    raise UnresolvedIdentity(f'method decorator needs a reviewed source profile at {path}:{method.lineno}')
            # This finite profile supports bound ordinary/property methods,
            # including positional-only self. It does not infer receivers in
            # static/class/variadic-only or renamed signatures.
            decorators = {_path(value) for value in method.decorator_list}
            positional = [*method.args.posonlyargs, *method.args.args]
            if (decorators - {'property'} or not positional or positional[0].arg != 'self'):
                raise UnresolvedIdentity(f'unsupported receiver signature at {path}:{method.lineno}; require first positional self in an ordinary/property method')
            for default in [*method.args.defaults, *[value for value in method.args.kw_defaults if value is not None]]:
                try: ast.literal_eval(default)
                except (ValueError, TypeError):
                    raise UnresolvedIdentity(f'executable method defaults require a separate source profile at {path}:{method.lineno}') from None
            if method.name in {'__getattr__','__getattribute__','__setattr__',selector}:
                raise ValueError('dynamic or overriding selector method is unsupported')
            aliases={}
            argument_names = {arg.arg for arg in [*positional, *method.args.kwonlyargs]}
            argument_names.update(arg.arg for arg in (method.args.vararg, method.args.kwarg) if arg is not None)
            argument_names.discard('self')
            parents={child:parent for parent in ast.walk(method) for child in ast.iter_child_nodes(parent)}
            def resolve(value):
                if isinstance(value,ast.Attribute):
                    parent=resolve(value.value)
                    return parent+'.'+value.attr if parent else None
                p=_path(value)
                if p:
                    head,*tail=p.split('.')
                    return aliases.get(head,head)+('.'+'.'.join(tail) if tail else '')
                if isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id=='getattr' and value.args:
                    parent=resolve(value.args[0]);attr=value.args[1] if len(value.args)>1 else None
                    if parent=='self':return wanted if not isinstance(attr,ast.Constant) else 'self.'+str(attr.value)
                return None
            for current in ast.walk(method):
                # Inspect the complete selected-Signal expression at its use
                # site. Tracking only assignment aliases misses loop targets,
                # comprehensions, NamedExpr and other Python binding forms.
                # The finite profile permits direct operations and explicitly
                # scalar metadata, never an escaped Signal/bound method.
                if isinstance(current, ast.Attribute) and isinstance(current.ctx, ast.Load):
                    expression = _path(current)
                    if _related(expression, wanted):
                        parent = parents.get(current)
                        if isinstance(parent, ast.Attribute) and parent.value is current:
                            pass  # The outermost attribute is checked below.
                        elif (isinstance(parent, ast.Call) and parent.func is current
                                and expression in {wanted + '.get', wanted + '.set', wanted + '.put'}):
                            pass
                        elif expression in {wanted + '.name', wanted + '.pvname'} and not (
                                isinstance(parent, ast.Call) and parent.func is current):
                            pass  # Classic Signal string metadata, not identity.
                        else:
                            raise UnresolvedIdentity(f'Signal/member must be used as a direct get/set/put call or string metadata; identity escapes require a separate profile at {path}:{current.lineno}')
            for current in ast.walk(method):
                if isinstance(current,ast.Attribute) and resolve(current) in {'self.__dict__','self.__class__'}:
                    raise UnresolvedIdentity(f'dynamic receiver namespace access needs source-bound review at {path}:{current.lineno}')
                if isinstance(current,ast.Name) and current.id=='self' and isinstance(current.ctx,ast.Load):
                    parent=parents.get(current)
                    allowed=(isinstance(parent,ast.Attribute) and parent.value is current)
                    allowed=allowed or (isinstance(parent,ast.Call) and _path(parent.func) in {'getattr','hasattr','isinstance','super'}
                                        and _path(parent.func) not in _bindings(module)
                                        and _path(parent.func) not in _bindings(method)
                                        and _path(parent.func) not in {a.arg for a in (*method.args.posonlyargs,*method.args.args,*method.args.kwonlyargs)})
                    allowed=allowed or isinstance(parent,ast.Compare)
                    if not allowed:
                        raise UnresolvedIdentity(f'receiver escape/alias needs source-bound review at {path}:{current.lineno}')
                if isinstance(current,ast.Name) and current.id in {'getattr','setattr','delattr','hasattr'} and isinstance(current.ctx,ast.Load):
                    parent=parents.get(current)
                    if not isinstance(parent,ast.Call) or parent.func is not current:
                        raise UnresolvedIdentity('reflection builtin aliases need source-bound review')
                if isinstance(current,ast.Call):
                    func=resolve(current.func)
                    if _related(func,wanted) and func.endswith((".__init__",".__setattr__",".__delattr__",".__dict__.update")):
                        raise UnresolvedIdentity(f'dynamic Signal reinitialization/mutation needs a reviewed source profile at {path}:{current.lineno}')
                    if _path(current.func)=='getattr' and current.args and resolve(current.args[0])=='self':
                        attr=current.args[1] if len(current.args)>1 else None
                        if not isinstance(attr,ast.Constant) or not isinstance(attr.value,str):
                            raise UnresolvedIdentity(f'dynamic receiver selection needs a reviewed source profile at {path}:{current.lineno}')
                    arguments=[*current.args,*[item.value for item in current.keywords]]
                    for argument in arguments:
                        value=resolve(argument)
                        # Receiver introspection is bounded only for literal
                        # getattr/hasattr and unshadowed type/super operations.
                        if value=='self' and _path(current.func) in {'getattr','hasattr','isinstance','super'}:
                            continue
                        if _related(value,wanted) and value not in {wanted+'.name',wanted+'.pvname'}:
                            raise UnresolvedIdentity(f'receiver/Signal escapes to a helper requiring source-bound review at {path}:{current.lineno}')
                if isinstance(current,ast.Name) and isinstance(current.ctx,(ast.Store,ast.Del)) and current.id=='self':
                    raise ValueError('self rebinding prevents instance identity proof')
                if isinstance(current,(ast.Assign,ast.AnnAssign)):
                    value=resolve(current.value)
                    if value in {wanted+".name",wanted+".pvname"}:value=None  # classic Signal string metadata
                    for target in _targets(current):
                        if isinstance(target,ast.Name) and (_related(value,wanted) or (value and value.split('.')[0] in argument_names)):
                            aliases[target.id]=value
                        elif _related(value,wanted):raise ValueError(f'selected Signal escapes through a persistent alias at {path}:{current.lineno}')
                if isinstance(current,ast.Attribute) and isinstance(current.ctx,(ast.Store,ast.Del)):
                    p=resolve(current)
                    if p and p.split('.')[0] in argument_names:
                        raise UnresolvedIdentity(f'member mutation through a caller object requires a separate profile at {path}:{current.lineno}')
                    if _related(p,wanted) and p!=wanted+'.name':
                        raise ValueError('Signal/prefix/get/set member reassignment is unsupported')
                if isinstance(current,ast.Subscript) and isinstance(current.ctx,(ast.Store,ast.Del)):
                    p=resolve(current.value)
                    if _related(p,wanted) or p in {'self.__dict__',wanted+'.__dict__'}:
                        raise ValueError('indexed Signal mutation is unsupported')
                if isinstance(current,ast.Call) and isinstance(current.func,ast.Name) and current.func.id in {'setattr','delattr'}:
                    p=resolve(current.args[0]) if current.args else None
                    attr=current.args[1] if len(current.args)>1 else None
                    if p=='self' and (not isinstance(attr,ast.Constant) or attr.value==selector):
                        raise ValueError('dynamic Signal replacement is unsupported')
                    if _related(p,wanted):raise ValueError('dynamic Signal member replacement is unsupported')
    return selector


def check_ophyd_surface(ctx,gate,surface):
    try:specs=signal_specs(ctx.cls.signal_bindings,ctx.cls.parameters)
    except Exception as exc:
        gate.error('OPHYD_CONFIG',str(exc),'driver.py');return
    approved=set();cache={}
    for name,item in specs.items():
        try:selector=prove_signal(ctx.tree,surface,item,cache)
        except (ValueError,SyntaxError,TypeError,AttributeError) as exc:
            code='OPHYD_IDENTITY_UNRESOLVED' if isinstance(exc,UnresolvedIdentity) else 'OPHYD_COMPONENT_SOURCE'
            gate.error(code,f'{name}: {exc}',name,item['source_ref']);continue
        approved.add(selector)
        for operation in ('get','set'):
            if item[operation]:approved.add(selector+'.'+operation)
    paths=set().union(*(log.found_paths for log in ctx.logs))
    for path in sorted(paths):
        if '.' in path and path not in approved:
            gate.error('OPHYD_UNPROVEN_MEMBER',f'{path!r} is not a proven Signal operation',path)
