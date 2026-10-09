# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable parameter-only looks, validated completely before material edits."""
import json, math, os, tempfile
from . import shaders as S, materials as M
from .geometry import role
ROLES = {'SKIN', 'HAIR', 'CLOTH', 'UNLIT', 'DETAIL', 'GENERAL'}

def plain(v):
    return list(v) if not isinstance(v, (str, int, float, bool)) else v

def number(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (not math.isfinite(v)) or (not lo <= v <= hi):
        raise ValueError('预设数值超出范围或格式错误')
    return float(v)

def validate(v, spec):
    kind, _, lo, hi = spec
    if kind in {'NodeSocketColor', 'NodeSocketVector'}:
        if not isinstance(v, list) or len(v) != (4 if kind == 'NodeSocketColor' else 3):
            raise ValueError('颜色或向量格式错误')
        return [number(x, lo, hi) for x in v]
    return number(v, lo, hi)

def global_values():
    g = S.globals_group()
    return {k: [i.default_value for i in g.nodes[k].inputs] if spec[0] == 'NodeSocketVector' else g.nodes[k].outputs[0].default_value for k, spec in S.CONTROLS.items()}

def set_globals(values):
    g = S.globals_group()
    for k, v in values.items():
        if isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                g.nodes[k].inputs[i].default_value = x
        else:
            g.nodes[k].outputs[0].default_value = v
    g.update_tag()

def native_state(mat):
    n = M.local_node(mat)
    if not n:
        return None
    return {'inputs': {i.name: plain(i.default_value) for i in n.inputs if i.name and '=' not in i.name and (not i.is_linked) and hasattr(i, 'default_value')}, 'hsv': [{'saturation': x.inputs['Saturation'].default_value, 'value': x.inputs['Value'].default_value} for x in M.iter_hsv(n.node_tree)], 'ramps': [{'interpolation': x.color_ramp.interpolation, 'elements': [[e.position, list(e.color)] for e in x.color_ramp.elements]} for x in M.iter_ramps(n.node_tree)]}

def snapshot(objects, scene, scope):
    records = []
    for o in objects:
        rows = []
        for i, slot in enumerate(o.material_slots):
            mat = slot.material
            if scope == 'ACTIVE' and i != o.active_material_index:
                continue
            n = M.toon_node(mat) if mat else None
            if not n:
                continue
            rows.append({'slot': i, 'name': mat.get('qinghui_source', mat.name), 'role': mat.get('qinghui_role', 'GENERAL'), 'backend': mat.get('qinghui_backend', 'THREE'), 'values': {x.name: plain(x.default_value) for x in n.inputs if x.name not in {'原色', '透明度'}}, 'native': native_state(mat)})
        if rows:
            records.append({'name': o.name, 'materials': rows})
    if not records:
        raise ValueError('所选范围没有晴绘材质')
    return {'schema': 'qinghui-toon/1', 'objects': records, 'global': global_values(), 'display': {'view': scene.view_settings.view_transform, 'look': scene.view_settings.look, 'exposure': scene.view_settings.exposure, 'gamma': scene.view_settings.gamma}}

def write(path, data):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=os.path.dirname(os.path.abspath(path)), delete=False) as f:
            temp = f.name
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.remove(temp)

