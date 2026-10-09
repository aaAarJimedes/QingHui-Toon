# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import bpy, math
from bpy.props import PointerProperty, EnumProperty, StringProperty, BoolProperty, FloatProperty, FloatVectorProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from . import shaders as S, materials as M, geometry as G, presets as P
GLOBAL_FIELDS = {'饱和度': 'saturation', '明度': 'brightness', '色彩对比': 'contrast', '阴影深度': 'shadow_depth', '边界柔度': 'softness', '灯光响应': 'light_gain', '方向光模式': 'direction_mix', '光照方向': 'light_direction', '轮廓光': 'rim'}

def global_property(name, spec):
    kind, default, lo, hi = spec

    def get(self):
        n = S.globals_group().nodes[name]
        return tuple((i.default_value for i in n.inputs)) if kind == 'NodeSocketVector' else n.outputs[0].default_value

    def write(self, value):
        g = S.globals_group()
        n = g.nodes[name]
        if kind == 'NodeSocketVector':
            for i, v in enumerate(value):
                n.inputs[i].default_value = max(lo, min(hi, v)) if math.isfinite(v) else default[i]
        else:
            n.outputs[0].default_value = max(lo, min(hi, value)) if math.isfinite(value) else default
        g.update_tag()
    return (FloatVectorProperty if kind == 'NodeSocketVector' else FloatProperty)(name=name, min=lo, max=hi, default=default, get=get, set=write, options=set())

class QH_Controls(bpy.types.PropertyGroup):
    __annotations__ = {field: global_property(name, S.CONTROLS[name]) for name, field in GLOBAL_FIELDS.items()}

def targets(context):
    target = context.scene.qh_target
    if target and target.name not in context.scene.objects:
        return []
    if target:
        return [target] if target.type == 'MESH' else [o for o in context.scene.objects if o.type == 'MESH' and any((m.type == 'ARMATURE' and m.object == target for m in o.modifiers))]
    meshes = [o for o in context.selected_objects if o.type == 'MESH']
    active = context.active_object
    return meshes or ([o for o in context.scene.objects if o.type == 'MESH' and any((m.type == 'ARMATURE' and m.object == active for m in o.modifiers))] if active and active.type == 'ARMATURE' else [])

def active_target(context):
    objects = targets(context)
    return context.active_object if context.active_object in objects else next(iter(objects), None)

def indices(obj, scope):
    return [obj.active_material_index] if scope == 'ACTIVE' and obj.active_material_index < len(obj.data.materials) else list(range(len(obj.data.materials))) if scope == 'ALL' else []

def skip(mat):
    return not mat or mat.name in {'晴绘卡渲 · 轮廓线', '柔色卡渲 · 轮廓线'} or 'mmd_edge' in mat.name.lower()

def unique_mesh(obj):
    if obj.data.users > 1:
        obj.data = obj.data.copy()

def assign(obj, index, material):
    slot = obj.material_slots[index]
    if slot.link == 'OBJECT':
        slot.material = material
    else:
        obj.data.materials[index] = material

def isolate(mat, selected):
    if mat.get(M.KEY) and any((slot.material == mat and (o.as_pointer(), i) not in selected for o in bpy.data.objects if o.type == 'MESH' for i, slot in enumerate(o.material_slots))):
        return M.isolated_copy(mat)
    return mat

def remember_scene(scene):
    if 'qh_original_engine' not in scene:
        scene['qh_original_engine'] = scene.render.engine
    if 'qh_original_view' not in scene:
        scene['qh_original_view'] = {'view': scene.view_settings.view_transform, 'look': scene.view_settings.look, 'exposure': scene.view_settings.exposure, 'gamma': scene.view_settings.gamma}

def set_display(scene, display):
    scene.view_settings.view_transform = display['view']
    try:
        scene.view_settings.look = display.get('look', 'None')
    except TypeError:
        scene.view_settings.look = 'None'
    scene.view_settings.exposure = display['exposure']
    scene.view_settings.gamma = display.get('gamma', 1.0)

def apply_project(scene, profile):
    remember_scene(scene)
    p = S.PROFILES[profile]
    P.set_globals({k: v[1] for k, v in S.CONTROLS.items()})
    S.globals_group().nodes['方向光模式'].outputs[0].default_value = p['direction']
    set_display(scene, {'view': p['view'], 'look': 'None', 'exposure': p['exposure'], 'gamma': 1.0})

