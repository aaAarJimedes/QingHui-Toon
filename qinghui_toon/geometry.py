# SPDX-License-Identifier: GPL-3.0-or-later
import bpy
from .shaders import node

def role(mat):
    name = mat.name.lower()
    if any((x in name for x in ['头发', '髪', 'hair'])):
        return 'HAIR'
    if any((x in name for x in ['衣料', 'cloth'])):
        return 'CLOTH'
    if any((x in name for x in ['光环', 'halo'])):
        return 'UNLIT'
    if any((x in name for x in ['眉', 'brow'])):
        return 'DETAIL'
    if any((x in name for x in ['头.', '身体', 'skin', 'face', '耳朵'])):
        return 'SKIN'
    return 'GENERAL'

def outline(obj, width=0.001):
    name = '晴绘卡渲 · 轮廓线'
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.diffuse_color = (0.035, 0.025, 0.035, 1)
        mat.use_backface_culling = True
        if hasattr(mat, 'use_backface_culling_shadow'):
            mat.use_backface_culling_shadow = True
        nt = mat.node_tree
        nt.nodes.clear()
        em = node(nt, 'ShaderNodeEmission', '柔墨色', 0, 0)
        em.inputs['Color'].default_value = (0.045, 0.032, 0.044, 1)
        out = node(nt, 'ShaderNodeOutputMaterial', '输出', 220, 0)
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    if mat.name not in obj.data.materials:
        obj.data.materials.append(mat)
    idx = list(obj.data.materials).index(mat)
    vg = obj.vertex_groups.get('晴绘_描边权重') or obj.vertex_groups.new(name='晴绘_描边权重')
    weights = {}
    for p in obj.data.polygons:
        face_mat = obj.material_slots[p.material_index].material if p.material_index < len(obj.material_slots) else None
        mr = face_mat.get('qinghui_role', role(face_mat)) if face_mat else 'GENERAL'
        w = {'HAIR': 1.0, 'SKIN': 0.25, 'CLOTH': 0.65, 'UNLIT': 0.0, 'DETAIL': 0.0}.get(mr, 0.5)
        for v in p.vertices:
            weights[v] = max(weights.get(v, 0), w)
    for i, w in weights.items():
        vg.add([i], w, 'REPLACE')
    mod = obj.modifiers.get(name) or obj.modifiers.new(name, 'SOLIDIFY')
    mod.thickness = width
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = idx
    mod.material_offset_rim = idx
    mod.vertex_group = vg.name
    mod.thickness_vertex_group = 0.0
    return mod
