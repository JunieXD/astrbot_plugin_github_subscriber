# GitHub 订阅提醒插件设计

## 背景

本插件面向没有公网 IP、无法稳定接收 GitHub Webhook 的 AstrBot 用户。插件通过轮询 GitHub REST API 检查仓库 Star、Release、Issue 和 Pull Request 变化，并把结果推送到指定的群聊或私聊。

插件目标是做成通用订阅插件，不绑定某一个项目。管理员既可以在 AstrBot WebUI 的插件配置中维护订阅，也可以在群聊或私聊中使用 `/ghsub` 命令管理当前会话的订阅。

## 官方约束

- 插件目录命名遵循 AstrBot 官方建议：以 `astrbot_plugin_` 开头、全小写、不包含空格。
- 插件元数据写入 `metadata.yaml`，供 AstrBot 识别插件。
- 后续配置使用 `_conf_schema.json` 暴露到 AstrBot WebUI。
- 持久化运行状态应放在 AstrBot 的 `data` 目录下，而不是插件目录内，避免更新或重装插件时丢失。
- 网络请求应使用异步库，如 `aiohttp` 或 `httpx`，不使用 `requests`。

参考：

- AstrBot 插件开发文档：https://docs.astrbot.app/dev/star/plugin-new.html
- AstrBot 插件配置文档：https://docs.astrbot.app/dev/star/guides/plugin-config.html
- GitHub Starring API：https://docs.github.com/en/rest/activity/starring
- GitHub REST API 最佳实践：https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api

## 范围

第一版实现以下能力：

- 订阅公开 GitHub 仓库。
- 支持群聊和私聊目标。
- 支持 Star、Release、Issue、PR 新建、PR 合并提醒。
- 支持全局可选 GitHub Token。
- 支持 WebUI 配置和管理员命令共同管理订阅。
- 支持全局默认模板与单条订阅模板覆盖。
- 支持 GitHub 用户名到 QQ UID 的映射，用于 PR 合并时 @ PR 作者。

第一版不实现以下能力：

- GitHub Webhook。
- 私有仓库的完整权限管理。
- Issue 评论、Issue 关闭、Issue 重开、Issue 编辑提醒。
- PR 评论、Review、普通关闭、重开、编辑提醒。
- 复杂模板表达式、条件、循环。
- 跨目标共享订阅状态。
- 对超出本轮展示上限的事件进行后续补发。

## 订阅模型

订阅以 `target_umo + owner/repo` 为隔离边界。

`target_umo` 是 AstrBot 的统一消息来源标识，可以代表群聊，也可以代表私聊。相同仓库在不同群聊或私聊中是不同订阅，事件开关、模板和去重状态互不影响。

示例：

```text
target_umo: aiocqhttp:GroupMessage:123456789
repo: JunieXD/AutoEmailSender
```

同一个仓库可以同时被多个目标订阅：

```text
群 A -> JunieXD/AutoEmailSender -> 开启 Release、Issue、PR
群 B -> JunieXD/AutoEmailSender -> 只开启 Release
私聊 C -> JunieXD/AutoEmailSender -> 开启 Star、Release
```

## 配置结构

配置由 AstrBot 插件配置管理，命令操作会持久写回同一份配置。

建议结构：