class QH_OT_apply(bpy.types.Operator):
    bl_idname = 'qinghui.apply'
    bl_label = '应用晴绘风格'
    bl_options = {'REGISTER', 'UNDO'}
    method_only: BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        s = context.scene
        objects = targets(context)
        if not objects:
            self.report({'WARNING'}, '请指定目标或选中模型')
            return {'CANCELLED'}
        backend = s.qh_method if self.method_only else S.PROFILES[s.qh_profile]['method']
        try:
            if backend in M.LOCAL_VARIANTS:
                M.local_blueprint(s.qh_library_path, backend)
        except (ValueError, OSError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        selected = {(o.as_pointer(), i) for o in objects for i in indices(o, s.qh_scope)}
        memo = {}
        count = 0
        errors = []
        for o in objects:
            unique_mesh(o)
            for i in indices(o, s.qh_scope):
                mat = o.material_slots[i].material
                if skip(mat):
                    continue
                key = mat.as_pointer()
                if key not in memo:
                    try:
                        M.source_kind(mat)
                        memo[key] = M.apply(isolate(mat, selected), s.qh_profile, s.qh_role, backend, s.qh_library_path, reset=not self.method_only)
                    except ValueError as exc:
                        errors.append(str(exc))
                        memo[key] = None
                if memo[key]:
                    assign(o, i, memo[key])
                    count += 1
        if count:
            remember_scene(s)
            s.render.engine = 'BLENDER_EEVEE'
            if not self.method_only and s.qh_apply_project:
                apply_project(s, s.qh_profile)
        self.report({'WARNING'} if errors else {'INFO'}, f'已更新 {count} 个材质' + ('；' + '；'.join(errors) if errors else '，原材质已保留'))
        return {'FINISHED'} if count else {'CANCELLED'}

class QH_OT_restore(bpy.types.Operator):
    bl_idname = 'qinghui.restore'
    bl_label = '还原所选范围'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene
        count = 0
        for o in targets(context):
            unique_mesh(o)
            for i in indices(o, s.qh_scope):
                mat = o.material_slots[i].material
                if not mat or not mat.get(M.KEY):
                    continue
                original = mat.get('qinghui_source_material') or bpy.data.materials.get(mat.get('qinghui_source', ''))
                if original:
                    assign(o, i, original)
                    count += 1
            if s.qh_scope == 'ALL':
                mod = o.modifiers.get('晴绘卡渲 · 轮廓线')
                if mod:
                    o.modifiers.remove(mod)
                for i in reversed(range(len(o.data.materials))):
                    if o.data.materials[i] and o.data.materials[i].name == '晴绘卡渲 · 轮廓线':
                        o.data.materials.pop(index=i)
        if not any((slot.material and slot.material.get(M.KEY) for o in s.objects if o.type == 'MESH' for slot in o.material_slots)):
            if 'qh_original_engine' in s:
                s.render.engine = s['qh_original_engine']
                del s['qh_original_engine']
            if 'qh_original_view' in s:
                set_display(s, s['qh_original_view'])
                del s['qh_original_view']
        self.report({'INFO'}, f'已还原 {count} 个原材质')
        return {'FINISHED'}

class QH_OT_project(bpy.types.Operator):
    bl_idname = 'qinghui.project_style'
    bl_label = '使用该预设的工程显示'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        apply_project(context.scene, context.scene.qh_profile)
        return {'FINISHED'}

class QH_OT_outline(bpy.types.Operator):
    bl_idname = 'qinghui.outline'
    bl_label = '添加 / 更新描边'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for o in targets(context):
            unique_mesh(o)
            G.outline(o)
        return {'FINISHED'}

class QH_OT_export(bpy.types.Operator, ExportHelper):
    bl_idname = 'qinghui.export_style'
    bl_label = '保存整套风格'
    filename_ext = '.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})

    def execute(self, context):
        try:
            P.write(self.filepath, P.snapshot(targets(context), context.scene, context.scene.qh_scope))
        except (OSError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}

class QH_OT_import(bpy.types.Operator, ImportHelper):
    bl_idname = 'qinghui.import_style'
    bl_label = '读取整套风格'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = '.json'
    filter_glob: StringProperty(default='*.json', options={'HIDDEN'})
    include_project: BoolProperty(name='同时载入工程整体与色彩显示', default=False)

    def execute(self, context):
        s = context.scene
        objects = targets(context)
        try:
            records, glob, display = P.load(self.filepath)
            for rec in records:
                if rec['backend'] in M.LOCAL_VARIANTS:
                    P.validate_native(M.local_blueprint(s.qh_library_path, rec['backend']), rec.get('native'))
            plan = []
            for o in objects:
                for i in indices(o, s.qh_scope):
                    mat = o.material_slots[i].material
                    if skip(mat):
                        continue
                    rec = P.match_record(records, o, mat, i)
                    if rec:
                        M.source_kind(mat)
                        plan.append((o, i, rec))
            if not plan:
                raise ValueError('没有匹配的材质；先设置材质类型再读取')
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        selected = {(o.as_pointer(), i) for o, i, _ in plan}
        memo = {}
        for o, i, rec in plan:
            unique_mesh(o)
            mat = o.material_slots[i].material
            key = (mat.as_pointer(), rec['name'])
            if key not in memo:
                mat = M.apply(isolate(mat, selected), material_role=rec['role'], backend=rec['backend'], folder=s.qh_library_path, reset=False)
                n = M.toon_node(mat)
                for k, v in rec['values'].items():
                    n.inputs[k].default_value = v
                if rec['backend'] in S.METHODS:
                    n.inputs['分层方式'].default_value = S.METHODS[rec['backend']]
                P.set_native(mat, rec.get('native'))
                memo[key] = mat
            assign(o, i, memo[key])
        remember_scene(s)
        s.render.engine = 'BLENDER_EEVEE'
        if self.include_project:
            P.set_globals(glob)
            if display:
                set_display(s, display)
        self.report({'INFO'}, f'已载入 {len(plan)} 个材质的风格')
        return {'FINISHED'}

class PanelBase:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '晴绘卡渲'

class QH_PT_main(PanelBase, bpy.types.Panel):
    bl_label = '晴绘卡渲'
    bl_idname = 'QH_PT_main'

    def draw(self, context):
        l = self.layout
        s = context.scene
        l.prop(s, 'qh_target', text='目标')
        l.prop(s, 'qh_scope', text='范围')
        l.prop(s, 'qh_profile', text='内置风格')
        l.prop(s, 'qh_apply_project', text='同时更新工程整体与色彩显示')
        l.operator('qinghui.apply', text='应用风格')
        l.prop(s, 'qh_method', text='卡渲方式')
        l.operator('qinghui.apply', text='切换方式，保留通用参数').method_only = True
        if s.qh_method in M.LOCAL_VARIANTS:
            l.prop(s, 'qh_library_path', text='本机节点库')
        o = active_target(context)
        if o:
            l.template_list('MATERIAL_UL_matslots', '', o, 'material_slots', o, 'active_material_index', rows=4)
            l.prop(s, 'qh_role', text='材质类型')
            l.operator('qinghui.restore')
        row = l.row(align=True)
        row.operator('qinghui.export_style', text='保存风格')
        row.operator('qinghui.import_style', text='读取风格')

class QH_PT_color(PanelBase, bpy.types.Panel):
    bl_label = '当前材质 · 颜色与对比'
    bl_idname = 'QH_PT_color'
    bl_parent_id = 'QH_PT_main'

    def draw(self, context):
        l = self.layout
        o = active_target(context)
        mat = o.active_material if o else None
        n = M.toon_node(mat) if mat else None
        if not n:
            l.label(text='应用风格后可单独调整')
            return
        l.label(text='当前方式：' + METHOD_LABELS[mat.get('qinghui_backend', 'THREE')])
        for k in ['色彩对比', '饱和度', '明度', '亮部保护', '对比中点']:
            l.prop(n.inputs[k], 'default_value', text=k)

class QH_PT_shadow(PanelBase, bpy.types.Panel):
    bl_label = '当前材质 · 阴影与光照'
    bl_idname = 'QH_PT_shadow'
    bl_parent_id = 'QH_PT_main'

    def draw(self, context):
        l = self.layout
        o = active_target(context)
        mat = o.active_material if o else None
        n = M.toon_node(mat) if mat else None
        if not n:
            return
        l.prop(n.inputs['阴影深度'], 'default_value', text='阴影深度')
        native = M.local_node(mat)
        if native:
            for sock in native.inputs:
                if sock.name and '=' not in sock.name and (not sock.is_linked) and hasattr(sock, 'default_value'):
                    l.prop(sock, 'default_value', text=sock.name)
            for i, hsv in enumerate(M.iter_hsv(native.node_tree)):
                if not hsv.inputs['Saturation'].is_linked:
                    l.prop(hsv.inputs['Saturation'], 'default_value', text=f'内部饱和度 {i + 1}')
            return
        for k in ['阴影色调', '阴影染色', '暗部阈值', '亮部阈值', '边界柔度', '连续明暗', '灯光响应', '轮廓光', '轮廓宽度', '轮廓色']:
            l.prop(n.inputs[k], 'default_value', text=k)

class QH_PT_global(PanelBase, bpy.types.Panel):
    bl_label = '工程整体控制'
    bl_idname = 'QH_PT_global'
    bl_parent_id = 'QH_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        l = self.layout
        s = context.scene
        if bpy.data.node_groups.get(S.GLOBAL):
            for k in ['色彩对比', '饱和度', '明度', '阴影深度', '边界柔度', '灯光响应', '轮廓光', '方向光模式']:
                l.prop(s.qh_controls, GLOBAL_FIELDS[k], text='固定方向混合' if k == '方向光模式' else k, slider=True)
            l.prop(s.qh_controls, 'light_direction', text='光照方向')
        l.separator()
        l.prop(s.view_settings, 'view_transform', text='色彩显示')
        l.prop(s.view_settings, 'look', text='显示对比')
        l.prop(s.view_settings, 'exposure', text='场景曝光')
        l.operator('qinghui.project_style')

class QH_PT_native_ramps(PanelBase, bpy.types.Panel):
    bl_label = '本机节点 · 阴影色带'
    bl_idname = 'QH_PT_native_ramps'
    bl_parent_id = 'QH_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        o = active_target(context)
        return bool(o and o.active_material and M.local_node(o.active_material))

    def draw(self, context):
        native = M.local_node(active_target(context).active_material)
        for i, n in enumerate(M.iter_ramps(native.node_tree)):
            self.layout.label(text=f'色带 {i + 1}')
            self.layout.template_color_ramp(n, 'color_ramp', expand=True)

class QH_PT_outline(PanelBase, bpy.types.Panel):
    bl_label = '描边'
    bl_idname = 'QH_PT_outline'
    bl_parent_id = 'QH_PT_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        l = self.layout
        o = active_target(context)
        mod = o.modifiers.get('晴绘卡渲 · 轮廓线') if o else None
        if mod:
            l.prop(mod, 'thickness', text='线宽')
            r = l.row(align=True)
            r.prop(mod, 'show_viewport', text='视图')
            r.prop(mod, 'show_render', text='渲染')
            mat = bpy.data.materials.get('晴绘卡渲 · 轮廓线')
            l.prop(mat.node_tree.nodes['柔墨色'].inputs['Color'], 'default_value', text='线色')
        l.operator('qinghui.outline')
METHOD_LABELS = {'TWO': '二段赛璐璐', 'THREE': '三段卡渲', 'SMOOTH': '连续明暗插画', 'MIAO_MANUAL': '本机 MiaoBox · 手动光照', 'MIAO_BLUE': '本机 MiaoBox · 蓝阴影', 'MIAO_RED': '本机 MiaoBox · 红阴影'}
CLASSES = (QH_Controls, QH_OT_apply, QH_OT_restore, QH_OT_project, QH_OT_outline, QH_OT_export, QH_OT_import, QH_PT_main, QH_PT_color, QH_PT_shadow, QH_PT_global, QH_PT_native_ramps, QH_PT_outline)
PROPS = ['qh_controls', 'qh_target', 'qh_scope', 'qh_profile', 'qh_method', 'qh_role', 'qh_apply_project', 'qh_library_path']

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.qh_controls = PointerProperty(type=QH_Controls)
    bpy.types.Scene.qh_target = PointerProperty(type=bpy.types.Object, poll=lambda self, o: o.type in {'MESH', 'ARMATURE'})
    bpy.types.Scene.qh_scope = EnumProperty(items=[('ALL', '全部材质', '目标对象的全部材质'), ('ACTIVE', '当前材质', '只更新当前材质槽')], default='ALL')
    bpy.types.Scene.qh_profile = EnumProperty(items=[(k, v['label'], '') for k, v in S.PROFILES.items()], default='BRIGHT')
    bpy.types.Scene.qh_method = EnumProperty(items=[(k, v, '') for k, v in METHOD_LABELS.items()], default='THREE')
    bpy.types.Scene.qh_role = EnumProperty(items=[('AUTO', '自动识别', ''), ('SKIN', '肤色', ''), ('HAIR', '头发', ''), ('CLOTH', '衣服', ''), ('UNLIT', '光环装饰', ''), ('DETAIL', '眉眼细节', ''), ('GENERAL', '通用', '')], default='AUTO')
    bpy.types.Scene.qh_apply_project = BoolProperty(default=True, description='应用风格时同时更新本文件共享控制和整个场景的色彩显示；只切换方式不受此项影响')
    bpy.types.Scene.qh_library_path = StringProperty(subtype='DIR_PATH', default=str(Path.home() / 'Documents' / 'Blender' / 'Miaobox_免费卡渲_250122'), description='使用本机已有节点库；插件安装包不包含 MiaoBox 资产')

def unregister():
    for name in PROPS:
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
