# 瞎拼开发、测试与发布验收手册

本文是跨电脑继续迭代时的发布合同。新环境、维护者和自动化代理必须按本文执行，不依赖
聊天记录或某台机器的历史状态。功能没有满足全部强制门槛时，不得因“当前能输入”而宣布
完成。

## 不可退让的产品要求

- 一个 Ubuntu 22.04 构建的 amd64 DEB 同时支持 Ubuntu 22.04、24.04 和 26.04；
- 用户通过 APT 安装本地 DEB，依赖由包元数据和 Ubuntu 软件源解决；
- 活动 GNOME 会话安装后无需运行 setup、手动添加输入源、注销或重启即可使用；
- 设置中显示在“汉语 → 瞎拼输入法”，`xiapin` 仅为内部 Engine ID；
- 顶栏短标识为 😎，Engine 元数据必须包含中文名称、`zh_CN`、SVG 图标和该符号；
- 候选固定横排，每页 9 项；现有输入、编辑、翻页、学习、Emoji 和导入导出功能不得回退；
- 中文模式自动输出中文标点，英文模式输出 ASCII 标点，不提供独立全角/半角状态；
- 卸载只移除瞎拼，不改变其他键盘或输入法，不删除个人学习数据；
- 不使用 Fcitx 5 输入法框架。`libfcitx5utils2` 只是 Ubuntu LibIME 的 ABI 依赖；
- 不含联网拼音、遥测、账号、运行时下载、个人路径、凭据或测试用户数据。

## 支持矩阵

| 系统 | 会话 | 构建用途 | 必测用途 |
|---|---|---|---|
| Ubuntu 22.04 | GNOME X11 | 唯一正式 amd64 构建环境 | 冷装、升级、重启、真实按键 |
| Ubuntu 24.04 | GNOME Wayland | 不得替代 22.04 构建 | 冷装、重装、重启、真实按键 |
| Ubuntu 26.04 | GNOME Wayland | 开发可用，正式包仍来自 22.04 | 冷装、重装、重启、真实按键 |

三台必须安装字节完全相同的候选包。记录并比较 SHA-256，不能分别在三台构建“同版本”包。
依赖解析测试不能代替真实桌面测试，私有 `dbus-run-session` 测试也不能代替 GNOME 会话。

## 发布流程

### 1. 源码检查

在工作树运行：

```bash
make check
make test
```

必须满足：Shell/Python 静态检查、全部 Python 测试、原生 LibIME 核心测试、动态注册测试和
静态 `--ibus` 工厂测试通过。测试数量会随版本变化，不以固定数量作为门槛，以退出码和
失败项为准。

### 2. 在 Ubuntu 22.04 干净构建

从显式源码清单创建干净目录，不复用其他系统生成的 ELF 或陈旧 `build/`：

```bash
make deb
sha256sum dist/xiapin-input-method_*_amd64.deb
dpkg-deb -f dist/xiapin-input-method_*_amd64.deb \
  Package Version Architecture Depends
```

`make deb` 必须完成 Jammy/Noble 依赖解析，ELF 所需 GLIBC 不高于 2.34，GLIBCXX 不高于
3.4.29。构建输出中的 warning 要逐项判断；lintian error 或测试失败禁止发布。

### 3. 每台虚拟机建立真正的冷缓存基线

冷缓存的目的，是复现“用户从未成功安装过当前包”，防止旧包留下的 IBus 注册缓存掩盖
首次安装缺陷。每台测试机都要满足：

```text
package=absent
component=absent
GNOME sources 中没有 ('ibus', 'xiapin')
IBus registry 中没有 xiapin
IBus daemon 只有一个且由 GNOME 用户服务管理
```

步骤：

