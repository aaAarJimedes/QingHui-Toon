"""Real Blender core tests, without character or optional MiaoBox assets."""
import sys, json, math, hashlib
from pathlib import Path
import bpy
from mathutils import Vector
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import qinghui_toon as addon
from qinghui_toon import materials as M, shaders as S, presets as P
out = Path(sys.argv[sys.argv.index('--') + 1]).resolve() if '--' in sys.argv else root / '.test-output'
out.mkdir(parents=True, exist_ok=True)
addon.register(); scene = bpy.context.scene
scene.render.fps = 24; scene.render.fps_base = 1.001
scene.frame_preview_start = -30; scene.frame_preview_end = 778
timing = (scene.render.fps, scene.render.fps_base, scene.frame_preview_start, scene.frame_preview_end)
scene.render.engine = 'CYCLES'; scene.view_settings.view_transform = 'AgX'; scene.view_settings.exposure = .37
obj = bpy.context.object; obj.name = 'Test garment'
obj.data.materials.clear()
original = bpy.data.materials.new('cloth'); original.use_nodes = True
original.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (.12, .31, .5, 1)
obj.data.materials.append(original)
other = obj.copy(); scene.collection.objects.link(other); shared = other.data
scene.qh_target = obj
assert bpy.ops.qinghui.apply() == {'FINISHED'}
toon = obj.active_material
assert toon != original and other.active_material == original and obj.data != shared and other.data == shared
assert bpy.ops.qinghui.apply() == {'FINISHED'} and obj.active_material == toon
n = M.toon_node(toon); n.inputs['色彩对比'].default_value = 1.43
for method, value in [('TWO', 0), ('SMOOTH', 2), ('THREE', 1)]:
    scene.qh_method = method
    assert bpy.ops.qinghui.apply(method_only=True) == {'FINISHED'}
    assert n.inputs['分层方式'].default_value == value and abs(n.inputs['色彩对比'].default_value - 1.43) < 1e-5
other.data = other.data.copy(); other.active_material = toon
scene.qh_profile = 'CEL'; bpy.ops.qinghui.apply()
assert obj.active_material != toon and other.active_material == toon
bpy.ops.qinghui.outline(); bpy.ops.qinghui.outline(); assert len(obj.modifiers) == 1
original.name = 'renamed original'
bpy.ops.qinghui.restore(); assert obj.active_material == original and not obj.modifiers
assert scene.render.engine == 'BLENDER_EEVEE'
scene.qh_target = other; bpy.ops.qinghui.restore()
assert other.active_material == original and scene.render.engine == 'CYCLES'
assert scene.view_settings.view_transform == 'AgX' and abs(scene.view_settings.exposure - .37) < 1e-5
scene.qh_target = obj; obj.material_slots[0].link = 'OBJECT'; obj.material_slots[0].material = original
bpy.ops.qinghui.apply(); bpy.ops.qinghui.restore(); assert obj.active_material == original
obj.material_slots[0].link = 'DATA'; obj.data.materials[0] = original
scene.qh_profile = 'BRIGHT'; bpy.ops.qinghui.apply()
n = M.toon_node(obj.active_material); n.inputs['明度'].default_value = 1.37
style = P.snapshot([obj], scene, 'ALL'); P.write(out / 'style.json', style)
n.inputs['明度'].default_value = .7
assert bpy.ops.qinghui.import_style(filepath=str(out / 'style.json')) == {'FINISHED'}
assert abs(M.toon_node(obj.active_material).inputs['明度'].default_value - 1.37) < 1e-5
before = P.snapshot([obj], scene, 'ALL'); before_mat = obj.active_material
bad = json.loads(json.dumps(style)); bad['objects'][0]['materials'][0]['values']['色彩对比'] = -9
P.write(out / 'bad.json', bad)
try: result = bpy.ops.qinghui.import_style(filepath=str(out / 'bad.json'))
except RuntimeError: result = {'CANCELLED'}
assert result == {'CANCELLED'} and before_mat == obj.active_material and before == P.snapshot([obj], scene, 'ALL')
scene.qh_library_path = str(out / 'missing-local-library'); scene.qh_method = 'MIAO_BLUE'
try: result = bpy.ops.qinghui.apply(method_only=True)
except RuntimeError: result = {'CANCELLED'}
assert result == {'CANCELLED'} and obj.active_material == before_mat
complex_mat = bpy.data.materials.new('unsupported mixed material'); complex_mat.use_nodes = True
nt = complex_mat.node_tree; nt.nodes.clear(); em = nt.nodes.new('ShaderNodeEmission'); output = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], output.inputs['Surface'])
obj.active_material = complex_mat
assert bpy.ops.qinghui.apply() == {'CANCELLED'} and obj.active_material == complex_mat
obj.data.materials.clear(); scene.qh_scope = 'ACTIVE'
assert bpy.ops.qinghui.apply() == {'CANCELLED'}
obj.data.materials.append(original); scene.qh_scope = 'ALL'; scene.qh_profile = 'BRIGHT'; bpy.ops.qinghui.apply()
other.hide_render = True
camera = scene.camera; camera.location = (5, -7, 5); camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.resolution_x = 256; scene.render.resolution_y = 256; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
for method in ('TWO', 'THREE', 'SMOOTH'):
    scene.qh_method = method; bpy.ops.qinghui.apply(method_only=True)
    scene.render.filepath = str(out / (method + '.png')); bpy.ops.render.render(write_still=True)
    assert (out / (method + '.png')).stat().st_size > 1000
assert timing == (scene.render.fps, scene.render.fps_base, scene.frame_preview_start, scene.frame_preview_end)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'roundtrip.blend'), compress=True)
bpy.ops.wm.open_mainfile(filepath=str(out / 'roundtrip.blend'), load_ui=False, use_scripts=False)
assert M.toon_node(bpy.data.objects['Test garment'].active_material)
addon.unregister(); addon.register(); addon.unregister()
print('QINGHUI_CORE_PASS: sharing, idempotence, methods, restore, outlines, presets, invalid-input guards, Eevee renders, save/reopen, timing, lifecycle')