```json
{
  "github_token": "",
  "default_intervals": {
    "star_minutes": 1,
    "release_minutes": 5,
    "issue_minutes": 2,
    "pr_minutes": 2,
    "min_interval_seconds": 60
  },
  "message_limits": {
    "issue_body_summary_chars": 300,
    "pr_body_summary_chars": 300,
    "release_notes_max_chars": 1500,
    "max_items_per_event_cycle": 5,
    "message_send_delay_seconds": 1
  },
  "github_to_qq": {
    "juniexd": "123456789"
  },
  "global_templates": {
    "star": "{repo} 新增 {new_star_count} 个 Star\n当前总 Star：{star_count}\n用户：{star_users}",
    "release": "{repo} 发布了 {tag_name}\n{release_name}\n{release_url}\n\n{release_notes}",
    "issue": "{repo} 新 Issue #{number}: {title}\n作者：{author}\n时间：{created_at}\n{body_summary}\n{url}",
    "pr_opened": "{repo} 新 PR #{number}: {title}\n作者：{author}\n时间：{created_at}\n{body_summary}\n{url}",
    "pr_merged": "{mention}{repo} PR 已合并 #{number}: {title}\n作者：{author}\n合并者：{merged_by}\n时间：{merged_at}\n{url}"
  },
  "subscriptions": [
    {
      "target_umo": "aiocqhttp:GroupMessage:123456789",
      "target_name": "示例交流群",
      "repo": "JunieXD/AutoEmailSender",
      "enabled": true,
      "events": {
        "star": false,
        "release": true,
        "issue": true,
        "pr": true
      },
      "intervals": {
        "star_minutes": 1,
        "release_minutes": 5,
        "issue_minutes": 2,
        "pr_minutes": 2
      },
      "template_overrides": {
        "star": "",
        "release": "",
        "issue": "",
        "pr_opened": "",
        "pr_merged": ""
      }
    }
  ]
}
```

`github_token` 是全局可选项：

- 配置 token 时，所有 GitHub API 请求带认证头，提高限流和稳定性。
- 未配置 token 时，仍支持公开仓库，但遇到限流时需要向管理员提示。
- 第一版不承诺完整支持私有仓库；遇到 `403` 或 `404` 时提示仓库不可访问或 token 权限不足。

## 运行状态

运行状态与配置分离。配置面向用户编辑，状态面向去重和轮询。

状态 key 使用 `target_umo + owner/repo` 派生：

```text
state_key = hash(target_umo + ":" + owner + "/" + repo)
```

建议状态结构：

```json
{
  "subscriptions": {
    "<state_key>": {
      "target_umo": "aiocqhttp:GroupMessage:123456789",
      "repo": "JunieXD/AutoEmailSender",
      "initialized_at": "2026-06-29T12:00:00Z",
      "known_star_users": ["alice", "bob"],
      "notified_release_ids": [123],
      "notified_issue_numbers": [1, 2],
      "notified_pr_numbers": [3],
      "notified_merged_pr_numbers": [3],
      "last_checked_at": {
        "star": "2026-06-29T12:05:00Z",
        "release": "2026-06-29T12:05:00Z",
        "issue": "2026-06-29T12:05:00Z",
        "pr": "2026-06-29T12:05:00Z"
      },
      "etag": {
        "star": "",
        "release": "",
        "issue": "",
        "pr": ""
      }
    }
  }
}
```

## 初始化规则

新增订阅时先建立 baseline，不发送历史消息：

- Star：拉取当前 stargazers，全部写入 `known_star_users`。
- Release：拉取当前 releases，把已有 release id 记录为已处理，或以订阅时刻作为过滤阈值。
- Issue：拉取当前 issue，把已有 issue number 记录为已处理，或以订阅时刻作为过滤阈值。
- PR：拉取当前 open/closed PR，把已有 PR number 和已合并 PR number 记录为已处理，或以订阅时刻作为过滤阈值。

之后只提醒订阅建立后的新增事件。

如果初始化接口失败，订阅不应静默半成功。命令添加时应向管理员提示失败原因；WebUI 配置启动时应记录错误日志，并在后续周期重试初始化。

## GitHub API 策略

使用专用 API，而不是统一 Events API。

### Star

接口：

```text
GET /repos/{owner}/{repo}/stargazers
Accept: application/vnd.github.star+json
```

行为：

- 读取 stargazer login 和 `starred_at`。
- 新 stargazer login 不在 `known_star_users` 中时，视为新增 star。
- 新增用户写入 `known_star_users`。
- 用户取消 star 后又重新 star，不重复提醒。
- 当前总 star 数可从仓库接口或响应关联信息获取；若 stargazers 响应不足以稳定获取总数，可额外查询 repository metadata。

