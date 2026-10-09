# SPDX-License-Identifier: GPL-3.0-or-later
bl_info = {'name': '晴绘卡渲 / QingHui Toon', 'author': 'Personal animation tools', 'version': (1, 0, 0), 'blender': (5, 1, 0), 'location': 'View3D > N > 晴绘卡渲', 'description': 'Multiple toon styles, independent contrast and non-destructive local MiaoBox compatibility', 'category': 'Material'}

def register():
    from . import ui
    ui.register()

def unregister():
    from . import ui
    ui.unregister()
