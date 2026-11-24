# 瞎拼输入法 2.0.2 发布验收证据

验收日期：2026-11-24（Asia/Shanghai）

本文记录 2.0.2 空闲按键透传修复的发布证据。长期验收规则与复现方法见
`docs/RELEASE_ACCEPTANCE.md`。

> 后续勘误：本次“安装后立即选中”的自动验收只检查了 IBus 全局 Engine，没有独立证明
> GNOME Shell 顶栏的当前来源已经同步。宿主机人工验收发现该缺口，因此下文相关结论
> 已撤回；修复和替代证据见 `docs/RELEASE_EVIDENCE_2.0.3.md`。空格、按键、冷缓存和重启
> 等其他原始记录仍保留。

## 唯一候选包

正式包由 Ubuntu 22.04 干净环境构建，三台虚拟机安装的是字节完全相同的文件：

```text
文件：xiapin-input-method_2.0.2_amd64.deb
大小：86114 bytes
SHA-256：325388bc36a19e10a36485e66ce30a740eb680263b93233920497bcfaed54a78
架构：amd64
```

源码测试通过 41 项 Python 测试、原生 Engine 核心测试、动态注册 IBus 测试和静态
`--ibus` IBus 测试。Jammy 与 Noble 依赖解析通过。

## 缺陷复现与修复断言

2.0.1 在 Ubuntu 22.04、24.04、26.04 的真实桌面 IBus 总线上均能复现：空组合按 Space
返回 handled，应用收不到空格。2.0.2 在空组合时返回 unhandled；存在拼音组合时 Space
仍选择当前候选。

真实 IBus 回归不只覆盖 Space，还覆盖 Backspace、Delete、Left、Right、Home、End、Up、
Down、PageUp、PageDown、Return、数字 1/9、减号、等号和逗号。通过输出包含：

```text
idle-passthrough=1 idle-space=1 commit=你好 edit=1 apostrophe=1 number=1
paging=1 partial=1 escape=1 enter=1 shift=1 ctrl-space=1 modified-shift=1
horizontal=1 page-size=9 emoji=😀 emoji-prefix=你好😀
```

## 冷缓存直装

安装前，三台均满足：包不存在、component 不存在、GNOME sources 无瞎拼、IBus registry
无瞎拼、只有一个由 GNOME 管理的 IBus daemon。个人学习目录只记录哈希，没有删除。

| 系统 | 会话 | doctor | 学习数据 | Engine/IBus | 真实按键 |
|---|---|---|---|---|---|
| Ubuntu 22.04.5 | GNOME X11 | 23 OK，0 warning，0 failure | 安装前后哈希相同 | 1 个静态 Engine，1 个 daemon | 通过 |
| Ubuntu 24.04.5 | GNOME Wayland | 23 OK，0 warning，0 failure | 安装前后哈希相同 | 1 个静态 Engine，1 个 daemon | 通过 |
| Ubuntu 26.04 | GNOME Wayland | 23 OK，0 warning，0 failure | 安装前后哈希相同 | 1 个静态 Engine，1 个 daemon | 通过 |

三台均自动加入 `('ibus', 'xiapin')` 并立即选中。注册元数据一致：显示名“瞎拼输入法”、
语言 `zh_CN`、顶栏符号 😎、图标 `/usr/share/icons/hicolor/scalable/apps/xiapin.svg`。
未运行手工 setup，未启动临时 `--register` Engine，`dpkg -V` 无输出。

## 完整重启复验

重启前后的系统启动时间和 Engine PID 均发生变化，确认不是只返回了重启命令：

| 系统 | 重启前启动时间 | 重启后启动时间 | Engine PID（前 → 后） |
|---|---|---|---|
| Ubuntu 22.04 | 21:10:33 | 21:38:10 | 11841 → 1749 |
| Ubuntu 24.04 | 21:10:33 | 21:38:11 | 4512 → 2202 |
| Ubuntu 26.04 | 21:11:31 | 21:38:08 | 6251 → 2860 |

重启后三台 doctor 再次为 23 OK、0 warning、0 failure；输入源、静态组件、服务、元数据、
单 daemon 和完整真实 IBus 按键测试再次通过。

Ubuntu 26.04 的测试客户端在销毁临时 PyGObject 包装对象时打印
`g_object_is_floating` 警告，但全部 Engine 断言和测试进程退出码均为成功。该信息来自测试
客户端，不来自输入法 Engine，也不进入用户输入链路。

冷缓存准备阶段还验证了会话环境差异：Ubuntu 22.04 使用 X11，不能注入
`WAYLAND_DISPLAY`；Ubuntu 24.04/26.04 使用 Wayland。统一套用 Wayland 环境会让 22.04 的
`ibus` 客户端连接错误地址。这项规避规则已加入长期验收手册。

## 发布边界

自动验收已完成冷装、安装后立即使用、重启持久性和 Engine 级真实按键行为。GTK、Qt、
Firefox、Chromium/Electron、挂起、多屏和分数缩放仍按验收手册列为人工桌面验收项。
宿主机在三台虚拟机验收期间保持完全回退，没有安装候选包。
