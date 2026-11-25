# 瞎拼输入法 2.0.6 发布说明

2.0.6 使用项目自有 IBus Engine，直接调用 LibIME，不安装或启动 Fcitx 5 框架。同一个
Ubuntu 22.04 构建的 amd64 DEB 支持 Ubuntu 22.04、24.04 和 26.04。

本版修复熄屏解锁后输入法唤不醒的问题。用户的 GNOME 输入源里残留一条失效来源
`('xkb', 'cn')`，GNOME 会把它展开成 `xkb:cn::zho`，但当前 IBus daemon 无法解析。
锁屏解锁时 GNOME 尝试恢复该来源失败，当前 Engine 退回普通键盘布局，于是短按 Shift 和
Ctrl+Space 都停留在英文键盘上；在右上角输入源菜单手动点一次瞎拼即可暂时恢复。

这不是瞎拼安装或旧版残留造成的：系统日志中的 `Cannot find engine xkb:cn::zho` 早于
瞎拼首次安装，项目从未写入该来源。安装器仍需处理它，因为用户无法区分来源由谁留下。

2.0.6 在安装和每次图形登录的幂等 setup 中查询一次 `ibus list-engine`，自动移除 IBus
无法解析的输入源，并同步清理 `mru-sources`。XKB 来源按 GNOME 的 `layout` /
`layout+variant` 规则匹配，因此 `('xkb', 'us+intl')` 等有效键盘变体会保留。若查询失败，
或结果中完全没有 XKB Engine（说明 simple 组件未加载），则不删除任何来源。

清理和首次选源合并为一次 `sources` 写入。此前先落盘清理结果、再做单源切换会让
GNOME Shell 取消进行中的 `SetEngine`，表现为来源已清干净但安装报告“未激活”。

2.0.5 的 Shift / Ctrl+Space 提交未转换拼音、2.0.4 的回车英文提交与方向键透传，以及
空格透传、整句输入、编辑、翻页、中文标点、Emoji、本地学习和 `.ucimem` 导入导出均
保持不变。本版不读写、不删除个人学习数据。

安装或升级：

```bash
sudo apt install ./xiapin-input-method_2.0.6_amd64.deb
```

可以直接覆盖 2.0.3 至 2.0.5，无需先卸载。升级后不需要重新添加输入源、注销或重启。
最终包校验值记录在发布目录的 `SHA256SUMS` 和 `RELEASE_MANIFEST.yml`。三系统冷装、
重启与真实按键证据记录在 `docs/RELEASE_EVIDENCE_2.0.6.md`。
