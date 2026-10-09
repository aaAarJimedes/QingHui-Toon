# GitHub 交付

仓库：`aaAarJimedes/QingHui-Toon`，公开。唯一主分支 `main`。

本机唯一源码在 `Agent Tools/Mama_Animation/Rendering/QingHui/development`；发行包在 `Agent Delivery/Mama_Animation/Rendering/QingHui/releases`。本机配置、人物工程、第三方资产和私用资料不进入仓库或 Release。

版本验证后提交并正常推送 main，创建不变的版本标签。在唯一正式发布页上传插件 ZIP、构建清单和 SHA-256 清单；本项目没有自动更新机制，不虚构 update.json。

新版本接棒时，按照工作区规则先保全旧页正文和资产、迁入历史楼层并实际下载验证，随后才移除被替代 Release 页面。不得移动旧标签或覆盖历史同名资产。只有原资产全部验证后才清理可再生临时文件。
