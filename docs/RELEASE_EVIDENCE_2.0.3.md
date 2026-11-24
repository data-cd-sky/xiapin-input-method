# 瞎拼输入法 2.0.3 发布验收证据

验收日期：2026-11-24（Asia/Shanghai）

本文记录 2.0.3 的唯一 Jammy 构建包、三系统冷缓存直装、GNOME 顶栏选择、真实 IBus
按键和完整重启证据。长期规则见 `docs/RELEASE_ACCEPTANCE.md`。

## 2.0.2 证据勘误

2.0.2 的自动切换验收只检查了 `ibus engine`，没有独立证明 GNOME Shell 顶栏的
`currentSource` 已同步。Ubuntu 26.04 宿主机人工测试发现顶栏仍停留在原输入源，因此
2.0.2 文档中“三台均立即选中”的结论撤回。2.0.3 禁止用直接设置 IBus 后端自证成功，
并从明确的非瞎拼 GNOME 来源状态开始测试 Shell 自身的激活路径。

## 缺陷和实现断言

- IBus daemon 重启后，必须等待 `org.freedesktop.IBus.Panel` 在新 IBus 总线上重新有 owner；
- 自动选择必须由 GNOME 的 `sources` 变化触发，不得执行 `ibus engine xiapin`；
- 锁屏安装必须先完成 APT，解锁辅助服务等待信号而非轮询，解锁后完成并退出；
- 中文模式输出 `，。`，英文模式把 `,.` 交给应用；Shift+`?` 不得误触发中英文切换；
- 空组合 Space 仍透传，候选仍为横排 9 项，Emoji 和学习功能不得回退。

## 唯一候选包

正式包由 Ubuntu 22.04.5 的 GCC 11 和 debhelper 构建。三台虚拟机安装的是字节完全相同的
文件：

```text
文件：xiapin-input-method_2.0.3_amd64.deb
大小：91182 bytes
SHA-256：19cb609d6632bd23e77dc74ba596c0cc01213c62bf24f5b412542efcc585272a
架构：amd64
Engine GLIBC 上限：2.34
Engine GLIBCXX 上限：3.4.29
```

源码和 Jammy 构建目录各通过 48 项 Python 测试、原生 Engine 核心测试、动态注册 IBus
测试和静态 `--ibus` IBus 测试。Jammy 与 Noble 的隔离 APT 运行依赖解析均通过。Lintian
没有 error；唯一 warning 是 `maintainer-script-calls-systemctl`。该调用只用于绕过 Jammy
`deb-systemd-invoke` 不支持用户 `daemon-reload` 的版本差异，只枚举数字 UID 对应且已经
运行的 user manager service，并通过 systemd 249 的 `--machine=UID@` reload。22.04 实测成功，冷装
后 `NeedDaemonReload=no`。

## 冷缓存、重启和真实按键

安装前，三台都满足：包不存在、component 不存在、GNOME sources 不含瞎拼、IBus
registry 的瞎拼计数为 0、当前 Engine 为 `xkb:us::eng`、只有一个 GNOME 管理的 IBus
daemon。个人学习文件只记录哈希，没有删除，安装前后逐文件 SHA-256 一致。

| 系统 | 会话 | 冷装耗时 | doctor | Engine / daemon | systemd reload |
|---|---|---:|---|---|---|
| Ubuntu 22.04.5 | GNOME X11 | 10415 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `NeedDaemonReload=no` |
| Ubuntu 24.04.5 | GNOME Wayland | 3276 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `NeedDaemonReload=no` |
| Ubuntu 26.04 | GNOME Wayland | 4846 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `NeedDaemonReload=no` |

三台均从明确的非瞎拼来源开始，不在测试或安装实现中执行 `ibus engine xiapin`，安装后
观察到 GNOME 激活 `xiapin`。GNOME sources 与 MRU 首项为 `('ibus', 'xiapin')`，注册表
只有一个当前元数据的静态 component，`dpkg -V` 无输出。三台桌面截图的 GNOME 顶栏均
实际显示 😎；截图保存在测试机临时目录，不进入发布包。

三台真实桌面 IBus 总线在冷装后和完整重启后均输出：

```text
xiapin-ibus-integration-ok idle-passthrough=1 idle-space=1 commit=你好
edit=1 apostrophe=1 number=1 paging=1 partial=1 escape=1 enter=1
shift=1 ctrl-space=1 modified-shift=1 chinese-punctuation=，。
english-punctuation=,. horizontal=1 page-size=9 emoji=😀 emoji-prefix=你好😀
```

重启前后的 Boot ID 不同，启动时间和 Engine PID 也改变：

| 系统 | 重启前 Boot ID | 重启后 Boot ID | 重启后启动时间 | Engine PID（前 → 后） |
|---|---|---|---|---|
| Ubuntu 22.04 | `1be8417b-23e3-4d2b-91c7-de2f47fc9b7f` | `0b4f6e5e-178a-4de5-babf-1d33c5f5e1f5` | 22:36:13 | 19451 → 1697 |
| Ubuntu 24.04 | `24b503da-412e-4000-89cb-7df0097da48f` | `ca766248-53b4-456b-9fd4-3e16a6bbcf9c` | 22:36:13 | 4355 → 2137 |
| Ubuntu 26.04 | `2bb944ac-4052-49e0-a5f4-0a6584615a99` | `f91f623b-d099-4a38-a7f4-f9840915bc91` | 22:36:28 | 14053 → 2935 |

Ubuntu 26.04 还从无包、无 component、无 registry 的锁屏状态安装同一最终包。APT 在
4355 ms 完成，`xiapin-unlock.service` 保持 active 等待；解锁后它自动选择瞎拼并变为
inactive，doctor 为 23 OK、0 warning、0 failure，学习数据哈希不变，完整按键再次通过。
该路径不轮询，也没有在测试中手工运行 setup。

Ubuntu 26.04 的测试客户端销毁临时 PyGObject wrapper 时仍会输出
`g_object_is_floating` warning；全部 Engine 断言和客户端退出码均成功。该信息不来自
输入法 Engine，不进入正常输入链路。

三台最终状态均建立外部磁盘快照 `passed-cold-cache-release-2.0.3`，不包含内存状态。

## 人工验收边界

GTK、Qt、Firefox、Chromium/Electron、挂起、多屏和分数缩放仍需用户在最终宿主机按
`docs/RELEASE_ACCEPTANCE.md` 人工验收。自动化结果不能代替这些应用和硬件场景。
