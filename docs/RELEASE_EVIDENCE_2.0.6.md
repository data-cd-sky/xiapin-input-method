# 瞎拼输入法 2.0.6 发布验收证据

验收日期：2026-11-25（Asia/Shanghai）

本文记录 2.0.6 的唯一 Jammy 构建包、三系统冷缓存直装、重启后复验和真实 IBus 按键
证据。长期规则见 `docs/RELEASE_ACCEPTANCE.md`。

## 缺陷和实现断言

- 残留的失效来源 `('xkb', 'cn')` 在解锁时无法被 IBus 解析，GNOME 退回键盘布局，
  Shift / Ctrl+Space 无法唤出瞎拼；
- 安装和每次图形登录的 setup 必须查询 `ibus list-engine`，自动移除无法解析的来源，
  同时清理 `mru-sources`；
- XKB 来源按 `layout` / `layout+variant` 匹配 `xkb:<layout>:<variant>:`，
  `('xkb', 'us+intl')` 等有效键盘布局必须保留；
- 查询失败或结果中没有 `xkb:` Engine 时不得删除任何来源；
- 清理与首次选源合并为一次 `sources` 写入，避免 Shell 取消进行中的 `SetEngine`；
- 2.0.5 的 Shift / Ctrl+Space 提交未转换拼音、2.0.4 的回车英文提交与方向键透传不得
  回退。

## 唯一候选包

正式包在 Ubuntu 22.04.5 内构建，三台虚拟机安装字节完全相同的文件：

```text
文件：xiapin-input-method_2.0.6_amd64.deb
大小：96492 bytes
SHA-256：0064aa997138d9dbb5db50f9f4f3001f7f4e57e7e8c6e39a81a9ef603daa58af
架构：amd64
Engine GLIBC 上限：2.34
Engine GLIBCXX 上限：3.4.29
```

Jammy 构建目录通过 53 项 Python 测试、原生 Engine 核心测试、动态注册 IBus 测试和
静态 `--ibus` IBus 测试；Jammy 与 Noble 的隔离 APT 运行依赖解析通过。Lintian 没有
error，唯一 warning 是延续自 2.0.4 的 `maintainer-script-calls-systemctl`。

## 失效来源清理

三台在 purge 后的冷缓存状态下都先写入以下来源再直装，其中 `xkb:cn` 在
`ibus list-engine` 中确实不存在（匹配数为 0）：

```text
sources    = [('xkb','us'), ('xkb','cn'), ('xkb','us+intl')]
mru-sources= [('xkb','cn'), ('xkb','us+intl'), ('xkb','us')]
```

| 系统 | 安装耗时 | 安装后 sources | 坏源 | us+intl | 当前 Engine |
|---|---:|---|---|---|---|
| Ubuntu 22.04.5 | 10202 ms | `[('ibus','xiapin'),('xkb','us'),('xkb','us+intl')]` | 已移除 | 保留 | `xiapin` |
| Ubuntu 24.04.5 | 3374 ms | 同上 | 已移除 | 保留 | `xiapin` |
| Ubuntu 26.04 | 5118 ms | 同上 | 已移除 | 保留 | `xiapin` |

三台的 `mru-sources` 都变为 `[('ibus','xiapin'),('xkb','us+intl'),('xkb','us')]`，
不含 `xkb:cn`。安装代码只写 `sources` 一次完成清理与选中，安装退出码为 0，没有出现
“清理成功但 Shell 未激活”的误报。

## 冷缓存、重启和真实按键

三台安装的都是上述同一个文件，字节和 SHA-256 一致。安装前都明确 purge 并重启当前
IBus 用户服务，确认包、component、GNOME sources 和 IBus registry 均不含瞎拼。个人
学习文件未删除，安装前后哈希一致。

| 系统 | 会话 | doctor | Engine / daemon | 按键回归 |
|---|---|---|---|---|
| Ubuntu 22.04.5 | GNOME X11 | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `toggle-passthrough=1` |
| Ubuntu 24.04.5 | GNOME Wayland | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `toggle-passthrough=1` |
| Ubuntu 26.04 | GNOME Wayland | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `toggle-passthrough=1` |

三台均从非瞎拼来源开始，安装后由 GNOME 激活 `xiapin`；`sources` 首项为
`('ibus', 'xiapin')`。`dpkg -V` 无输出。真实 IBus 输出均包含：

```text
xiapin-ibus-integration-ok idle-passthrough=1 idle-space=1 commit=你好
edit=1 apostrophe=1 number=1 paging=1 partial=1 escape=1 enter=1
shift=1 ctrl-space=1 modified-shift=1 enter-passthrough=1
toggle-passthrough=1 chinese-punctuation=，。 english-punctuation=,.
horizontal=1 page-size=9 emoji=😀 emoji-prefix=你好😀
```

三台都执行真实重启，Boot ID 改变、uptime 归零后重新增长、Engine PID 改变：

| 系统 | Boot ID（前 → 后） | 重启后 uptime | Engine PID（前 → 后） |
|---|---|---:|---|
| Ubuntu 22.04 | `f55fe2bd-f594-48bc-99aa-588888995b08` → `476e96d1-deb4-4208-9bc9-e8b5fb193c86` | 58 s | 119244 → 1705 |
| Ubuntu 24.04 | `79ad55ed-c809-4952-be34-41cdf70d5879` → `af7118c6-7a04-49e6-8e84-12d817d1f9c4` | 58 s | 2226 → 2224 |
| Ubuntu 26.04 | `07df2cfc-afe7-46c3-8490-b1ed5c98f3e8` → `703af12e-81ed-4e36-ba5c-2ab048c5006a` | 61 s | 8082 → 3269 |

重启后三台均为 23 OK、0 failure，`sources` 仍不含 `xkb:cn`、保留 `us+intl`，
`xiapin-bootstrap.service` 与 GNOME IBus 服务 active，真实按键输出再次全部通过。

## 重装、覆盖升级和锁屏

- 24.04 与 26.04 的 remove→reinstall：卸载只移除 `ibus:xiapin`，保留
  `('xkb','us')` 和 `('xkb','us+intl')`；旧 Engine 进程归零；学习数据保留；重装后自动
  恢复 2.0.6、单 Engine、单 daemon、23 OK 和完整按键回归；
- 26.04 的 2.0.5 → 2.0.6 覆盖升级：升级前 `sources` 同时含 `xkb:cn` 与
  `xkb:us+intl`，升级后 `xkb:cn` 从 `sources` 和 `mru-sources` 中消失，`us+intl`
  保留；学习数据和 Engine 进程正常，按键回归通过；
- 26.04 锁屏安装：锁屏状态下 purge 后注入 `xkb:cn`，APT 正常结束，密码上下文没有强制
  启用第三方 Engine；`xiapin-unlock.service` 在锁屏期间 active，解锁后自动选中
  `xiapin`，坏源已被清理，服务自行退出；
- 26.04 解锁回归：正常锁屏/解锁后 Engine 仍为 `xiapin`，真实按键通过，用户日志中
  `Cannot find engine xkb:cn` 出现 0 次；
- 26.04 失效来源对照：把 `('xkb','cn')` 设为唯一来源后解锁，Engine 停在
  `xkb:us::eng`，复现用户“唤不醒”的现象；运行安装/登录同一路径的
  `ibusctl.py setup` 后恢复为 `xiapin`，坏源被移除，按键回归通过。

## 未验收项

GTK、Qt、Firefox、Chromium/Electron 的候选窗外观、挂起恢复、多屏和分数缩放仍未做
人工验收；本记录不把它们推断为通过。
