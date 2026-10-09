# SPDX-License-Identifier: GPL-3.0-or-later
"""Original toon shaders. No MiaoBox shader assets are bundled."""
import bpy
GROUP = '晴绘 · Toon Surface v1'
GLOBAL = '晴绘 · 工程整体控制 v1'
CONTROLS = {'饱和度': ('NodeSocketFloat', 1.0, 0.0, 1.8), '明度': ('NodeSocketFloat', 1.0, 0.05, 4.0), '色彩对比': ('NodeSocketFloat', 1.0, 0.4, 2.0), '阴影深度': ('NodeSocketFloat', 1.0, 0.0, 2.0), '边界柔度': ('NodeSocketFloat', 1.0, 0.1, 4.0), '灯光响应': ('NodeSocketFloat', 1.0, 0.01, 10.0), '方向光模式': ('NodeSocketFloat', 0.0, 0.0, 1.0), '光照方向': ('NodeSocketVector', (-0.45, -0.55, 0.7), -1.0, 1.0), '轮廓光': ('NodeSocketFloat', 1.0, 0.0, 3.0)}
INPUTS = {'原色': ('NodeSocketColor', (0.5, 0.5, 0.5, 1), 0.0, 1.0), '透明度': ('NodeSocketFloat', 1.0, 0.0, 1.0), '饱和度': ('NodeSocketFloat', 0.82, 0.0, 1.8), '明度': ('NodeSocketFloat', 1.155, 0.01, 6.0), '色彩对比': ('NodeSocketFloat', 1.2, 0.4, 2.0), '对比中点': ('NodeSocketFloat', 0.18, 0.01, 1.0), '亮部保护': ('NodeSocketFloat', 1.0, 0.0, 1.0), '阴影深度': ('NodeSocketFloat', 0.32, 0.0, 0.95), '阴影色调': ('NodeSocketColor', (0.76, 0.8, 0.89, 1), 0.0, 1.0), '阴影染色': ('NodeSocketFloat', 0.22, 0.0, 1.0), '暗部阈值': ('NodeSocketFloat', 0.22, 0.0, 2.0), '亮部阈值': ('NodeSocketFloat', 0.62, 0.0, 3.0), '边界柔度': ('NodeSocketFloat', 0.08, 0.003, 0.4), '连续明暗': ('NodeSocketFloat', 0.12, 0.0, 1.0), '灯光响应': ('NodeSocketFloat', 0.63, 0.01, 10.0), '轮廓光': ('NodeSocketFloat', 0.024, 0.0, 0.25), '轮廓宽度': ('NodeSocketFloat', 6.0, 1.0, 30.0), '轮廓色': ('NodeSocketColor', (0.94, 0.88, 0.78, 1), 0.0, 1.0), '分层方式': ('NodeSocketFloat', 1.0, 0.0, 2.0)}
METHODS = {'TWO': 0.0, 'THREE': 1.0, 'SMOOTH': 2.0}
PROFILES = {'BRIGHT': {'label': '明亮日系 · 参考增强', 'method': 'THREE', 'view': 'Standard', 'exposure': -0.65, 'direction': 0.0, 'values': {}}, 'CEL': {'label': '清晰赛璐璐', 'method': 'TWO', 'view': 'Standard', 'exposure': -0.65, 'direction': 0.75, 'values': {'饱和度': 0.88, '色彩对比': 1.1, '阴影深度': 0.4, '暗部阈值': 0.53, '亮部阈值': 0.82, '边界柔度': 0.018, '连续明暗': 0.0, '灯光响应': 0.16, '轮廓光': 0.01}}, 'PAINTERLY': {'label': '柔绘插画', 'method': 'SMOOTH', 'view': 'AgX', 'exposure': -0.65, 'direction': 0.75, 'values': {'饱和度': 0.86, '明度': 2.6, '色彩对比': 1.08, '阴影深度': 0.6, '灯光响应': 0.16, '边界柔度': 0.13, '连续明暗': 1.0, '轮廓光': 0.016}}}