1. 先记录 `~/.local/share/xiapin/` 内所有文件的 SHA-256，不删除该目录；
2. `apt purge xiapin-input-method`，不得执行会删除学习数据的自定义清理；
3. 确认 `/usr/share/ibus/component/xiapin.xml` 不存在；
4. 在真实桌面用户环境中执行 `ibus write-cache`，使注册表明确不含瞎拼；
5. 让 IBus 恢复到单 daemon、GNOME 服务 active 的正常状态；
6. 确认 GNOME sources 和 IBus registry 均不含瞎拼。

Ubuntu 22.04 的 `ibus restart` 可能成功退出却只停止 daemon，不会自动拉起。此时应通过
当前桌面用户的 systemd 服务恢复 `org.freedesktop.IBus.session.GNOME.service`，等待总线
可用后继续。不要立即另起一个 `ibus-daemon --daemonize`，否则可能形成双 daemon 或把
IBus 地址文件指向竞争失败的进程。

### 4. 冷缓存直接安装

只执行用户会执行的命令，不手工调用项目 setup：

```bash
sudo apt install ./xiapin-input-method_VERSION_amd64.deb
```

安装完成后立即验证：

```bash
ubuntu-cn-input-doctor
gsettings get org.gnome.desktop.input-sources sources
ibus engine
pgrep -af '^/usr/libexec/ibus-engine-xiapin'
dpkg -V xiapin-input-method
```

强制通过条件：

- doctor 为 `0 failures`；warning 必须解释并在发布前消除或列为已知限制；
- 不要写死 doctor 的 OK 数量。未创建学习数据时通常是 22 OK；存在 `user.dict` 和
  `user.history` 且权限正确时通常是 23 OK；
- sources 包含 `('ibus', 'xiapin')`，且保留原有输入源；
- 当前 Engine 为 `xiapin`；
- 安装前必须让 GNOME 当前来源明确不是瞎拼；安装代码和测试不得执行
  `ibus engine xiapin`。只有 GNOME Shell 根据 `sources` 变化自行激活后观察到
  `global-engine-changed`/当前 Engine 变为 `xiapin`，才能证明顶栏选择路径成功；
- `org.gnome.desktop.input-sources current` 已废弃并被 GNOME Shell 忽略，不得把它作为
  顶栏当前来源证据；
- IBus 注册表中的 symbol/icon/longname/language 分别为 😎、SVG 路径、瞎拼输入法、
  `zh_CN`；
- 只有静态 `/usr/libexec/ibus-engine-xiapin --ibus`，不得以 `--register` 临时 Engine
  充当安装成功；
- `xiapin-bootstrap.service` 和 GNOME IBus 服务 active，只有一个 IBus daemon；
- `dpkg -V` 无输出；
- 安装前后学习数据逐文件 SHA-256 完全一致。

### 5. 真实 IBus 按键验收

在每台真实桌面 IBus 总线上运行 `tests/ibus-integration-client.py`，不得只在私有测试总线上
运行。通过输出应覆盖：

```text
commit=你好 edit=1 apostrophe=1 number=1 paging=1 partial=1
escape=1 enter=1 shift=1 ctrl-space=1 modified-shift=1
idle-passthrough=1 idle-space=1 chinese-punctuation=，。 english-punctuation=,.
horizontal=1 page-size=9 emoji=😀 emoji-prefix=你好😀
```

真实输入会正常更新 `user.history`，因此“安装不改学习数据”的哈希比较必须在这一步之前
完成。真实输入后的历史哈希变化不是安装缺陷。

### 6. 重启后复验

三台都做一次完整正常重启。以 uptime 变小和 Engine PID 改变确认机器确实重启，不能只看
重启命令返回成功。重启后再次验证：

- 图形会话、GNOME IBus 服务和 `xiapin-bootstrap.service` active；
- 输入源仍含瞎拼，当前 Engine 可选，进程为静态 `--ibus`；
- doctor 为 0 failures；
- 再跑一次真实 IBus 按键测试。

