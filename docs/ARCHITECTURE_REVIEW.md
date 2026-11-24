# 2.0 架构决定

更新日期：2026-11-25。

## 采用方案

```text
GNOME / 应用 → IBus → 瞎拼自有 Engine → LibIME
```

2.0 不使用 Fcitx 5 框架。IBus 负责 Ubuntu 桌面输入协议、候选显示和文本提交；瞎拼
Engine 自己维护拼音状态、候选选择、切换、敏感上下文和本地学习，直接调用 LibIME。

中文模式在 Engine 边界把常用标点转换为中文形式；英文模式把按键交还应用，因此不维护
独立的全角/半角状态、设置项或快捷键。

这一边界使候选框跟随 GNOME，Engine 崩溃不会重启 GNOME Shell 或 IBus daemon，且能
用一个在 Jammy 构建的 amd64 包覆盖 22.04、24.04、26.04。

`libfcitx5utils2` 仍是依赖，因为 Ubuntu 的 LibIME 使用该基础工具库。它不包含 Fcitx
输入法守护进程、前端或拼音 addon，也不改变上述架构边界。

## 为什么不同时去掉 Fcitx 和 IBus

LibIME 不负责把按键和候选接入桌面。完全自研桌面层至少需要维护 GTK 3/4 输入模块、
Qt 5/6 输入上下文插件、X11/XWayland XIM、GNOME Wayland 特权通道，以及 Firefox、
Chromium、Electron、Flatpak 和 Snap 的兼容行为。

全局抓键、`uinput`、剪贴板粘贴或 Shell 扩展不能可靠表达预编辑、候选、敏感字段与
准确光标位置，并扩大权限边界。为实现同等覆盖而仿照 GNOME 的 IBus D-Bus 通道，实际
是在重新实现输入法框架。因此完全自研桌面层只保留为研究方向，不进入 2.0。

## 1.x 升级边界

包保留最小旧版迁移器，用于导入 Fcitx 原生拼音和更早 Table 格式的用户数据，从旧
profile 精确移除瞎拼，并在文件仍等于项目应用版本时恢复旧桌面配置。所有无法证明由
瞎拼管理的 Fcitx 用户配置必须保留。

迁移成功后创建 `~/.local/state/ubuntu-cn-input/2.0-fcitx-migration-complete`，以后不再
运行旧配置恢复器。

## 已验证属性

本节历史结论必须以当前版本的 `docs/RELEASE_EVIDENCE_2.0.4.md` 为准。2.0.2 曾只检查
IBus 全局 Engine，没有独立证明 GNOME Shell 顶栏来源同步；该验收缺口由 2.0.3 修正。

- 22.04 LibIME 1.0 和 26.04 LibIME 1.1 的核心行为一致；
- 22.04 X11 与 24.04/26.04 Wayland 的零残留直装和真实桌面 IBus 按键验收通过；
- 24.04/26.04 remove→reinstall 只改变瞎拼输入源，并停止旧 Engine；
- 三套系统新登录通过静态 `--ibus` component 启动；
- 三套系统锁屏恢复后完整按键回归通过；
- 1.0.11→2.0 学习数据迁移、旧配置恢复和当前会话 IBus 恢复通过。

应用候选窗矩阵、挂起、多屏和混合缩放仍属于人工验收，不应由核心测试推断为已通过。