def load(path):
    with open(path, encoding='utf8') as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get('schema') != 'qinghui-toon/1':
        raise ValueError('不是晴绘风格文件')
    records = data.get('objects')
    glob = data.get('global', {})
    display = data.get('display', {})
    if not isinstance(records, list) or not records or len(records) > 128 or (not isinstance(glob, dict)) or (not isinstance(display, dict)):
        raise ValueError('风格文件结构错误')
    validated = []
    for obj in records:
        if not isinstance(obj, dict) or not isinstance(obj.get('name'), str) or (not isinstance(obj.get('materials'), list)):
            raise ValueError('对象参数结构错误')
        for rec in obj['materials']:
            if not isinstance(rec, dict) or rec.get('role') not in ROLES or rec.get('backend') not in set(S.METHODS) | set(M.LOCAL_VARIANTS):
                raise ValueError('材质类型或卡渲方式错误')
            if not isinstance(rec.get('slot'), int) or rec['slot'] < 0 or (not isinstance(rec.get('name'), str)) or (not isinstance(rec.get('values'), dict)):
                raise ValueError('材质参数结构错误')
            values = {k: validate(v, S.INPUTS[k]) for k, v in rec['values'].items() if k in S.INPUTS and k not in {'原色', '透明度'}}
            if values.get('暗部阈值', 0) > values.get('亮部阈值', 3):
                raise ValueError('暗部阈值不能高于亮部阈值')
            native = rec.get('native')
            if native is not None:
                if rec['backend'] not in M.LOCAL_VARIANTS:
                    raise ValueError('本机节点参数与卡渲方式不匹配')
                if not isinstance(native, dict) or not isinstance(native.get('inputs'), dict) or (not isinstance(native.get('hsv'), list)):
                    raise ValueError('本机节点参数错误')
                for k, v in native['inputs'].items():
                    if isinstance(v, list):
                        if len(v) not in {3, 4}:
                            raise ValueError('本机节点向量错误')
                        for x in v:
                            number(x, -1000, 1000)
                    else:
                        number(v, -1000, 1000)
                for x in native['hsv']:
                    if not isinstance(x, dict):
                        raise ValueError('内部颜色参数错误')
                    number(x.get('saturation'), 0, 2)
                    number(x.get('value'), 0, 2)
                ramps = native.get('ramps', [])
                if not isinstance(ramps, list):
                    raise ValueError('色带参数格式错误')
                for ramp in ramps:
                    if not isinstance(ramp, dict) or ramp.get('interpolation') not in {'LINEAR', 'CONSTANT', 'EASE', 'CARDINAL', 'B_SPLINE'} or (not isinstance(ramp.get('elements'), list)) or (not 2 <= len(ramp['elements']) <= 32):
                        raise ValueError('色带参数错误')
                    for e in ramp['elements']:
                        if not isinstance(e, list) or len(e) != 2 or (not isinstance(e[1], list)) or (len(e[1]) != 4):
                            raise ValueError('色带颜色格式错误')
                        number(e[0], 0, 1)
                        for c in e[1]:
                            number(c, 0, 1)
            validated.append(dict(rec, values=values, object_name=obj['name']))
    if not validated:
        raise ValueError('风格文件没有材质')
    global_parsed = {k: validate(v, S.CONTROLS[k]) for k, v in glob.items() if k in S.CONTROLS}
    if display:
        if display.get('view') not in {'Standard', 'AgX', 'Filmic', 'Khronos PBR Neutral', 'Raw'} or not isinstance(display.get('look'), str):
            raise ValueError('场景色彩显示设置错误')
        number(display.get('exposure'), -32, 32)
        number(display.get('gamma'), 0.1, 5)
    return (validated, global_parsed, display)

def match_record(records, obj, mat, index):
    source = mat.get('qinghui_source', mat.name)
    r = mat.get('qinghui_role', role(mat))
    return next((x for x in records if x['name'] == source), None) or next((x for x in records if x['role'] == r), None) or next((x for x in records if x['object_name'] == obj.name and x['slot'] == index), None)

def set_native(mat, state):
    if state is None:
        return
    n = M.local_node(mat)
    if not n:
        raise ValueError('预设要求本机节点，但目标材质不是该方式')
    for k, v in state['inputs'].items():
        sock = n.inputs.get(k)
        if sock and (not sock.is_linked):
            sock.default_value = v
    for shader, data in zip(M.iter_hsv(n.node_tree), state['hsv']):
        shader.inputs['Saturation'].default_value = data['saturation']
        shader.inputs['Value'].default_value = data['value']
    for shader, data in zip(M.iter_ramps(n.node_tree), state.get('ramps', [])):
        ramp = shader.color_ramp
        ramp.interpolation = data['interpolation']
        elements = sorted(data['elements'], key=lambda x: x[0])
        while len(ramp.elements) > 2:
            ramp.elements.remove(ramp.elements[-1])
        ramp.elements[0].position = elements[0][0]
        ramp.elements[0].color = elements[0][1]
        ramp.elements[1].position = elements[-1][0]
        ramp.elements[1].color = elements[-1][1]
        for pos, color in elements[1:-1]:
            ramp.elements.new(pos).color = color

def validate_native(blueprint, state):
    if state is None:
        return
    inputs = {x.name: x for x in blueprint.interface.items_tree if x.item_type == 'SOCKET' and x.in_out == 'INPUT'}
    for k, v in state['inputs'].items():
        item = inputs.get(k)
        if not item or k in {'颜色', 'Alpha', '阴影强度'} or '=' in k:
            raise ValueError('本机预设包含不可写参数：' + k)
        validate(v, (item.socket_type, item.default_value, getattr(item, 'min_value', 0.0), getattr(item, 'max_value', 1.0)))
    if len(state['hsv']) != len(list(M.iter_hsv(blueprint))) or len(state.get('ramps', [])) != len(list(M.iter_ramps(blueprint))):
        raise ValueError('本机节点库版本与预设不匹配')
