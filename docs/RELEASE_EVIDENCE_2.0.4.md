# 瞎拼输入法 2.0.4 发布验收证据

验收日期：2026-11-25（Asia/Shanghai）

本文记录 2.0.4 的唯一 Jammy 构建包、三系统冷缓存直装、重启后复验和真实 IBus 按键
证据。长期规则见 `docs/RELEASE_ACCEPTANCE.md`。

## 缺陷和实现断言

- 中文模式输入拼音后不选候选、直接回车，必须提交原始英文并结束组合；
- 组合结束后 `Up`/`Down`/PageUp/PageDown 必须回到应用，不能被遗留候选缓存吞掉；
- `Enter`、`Esc`、候选提交、Emoji 提交和上下文 reset 必须走同一条组合清理路径；
- 候选导航只在组合和候选列表都有效时处理；
- 2.0.2 的空格透传、2.0.3 的 GNOME 顶栏选择、中文标点和既有输入功能不得回退。

## 唯一候选包

正式包在 Ubuntu 22.04.5 内构建，三台虚拟机安装字节完全相同的文件：

```text
文件：xiapin-input-method_2.0.4_amd64.deb
大小：92550 bytes
SHA-256：c446795fbf3a7d52f889d02cba64c408c195af8e9b67c53bf5fe134eab30c73c
架构：amd64
Engine GLIBC 上限：2.34
Engine GLIBCXX 上限：3.4.29
```

Jammy 构建目录通过 48 项 Python 测试、原生 Engine 核心测试、动态注册 IBus 测试和
静态 `--ibus` IBus 测试；Jammy 与 Noble 的隔离 APT 运行依赖解析通过。Lintian 没有
error，唯一 warning 是延续自 2.0.3 的 `maintainer-script-calls-systemctl`。

## 冷缓存、重启和真实按键

三台安装的都是上述同一个文件，字节和 SHA-256 一致。安装前都先明确切到 `xkb:us::eng`
或 `('xkb', 'us')`，再 purge 并 `ibus write-cache`；确认包或 component 不存在、GNOME
sources 不含瞎拼、registry 的瞎拼计数为 0。个人学习文件未删除，安装前后哈希一致。

| 系统 | 会话 | 冷装耗时 | doctor | Engine / daemon | reload |
|---|---|---:|---|---|---|
| Ubuntu 22.04.5 | GNOME X11 | 4554 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `NeedDaemonReload=no` |
| Ubuntu 24.04.5 | GNOME Wayland | 2839 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `NeedDaemonReload=no` |
| Ubuntu 26.04 | GNOME Wayland | 4056 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `NeedDaemonReload=no` |

三台均从非瞎拼来源开始，安装后由 GNOME 激活 `xiapin`；`sources` 首项为
`('ibus', 'xiapin')`，保留 `('xkb', 'us')`。静态组件和注册表元数据当前，`dpkg -V`
无输出。24.04 与 26.04 另外完成 remove→reinstall：remove 只移除瞎拼来源，旧 Engine
停止、其他来源保留；重装无需手工 setup，doctor 和真实按键再次通过。26.04 的首次
desktop 验收曾因外层执行环境 `HOME=/root` 查询了错误 IBus 缓存而出现一次假 failure；
改为桌面用户 `HOME=/home/xiapin` 后复验为 23 OK、0 failures。

三台重启前后都观察真实重启：Boot ID 改变，uptime 归零后重新增长，Engine PID 改变。

| 系统 | Boot ID（前 → 后） | 重启后 uptime | Engine PID（前 → 后） |
|---|---|---:|---|
| Ubuntu 22.04 | `0b4f6e5e-178a-4de5-babf-1d33c5f5e1f5` → `8ca88a33-217b-44da-868e-c1c76c78b9e6` | 29.17 s | 8133 → 1862 |
| Ubuntu 24.04 | `ca766248-53b4-456b-9fd4-3e16a6bbcf9c` → `915094fa-68e9-46bd-9802-793eab097770` | 60.38 s | 3380 → 2198 |
| Ubuntu 26.04 | `f91f623b-d099-4a38-a7f4-f9840915bc91` → `e5f24caf-48b3-4972-b537-8379a97cb7ca` | 66.20 s | 5884 → 2886 |

26.04 的同步 `systemctl reboot` 被 GNOME 会话的 shutdown block inhibitor 拒绝，因此使用
`systemctl reboot --ignore-inhibitors`；重启仍由 Boot ID、uptime 和新 Engine PID 确认，
不是假重启。三台真实桌面 IBus 总线安装后与重启后均输出：

```text
xiapin-ibus-integration-ok idle-passthrough=1 idle-space=1 commit=你好
edit=1 apostrophe=1 number=1 paging=1 partial=1 escape=1 enter=1
shift=1 ctrl-space=1 modified-shift=1 enter-passthrough=1
chinese-punctuation=，。 english-punctuation=,.
horizontal=1 page-size=9 emoji=😀 emoji-prefix=你好😀
```

其中 `enter-passthrough=1` 正是本版回归：中文模式输入 `sub` 后直接回车提交英文，
`Up`/`Down`/PageUp/PageDown 必须交还应用。三台最终状态建立外部磁盘快照
`passed-cold-cache-release-2.0.4`，不包含内存状态；26.04 因历史 overlay 文件名超过
255 字节，先将活动链安全 blockcommit 到父镜像，再建立短名快照。

## 人工验收边界

GTK、Qt、Firefox、Chromium/Electron 中的候选窗位置、挂起、多屏和分数缩放仍需按
`docs/RELEASE_ACCEPTANCE.md` 人工验收；自动化结果不能代替这些场景。Codex 和浏览器
地址栏中的方向键场景已由真实 IBus 客户端覆盖 Engine 行为，但应用级人工检查仍须在
发布后由最终桌面会话复验；未执行前不得记为人工通过。
