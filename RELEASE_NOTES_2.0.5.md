# 瞎拼输入法 2.0.5 发布说明

2.0.5 使用项目自有 IBus Engine，直接调用 LibIME，不安装或启动 Fcitx 5 框架。同一个
Ubuntu 22.04 构建的 amd64 DEB 支持 Ubuntu 22.04、24.04 和 26.04。

本版修复中文输入过程中切换模式会丢弃未转换输入的问题。中文模式下输入 `sub` 后不选
候选，短按 Shift 或按 Ctrl+Space 切换到英文时，此前会直接清空组合，`sub` 既没有
变成中文，也没有以英文原文进入应用。2.0.5 在切换模式前先按原始输入提交，行为与
回车以英文原样提交一致，然后才清空组合并翻转中英文状态。

Shift 与 Ctrl+Space 使用同一条切换路径。切换后候选列表和候选位置同时失效，方向键
和翻页键回到应用。2.0.4 的回车英文提交、方向键透传、空格透传、整句输入、编辑、
翻页、中文标点、Emoji、本地学习和 `.ucimem` 导入导出保持不变。

真实 IBus 验收新增 `toggle-passthrough=1`：在中文组合存在时分别用 Shift 和
Ctrl+Space 切换，必须提交原始拼音且不丢失输入。

安装：

```bash
sudo apt install ./xiapin-input-method_2.0.5_amd64.deb
```

最终包校验值记录在发布目录的 `SHA256SUMS` 和 `RELEASE_MANIFEST.yml`。三系统冷装、
重启与真实按键证据记录在 `docs/RELEASE_EVIDENCE_2.0.5.md`。
