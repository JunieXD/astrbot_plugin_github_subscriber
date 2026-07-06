# Changelog

## v0.1.5

- 修复 GitHub token 无法访问 stargazers API 时 Star 事件完全不推送的问题。
- Star 用户明细不可用时，会改用仓库总 Star 数差值发送兜底提醒，并记录计数状态避免后续重复推送历史用户。

## v0.1.4

- 默认将 Issue、PR、Release 相关时间显示为上海时间。
- 时间占位符格式改为 `YYYY-MM-DD HH:MM:SS`。

## v0.1.3

- 修复运行中的 AstrBot 重新安装或热加载插件后，后台轮询任务未启动导致订阅不推送的问题。
- 轮询任务启动后会先执行一次检查，再进入固定间隔循环。

## v0.1.2

- 修复 GitHub 用户名到 QQ UID 映射在 WebUI 中被写成对象后无法新增、删除的问题。
- 启动时自动将旧版映射配置迁移回 AstrBot `template_list` 数组格式。

## v0.1.1

- 修复通过 GitHub 链接导入时包内模块导入失败的问题。
- 修复配置 schema 使用 AstrBot 不支持的 `dict` 类型导致加载失败的问题。
- 修复 `/ghsub add` 后首次轮询前创建的 Issue、PR、Release 被 baseline 误吞的问题。
- 补充模板占位符文档和插件更新日志文件。

## v0.1.0

- 支持按群聊或私聊独立订阅 GitHub 仓库。
- 支持 Star、Release、Issue、新 PR、PR 合并提醒。
- 支持管理员使用 `/ghsub` 命令添加、查看、启用、关闭和删除订阅。
- 支持全局消息模板和单个订阅项模板覆盖。
- 支持 GitHub 用户名到 QQ UID 映射，PR 合并提醒可 @ PR 作者。
- 支持首次 baseline，不发送订阅前已有历史事件。
- 支持每类事件独立轮询间隔、逐条发送和每轮展示上限。