def profile_values(profile, role):
    values = {k: spec[1] for k, spec in INPUTS.items() if k not in {'原色', '透明度'}}
    values.update(PROFILES[profile]['values'])
    values['分层方式'] = METHODS[PROFILES[profile]['method']]
    if role == 'SKIN':
        values.update({'饱和度': 0.92, '色彩对比': 1.08, '阴影深度': values['阴影深度'] * 0.65, '阴影色调': (0.92, 0.77, 0.73, 1), '阴影染色': 0.16, '边界柔度': max(0.065, values['边界柔度']), '轮廓光': 0.006})
    elif role == 'HAIR':
        values.update({'饱和度': 0.79, '色彩对比': 1.12, '阴影色调': (0.78, 0.7, 0.72, 1), '阴影染色': 0.24, '轮廓光': 0.035})
    elif role == 'CLOTH':
        values.update({'饱和度': 0.8, '色彩对比': 1.4, '阴影色调': (0.73, 0.79, 0.9, 1), '阴影染色': 0.24, '轮廓光': 0.01})
    elif role in {'UNLIT', 'DETAIL'}:
        values.update({'阴影深度': 0.0, '阴影染色': 0.0, '轮廓光': 0.0, '色彩对比': 1.0, '饱和度': 0.86})
    return values

def socket(g, name, kind, d, lo=0, hi=1, io='INPUT'):
    s = g.interface.new_socket(name=name, in_out=io, socket_type=kind)
    if hasattr(s, 'default_value'):
        s.default_value = d
    if hasattr(s, 'min_value'):
        s.min_value = lo
        s.max_value = hi
    return s

def node(g, kind, name, x, y):
    n = g.nodes.new(kind)
    n.name = name
    n.label = name
    n.location = (x, y)
    return n

def put(g, dest, value):
    if hasattr(value, 'is_output'):
        g.links.new(value, dest)
    else:
        if dest.type == 'RGBA' and isinstance(value, (int, float)):
            value = (value, value, value, 1.0)
        dest.default_value = value

def mathnode(g, op, a, b=None, name='', x=0, y=0):
    n = node(g, 'ShaderNodeMath', name or op, x, y)
    n.operation = op
    put(g, n.inputs[0], a)
    if b is not None:
        put(g, n.inputs[1], b)
    return n.outputs[0]

def mix(g, a, b, f, blend='MIX', name='', x=0, y=0):
    n = node(g, 'ShaderNodeMixRGB', name or blend, x, y)
    n.blend_type = blend
    put(g, n.inputs[0], f)
    put(g, n.inputs[1], a)
    put(g, n.inputs[2], b)
    return n.outputs[0]

def globals_group():
    g = bpy.data.node_groups.get(GLOBAL)
    if g:
        return g
    g = bpy.data.node_groups.new(GLOBAL, 'ShaderNodeTree')
    g.use_fake_user = True
    out = node(g, 'NodeGroupOutput', '全局控制输出', 240, 0)
    for i, (name, (kind, default, lo, hi)) in enumerate(CONTROLS.items()):
        socket(g, name, kind, default, lo, hi, 'OUTPUT')
        if kind == 'NodeSocketVector':
            n = node(g, 'ShaderNodeCombineXYZ', name, -100, -i * 100)
            for j, v in enumerate(default):
                n.inputs[j].default_value = v
            g.links.new(n.outputs[0], out.inputs[name])
        else:
            n = node(g, 'ShaderNodeValue', name, -100, -i * 100)
            n.outputs[0].default_value = default
            g.links.new(n.outputs[0], out.inputs[name])
    return g

def graded_color(g, I, G, x=-1100, y=500):
    hsv = node(g, 'ShaderNodeHueSaturation', '颜色独立控制', x, y)
    g.links.new(I['原色'], hsv.inputs['Color'])
    g.links.new(mathnode(g, 'MULTIPLY', I['饱和度'], G['饱和度'], '合并饱和度', x - 180, y), hsv.inputs['Saturation'])
    g.links.new(mathnode(g, 'MULTIPLY', I['明度'], G['明度'], '合并明度', x - 180, y - 140), hsv.inputs['Value'])
    luminance = node(g, 'ShaderNodeRGBToBW', '保色相的对比度', x + 180, y - 140)
    g.links.new(hsv.outputs[0], luminance.inputs[0])
    safe = mathnode(g, 'MAXIMUM', luminance.outputs[0], 1e-05, x=x + 350, y=y - 140)
    relative = mathnode(g, 'DIVIDE', safe, I['对比中点'], x=x + 520, y=y - 140)
    contrast = mathnode(g, 'SUBTRACT', mathnode(g, 'MULTIPLY', I['色彩对比'], G['色彩对比'], x=x + 160, y=y - 290), 1.0, x=x + 350, y=y - 290)
    factor = mathnode(g, 'POWER', relative, contrast, '亮暗围绕中点展开', x + 690, y - 140)
    protected = mathnode(g, 'MINIMUM', factor, 1.0, '保持白衣和肤色亮部', x + 690, y - 290)
    protection = mathnode(g, 'MULTIPLY', I['亮部保护'], mathnode(g, 'GREATER_THAN', contrast, 0.0, x=x + 520, y=y - 420), x=x + 690, y=y - 420)
    factor = mix(g, factor, protected, protection, name='增加对比时保护亮部', x=x + 880, y=y - 200)
    return mix(g, hsv.outputs[0], factor, 1.0, 'MULTIPLY', '独立对比度输出', x + 880, y)

