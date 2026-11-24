# 瞎拼项目长期开发约束

开始修改前必须完整阅读：

- `docs/DEVELOPMENT.md`
- `docs/RELEASE_ACCEPTANCE.md`
- `docs/ARCHITECTURE_REVIEW.md`

不得仅凭本机单元测试或旧包覆盖安装宣布发布通过。发布候选必须是在 Ubuntu 22.04
构建的同一个 amd64 DEB，并在 Ubuntu 22.04 X11、24.04 Wayland、26.04 Wayland 上按
`docs/RELEASE_ACCEPTANCE.md` 完成冷缓存直装、重启后复验和真实 IBus 按键测试。

安装应一次完成依赖解析、输入源注册和当前会话启用。用户不得在正常安装后执行 setup、
手动添加输入源、注销或重启才能首次使用。测试和卸载不得删除个人学习数据。任何未实际
执行的人工矩阵项必须明确记为未验收，不能从自动化结果推断为通过。

改动发布要求、安装生命周期、测试矩阵或数据格式时，同步更新上述文档和自动检查。
