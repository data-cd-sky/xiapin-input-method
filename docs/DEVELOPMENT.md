# 瞎拼输入法开发说明

## 架构边界

2.0 的桌面协议层是 IBus，解码层是项目自有 C++ Engine，拼音算法和本地语言模型来自
LibIME。Engine 不启动、不嵌入 Fcitx 5，也不监管 `ibus-daemon`。仅在 1.x 升级导致
当前会话没有 IBus 总线时，`ibusctl.py` 启动一次 Ubuntu 自带的 IBus daemon。

运行时组件：

- `src/engine_core.*`：与 IBus 无关的输入状态、候选、学习和原子存储；
- `src/ibus_engine.cpp`：IBus Engine、按键映射、预编辑和敏感输入标记；
- `src/history_tool.cpp`：跨 LibIME 版本编译和导出历史文件；
- `libexec/ibusctl.py`：GNOME 输入源合并、当前会话注册和 1.x 升级协调；
- `libexec/memoryctl.py`：`.ucimem` 校验、导入、导出和旧学习数据转换；
- `scripts/legacy-fcitx-cleanup.sh` 与 `libexec/legacy_profilectl.py`：只用于恢复 1.x
  曾受管的配置。不得在新功能中依赖它们；
- `systemd/xiapin-bootstrap.service` 与 XDG autostart：每个图形会话执行幂等 setup；
- `systemd/xiapin-unlock.service`：仅当安装发生在锁屏时按解锁信号等待，回到普通桌面后
  完成选择并退出。它不轮询，也不监管 Engine 或 IBus 主进程。

Ubuntu 的 LibIME CMake 包和动态库依赖 Fcitx5Utils，因此构建需要
`libfcitx5utils-dev`，运行需要 `libfcitx5utils2`。这不是 Fcitx 框架集成。

## 兼容策略

最终 amd64 二进制必须在 Ubuntu 22.04 构建。不得在 24.04 或 26.04 构建后把同一包
宣称兼容 22.04。CMake 在构建时探测 LibIME 1.1 的光标候选 API；LibIME 1.0 使用
等价兼容路径。发布词典固定使用 LibIME 1.0 格式。

同一包需要在 Ubuntu 22.04/LibIME 1.0/GNOME X11、Ubuntu 24.04/LibIME 1.1/GNOME
Wayland、Ubuntu 26.04/LibIME 1.1/GNOME Wayland 分别安装和运行。依赖解析测试不能
替代桌面总线测试。

## 构建和测试

完整的跨系统操作步骤、证据要求和历史踩坑见
[`RELEASE_ACCEPTANCE.md`](RELEASE_ACCEPTANCE.md)。该文档是发布合同，本节只概括日常命令。

```bash
make check
make test
make deb
make release
```

`make test` 覆盖 C++ 核心、IBus 动态和静态工厂、Python 工具、Debian 维护脚本、
词典与图标。发布前还要在三个桌面环境中安装同一 SHA-256 的包，并记录会话类型、
服务状态、输入源列表和完整 IBus 验收输出。

`make deb` 必须在 Ubuntu 22.04 执行。`make release` 不重新编译二进制，只归档
`dist/` 中已通过三系统验收的包，并拒绝超过 Jammy GLIBC/GLIBCXX 上限的 ELF。

## 数据与并发

Engine 和记忆工具共同使用 `~/.local/share/xiapin/.memory.lock`。所有写入采用同目录临时
文件、`0600` 权限和原子替换。外部导入后增加 `.memory.generation` 并向 Engine 发送
SIGHUP；Engine 重新加载共享数据而不更换 PID。

用户词典或历史加载失败时必须隔离原文件，不能覆盖坏文件或阻止基础输入。归档读取必须
限制总尺寸、成员名、单成员尺寸、重复成员、符号链接、UTF-8、格式版本和 SHA-256。
密码、PIN 或 `IBUS_INPUT_HINT_PRIVATE` 上下文不能更新用户词典和历史。

Emoji 候选来自 `/usr/share/ibus/dicts/emoji-zh.dict`。`emoji_index.cpp` 直接读取 IBus
版本 5 的 GVariant 数据，建立“中文注释或描述 → Emoji”的只读索引。候选刷新只检查
首页前八个 LibIME 候选，并至多在第九位追加一个 Emoji。Emoji 选择直接提交并清空
上下文，不调用 LibIME 的选择或学习接口。解析失败必须降级为纯拼音输入。

## Debian 安装约束

- root 维护脚本不得遍历 home 或猜测桌面用户；
- setup 合并 GNOME 输入源，只把 `('ibus', 'xiapin')` 放首位；
- IBus 注册表刷新后必须等待 GNOME Shell 在新 IBus 总线上重新取得
  `org.freedesktop.IBus.Panel`，再触发输入源选择；
- 不得用 `ibus engine xiapin` 证明 GNOME 顶栏已切换。GNOME 的 `current` GSettings key
  已废弃且被忽略；验收必须从明确的非瞎拼来源开始观察 Shell 自己激活 Engine；
- 锁屏密码上下文不得强行启用第三方 Engine；锁屏安装只配置来源，由事件驱动的解锁
  helper 在普通桌面恢复后完成选择；
- remove 只移除瞎拼输入源，不改变其他键盘和输入法；
- remove 和重装必须停止当前用户所有精确匹配的瞎拼 `--ibus`/`--register` Engine，
  不能让已删除或替换的二进制继续驻留；
- 1.x 旧 autostart 通过 `dpkg-maintscript-helper rm_conffile` 无交互迁移；
- 正常登录不停止健康的 IBus；覆盖安装发现瞎拼的 symbol/icon 仍是旧值时，允许通过
  `ibus restart` 刷新一次注册表，并在 22.04 未自动拉起 daemon 时立即恢复总线；
- 包内不得含机器特定绝对路径、用户学习文件、VM 密钥或构建缓存。

## 发布门槛

1. Ubuntu 22.04 构建完成，测试与 lintian 没有 error；
2. 包的 GLIBC/GLIBCXX 需求不高于 Jammy；
3. 22/24/26 安装后无需注销或配置即可输入；
4. 24/26 上 remove→reinstall 保留其他输入源、停止旧 Engine 并恢复服务；
5. 1.0.11→2.0 无交互升级，学习数据迁移且无关 Fcitx 配置保留；
6. 新登录由 IBus component 的 `--ibus` 路径启动；
7. 锁屏恢复必须通过自动化回归；GTK、Qt、Firefox、Chromium/Electron、挂起和多屏按
   当次实际完成情况记录，未完成项必须在发布说明和 README 中明确列为人工验收项；
8. 清理后重新构建并冒烟三套系统，最终 SHA-256 写入发布目录的 `SHA256SUMS` 和
   `RELEASE_MANIFEST.yml`，不写进包内文档。

doctor 的 OK 数量会因学习文件是否已经创建而变化。验收以 `0 failures`、warning 解释和
具体检查项为准，不得写死 22 或 23 项。