若 GNOME 阻止自动化重启，优先正常结束阻止任务或使用 systemd 的忽略 inhibitor 选项，
仍需走正常文件系统同步和服务停止流程。禁止把未发生的重启记为通过，禁止强制断电代替
生命周期测试。

### 7. 升级、重装与卸载专项

发布前至少验证：

- 当前版本覆盖重装不会继续运行已删除的旧 Engine；
- 旧包直接升级后元数据不是旧 symbol/icon，学习数据保留；
- remove 后 sources 只失去瞎拼，其他输入源顺序不变；
- remove 后重新安装与冷装一样自动完成；
- 1.0.11 升级能迁移学习数据，并只恢复可证明由旧瞎拼管理的 Fcitx 配置；
- 无活动图形会话时 APT 正常完成，首次图形登录自动 setup。
- 锁屏安装时 APT 先结束，密码上下文不强制启用第三方 Engine；无轮询解锁 helper 保持
  等待，解锁回到普通桌面后自动选择并退出。

### 8. 人工桌面验收

自动化通过后，在真实应用中检查 GTK、Qt、Firefox、Chromium/Electron：

1. `nihao` 空格提交“你好”；
2. 中间移动光标、删除和插入；
3. `xi'an` 使用数字 1 提交“西安”；
4. PageUp/PageDown 和 `-`/`=` 翻页；
5. Esc、Enter、短按 Shift、Ctrl+Space；
6. `xiaolian` 第 9 项为 😀，数字 9 提交；
7. 候选框横排、位置正确，顶栏显示 😎；
8. 锁屏、挂起、多屏和分数缩放后重复核心输入。
9. 中文模式输入 `,.!?;:` 得到 `，。！？；：`，英文模式得到 ASCII 标点；项目中没有
   独立全角/半角开关。

未执行的应用或硬件项必须在 README/发布说明中标为“未人工验收”，不能从 Engine 测试
推断通过。

### 9. 发布物和隐私检查

发布前只保留当前版本，旧候选必须移出 `dist/`，避免用户误装。运行 `make release` 后：

- `SHA256SUMS` 全部通过；顶层 DEB 与发布目录 DEB 字节一致；
- DEB、源码归档和维护脚本不含机器特定的用户主目录绝对路径、工作区路径、ISO/qcow2、`.ucimem`、
  `user.dict`、`user.history`、密码、令牌或私钥；
- 邮箱只能是明确的 `example.org`/`example.invalid` 占位地址；
- 文档中的版本、安装命令、支持矩阵、已知限制与实际测试一致；
- 三台通过后再建立带版本号的虚拟机快照。

## 已踩过的坑与规避规则

### 旧 IBus 缓存造成“能输入但设置里找不到”

临时 `--register` Engine 能接收按键，却不会成为 GNOME 可持久枚举的输入源。首次安装必须
刷新旧注册缓存并验证完整静态元数据。doctor 必须把缺少静态注册或仅有 `--register`
判为失败。

### 覆盖安装通过不代表首次安装通过

旧包可能已经把 component 写进 IBus registry。每个候选都要从组件不存在、registry 不含
瞎拼的冷缓存状态直装，不能只测“旧包再装新包”。

### 测试可执行文件存在不代表它来自当前源码

集成测试必须在运行前执行一次增量构建，不能用“目标文件存在”作为跳过编译的条件。源码
修改后残留的旧 Engine 既可能制造假失败，也可能让新回归测试误用旧逻辑而产生假成功。
项目目录改名或移动后，CMake 缓存中的源码绝对路径也会失效；此时应清理可再生成的
`build/` 后重新配置，不能修改缓存路径后继续复用旧对象文件。

### IBus 重启具有版本差异

22.04 可能只停不启，24/26 常由 systemd 异步拉起。重启后先等待总线，再恢复 GNOME 服务，
最后才允许非 systemd 桌面使用直接 daemon 兜底。不要并发启动第二个 daemon。