消息：

- 每轮最多发送 1 条聚合消息。
- 显示新增 star 数、当前总 star 数、GitHub 用户名。
- 用户名最多展示 5 个；超过 5 个显示“等，共 N 人”。

### Release

接口：

```text
GET /repos/{owner}/{repo}/releases
```

行为：

- 每个 release id 只提醒一次。
- 每轮如果发现多个新 release，只发送最新 1 个。
- 未展示的较旧 release 标记为已处理，后续不补发。
- 发送 release name、tag、URL、发布时间和 release note。

消息：

- 每轮每订阅项最多 1 条。
- release note 默认最多 1500 字符，超出追加 `...`。

### Issue

接口：

```text
GET /repos/{owner}/{repo}/issues
```

行为：

- 只提醒新建 issue。
- 每个 issue number 只提醒一次。
- 过滤掉带 `pull_request` 字段的条目，因为 GitHub issues 接口会混入 PR。
- 不提醒 close、reopen、comment、label、编辑。

消息：

- 每轮最多 5 条详细消息。
- 每条消息间隔 1 秒。
- 超过 5 条时，额外发送 1 条摘要说明还有多少条未展示。
- 超出部分标记为已处理，后续不补发。
- issue body 摘要默认最多 300 字符，超出追加 `...`。

### Pull Request

接口：

```text
GET /repos/{owner}/{repo}/pulls?state=open
GET /repos/{owner}/{repo}/pulls?state=closed
```

行为：

- 新建 PR：每个 PR number 只提醒一次。
- PR 合并：`merged_at` 不为空时提醒，每个 PR number 只提醒一次。
- 不提醒普通 close、reopen、comment、review、编辑。

PR 合并 @ 规则：

- 读取 PR 作者 GitHub login。
- 以大小写不敏感方式查询 `github_to_qq` 映射。
- 命中时，在合并消息中插入 QQ At 组件。
- 未命中时正常发送合并消息，不 @。

消息：

- 新建 PR 每轮最多 5 条详细消息。
- PR 合并每轮最多 5 条详细消息。
- 每条消息间隔 1 秒。
- 超过 5 条时，额外发送摘要说明，超出部分标记为已处理。
- PR body 摘要默认最多 300 字符，超出追加 `...`。

## 轮询调度

全局默认间隔：

```text
star_interval_minutes: 1
release_interval_minutes: 5
issue_interval_minutes: 2
pr_interval_minutes: 2
min_interval_seconds: 60
```

每条订阅可以覆盖四类事件的间隔。最终生效间隔不得低于 `min_interval_seconds`。

调度要求：

- 已关闭的事件不轮询。
- 同一订阅同一事件类型不并发执行。
- 网络失败、限流、解析失败不应导致插件崩溃。
- 遇到 GitHub rate limit 时记录日志，并向相关目标或管理员提示一次，避免每轮刷屏。
- 插件卸载或重载时应取消后台任务。

## 命令设计

所有 `/ghsub` 指令仅 AstrBot 管理员可用。

命令默认作用于当前会话 UMO：

- 群聊中执行，管理当前群聊订阅。
- 私聊中执行，管理当前私聊订阅。
- WebUI 可以手动配置任意 `target_umo`。

命令列表：

```text
/ghsub help
/ghsub add https://github.com/owner/repo
/ghsub list
/ghsub status owner/repo
/ghsub remove owner/repo
/ghsub enable owner/repo star|release|issue|pr|all
/ghsub disable owner/repo star|release|issue|pr|all
```

新增订阅默认开关：

```text
release: on
issue: on
pull_request: on
star: off
```

`add/remove/enable/disable` 会持久写回插件配置。WebUI 与命令看到的是同一份订阅列表。

### help 文案

建议 `/ghsub help` 输出：

