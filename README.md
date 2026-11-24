# 瞎拼输入法（Xiapin）

瞎拼是面向 Ubuntu GNOME 的离线简体中文全拼输入法。2.0 自带 IBus Engine，直接使用
LibIME 完成拼音切分、整句候选和本地学习，不使用 Fcitx 5 输入法框架。

当前版本：**2.0.4**。发布包为 `xiapin-input-method_2.0.4_amd64.deb`，同一个文件支持
Ubuntu 22.04、24.04 和 26.04 amd64。包在 Ubuntu 22.04 构建，以该版本的 glibc、
libstdc++ 和 LibIME ABI 为兼容下限。

## 下载

从 [GitHub Releases](https://github.com/data-cd-sky/xiapin-input-method/releases/latest)
下载 `xiapin-input-method_2.0.4_amd64.deb`。同一页面提供 `SHA256SUMS`、源码归档和发布
说明；下载后可按“版本和安装包校验”一节核对哈希。

也可以直接下载当前版本：

```bash
curl -fLO https://github.com/data-cd-sky/xiapin-input-method/releases/download/v2.0.4/xiapin-input-method_2.0.4_amd64.deb
```

## 功能与隐私原则

- 支持整句输入、数字选词、候选翻页和候选鼠标点击；
- 使用 Ubuntu 自带中文 Emoji 数据，匹配首页中文候选并追加一个表情候选；
- 支持 `Left`、`Right`、`Home`、`End`、`Backspace`、`Delete` 和中间插入；
- 支持撇号分词，例如 `xi'an`；
- `Enter` 提交原始拼音，`Esc` 取消当前输入；
- 短按 Shift 或按 Ctrl+Space 切换中英文，Shift 与其他按键组合不会被吞掉；
- 中文模式自动使用 `，。！？；：` 等中文标点，英文模式使用 ASCII `,.!?;:`，无需
  单独设置全角或半角；
- 用户词典和历史仅保存在本机，支持校验、导出、合并导入和替换导入；
- 密码、PIN 和应用标记为私密的输入上下文不参与学习；
- 用户数据损坏时隔离坏文件，保留基础词典输入能力；
- 没有云拼音、账户、遥测或运行时词典下载。

候选框由 Ubuntu GNOME/IBus 绘制，固定使用紧凑横排，颜色和圆角随系统主题变化。
输入源图标使用 Ubuntu 橙色高光的像素墨镜，GNOME 顶栏使用墨镜短标识；核心输入功能
不依赖 GNOME Shell 扩展或自定义候选框主题。

## 支持范围与验证状态

| 系统 | 桌面会话 | 自动化验收 |
|---|---|---|
| Ubuntu 22.04.5 | GNOME X11 | 安装、重装、1.0.11 升级、学习数据迁移、真实 IBus 按键行为通过 |
| Ubuntu 24.04.5 | GNOME Wayland | 纯净直装、卸载后重装、重新登录、静态组件启动、真实 IBus 按键行为通过 |
| Ubuntu 26.04 | GNOME Wayland | 纯净直装、锁屏恢复、重启、静态组件启动、真实 IBus 按键行为通过 |

2.0.4 的最终三系统结果以
[`docs/RELEASE_EVIDENCE_2.0.4.md`](docs/RELEASE_EVIDENCE_2.0.4.md) 为准。测试不能替代
每个应用的人工候选窗检查，GTK、Qt、Firefox、
Chromium/Electron、挂起恢复、多屏和混合缩放仍应在发布前按“桌面验收”逐项检查。

## 快速安装 `.deb`

在包所在目录运行：

```bash
sudo apt install ./xiapin-input-method_2.0.4_amd64.deb
```

仓库构建产物位于 `dist/` 时运行：

```bash
sudo apt install ./dist/xiapin-input-method_2.0.4_amd64.deb
```

必须使用 APT 安装本地包。APT 会从当前 Ubuntu 软件源安装 IBus、LibIME、字体和 GTK
输入模块等依赖。单个 `.deb` 不复制 Ubuntu 自带运行库；完全离线安装需要离线 APT
源或预先缓存依赖。

安装完成后不需要另开终端执行 setup、不需要重启，也不需要手动添加输入源。活动 GNOME 会话
会立即把“瞎拼输入法”加入输入源并选中；没有活动桌面会话的用户在下次登录自动完成。
安装脚本保留已有键盘和其他输入法，只把瞎拼放到首位。

如果安装时桌面正处于锁屏密码界面，APT 会先正常完成；解锁回到普通桌面后，瞎拼自动
完成选中。安装结束会打印可选检查命令 `ubuntu-cn-input-doctor`，用户无需运行该命令
才能使用。

在 GNOME“设置 → 键盘 → 添加输入源”中，瞎拼归类在“汉语”下，显示名为“瞎拼输入法”。
`xiapin` 只是在配置文件和诊断输出中使用的内部 Engine ID，不是面向用户的显示名。

1.x 升级时，安装程序会恢复旧版受管的桌面配置，把旧 Fcitx 路径中的用户词典和历史
迁入 2.0 私有目录，并停止旧的瞎拼 Fcitx 进程。与瞎拼无关的 Fcitx profile 项和用户
配置不会删除。

## 桌面验收

安装后先运行：

```bash
ubuntu-cn-input-doctor
```

再在常用 GTK、Qt、Firefox 和 Chromium/Electron 应用中检查：

1. 输入 `nihao`，空格提交“你好”；
2. 在 `nihao` 中移动光标，使用删除键和字母修改；
3. 输入 `xi'an`，数字 1 提交“西安”；
4. 使用 PageUp/PageDown 或 `-`/`=` 翻页；
5. 使用 Esc、Enter、短按 Shift 和 Ctrl+Space；
6. 中文模式输入 `sub` 后直接回车提交英文，再按 `Up`/`Down` 和 PageUp/PageDown，
   确认按键交给应用；
7. 锁屏解锁和挂起恢复后重复上述操作；
8. 中文模式输入 `,.!?;:`，确认得到 `，。！？；：`；切换英文后确认得到 ASCII 标点；
9. 多屏或分数缩放环境中，把输入框移到各屏边缘检查候选窗位置；
10. 输入 `xiaolian`，确认第 9 个候选为 😀，按数字 9 提交表情。

## 升级

在新版 `.deb` 所在目录重复 APT 安装：

```bash
sudo apt install ./xiapin-input-method_2.0.4_amd64.deb
```

查看已安装版本：

```bash
dpkg-query -W -f='${Version}\n' xiapin-input-method
```

升级和重装不会删除 `~/.local/share/xiapin/` 中的本地学习数据。

## 卸载、清理和恢复

```bash
sudo apt remove xiapin-input-method
```

卸载会停止本包的用户服务，并从活动用户的 GNOME 输入源中只移除 `ibus:xiapin`。
已有键盘和其他输入法保持原顺序。用户学习数据不会自动删除，以便以后重装恢复。

如需自行删除学习数据，请先备份，再删除以下目录：

```text
~/.local/share/xiapin/
~/.local/state/ubuntu-cn-input/memory/
```

这是不可恢复的数据删除操作，因此安装包不会自动执行。

## 本地学习与跨电脑迁移

2.0 学习数据位于：

```text
~/.local/share/xiapin/user.dict
~/.local/share/xiapin/user.history
```

常用命令：

```bash
ubuntu-cn-input-memory status
ubuntu-cn-input-memory export ~/xiapin.ucimem
ubuntu-cn-input-memory verify ~/xiapin.ucimem
ubuntu-cn-input-memory import ~/xiapin.ucimem
ubuntu-cn-input-memory import ~/xiapin.ucimem --replace
```

默认导入会与现有词典和历史合并，`--replace` 完全替换。写入前会在
`~/.local/state/ubuntu-cn-input/memory/backups/` 自动保存当前数据，随后向运行中的
Engine 发送 SIGHUP 原位重载，进程无需重启。

`.ucimem` 是含版本、尺寸和逐文件 SHA-256 的 ZIP 容器，文件权限为 `0600`，但没有
加密。文件可能包含姓名、项目名和输入历史，请使用可信或加密介质传输。

完整命令说明见：

```bash
man ubuntu-cn-input-memory
```

## 词典来源和许可证

基础候选来自目标系统的 `/usr/share/libime/sc.dict`。包内补充词典由 `data/base.tsv`
和 `data/hotwords.tsv` 构建，共 243 条；其来源、审阅规则和兼容格式说明见
[`data/SOURCES.md`](data/SOURCES.md)。项目不复制商业输入法词库或用户数据。

项目源码与自建词表使用 MIT 许可证。Ubuntu 提供的 IBus、LibIME、语言模型和字体遵循
各自许可证。

## 技术架构与语言

运行链路：

```text
应用 / GNOME → IBus → 瞎拼 Engine → LibIME → 系统词典 + 本地学习数据
                              └→ 系统中文 Emoji 数据（只读）
```

LibIME 在 Ubuntu 中会动态链接 `libFcitx5Utils.so.2`，所以 `.deb` 依赖
`libfcitx5utils2`。这是 LibIME 的底层 ABI 依赖，不表示瞎拼集成或启动 Fcitx 5。

完全不用 Fcitx 和 IBus 在技术上可行，但需要自行维护 GTK 3/4、Qt 5/6、XIM、GNOME
Wayland 特权输入通道以及浏览器和沙箱兼容层。2.0 使用 IBus 作为桌面协议层，自有 Engine
直接调用 LibIME，以较小权限和维护范围覆盖 Ubuntu 22.04、24.04、26.04。

主要实现语言：C++20 用于 Engine 和历史格式工具，Python 3 用于安装协调与记忆迁移，
Shell 用于构建、测试和 Debian 维护脚本。

## 源码目录

```text
xiapin-input-method/
├── src/             Engine、LibIME 核心和历史转换工具
├── ibus/            IBus component 元数据
├── libexec/         会话协调、记忆工具和 1.x 升级兼容层
├── data/            离线补充词典及来源说明
├── debian/          Debian 打包元数据和维护脚本
├── systemd/         用户会话一次性配置服务
├── desktop/         XDG 登录兜底入口
├── tests/           单元、核心和 IBus 集成测试
├── docs/            架构、开发和命令文档
├── build/           本地中间产物，不属于源码
└── dist/            最终 `.deb` 和发布产物
```

## 从源码构建

Ubuntu 22.04 是正式发布构建环境：

```bash
sudo apt update
sudo apt install build-essential debhelper cmake ninja-build g++ pkg-config \
  libibus-1.0-dev libimecore-dev libimepinyin-dev libfcitx5utils-dev \
  libboost-dev libime-bin libime-data libime-data-language-model \
  python3 python3-gi python3-pil ffmpeg lintian shellcheck
```

然后运行：

```bash
make check
make test
make deb
sha256sum dist/xiapin-input-method_2.0.4_amd64.deb
```

`make deb` 优先使用 debhelper；缺少 debhelper 时使用 `scripts/build-deb.sh` 构建兼容的
二进制包。公开发布必须使用 Ubuntu 22.04 构建结果并在三套系统重装复验。

## 测试覆盖

开发、三系统冷缓存测试、重启复验、人工验收、发布证据和历史踩坑的完整标准见
[`docs/RELEASE_ACCEPTANCE.md`](docs/RELEASE_ACCEPTANCE.md)。换电脑或更换维护者后也必须按
该文档执行，不能用旧包覆盖安装或单机测试代替发布矩阵。

2.0.4 的候选包哈希、冷装结果、顶栏选择和重启证据见
[`docs/RELEASE_EVIDENCE_2.0.4.md`](docs/RELEASE_EVIDENCE_2.0.4.md)。2.0.2 的记录保留为
历史资料，其中仅凭 `ibus engine` 判断 GNOME 顶栏已经切换的结论已在 2.0.3 证据中撤回。

- Python 单元测试：输入源合并、IBus 缺失恢复、旧配置恢复、记忆校验和迁移；
- 原生核心测试：候选、编辑、翻页、部分选词、学习、敏感字段、Emoji 和切换；
- IBus 集成测试：动态注册与普通 `--ibus` 组件路径上的完整按键序列；
- Debian 测试：依赖、文件、ABI、维护脚本、卸载/重装和旧 conffile 迁移；
- 字典和图标测试：词表去重回读、22.04 格式兼容和小尺寸 SVG 渲染；
- 虚拟机验收：22.04 X11、24.04/26.04 Wayland 的零残留直装、真实桌面总线、锁屏恢复、
  静态组件启动，以及 1.0.11 数据升级。

## 故障排查

```bash
ubuntu-cn-input-doctor
journalctl --user -u xiapin-bootstrap.service --since today
pgrep -af ibus-engine-xiapin
```

- 找不到瞎拼：确认 `/usr/share/ibus/component/xiapin.xml` 存在，运行
  `/usr/libexec/xiapin/ibusctl.py setup` 并查看用户服务日志；
- 已安装但无法输入：运行 `/usr/libexec/xiapin/ibusctl.py setup`，再查看用户服务日志；
- 个别应用没有候选框：关闭并重新打开该应用，记录其 GTK/Qt/Electron 版本和
  Wayland/XWayland 模式；
- 学习文件损坏：Engine 会把文件改名为 `.corrupt-时间戳` 并继续使用基础词典；
- 中文显示为方框：确认 `fonts-noto-cjk` 已安装且 locale 使用 UTF-8。
- Emoji 显示为方框：确认 `ibus-data` 和 `fonts-noto-color-emoji` 已安装；缺少或损坏的
  Emoji 数据只会关闭表情候选，不影响普通拼音输入。

## 版本和安装包校验

```bash
cat VERSION
dpkg-deb -f dist/xiapin-input-method_2.0.4_amd64.deb Package Version Architecture Depends
sha256sum dist/xiapin-input-method_2.0.4_amd64.deb
```

安装前应把 SHA-256 与发布说明逐字符比较。

## 已知限制

- 只发布 amd64 包；其他架构需要在对应的 Ubuntu 22.04 构建环境重新编译；
- 当前只支持全拼，没有双拼、模糊音或图形设置页；中英文模式自动决定标点形式，不提供
  独立全角/半角开关；
- 每次输入只追加一个 Emoji 候选，不提供独立的表情分类浏览器；
- 候选框样式由 GNOME/IBus 控制；
- `.ucimem` 有完整性校验但不加密；
- 完全离线安装需要用户自行准备 Ubuntu 依赖源；
- GTK/Qt/浏览器候选窗、挂起、多屏和混合缩放人工检查完成前不应宣称这些场景已验收。

许可证：MIT，详见 [`LICENSE`](LICENSE)。
