# 晴绘卡渲 / QingHui Toon

Blender 5.1 / Eevee 卡渲插件，提供二段、三段、连续明暗，以及可独立调节的颜色对比、亮部保护、阴影和描边。版本 **1.0.0**。

## 安装

从 [Release](https://github.com/aaAarJimedes/QingHui-Toon/releases/latest) 下载 `qinghui_toon-1.0.0.zip`。在 Blender 的偏好设置 → 插件 → 从磁盘安装中选择 ZIP，启用插件；三维视图按 N 打开 **晴绘卡渲**。

1. 指定人物网格或骨架，选择全部材质或当前材质。
2. 应用明亮日系、清晰赛璐璐或柔绘插画风格。
3. 调整当前材质的颜色和阴影，或使用工程整体控制。
4. 导出 JSON 风格，在其他工程按材质名称/类型/槽位匹配导入。
5. 需要撤回时使用还原，恢复原材质；共享网格与材质转换时会隔离。

详见 [使用说明](qinghui_toon/使用说明.md)。已经生成的节点保存在工程中；渲染依赖 Eevee，无需始终启用控制面板插件。

## 兼容与范围

原创三种着色方式开箱可用。MiaoBox 手动光照、蓝影、红影是可选的本机兼容入口，使用者需提供自己的节点库；仓库与安装包不包含第三方节点、代码或素材。

支持直接输出的 Principled、MMD Tools 基础材质和旧柔色/MiaoBox 基础材质；复杂混合材质保留并提示。MMD 球面贴图、高光、凹凸和次表面效果不保证完整迁移，玻璃、金属和水可沿用原材质。尚未验证 Cycles 或其他 Blender 版本。

## 开发

- `qinghui_toon/shaders.py`：原创节点与风格。
- `materials.py`：转换、还原和可选本机兼容。
- `presets.py`：JSON 校验和风格导入导出。
- `geometry.py`：描边及材质类型判断。
- `ui.py`：中文面板与操作。
- `tests/core_test.py`：无需人物或第三方资产的 Blender 回归测试。
- `tools/build.py`：生成可安装 ZIP 和 SHA-256 清单。

```text
blender --background --factory-startup --python-exit-code 1 --python tests/core_test.py -- <output-directory>
python tools/build.py --output <release-directory>
```

本轮验证范围见 [验证说明](docs/VALIDATION.md)，发布流程见 [GitHub 交付](docs/GITHUB_DELIVERY.md)。源码为 GPL-3.0-or-later，完整许可证见 [LICENSE](LICENSE)。