```text
GitHub 订阅命令：
/ghsub add https://github.com/JunieXD/AutoEmailSender
/ghsub list
/ghsub status JunieXD/AutoEmailSender
/ghsub enable JunieXD/AutoEmailSender star
/ghsub disable JunieXD/AutoEmailSender issue
/ghsub remove JunieXD/AutoEmailSender

默认开启：Release、Issue、PR
默认关闭：Star
所有命令仅管理员可用。
```

## 仓库链接解析

支持：

```text
https://github.com/owner/repo
https://github.com/owner/repo/
https://github.com/owner/repo.git
github.com/owner/repo
owner/repo
```

不支持 issue、PR、release 子页面作为订阅入口：

```text
https://github.com/owner/repo/issues/1
https://github.com/owner/repo/pull/1
https://github.com/owner/repo/releases/tag/v1.0.0
```

遇到子页面链接时提示：

```text
请提供仓库主页链接，例如：https://github.com/owner/repo
```

## 模板设计

支持全局默认模板和单条订阅覆盖模板。

渲染规则：

- 单条订阅有覆盖模板时，使用订阅模板。
- 没有覆盖模板时，使用全局默认模板。
- 只支持 `{变量名}` 占位符替换。
- 不支持表达式、循环、条件或任意代码执行。
- 未知变量替换为空，并记录日志。

通用变量：

```text
{repo}
{repo_url}
{owner}
{repo_name}
{event_time}
```

Star 变量：

```text
{new_star_count}
{star_count}
{star_users}
```

Release 变量：

```text
{tag_name}
{release_name}
{release_author}
{release_time}
{release_url}
{release_notes}
```

Issue 变量：

```text
{number}
{title}
{author}
{created_at}
{url}
{body_summary}
```

PR 新建变量：

```text
{number}
{title}
{author}
{created_at}
{url}
{body_summary}
```

PR 合并变量：

```text
{number}
{title}
{author}
{merged_by}
{merged_at}
{url}
{body_summary}
{mention}
```

`{mention}` 是特殊占位符。命中 QQ 映射时渲染为消息链中的 At 组件；未命中时渲染为空。

## 错误处理

需要覆盖的错误场景：

- GitHub token 缺失：允许运行公开仓库订阅，但提示限流较低。
- `401`：token 无效。
- `403`：权限不足、限流或 abuse detection。
- `404`：仓库不存在、仓库私有或 token 无权限。
- 网络超时：记录日志，下轮重试。
- JSON 解析失败：记录日志，下轮重试。
- 消息发送失败：记录日志，不回滚已处理事件，避免重复刷屏。
- 配置中的订阅项非法：跳过该订阅并记录可读错误。

对群聊/私聊的错误提示要节制。重复错误应限频，避免每轮轮询都发错误消息。

## 测试范围

第一版建议测试：

- 仓库链接解析。
- 订阅 key 生成与目标隔离。
- 命令权限判断。
- `/ghsub add/list/status/remove/enable/disable/help` 行为。
- 命令写回配置。
- 初始化 baseline 不发送历史消息。
- Star 去重，取消后再 star 不重复提醒。
- Release 每轮只发送最新 1 个。
- Issue 过滤 PR，且只提醒新建 issue。
- PR 新建提醒。
- PR 合并提醒和 GitHub login 到 QQ UID 映射。
- 模板变量替换与未知变量处理。
- 摘要长度截断。
- 每类事件每轮最多 5 条，超出只发摘要且不补发。
- GitHub token 缺失、403、404、网络失败处理。

## 后续扩展

可在第一版稳定后考虑：

- 支持 GitHub App 或每条订阅单独 token。
- 支持私有仓库。
- 支持 Issue/PR 评论提醒。
- 支持 label、author、branch 过滤。
- 支持按仓库或事件类型配置通知静默时段。
- 支持把 release note 转为更短摘要。
- 支持更多平台的 @ 适配。
