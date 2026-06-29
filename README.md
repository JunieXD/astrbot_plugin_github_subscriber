# astrbot_plugin_github_subscriber

通用 GitHub 仓库订阅提醒插件。插件通过轮询 GitHub REST API，把 Star、Release、Issue、新 PR、PR 合并推送到 AstrBot 群聊或私聊。

## 功能

- 支持公开 GitHub 仓库订阅。
- 支持群聊和私聊目标，同一个仓库可以在不同会话中使用不同订阅配置。
- 支持全局可选 GitHub token；不填写也可订阅公开仓库，填写后可提高 GitHub API 限流额度。
- 支持按订阅项开关 Star、Release、Issue、PR 事件。
- 支持全局消息模板，也支持单条订阅覆盖模板。
- 支持 GitHub 用户名到 QQ UID 映射。
- 支持 PR 合并提醒时 @ PR 作者。
- 首次 baseline 只记录仓库现状，不发送历史消息。

## 命令

所有命令仅 AstrBot 管理员可用。

```text
/ghsub help
/ghsub add https://github.com/owner/repo
/ghsub list
/ghsub status owner/repo
/ghsub remove owner/repo
/ghsub enable owner/repo star|release|issue|pr|all
/ghsub disable owner/repo star|release|issue|pr|all
```

命令默认作用于当前会话：在群聊中执行时管理当前群，在私聊中执行时管理当前私聊。

使用 `/ghsub add` 新增订阅时，默认开启 Release、Issue、PR 提醒，默认关闭 Star 提醒。需要 Star 提醒时，可执行：

```text
/ghsub enable owner/repo star
```

## 配置

插件配置由 AstrBot WebUI 的插件配置管理，命令添加、移除、启用或关闭订阅时也会写回同一份配置。

主要配置项：

- `github_token`：可选 GitHub token。公开 GitHub API 不配置 token 也可以使用，但限流较低；建议配置 token 提高稳定性。
- `github_to_qq`：GitHub 用户名到 QQ UID 的映射，用于 PR 合并提醒时 @ PR 作者。用户名匹配不区分大小写。
- `global_templates`：全局默认消息模板，支持 `star`、`release`、`issue`、`pr_opened`、`pr_merged`。
- `subscriptions`：订阅列表。每条订阅包含目标会话 `target_umo`、仓库 `repo`、启用状态、事件开关、轮询间隔和 `template_overrides`。

单条订阅的 `template_overrides` 留空时使用 `global_templates`；填写后只覆盖当前订阅，不影响其他群聊或私聊。

## 限流与发送

- 插件内部每 60 秒唤醒一次，但每个订阅项的 Star、Release、Issue、PR 会分别按各自配置的检查间隔判断是否需要请求 GitHub。
- Issue 和 PR 每类事件每轮最多展示 `max_items_per_event_cycle` 条。
- 超过展示上限的 Issue 或 PR 会发送 summary，超出部分会标记为已处理，后续不会补发。
- Release 每轮只发送最新 1 个；同一轮发现的较旧 Release 会标记为已处理，后续不会补发。
- 多条消息会按 `message_send_delay_seconds` 间隔逐条发送，避免短时间刷屏。
- GitHub 请求或消息发送失败时，本轮该订阅项的状态会回滚，下轮满足间隔后重试。

## Baseline

首次轮询会拉取仓库全部相关事件建立 baseline，不发送历史消息。后续只提醒 baseline 之后新增的事件。

如果某个事件原本关闭，后续再开启，也不会把关闭期间或历史已有的事件刷出来；插件会以已记录状态为准继续提醒新事件。

## 注意事项

- 本插件面向公开 GitHub 仓库订阅；私有仓库是否可访问取决于 token 权限和 GitHub API 返回结果。
- 无 token 时公开 GitHub API 仍可用，但限流低，仓库较多或轮询较频繁时建议配置 `github_token`。
- 订阅目标按 AstrBot 的 `target_umo` 隔离，同一仓库在不同群聊或私聊中会拥有独立事件开关、模板和去重状态。