### IBus 总线可用不代表 GNOME Shell 已经就绪

`ibus list-engine` 可能在新 daemon 出现后立即成功，但 GNOME Shell 仍在异步重连。首次
安装刷新注册表后，必须等待 `org.freedesktop.IBus.Panel` 在同一 IBus 总线上有 owner，
再修改 `sources` 触发 Shell 重建来源。固定 sleep、`ibus engine xiapin` 和已废弃的
GSettings `current` 都不能证明顶栏同步。

### Jammy 的 deb-systemd-invoke 不支持用户 daemon-reload

Ubuntu 22.04 的 `deb-systemd-invoke --user` 只支持 start/stop/restart；对 daemon-reload
不会像 24.04/26.04 新版一样逐个联系用户 manager。安装脚本必须枚举已经运行的
`user@数字.service`，通过 systemd 249 支持的 `systemctl --user --machine=UID@ daemon-reload`
先 reload，再 restart bootstrap。冷装后检查 `NeedDaemonReload=no`，不能因服务 active 就
忽略“unit changed on disk”警告。

### PyGObject Bus 对象可能保留重启前状态

IBus 重启后应在新进程中读取 Engine 元数据。复用旧 GI Bus 可能误报缺失或读到旧 descriptor。

### doctor 的 OK 数量不是固定协议

无学习文件时一项检查即可通过；有两个学习文件时会分别检查权限。验收看 failures、warnings
和具体检查项，不以 22/23 等固定数字作为唯一标准。

### 空组合时空格必须透传

空格在有拼音组合时用于选词，在没有组合时必须返回给应用。真实 IBus 测试还必须覆盖
退格、删除、方向键、回车、翻页、数字和普通符号等空组合透传。测试输出必须包含
`idle-passthrough=1 idle-space=1`，不能只测试 `nihao` 后按空格选词。

### `/tmp` 测试脚本会在重启后消失

重启后真实按键复验前重新上传或从持久位置读取客户端。脚本不存在不能记为输入法失败，
也不能因此跳过重启后的输入测试。

### 自动化命令成功不等于动作发生

重启可能被 inhibitor 拒绝；异步服务可能稍后才恢复。用 uptime、PID、服务状态和最终功能
交叉验证，不以命令返回或等待固定秒数代替状态检查。

### 学习历史会被真实输入测试更新

先验证安装前后哈希，再执行真实输入。不要在真实按键测试后要求历史文件哈希不变。

### 多层 Shell 引号容易使测试根本没有送入虚拟机

复杂 guest-agent 脚本应通过文件或 Base64 传递。每次检查 guest-exec 的退出码和输出，不能
把宿主 shell 的语法失败误认为虚拟机测试结果。

### 测试命令必须使用真实桌面会话类型

从 root 或 guest agent 进入桌面用户总线时，应从 `loginctl` 读取当前会话类型，并传入该
会话已有的 `DISPLAY`、`WAYLAND_DISPLAY`、`XDG_RUNTIME_DIR` 和用户 D-Bus 地址。22.04 X11
测试必须取消 `WAYLAND_DISPLAY`，24/26 Wayland 测试必须保留它；不能给三台套同一组环境
变量。否则 `ibus` 可能寻找错误的地址文件，出现 daemon 明明 active 却无法连接的假失败。

### 测试机状态必须与本机隔离

开发自动化只操作明确命名的虚拟机。用户要求本机回退后，不得在三系统全部通过前重新安装。
删除包、快照或学习数据前核对目标；学习数据默认永不自动删除。

## 每次发布应记录的证据

建议在当次发布记录中保存：版本、源码状态、构建系统、DEB SHA-256、三台系统版本和会话
类型、冷缓存断言、doctor 摘要、元数据、服务与进程状态、安装前后学习数据比较、真实按键
完整输出、重启证据、人工矩阵、隐私扫描和快照名。没有证据的项目视为未验收。