def group():
    g = bpy.data.node_groups.get(GROUP)
    if g:
        return g
    g = bpy.data.node_groups.new(GROUP, 'ShaderNodeTree')
    g.use_fake_user = True
    g['qinghui_shader_version'] = 1
    for name, (kind, d, lo, hi) in INPUTS.items():
        socket(g, name, kind, d, lo, hi)
    socket(g, '表面', 'NodeSocketShader', None, io='OUTPUT')
    socket(g, '色彩', 'NodeSocketColor', (0, 0, 0, 1), io='OUTPUT')
    socket(g, '明暗遮罩', 'NodeSocketFloat', 0.0, io='OUTPUT')
    inp = node(g, 'NodeGroupInput', '局部材质控制', -1300, 450)
    out = node(g, 'NodeGroupOutput', '成品与调试输出', 1800, 450)
    glob = node(g, 'ShaderNodeGroup', '工程整体控制', -1300, -50)
    glob.node_tree = globals_group()
    I = inp.outputs
    G = glob.outputs
    graded = graded_color(g, I, G, x=-1800, y=1300)
    diffuse = node(g, 'ShaderNodeBsdfDiffuse', '只采样光照，不混入贴图', -1100, -330)
    diffuse.inputs['Color'].default_value = (1, 1, 1, 1)
    diffuse.inputs['Roughness'].default_value = 0.35
    rgb = node(g, 'ShaderNodeShaderToRGB', 'EEVEE光照采样', -890, -330)
    g.links.new(diffuse.outputs[0], rgb.inputs[0])
    bw = node(g, 'ShaderNodeRGBToBW', '光照亮度', -690, -330)
    g.links.new(rgb.outputs['Color'], bw.inputs['Color'])
    gain = mathnode(g, 'MULTIPLY', I['灯光响应'], G['灯光响应'], '合并灯光响应', -870, -490)
    physical = mathnode(g, 'MULTIPLY', bw.outputs[0], gain, '场景明暗', -490, -330)
    geom = node(g, 'ShaderNodeNewGeometry', '表面法线', -1100, -690)
    direction = node(g, 'ShaderNodeVectorMath', '归一化主光方向', -900, -690)
    direction.operation = 'NORMALIZE'
    g.links.new(G['光照方向'], direction.inputs[0])
    dot = node(g, 'ShaderNodeVectorMath', '方向光明暗', -700, -690)
    dot.operation = 'DOT_PRODUCT'
    g.links.new(geom.outputs['Normal'], dot.inputs[0])
    g.links.new(direction.outputs['Vector'], dot.inputs[1])
    fake = mathnode(g, 'ADD', mathnode(g, 'MULTIPLY', dot.outputs['Value'], 0.5, x=-500, y=-670), 0.5, '包裹方向光', -320, -670)
    light = mix(g, physical, fake, G['方向光模式'], name='自由选择光照来源', x=-200, y=-330)
    soft = mathnode(g, 'MULTIPLY', I['边界柔度'], G['边界柔度'], '合并边界柔度', -480, 10)

    def boundary(threshold, x, y):
        lo = mathnode(g, 'SUBTRACT', threshold, soft, x=x - 180, y=y)
        hi = mathnode(g, 'ADD', threshold, soft, x=x - 180, y=y - 120)
        n = node(g, 'ShaderNodeMapRange', '稳定柔化的分层边界', x, y)
        n.clamp = True
        n.interpolation_type = 'SMOOTHERSTEP'
        g.links.new(light, n.inputs['Value'])
        g.links.new(lo, n.inputs['From Min'])
        g.links.new(hi, n.inputs['From Max'])
        return n.outputs['Result']
    low = boundary(I['暗部阈值'], 40, -300)
    high = boundary(I['亮部阈值'], 40, -650)
    depth = mathnode(g, 'MINIMUM', mathnode(g, 'MAXIMUM', mathnode(g, 'MULTIPLY', I['阴影深度'], G['阴影深度'], '合并阴影深度', -650, 500), 0.0, x=-450, y=500), 0.95, '阴影深度安全范围', -280, 500)
    shadow = mathnode(g, 'SUBTRACT', 1.0, depth, '阴影亮度', -80, 500)
    mid = mathnode(g, 'SUBTRACT', 1.0, mathnode(g, 'MULTIPLY', depth, 0.36, x=-100, y=320), '中间调亮度', 100, 400)
    level = mix(g, mix(g, shadow, mid, low, name='暗部到中间调', x=290, y=100), 1.0, high, name='中间调到亮部', x=490, y=100)
    continuous = node(g, 'ShaderNodeMapRange', '连续体积明暗', 250, -600)
    continuous.clamp = True
    g.links.new(light, continuous.inputs['Value'])
    continuous.inputs['From Min'].default_value = 0.0
    continuous.inputs['From Max'].default_value = 1.0
    g.links.new(shadow, continuous.inputs['To Min'])
    continuous.inputs['To Max'].default_value = 1.0
    two = mix(g, shadow, 1.0, low, name='二段明暗', x=290, y=-950)
    is_three = mathnode(g, 'GREATER_THAN', I['分层方式'], 0.5, x=300, y=-1120)
    level = mix(g, two, level, is_three, name='二段或三段', x=490, y=-950)
    volume = mathnode(g, 'MAXIMUM', I['连续明暗'], mathnode(g, 'GREATER_THAN', I['分层方式'], 1.5, x=500, y=-1120), x=670, y=-950)
    level = mix(g, level, continuous.outputs[0], volume, name='分层与连续明暗混合', x=680, y=100)
    shadowmask = mathnode(g, 'SUBTRACT', 1.0, low, '暗部染色遮罩', 300, -200)
    tintfactor = mathnode(g, 'MULTIPLY', shadowmask, I['阴影染色'], '独立阴影染色强度', 500, -200)
    tint = mix(g, (1, 1, 1, 1), I['阴影色调'], tintfactor, name='阴影色', x=700, y=-200)
    base = mix(g, graded, level, 1.0, 'MULTIPLY', '颜色乘明暗', x=900, y=480)
    base = mix(g, base, tint, 1.0, 'MULTIPLY', '只对暗部染色', x=1100, y=480)
    facing = node(g, 'ShaderNodeLayerWeight', '视角轮廓', 680, -500)
    facing.inputs['Blend'].default_value = 0.5
    rim = mathnode(g, 'POWER', facing.outputs['Facing'], I['轮廓宽度'], '细轮廓光遮罩', 880, -450)
    rim = mathnode(g, 'MULTIPLY', rim, mathnode(g, 'MULTIPLY', I['轮廓光'], G['轮廓光'], x=900, y=-650), '轮廓光强度', 1090, -420)
    color = mix(g, base, I['轮廓色'], rim, 'ADD', '轻微轮廓光', x=1320, y=480)
    emit = node(g, 'ShaderNodeEmission', '可控色彩输出', 1500, 480)
    g.links.new(color, emit.inputs['Color'])
    transparent = node(g, 'ShaderNodeBsdfTransparent', '保留透明贴图', 1330, 220)
    shmix = node(g, 'ShaderNodeMixShader', '透明度', 1510, 220)
    g.links.new(I['透明度'], shmix.inputs[0])
    g.links.new(transparent.outputs[0], shmix.inputs[1])
    g.links.new(emit.outputs[0], shmix.inputs[2])
    g.links.new(shmix.outputs[0], out.inputs['表面'])
    g.links.new(color, out.inputs['色彩'])
    g.links.new(light, out.inputs['明暗遮罩'])
    return g
