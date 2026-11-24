# 中文输入法功能对比与 2.x 路线

## 当前定位

| 方案 | 优势 | 与瞎拼 2.0 的差异 |
|---|---|---|
| 搜狗、微软拼音、macOS 拼音 | 大词库、产品化设置、跨功能整合 | 多为闭源或平台限定；瞎拼优先离线、可审计和 Ubuntu 一包安装 |
| Rime | 高度可配置、方案丰富、本地数据 | 瞎拼配置面更小，固定为 LibIME 全拼与 GNOME 原生候选框 |
| Fcitx 5 拼音 | Linux 前端覆盖广、LibIME 功能完整 | 瞎拼 2.0 不使用 Fcitx 框架，只复用 LibIME 算法库 |
| IBus LibPinyin | GNOME 集成成熟 | 使用 LibPinyin；瞎拼使用自有 IBus Engine 和 LibIME |
| 瞎拼 2.0 | 离线、可编辑整句、私有学习、可迁移、三代 Ubuntu ABI | 当前没有双拼、模糊音、设置页和自定义候选主题 |

## 后续优先级

1. 完成 GTK/Qt/浏览器/Electron、锁屏、挂起和多屏人工矩阵；
2. 增加删除误学词、暂停学习和清空数据的安全命令；
3. 建立固定语料的候选准确率和按键延迟基线；
4. 增加可选双拼、模糊音和本地领域词典；
5. 仅在不影响核心 Engine 和三版本兼容时考虑图形设置页。

候选皮肤、云同步、本地模型重排和复杂扩展不应早于输入正确性、升级安全和应用兼容。

## 数据边界

2.0 私有数据是 `$XDG_DATA_HOME/xiapin/user.dict` 与 `user.history`。导出归档包含可读
UTF-8 数据和校验值但不加密。项目不会将数据上传到服务器。旧 Fcitx 路径只在一次性
升级迁移和状态诊断中读取，不再作为 2.0 日常运行目录。

## 参考实现

- [LibIME](https://github.com/fcitx/libime)
- [IBus](https://github.com/ibus/ibus)
- [IBus LibPinyin](https://github.com/libpinyin/ibus-libpinyin)
- [Rime](https://github.com/rime/home)
