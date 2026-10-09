# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-destructive material conversion and private local-node compatibility."""
from pathlib import Path
import bpy
from . import shaders as S
from .geometry import role
LOCAL_VARIANTS = {'MIAO_MANUAL': '01，手动打光', 'MIAO_BLUE': '02，懒人版_偏蓝', 'MIAO_RED': '03，懒人版_偏红'}
KEY = 'qinghui_version'

def active_output(mat):
    return next((n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None) if mat.node_tree else None

def root_node(mat):
    out = active_output(mat)
    if not out or not out.inputs['Surface'].is_linked:
        return None
    n = out.inputs['Surface'].links[0].from_node
    visited = set()
    while n.type == 'REROUTE' and n.inputs[0].is_linked:
        if n.as_pointer() in visited:
            return None
        visited.add(n.as_pointer())
        n = n.inputs[0].links[0].from_node
    return n

def toon_node(mat):
    n = root_node(mat)
    return n if n and n.type == 'GROUP' and n.node_tree and (n.node_tree.get('qinghui_shader_version') == 1) else None

def source_kind(mat):
    if not mat.use_nodes or not mat.node_tree:
        return 'SOLID'
    if mat.get(KEY):
        if toon_node(mat):
            return 'OWN'
        raise ValueError('晴绘节点已被移除，请先还原：' + mat.name)
    n = root_node(mat)
    if n and n.type == 'BSDF_PRINCIPLED':
        return 'PRINCIPLED'
    if n and n.type == 'GROUP':
        if n.node_tree and n.node_tree.get('soft_toon_version') and n.inputs.get('原色'):
            return 'SOFT'
        if n.name == 'mmd_shader' and mat.node_tree.nodes.get('mmd_base_tex'):
            return 'MMD'
        if n.node_tree and 'miaobox' in n.node_tree.name.lower() and n.inputs.get('颜色') and n.inputs.get('Alpha'):
            return 'MIAO'
    raise ValueError('保留未识别的复杂材质，请手动接入原色：' + mat.name)

def input_value(socket):
    if socket.is_linked:
        return socket.links[0].from_socket
    value = socket.default_value
    return tuple(value) if socket.type in {'RGBA', 'VECTOR'} else value

def extract_base(mat, kind):
    nt = mat.node_tree
    n = root_node(mat)
    if kind == 'PRINCIPLED':
        return (input_value(n.inputs['Base Color']), input_value(n.inputs['Alpha']))
    if kind in {'OWN', 'SOFT'}:
        return (input_value(n.inputs['原色']), input_value(n.inputs['透明度']))
    if kind == 'MIAO':
        return (input_value(n.inputs['颜色']), input_value(n.inputs['Alpha']))
    if kind == 'MMD':
        tex = nt.nodes['mmd_base_tex']
        base = tex.outputs['Color']
        alpha = tex.outputs['Alpha']
        if n.inputs.get('Alpha'):
            alpha = S.mathnode(nt, 'MULTIPLY', alpha, input_value(n.inputs['Alpha']), '保留MMD透明度', x=-300, y=-500)
        if n.inputs.get('Diffuse Color'):
            base = S.mix(nt, base, input_value(n.inputs['Diffuse Color']), 1.0, 'MULTIPLY', '保留MMD基础色', x=-300, y=-300)
        return (base, alpha)
    return (tuple(mat.diffuse_color), mat.diffuse_color[3])

def find_library(folder, variant):
    folder = Path(bpy.path.abspath(folder)).expanduser()
    if not folder.is_dir():
        raise ValueError('请选择本机 MiaoBox 节点库目录')
    paths = list(folder.rglob(LOCAL_VARIANTS[variant] + '*.blend'))
    if len(paths) != 1:
        raise ValueError('该目录未找到唯一对应的节点库：' + LOCAL_VARIANTS[variant])
    return paths[0]

def local_blueprint(folder, variant):
    path = find_library(folder, variant)
    stamp = str(path.stat().st_mtime_ns)
    for g in bpy.data.node_groups:
        if g.get('qinghui_local_source') == str(path) and g.get('qinghui_local_stamp') == stamp:
            return g
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        if 'Miaobox' not in src.node_groups:
            raise ValueError('节点库中没有 Miaobox 组')
        dst.node_groups = ['Miaobox']
    g = dst.node_groups[0]
    g.name = '晴绘兼容源 · ' + variant
    g['qinghui_local_source'] = str(path)
    g['qinghui_local_stamp'] = stamp
    return g

def clone_tree(tree, memo=None):
    """Copy nested shader groups too, preventing edits reaching other materials."""
    if tree.name == S.GLOBAL:
        return tree
    memo = {} if memo is None else memo
    if tree.as_pointer() in memo:
        return memo[tree.as_pointer()]
    g = tree.copy()
    memo[tree.as_pointer()] = g
    g.use_fake_user = False
    for key in ['qinghui_local_source', 'qinghui_local_stamp']:
        if key in g:
            del g[key]
    for n in g.nodes:
        if n.type == 'GROUP' and n.node_tree:
            n.node_tree = clone_tree(n.node_tree, memo)
    return g

def local_wrapper(blueprint, material_name, variant):
    g = bpy.data.node_groups.new('晴绘兼容 · ' + material_name, 'ShaderNodeTree')
    g['qinghui_shader_version'] = 1
    g['qinghui_backend'] = variant
    for name, (kind, d, lo, hi) in S.INPUTS.items():
        S.socket(g, name, kind, d, lo, hi)
    S.socket(g, '表面', 'NodeSocketShader', None, io='OUTPUT')
    inp = S.node(g, 'NodeGroupInput', '颜色与透明度', -1400, 400)
    glob = S.node(g, 'ShaderNodeGroup', '整体调色', -1400, -50)
    glob.node_tree = S.globals_group()
    color = S.graded_color(g, inp.outputs, glob.outputs, x=-1000, y=600)
    native = S.node(g, 'ShaderNodeGroup', '本机MiaoBox节点', 100, 100)
    native.node_tree = clone_tree(blueprint)
    g.links.new(color, native.inputs['颜色'])
    g.links.new(inp.outputs['透明度'], native.inputs['Alpha'])
    if native.inputs.get('阴影强度'):
        depth = S.mathnode(g, 'MULTIPLY', inp.outputs['阴影深度'], glob.outputs['阴影深度'], x=-100, y=-200)
        depth = S.mathnode(g, 'MINIMUM', depth, 1.0, x=100, y=-200)
        g.links.new(depth, native.inputs['阴影强度'])
    out = S.node(g, 'NodeGroupOutput', '材质输出', 500, 100)
    g.links.new(native.outputs['输出'], out.inputs['表面'])
    return g

def local_node(mat):
    n = toon_node(mat)
    return n.node_tree.nodes.get('本机MiaoBox节点') if n else None

def iter_hsv(tree, seen=None):
    seen = set() if seen is None else seen
    if tree.as_pointer() in seen:
        return
    seen.add(tree.as_pointer())
    for n in tree.nodes:
        if n.type == 'HUE_SAT':
            yield n
        if n.type == 'GROUP' and n.node_tree:
            yield from iter_hsv(n.node_tree, seen)

def iter_ramps(tree, seen=None):
    seen = set() if seen is None else seen
    if tree.as_pointer() in seen:
        return
    seen.add(tree.as_pointer())
    for n in tree.nodes:
        if n.type == 'VALTORGB':
            yield n
        if n.type == 'GROUP' and n.node_tree:
            yield from iter_ramps(n.node_tree, seen)

def apply(mat, profile='BRIGHT', material_role='AUTO', backend=None, folder='', reset=True):
    kind = source_kind(mat)
    material_role = mat.get('qinghui_role', mat.get('soft_toon_role', role(mat))) if material_role == 'AUTO' else material_role
    backend = backend or S.PROFILES[profile]['method']
    blueprint = local_blueprint(folder, backend) if backend in LOCAL_VARIANTS else None
    if kind == 'OWN':
        result = mat
        n = toon_node(result)
        prior = result.get('qinghui_backend', 'THREE')
        if prior == backend or (prior in S.METHODS and backend in S.METHODS):
            if reset:
                for k, v in S.profile_values(profile, material_role).items():
                    n.inputs[k].default_value = v
            if backend in S.METHODS:
                n.inputs['分层方式'].default_value = S.METHODS[backend]
            result['qinghui_backend'] = backend
            result['qinghui_role'] = material_role
            return result
        base, alpha = extract_base(result, 'OWN')
        old_values = {i.name: input_value(i) for i in n.inputs if i.name not in {'原色', '透明度'}}
        result.node_tree.nodes.remove(n)
    else:
        mat.use_fake_user = True
        result = mat.copy()
        result.name = '晴绘_' + mat.name
        result[KEY] = 1
        result['qinghui_source_material'] = mat
        result['qinghui_source'] = mat.name
        result.use_fake_user = False
        if not result.use_nodes:
            result.use_nodes = True
        base, alpha = extract_base(result, kind)
        old_values = {}
    nt = result.node_tree
    out = active_output(result) or nt.nodes.new('ShaderNodeOutputMaterial')
    n = nt.nodes.new('ShaderNodeGroup')
    n.name = '晴绘卡渲'
    n.label = '晴绘 · 材质独立控制'
    n.node_tree = local_wrapper(blueprint, result.name, backend) if blueprint else S.group()
    n.width = 280
    n.location = (out.location.x - 360, out.location.y)
    S.put(nt, n.inputs['原色'], base)
    S.put(nt, n.inputs['透明度'], alpha)
    values = S.profile_values(profile, material_role) if reset or not old_values else old_values
    if blueprint and (not old_values):
        values.update({'饱和度': 1.0, '明度': 1.0, '色彩对比': 1.0, '阴影深度': 0.6})
    for k, v in values.items():
        n.inputs[k].default_value = v
    if backend in S.METHODS:
        n.inputs['分层方式'].default_value = S.METHODS[backend]
    nt.links.new(n.outputs['表面'], out.inputs['Surface'])
    result['qinghui_backend'] = backend
    result['qinghui_role'] = material_role
    result.surface_render_method = 'DITHERED'
    result.use_backface_culling = False
    return result

def isolated_copy(mat):
    copy = mat.copy()
    n = toon_node(copy)
    if n and copy.get('qinghui_backend') in LOCAL_VARIANTS:
        n.node_tree = clone_tree(n.node_tree)
    return copy
