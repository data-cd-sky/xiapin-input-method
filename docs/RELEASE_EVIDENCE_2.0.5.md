# 瞎拼输入法 2.0.5 发布验收证据

验收日期：2026-11-25（Asia/Shanghai）

本文记录 2.0.5 的唯一 Jammy 构建包、三系统冷缓存直装、重启后复验和真实 IBus 按键
证据。长期规则见 `docs/RELEASE_ACCEPTANCE.md`。

## 缺陷和实现断言

- 中文模式下存在拼音组合时短按 Shift 或按 Ctrl+Space，切换前必须提交原始输入；
- 模式切换后组合、候选列表和候选位置必须同时失效，方向键和翻页键回到应用；
- 空闲状态切换模式不得产生 commit；
- 2.0.4 的回车英文提交与方向键透传、空格透传、编辑、标点、Emoji 和学习功能不得回退。

## 唯一候选包

正式包在 Ubuntu 22.04.5 内构建，三台虚拟机安装字节完全相同的文件：

```text
文件：xiapin-input-method_2.0.5_amd64.deb
大小：92788 bytes
SHA-256：6920de3f00aed0c4de2bbd1f22dee3dbffc7df5775eae938a5751fd2f5133cee
架构：amd64
Engine GLIBC 上限：2.34
Engine GLIBCXX 上限：3.4.29
```

Jammy 构建目录通过 48 项 Python 测试、原生 Engine 核心测试、动态注册 IBus 测试和
静态 `--ibus` IBus 测试；Jammy 与 Noble 的隔离 APT 运行依赖解析通过。Lintian 没有
error，唯一 warning 是延续自 2.0.4 的 `maintainer-script-calls-systemctl`。

## 冷缓存、重启和真实按键

三台安装的都是上述同一个文件，字节和 SHA-256 一致。安装前都明确 purge 并重启当前
IBus 用户服务，确认包、component、GNOME sources 和 IBus registry 均不含瞎拼。个人
学习文件未删除，安装前后哈希一致。

| 系统 | 会话 | 冷装耗时 | doctor | Engine / daemon | 按键回归 |
|---|---|---:|---|---|---|
| Ubuntu 22.04.5 | GNOME X11 | 10673 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `toggle-passthrough=1` |
| Ubuntu 24.04.5 | GNOME Wayland | 3219 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `toggle-passthrough=1` |
| Ubuntu 26.04 | GNOME Wayland | 6377 ms | 23 OK，0 warning，0 failure | 1 个静态 Engine / 1 个 daemon | `toggle-passthrough=1` |

三台均从 `('xkb', 'us')` 开始，安装后由 GNOME 激活 `xiapin`；`sources` 首项为
`('ibus', 'xiapin')`，保留原有键盘来源。`dpkg -V` 无输出。真实 IBus 输出均包含：

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
| Ubuntu 22.04 | `4c43eb30-20ed-4a37-8ac7-502193dc3ea4` → `f55fe2bd-f594-48bc-99aa-588888995b08` | 20 s | 12549 → 1843 |
| Ubuntu 24.04 | `e8f1fc32-43a9-4159-947a-3f0870e01db4` → `801d49ab-86c3-40df-9afe-1148ea1b12fc` | 26 s | 4014 → 2178 |
| Ubuntu 26.04 | `3a7201b8-9222-40e5-9c3f-f2daa6ef29d9` → `757a8575-b943-49fa-af9f-7279ba6374a7` | 30 s | 8229 → 3186 |

重启后三台 `xiapin-bootstrap.service` 与 GNOME IBus 服务 active，sources 仍含瞎拼，
当前 Engine 为 `xiapin`，doctor 均为 23 OK、0 failure，真实按键回归再次通过。

24.04 与 26.04 另外完成 remove→reinstall：remove 只移除瞎拼来源，其他来源保留，旧
Engine 停止、学习数据保留；重装无需手工 setup，sources 恢复、Engine 自动选中，
doctor 和真实按键再次通过。22.04 完成 2.0.4→2.0.5 覆盖升级后再次通过 doctor 与
`toggle-passthrough=1` 回归。

## 人工验收边界

GTK、Qt、Firefox、Chromium/Electron 中的候选窗位置、挂起、多屏和分数缩放仍需按
`docs/RELEASE_ACCEPTANCE.md` 人工验收；自动化结果不能代替这些场景。应用级人工检查
未执行前不得记为人工通过。
