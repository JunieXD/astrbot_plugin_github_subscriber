# GitHub 订阅提醒插件实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建一个 AstrBot GitHub 订阅插件，通过轮询 GitHub 专用 REST API，把公开仓库 Star、Release、Issue、PR 新建和 PR 合并事件推送到指定群聊或私聊。

**架构：** 插件入口 `main.py` 只负责 AstrBot 生命周期、命令注册和后台任务协调；核心逻辑拆到 `github_subscriber/` 包中。配置由 AstrBot `_conf_schema.json` 管理，运行状态单独写入 AstrBot data 目录，GitHub API、模板渲染、事件去重和消息构建均为可单测的纯 Python 单元。

**技术栈：** Python 3.10+、AstrBot Star 插件 API、`aiohttp`、`pytest`、`pytest-asyncio`、GitHub REST API。

---

## 文件结构

- 创建：`/home/junie/astrbot_plugin_github_subscriber/main.py`
  - AstrBot 插件入口，注册 `/ghsub` 指令组，启动/停止后台轮询任务，调用服务层。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/_conf_schema.json`
  - AstrBot WebUI 配置 schema，包含 GitHub token、默认间隔、消息限制、模板、订阅列表和 GitHub 到 QQ 映射。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/requirements.txt`
  - 插件依赖，至少包含 `aiohttp`。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/__init__.py`
  - 包导出。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/models.py`
  - 数据模型与归一化函数。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/repo_parser.py`
  - GitHub 仓库链接解析。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/config.py`
  - AstrBot 配置读写适配、默认值、命令写回配置。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/state.py`
  - 运行状态文件读写、订阅状态 key、去重集合。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/github_client.py`
  - GitHub REST API 异步客户端。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/templates.py`
  - 安全占位符模板渲染。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/messages.py`
  - 事件消息文本与消息链构建，包括 PR 合并 @。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/poller.py`
  - 初始化 baseline、按事件轮询、限流、去重、返回待发送消息。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/`
  - 单元测试目录。
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_repo_parser.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_templates.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_config.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_state.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_poller.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_messages.py`

## 任务 1：初始化测试工具链和依赖声明

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/requirements.txt`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/pytest.ini`

- [ ] **步骤 1：创建依赖文件**

写入 `requirements.txt`：

```text
aiohttp>=3.9
pytest>=8
pytest-asyncio>=0.23
```

- [ ] **步骤 2：创建 pytest 配置**

写入 `pytest.ini`：

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
pythonpath = .
```

- [ ] **步骤 3：运行空测试命令**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest -q
```

预期：pytest 能启动，允许显示 `no tests ran`，退出码可能为 5。此步骤只验证测试工具入口可用；后续任务会加入真实测试。

## 任务 2：仓库链接解析

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/__init__.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/repo_parser.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_repo_parser.py`

- [ ] **步骤 1：编写失败测试**

写入 `tests/test_repo_parser.py`：

```python
import pytest

from github_subscriber.repo_parser import RepoParseError, parse_repo_ref


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("github.com/owner/repo", "owner/repo"),
        ("owner/repo", "owner/repo"),
        ("Owner-Name/repo.name", "Owner-Name/repo.name"),
    ],
)
def test_parse_supported_repo_refs(value: str, expected: str):
    assert parse_repo_ref(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/releases/tag/v1.0.0",
        "https://gitlab.com/owner/repo",
        "owner",
        "",
    ],
)
def test_reject_invalid_or_subpage_refs(value: str):
    with pytest.raises(RepoParseError):
        parse_repo_ref(value)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_repo_parser.py -q
```

预期：FAIL，提示 `ModuleNotFoundError` 或 `ImportError`。

- [ ] **步骤 3：实现仓库解析**

写入 `github_subscriber/__init__.py`：

```python
"""GitHub subscription helpers for AstrBot."""
```

写入 `github_subscriber/repo_parser.py`：

```python
from __future__ import annotations

import re


class RepoParseError(ValueError):
    """Raised when a user-provided value is not a repository reference."""


_REPO_PATTERN = re.compile(
    r"^(?:https?://)?(?:github\.com/)?"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


def parse_repo_ref(value: str) -> str:
    raw = value.strip()
    match = _REPO_PATTERN.match(raw)
    if not match:
        raise RepoParseError("请提供仓库主页链接，例如：https://github.com/owner/repo")

    owner = match.group("owner")
    repo = match.group("repo")
    if not owner or not repo:
        raise RepoParseError("请提供仓库主页链接，例如：https://github.com/owner/repo")

    return f"{owner}/{repo}"
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_repo_parser.py -q
```

预期：所有测试 PASS。

## 任务 3：数据模型和默认配置

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/models.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/config.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_config.py`

- [ ] **步骤 1：编写失败测试**

写入 `tests/test_config.py`：

```python
from github_subscriber.config import (
    DEFAULT_GLOBAL_TEMPLATES,
    add_subscription,
    disable_event,
    enable_event,
    get_subscriptions_for_target,
    normalize_config,
    remove_subscription,
)


def test_normalize_config_adds_defaults():
    config = normalize_config({})

    assert config["github_token"] == ""
    assert config["default_intervals"]["star_minutes"] == 1
    assert config["default_intervals"]["release_minutes"] == 5
    assert config["default_intervals"]["issue_minutes"] == 2
    assert config["default_intervals"]["pr_minutes"] == 2
    assert config["message_limits"]["max_items_per_event_cycle"] == 5
    assert config["global_templates"] == DEFAULT_GLOBAL_TEMPLATES
    assert config["subscriptions"] == []


def test_add_subscription_defaults_events_and_target():
    config = normalize_config({})
    sub = add_subscription(
        config,
        target_umo="aiocqhttp:GroupMessage:123",
        target_name="群 123",
        repo="Owner/Repo",
    )

    assert sub["repo"] == "Owner/Repo"
    assert sub["target_umo"] == "aiocqhttp:GroupMessage:123"
    assert sub["events"] == {
        "star": False,
        "release": True,
        "issue": True,
        "pr": True,
    }
    assert get_subscriptions_for_target(config, "aiocqhttp:GroupMessage:123") == [sub]


def test_add_subscription_is_idempotent_per_target_and_repo():
    config = normalize_config({})
    first = add_subscription(config, "umo-a", "A", "Owner/Repo")
    second = add_subscription(config, "umo-a", "A", "Owner/Repo")
    third = add_subscription(config, "umo-b", "B", "Owner/Repo")

    assert first is second
    assert len(config["subscriptions"]) == 2
    assert third["target_umo"] == "umo-b"


def test_enable_disable_and_remove_subscription():
    config = normalize_config({})
    add_subscription(config, "umo-a", "A", "Owner/Repo")

    enable_event(config, "umo-a", "Owner/Repo", "star")
    assert config["subscriptions"][0]["events"]["star"] is True

    disable_event(config, "umo-a", "Owner/Repo", "all")
    assert config["subscriptions"][0]["events"] == {
        "star": False,
        "release": False,
        "issue": False,
        "pr": False,
    }

    remove_subscription(config, "umo-a", "Owner/Repo")
    assert config["subscriptions"] == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_config.py -q
```

预期：FAIL，提示模块或函数不存在。

- [ ] **步骤 3：实现模型和配置工具**

写入 `github_subscriber/models.py`：

```python
from __future__ import annotations

from dataclasses import dataclass


EVENT_KEYS = ("star", "release", "issue", "pr")


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @classmethod
    def from_full_name(cls, full_name: str) -> "RepoRef":
        owner, name = full_name.split("/", 1)
        return cls(owner=owner, name=name)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full_name}"
```

写入 `github_subscriber/config.py`：

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import EVENT_KEYS


DEFAULT_GLOBAL_TEMPLATES = {
    "star": "{repo} 新增 {new_star_count} 个 Star\n当前总 Star：{star_count}\n用户：{star_users}",
    "release": "{repo} 发布了 {tag_name}\n{release_name}\n{release_url}\n\n{release_notes}",
    "issue": "{repo} 新 Issue #{number}: {title}\n作者：{author}\n时间：{created_at}\n{body_summary}\n{url}",
    "pr_opened": "{repo} 新 PR #{number}: {title}\n作者：{author}\n时间：{created_at}\n{body_summary}\n{url}",
    "pr_merged": "{mention}{repo} PR 已合并 #{number}: {title}\n作者：{author}\n合并者：{merged_by}\n时间：{merged_at}\n{url}",
}

DEFAULT_CONFIG = {
    "github_token": "",
    "default_intervals": {
        "star_minutes": 1,
        "release_minutes": 5,
        "issue_minutes": 2,
        "pr_minutes": 2,
        "min_interval_seconds": 60,
    },
    "message_limits": {
        "issue_body_summary_chars": 300,
        "pr_body_summary_chars": 300,
        "release_notes_max_chars": 1500,
        "max_items_per_event_cycle": 5,
        "message_send_delay_seconds": 1,
    },
    "github_to_qq": {},
    "global_templates": DEFAULT_GLOBAL_TEMPLATES,
    "subscriptions": [],
}


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    _deep_update(config, raw)
    config["subscriptions"] = list(config.get("subscriptions") or [])
    return config


def add_subscription(
    config: dict[str, Any],
    target_umo: str,
    target_name: str,
    repo: str,
) -> dict[str, Any]:
    existing = find_subscription(config, target_umo, repo)
    if existing is not None:
        return existing

    sub = {
        "target_umo": target_umo,
        "target_name": target_name,
        "repo": repo,
        "enabled": True,
        "events": {"star": False, "release": True, "issue": True, "pr": True},
        "intervals": {},
        "template_overrides": {
            "star": "",
            "release": "",
            "issue": "",
            "pr_opened": "",
            "pr_merged": "",
        },
    }
    config.setdefault("subscriptions", []).append(sub)
    return sub


def find_subscription(
    config: dict[str, Any],
    target_umo: str,
    repo: str,
) -> dict[str, Any] | None:
    repo_lower = repo.lower()
    for sub in config.get("subscriptions", []):
        if sub.get("target_umo") == target_umo and str(sub.get("repo", "")).lower() == repo_lower:
            return sub
    return None


def get_subscriptions_for_target(config: dict[str, Any], target_umo: str) -> list[dict[str, Any]]:
    return [sub for sub in config.get("subscriptions", []) if sub.get("target_umo") == target_umo]


def remove_subscription(config: dict[str, Any], target_umo: str, repo: str) -> bool:
    before = len(config.get("subscriptions", []))
    repo_lower = repo.lower()
    config["subscriptions"] = [
        sub
        for sub in config.get("subscriptions", [])
        if not (sub.get("target_umo") == target_umo and str(sub.get("repo", "")).lower() == repo_lower)
    ]
    return len(config["subscriptions"]) != before


def enable_event(config: dict[str, Any], target_umo: str, repo: str, event_name: str) -> bool:
    return _set_event(config, target_umo, repo, event_name, True)


def disable_event(config: dict[str, Any], target_umo: str, repo: str, event_name: str) -> bool:
    return _set_event(config, target_umo, repo, event_name, False)


def _set_event(config: dict[str, Any], target_umo: str, repo: str, event_name: str, value: bool) -> bool:
    sub = find_subscription(config, target_umo, repo)
    if sub is None:
        return False

    names = EVENT_KEYS if event_name == "all" else (event_name,)
    for name in names:
        if name not in EVENT_KEYS:
            raise ValueError(f"未知事件类型：{name}")
        sub.setdefault("events", {})[name] = value
    return True


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = deepcopy(value)
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_config.py -q
```

预期：所有测试 PASS。

## 任务 4：配置 schema

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/_conf_schema.json`

- [ ] **步骤 1：创建 AstrBot 配置 schema**

写入 `_conf_schema.json`：

```json
{
  "github_token": {
    "description": "GitHub Token（可选）",
    "type": "string",
    "hint": "不填写也可以订阅公开仓库；填写后可提高 GitHub API 限流额度。"
  },
  "default_intervals": {
    "description": "全局默认轮询间隔",
    "type": "object",
    "items": {
      "star_minutes": {
        "description": "Star 检查间隔（分钟）",
        "type": "int",
        "default": 1
      },
      "release_minutes": {
        "description": "Release 检查间隔（分钟）",
        "type": "int",
        "default": 5
      },
      "issue_minutes": {
        "description": "Issue 检查间隔（分钟）",
        "type": "int",
        "default": 2
      },
      "pr_minutes": {
        "description": "PR 检查间隔（分钟）",
        "type": "int",
        "default": 2
      },
      "min_interval_seconds": {
        "description": "最小轮询间隔（秒）",
        "type": "int",
        "default": 60
      }
    }
  },
  "message_limits": {
    "description": "消息长度和发送节奏限制",
    "type": "object",
    "items": {
      "issue_body_summary_chars": {
        "description": "Issue 内容摘要最大字符数",
        "type": "int",
        "default": 300
      },
      "pr_body_summary_chars": {
        "description": "PR 内容摘要最大字符数",
        "type": "int",
        "default": 300
      },
      "release_notes_max_chars": {
        "description": "Release Note 最大字符数",
        "type": "int",
        "default": 1500
      },
      "max_items_per_event_cycle": {
        "description": "每类事件每轮最多展示条数",
        "type": "int",
        "default": 5
      },
      "message_send_delay_seconds": {
        "description": "逐条发送消息的间隔秒数",
        "type": "int",
        "default": 1
      }
    }
  },
  "github_to_qq": {
    "description": "GitHub 用户名到 QQ UID 的映射",
    "type": "dict",
    "hint": "用于 PR 合并提醒时 @ PR 作者。key 填 GitHub 用户名，value 填 QQ UID。"
  },
  "global_templates": {
    "description": "全局默认消息模板",
    "type": "object",
    "items": {
      "star": {
        "description": "Star 提醒模板",
        "type": "text",
        "default": "{repo} 新增 {new_star_count} 个 Star\n当前总 Star：{star_count}\n用户：{star_users}"
      },
      "release": {
        "description": "Release 提醒模板",
        "type": "text",
        "default": "{repo} 发布了 {tag_name}\n{release_name}\n{release_url}\n\n{release_notes}"
      },
      "issue": {
        "description": "Issue 提醒模板",
        "type": "text",
        "default": "{repo} 新 Issue #{number}: {title}\n作者：{author}\n时间：{created_at}\n{body_summary}\n{url}"
      },
      "pr_opened": {
        "description": "新 PR 提醒模板",
        "type": "text",
        "default": "{repo} 新 PR #{number}: {title}\n作者：{author}\n时间：{created_at}\n{body_summary}\n{url}"
      },
      "pr_merged": {
        "description": "PR 合并提醒模板",
        "type": "text",
        "default": "{mention}{repo} PR 已合并 #{number}: {title}\n作者：{author}\n合并者：{merged_by}\n时间：{merged_at}\n{url}"
      }
    }
  },
  "subscriptions": {
    "description": "GitHub 仓库订阅列表",
    "type": "list",
    "hint": "命令添加的订阅也会写入这里。每项包含 target_umo、repo、events、intervals 和 template_overrides。"
  }
}
```

- [ ] **步骤 2：验证 JSON 格式**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m json.tool _conf_schema.json >/tmp/github_subscriber_schema.json
```

预期：命令退出码 0。

## 任务 5：状态读写与去重 key

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/state.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_state.py`

- [ ] **步骤 1：编写失败测试**

写入 `tests/test_state.py`：

```python
from pathlib import Path

from github_subscriber.state import JsonStateStore, subscription_state_key


def test_subscription_state_key_is_stable_and_target_scoped():
    a = subscription_state_key("umo-a", "Owner/Repo")
    b = subscription_state_key("umo-a", "owner/repo")
    c = subscription_state_key("umo-b", "Owner/Repo")

    assert a == b
    assert a != c


def test_state_store_creates_and_persists_subscription_state(tmp_path: Path):
    store = JsonStateStore(tmp_path / "state.json")
    state = store.get_subscription_state("umo-a", "Owner/Repo")
    state["known_star_users"].append("alice")
    state["notified_issue_numbers"].append(1)
    store.save()

    reloaded = JsonStateStore(tmp_path / "state.json")
    loaded = reloaded.get_subscription_state("umo-a", "Owner/Repo")

    assert loaded["known_star_users"] == ["alice"]
    assert loaded["notified_issue_numbers"] == [1]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_state.py -q
```

预期：FAIL，提示模块不存在。

- [ ] **步骤 3：实现状态存储**

写入 `github_subscriber/state.py`：

```python
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_SUBSCRIPTION_STATE = {
    "initialized_at": "",
    "known_star_users": [],
    "notified_release_ids": [],
    "notified_issue_numbers": [],
    "notified_pr_numbers": [],
    "notified_merged_pr_numbers": [],
    "last_checked_at": {"star": "", "release": "", "issue": "", "pr": ""},
    "etag": {"star": "", "release": "", "issue": "", "pr": ""},
}


def subscription_state_key(target_umo: str, repo: str) -> str:
    normalized = f"{target_umo}:{repo.lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class JsonStateStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def get_subscription_state(self, target_umo: str, repo: str) -> dict[str, Any]:
        key = subscription_state_key(target_umo, repo)
        subscriptions = self.data.setdefault("subscriptions", {})
        if key not in subscriptions:
            subscriptions[key] = deepcopy(DEFAULT_SUBSCRIPTION_STATE)
            subscriptions[key]["target_umo"] = target_umo
            subscriptions[key]["repo"] = repo
        return subscriptions[key]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"subscriptions": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_state.py -q
```

预期：所有测试 PASS。

## 任务 6：模板渲染与摘要截断

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/templates.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_templates.py`

- [ ] **步骤 1：编写失败测试**

写入 `tests/test_templates.py`：

```python
from github_subscriber.templates import render_template, truncate_text


def test_render_template_replaces_known_variables_and_blanks_unknown():
    text = render_template(
        "{repo} #{number}: {title} {unknown}",
        {"repo": "Owner/Repo", "number": 1, "title": "Hello"},
    )

    assert text == "Owner/Repo #1: Hello "


def test_truncate_text_adds_ellipsis_when_needed():
    assert truncate_text("abcdef", 3) == "abc..."
    assert truncate_text("abc", 3) == "abc"
    assert truncate_text("", 3) == ""
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_templates.py -q
```

预期：FAIL。

- [ ] **步骤 3：实现模板工具**

写入 `github_subscriber/templates.py`：

```python
from __future__ import annotations

import re
from typing import Any


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render_template(template: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = variables.get(key, "")
        return "" if value is None else str(value)

    return _PLACEHOLDER.sub(replace, template)


def truncate_text(value: str | None, max_chars: int) -> str:
    text = value or ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_templates.py -q
```

预期：所有测试 PASS。

## 任务 7：GitHub API 客户端

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/github_client.py`

- [ ] **步骤 1：实现客户端类型和错误**

写入 `github_subscriber/github_client.py`：

```python
from __future__ import annotations

from typing import Any

import aiohttp


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API error {status}: {message}")
        self.status = status
        self.message = message


class GitHubClient:
    def __init__(self, token: str = "", session: aiohttp.ClientSession | None = None):
        self.token = token.strip()
        self._external_session = session
        self._session: aiohttp.ClientSession | None = session

    async def __aenter__(self) -> "GitHubClient":
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._external_session is None and self._session is not None:
            await self._session.close()

    async def get_stargazers(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return await self._get_paginated(
            f"https://api.github.com/repos/{owner}/{repo}/stargazers",
            accept="application/vnd.github.star+json",
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._get_json(f"https://api.github.com/repos/{owner}/{repo}")

    async def get_releases(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return await self._get_paginated(f"https://api.github.com/repos/{owner}/{repo}/releases")

    async def get_issues(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return await self._get_paginated(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            params={"state": "open", "sort": "created", "direction": "desc"},
        )

    async def get_pulls(self, owner: str, repo: str, state: str) -> list[dict[str, Any]]:
        return await self._get_paginated(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            params={"state": state, "sort": "created", "direction": "desc"},
        )

    async def _get_paginated(
        self,
        url: str,
        *,
        accept: str = "application/vnd.github+json",
        params: dict[str, Any] | None = None,
        max_pages: int = 3,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url: str | None = url
        page_params = dict(params or {})
        page_params.setdefault("per_page", 100)
        pages = 0

        while next_url and pages < max_pages:
            payload, links = await self._request_json(next_url, accept=accept, params=page_params)
            if not isinstance(payload, list):
                raise GitHubApiError(500, "Expected list response")
            items.extend(payload)
            next_url = links.get("next", {}).get("url")
            page_params = None
            pages += 1

        return items

    async def _get_json(
        self,
        url: str,
        *,
        accept: str = "application/vnd.github+json",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload, _ = await self._request_json(url, accept=accept, params=params)
        if not isinstance(payload, dict):
            raise GitHubApiError(500, "Expected object response")
        return payload

    async def _request_json(
        self,
        url: str,
        *,
        accept: str,
        params: dict[str, Any] | None,
    ) -> tuple[Any, dict[str, dict[str, str]]]:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "astrbot-plugin-github-subscriber",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with self._session.get(url, headers=headers, params=params, timeout=30) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise GitHubApiError(resp.status, text[:500])
            return await resp.json(), resp.links
```

- [ ] **步骤 2：运行已有测试确保未破坏**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest -q
```

预期：已有测试 PASS。

## 任务 8：消息构建

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/messages.py`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/tests/test_messages.py`

- [ ] **步骤 1：编写失败测试**

写入 `tests/test_messages.py`：

```python
from github_subscriber.config import normalize_config
from github_subscriber.messages import build_star_variables, resolve_template


def test_resolve_template_uses_subscription_override_first():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": "override {title}"}}

    assert resolve_template(config, sub, "issue") == "override {title}"


def test_resolve_template_falls_back_to_global():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": ""}}

    assert resolve_template(config, sub, "issue") == "global {title}"


def test_build_star_variables_limits_user_names():
    variables = build_star_variables(
        repo="Owner/Repo",
        repo_url="https://github.com/Owner/Repo",
        star_count=100,
        new_users=["a", "b", "c", "d", "e", "f"],
    )

    assert variables["new_star_count"] == 6
    assert variables["star_users"] == "a、b、c、d、e 等，共 6 人"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_messages.py -q
```

预期：FAIL。

- [ ] **步骤 3：实现消息变量工具**

写入 `github_subscriber/messages.py`：

```python
from __future__ import annotations

from typing import Any


def resolve_template(config: dict[str, Any], sub: dict[str, Any], template_name: str) -> str:
    override = (sub.get("template_overrides") or {}).get(template_name) or ""
    if override.strip():
        return override
    return (config.get("global_templates") or {}).get(template_name, "")


def build_star_variables(
    *,
    repo: str,
    repo_url: str,
    star_count: int,
    new_users: list[str],
) -> dict[str, Any]:
    shown = new_users[:5]
    if len(new_users) > 5:
        star_users = f"{'、'.join(shown)} 等，共 {len(new_users)} 人"
    else:
        star_users = "、".join(shown)
    return {
        "repo": repo,
        "repo_url": repo_url,
        "owner": repo.split("/", 1)[0],
        "repo_name": repo.split("/", 1)[1],
        "new_star_count": len(new_users),
        "star_count": star_count,
        "star_users": star_users,
    }


def normalize_github_login(login: str) -> str:
    return login.strip().lower()
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_messages.py -q
```

预期：所有测试 PASS。

## 任务 9：轮询核心逻辑

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/poller.py`
- 修改：`/home/junie/astrbot_plugin_github_subscriber/tests/test_poller.py`

- [ ] **步骤 1：编写失败测试**

写入 `tests/test_poller.py`：

```python
from github_subscriber.config import normalize_config
from github_subscriber.poller import (
    collect_new_issues,
    collect_new_prs,
    collect_new_releases,
    collect_new_stars,
)


def test_collect_new_stars_updates_known_users_and_limits_message():
    state = {"known_star_users": ["alice"]}
    new_users = collect_new_stars(
        state,
        stargazers=[
            {"user": {"login": "alice"}, "starred_at": "2026-06-01T00:00:00Z"},
            {"user": {"login": "bob"}, "starred_at": "2026-06-02T00:00:00Z"},
        ],
    )

    assert new_users == ["bob"]
    assert state["known_star_users"] == ["alice", "bob"]


def test_collect_new_releases_returns_latest_only_and_marks_all_seen():
    state = {"notified_release_ids": []}
    releases = [
        {"id": 1, "published_at": "2026-06-01T00:00:00Z"},
        {"id": 2, "published_at": "2026-06-02T00:00:00Z"},
    ]

    selected, skipped_count = collect_new_releases(state, releases)

    assert selected["id"] == 2
    assert skipped_count == 1
    assert state["notified_release_ids"] == [1, 2]


def test_collect_new_issues_filters_prs_and_limits_to_five():
    state = {"notified_issue_numbers": []}
    issues = [
        {"number": i, "created_at": f"2026-06-{i:02d}T00:00:00Z"}
        for i in range(1, 8)
    ]
    issues.append({"number": 99, "pull_request": {}})

    selected, skipped_count = collect_new_issues(state, issues, limit=5)

    assert [item["number"] for item in selected] == [7, 6, 5, 4, 3]
    assert skipped_count == 2
    assert set(state["notified_issue_numbers"]) == set(range(1, 8))


def test_collect_new_prs_splits_opened_and_merged():
    state = {"notified_pr_numbers": [], "notified_merged_pr_numbers": []}
    open_prs = [{"number": 1, "created_at": "2026-06-01T00:00:00Z"}]
    closed_prs = [
        {"number": 2, "merged_at": "2026-06-02T00:00:00Z"},
        {"number": 3, "merged_at": None},
    ]

    opened, merged = collect_new_prs(state, open_prs=open_prs, closed_prs=closed_prs, limit=5)

    assert [item["number"] for item in opened] == [1]
    assert [item["number"] for item in merged] == [2]
    assert state["notified_pr_numbers"] == [1]
    assert state["notified_merged_pr_numbers"] == [2]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_poller.py -q
```

预期：FAIL。

- [ ] **步骤 3：实现轮询去重纯函数**

写入 `github_subscriber/poller.py`：

```python
from __future__ import annotations

from typing import Any

from .messages import normalize_github_login


def collect_new_stars(state: dict[str, Any], stargazers: list[dict[str, Any]]) -> list[str]:
    known = {normalize_github_login(login) for login in state.setdefault("known_star_users", [])}
    new_users: list[str] = []
    for item in sorted(stargazers, key=lambda row: row.get("starred_at") or ""):
        login = ((item.get("user") or {}).get("login") or "").strip()
        normalized = normalize_github_login(login)
        if login and normalized not in known:
            known.add(normalized)
            new_users.append(login)
            state["known_star_users"].append(login)
    return new_users


def collect_new_releases(
    state: dict[str, Any],
    releases: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, int]:
    seen = set(state.setdefault("notified_release_ids", []))
    new_releases = [item for item in releases if item.get("id") not in seen]
    if not new_releases:
        return None, 0
    new_releases.sort(key=lambda row: row.get("published_at") or row.get("created_at") or "", reverse=True)
    for item in new_releases:
        state["notified_release_ids"].append(item["id"])
    return new_releases[0], max(0, len(new_releases) - 1)


def collect_new_issues(
    state: dict[str, Any],
    issues: list[dict[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    seen = set(state.setdefault("notified_issue_numbers", []))
    candidates = [
        item
        for item in issues
        if "pull_request" not in item and item.get("number") not in seen
    ]
    candidates.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    for item in candidates:
        state["notified_issue_numbers"].append(item["number"])
    return candidates[:limit], max(0, len(candidates) - limit)


def collect_new_prs(
    state: dict[str, Any],
    *,
    open_prs: list[dict[str, Any]],
    closed_prs: list[dict[str, Any]],
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen_opened = set(state.setdefault("notified_pr_numbers", []))
    seen_merged = set(state.setdefault("notified_merged_pr_numbers", []))

    opened = [item for item in open_prs if item.get("number") not in seen_opened]
    opened.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    for item in opened:
        state["notified_pr_numbers"].append(item["number"])

    merged = [
        item
        for item in closed_prs
        if item.get("merged_at") and item.get("number") not in seen_merged
    ]
    merged.sort(key=lambda row: row.get("merged_at") or "", reverse=True)
    for item in merged:
        state["notified_merged_pr_numbers"].append(item["number"])

    return opened[:limit], merged[:limit]
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_poller.py -q
```

预期：所有测试 PASS。

## 任务 10：AstrBot 插件入口与管理员命令

**文件：**
- 创建：`/home/junie/astrbot_plugin_github_subscriber/main.py`

- [ ] **步骤 1：实现插件骨架与命令组**

写入 `main.py`：

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from github_subscriber.config import (
    add_subscription,
    disable_event,
    enable_event,
    find_subscription,
    get_subscriptions_for_target,
    normalize_config,
    remove_subscription,
)
from github_subscriber.repo_parser import RepoParseError, parse_repo_ref
from github_subscriber.state import JsonStateStore


@filter.command_group("ghsub")
def ghsub():
    pass


class GitHubSubscriberPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.normalized_config: dict[str, Any] = normalize_config(dict(config))
        self._poller_task: asyncio.Task | None = None
        self.state = JsonStateStore(self._state_path())

    async def terminate(self):
        if self._poller_task is not None:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                pass
        self.state.save()

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        if self._poller_task is None:
            self._poller_task = asyncio.create_task(self._poll_loop())
            logger.info("GitHub subscriber poller started.")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("help")
    async def ghsub_help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "GitHub 订阅命令：\n"
            "/ghsub add https://github.com/JunieXD/AutoEmailSender\n"
            "/ghsub list\n"
            "/ghsub status JunieXD/AutoEmailSender\n"
            "/ghsub enable JunieXD/AutoEmailSender star\n"
            "/ghsub disable JunieXD/AutoEmailSender issue\n"
            "/ghsub remove JunieXD/AutoEmailSender\n\n"
            "默认开启：Release、Issue、PR\n"
            "默认关闭：Star\n"
            "所有命令仅管理员可用。"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("add")
    async def ghsub_add(self, event: AstrMessageEvent, repo_ref: str):
        try:
            repo = parse_repo_ref(repo_ref)
        except RepoParseError as exc:
            yield event.plain_result(str(exc))
            return

        sub = add_subscription(
            self.normalized_config,
            target_umo=event.unified_msg_origin,
            target_name=event.get_group_name() if hasattr(event, "get_group_name") else "",
            repo=repo,
        )
        self._persist_config()
        yield event.plain_result(
            f"已订阅 {sub['repo']}\n"
            "已开启：Release、Issue、PR\n"
            "未开启：Star\n"
            f"可使用 /ghsub enable {sub['repo']} star 开启 Star 提醒"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("list")
    async def ghsub_list(self, event: AstrMessageEvent):
        subs = get_subscriptions_for_target(self.normalized_config, event.unified_msg_origin)
        if not subs:
            yield event.plain_result("当前会话还没有 GitHub 订阅。")
            return
        lines = ["当前 GitHub 订阅："]
        for sub in subs:
            enabled = [name for name, ok in sub.get("events", {}).items() if ok]
            lines.append(f"- {sub['repo']}：{', '.join(enabled) or '未开启事件'}")
        yield event.plain_result("\n".join(lines))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("status")
    async def ghsub_status(self, event: AstrMessageEvent, repo_ref: str):
        repo = parse_repo_ref(repo_ref)
        sub = find_subscription(self.normalized_config, event.unified_msg_origin, repo)
        if sub is None:
            yield event.plain_result(f"当前会话未订阅 {repo}")
            return
        enabled = [name for name, ok in sub.get("events", {}).items() if ok]
        yield event.plain_result(f"{repo}\n开启事件：{', '.join(enabled) or '无'}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("remove")
    async def ghsub_remove(self, event: AstrMessageEvent, repo_ref: str):
        repo = parse_repo_ref(repo_ref)
        if remove_subscription(self.normalized_config, event.unified_msg_origin, repo):
            self._persist_config()
            yield event.plain_result(f"已移除订阅 {repo}")
        else:
            yield event.plain_result(f"当前会话未订阅 {repo}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("enable")
    async def ghsub_enable(self, event: AstrMessageEvent, repo_ref: str, event_name: str):
        repo = parse_repo_ref(repo_ref)
        if enable_event(self.normalized_config, event.unified_msg_origin, repo, event_name):
            self._persist_config()
            yield event.plain_result(f"已开启 {repo} 的 {event_name} 提醒")
        else:
            yield event.plain_result(f"当前会话未订阅 {repo}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("disable")
    async def ghsub_disable(self, event: AstrMessageEvent, repo_ref: str, event_name: str):
        repo = parse_repo_ref(repo_ref)
        if disable_event(self.normalized_config, event.unified_msg_origin, repo, event_name):
            self._persist_config()
            yield event.plain_result(f"已关闭 {repo} 的 {event_name} 提醒")
        else:
            yield event.plain_result(f"当前会话未订阅 {repo}")

    async def _poll_loop(self):
        while True:
            await asyncio.sleep(60)
            logger.debug("GitHub subscriber poll tick.")

    def _persist_config(self) -> None:
        self.config.clear()
        self.config.update(self.normalized_config)
        self.config.save_config()

    def _state_path(self) -> Path:
        return Path("data") / "plugin_data" / "astrbot_plugin_github_subscriber" / "state.json"
```

- [ ] **步骤 2：运行单元测试**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest -q
```

预期：已有单元测试 PASS。此任务暂不要求在 AstrBot 内启动，因为插件入口依赖 AstrBot 运行环境。

## 任务 11：把轮询结果转换为主动消息

**文件：**
- 修改：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/messages.py`
- 修改：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/poller.py`
- 修改：`/home/junie/astrbot_plugin_github_subscriber/main.py`

- [ ] **步骤 1：扩展消息构建函数**

在 `github_subscriber/messages.py` 增加：

```python
from .templates import render_template, truncate_text


def build_issue_variables(repo: str, item: dict, max_chars: int) -> dict:
    body_summary = truncate_text(item.get("body") or "", max_chars)
    return {
        "repo": repo,
        "repo_url": f"https://github.com/{repo}",
        "owner": repo.split("/", 1)[0],
        "repo_name": repo.split("/", 1)[1],
        "number": item.get("number", ""),
        "title": item.get("title", ""),
        "author": (item.get("user") or {}).get("login", ""),
        "created_at": item.get("created_at", ""),
        "url": item.get("html_url", ""),
        "body_summary": body_summary,
    }


def render_text_message(config: dict, sub: dict, template_name: str, variables: dict) -> str:
    template = resolve_template(config, sub, template_name)
    return render_template(template, variables)
```

- [ ] **步骤 2：扩展 poller 为异步单订阅轮询**

在 `github_subscriber/poller.py` 增加以下代码。该实现调用 `GitHubClient` 的专用接口，根据订阅开关收集事件，返回结构化待发送消息。所有被发现的新事件，无论是否超过展示上限，都会写入 state 去重集合：

```python
from datetime import datetime, timezone

from .messages import (
    build_issue_variables,
    build_star_variables,
    normalize_github_login,
)
from .templates import truncate_text


def _repo_parts(repo: str) -> tuple[str, str]:
    owner, name = repo.split("/", 1)
    return owner, name


def _base_variables(repo: str) -> dict[str, str]:
    owner, name = _repo_parts(repo)
    return {
        "repo": repo,
        "repo_url": f"https://github.com/{repo}",
        "owner": owner,
        "repo_name": name,
        "event_time": datetime.now(timezone.utc).isoformat(),
    }


def _release_variables(repo: str, item: dict, max_chars: int) -> dict:
    variables = _base_variables(repo)
    variables.update(
        {
            "tag_name": item.get("tag_name", ""),
            "release_name": item.get("name") or item.get("tag_name", ""),
            "release_author": (item.get("author") or {}).get("login", ""),
            "release_time": item.get("published_at") or item.get("created_at") or "",
            "release_url": item.get("html_url", ""),
            "release_notes": truncate_text(item.get("body") or "", max_chars),
        }
    )
    return variables


def _pr_variables(repo: str, item: dict, max_chars: int) -> dict:
    variables = build_issue_variables(repo, item, max_chars)
    variables.update(
        {
            "merged_by": (item.get("merged_by") or {}).get("login", ""),
            "merged_at": item.get("merged_at") or "",
            "mention": "",
        }
    )
    return variables


def _summary_message(target_umo: str, repo: str, event_label: str, skipped_count: int) -> dict:
    return {
        "target_umo": target_umo,
        "template_name": "_raw",
        "variables": {
            "text": f"本轮 {repo} 新增 {event_label} 较多，已展示 5 条，还有 {skipped_count} 条未展示。"
        },
        "mention_qq": "",
    }


async def poll_subscription_once(client, config, sub, state):
    repo = sub["repo"]
    owner, name = _repo_parts(repo)
    target_umo = sub["target_umo"]
    events = sub.get("events") or {}
    limits = config.get("message_limits") or {}
    max_items = int(limits.get("max_items_per_event_cycle", 5))
    issue_chars = int(limits.get("issue_body_summary_chars", 300))
    pr_chars = int(limits.get("pr_body_summary_chars", 300))
    release_chars = int(limits.get("release_notes_max_chars", 1500))
    messages: list[dict] = []

    if events.get("star"):
        stargazers = await client.get_stargazers(owner, name)
        repo_meta = await client.get_repo(owner, name)
        new_users = collect_new_stars(state, stargazers)
        if new_users:
            variables = build_star_variables(
                repo=repo,
                repo_url=f"https://github.com/{repo}",
                star_count=int(repo_meta.get("stargazers_count") or 0),
                new_users=new_users,
            )
            messages.append(
                {
                    "target_umo": target_umo,
                    "template_name": "star",
                    "variables": variables,
                    "mention_qq": "",
                }
            )

    if events.get("release"):
        releases = await client.get_releases(owner, name)
        selected_release, skipped_count = collect_new_releases(state, releases)
        if selected_release:
            messages.append(
                {
                    "target_umo": target_umo,
                    "template_name": "release",
                    "variables": _release_variables(repo, selected_release, release_chars),
                    "mention_qq": "",
                }
            )

    if events.get("issue"):
        issues = await client.get_issues(owner, name)
        selected_issues, skipped_count = collect_new_issues(state, issues, limit=max_items)
        for item in selected_issues:
            messages.append(
                {
                    "target_umo": target_umo,
                    "template_name": "issue",
                    "variables": build_issue_variables(repo, item, issue_chars),
                    "mention_qq": "",
                }
            )
        if skipped_count:
            messages.append(_summary_message(target_umo, repo, "Issue", skipped_count))

    if events.get("pr"):
        open_prs = await client.get_pulls(owner, name, "open")
        closed_prs = await client.get_pulls(owner, name, "closed")
        opened, merged = collect_new_prs(
            state,
            open_prs=open_prs,
            closed_prs=closed_prs,
            limit=max_items,
        )
        for item in opened:
            messages.append(
                {
                    "target_umo": target_umo,
                    "template_name": "pr_opened",
                    "variables": _pr_variables(repo, item, pr_chars),
                    "mention_qq": "",
                }
            )
        github_to_qq = {
            normalize_github_login(login): qq
            for login, qq in (config.get("github_to_qq") or {}).items()
        }
        for item in merged:
            variables = _pr_variables(repo, item, pr_chars)
            author_login = normalize_github_login(variables.get("author", ""))
            mention_qq = github_to_qq.get(author_login, "")
            variables["mention"] = "" if not mention_qq else " "
            messages.append(
                {
                    "target_umo": target_umo,
                    "template_name": "pr_merged",
                    "variables": variables,
                    "mention_qq": mention_qq,
                }
            )

    return messages
```

- [ ] **步骤 3：在 main.py 中发送主动消息**

修改 `_poll_loop`：

```python
async def _poll_loop(self):
    from astrbot.api.event import MessageChain
    import astrbot.api.message_components as Comp
    from github_subscriber.github_client import GitHubClient, GitHubApiError
    from github_subscriber.messages import render_text_message
    from github_subscriber.poller import poll_subscription_once

    while True:
        await asyncio.sleep(60)
        async with GitHubClient(self.normalized_config.get("github_token", "")) as client:
            for sub in list(self.normalized_config.get("subscriptions", [])):
                if not sub.get("enabled", True):
                    continue
                sub_state = self.state.get_subscription_state(sub["target_umo"], sub["repo"])
                try:
                    messages = await poll_subscription_once(
                        client,
                        self.normalized_config,
                        sub,
                        sub_state,
                    )
                except GitHubApiError as exc:
                    logger.warning("GitHub polling failed for %s: %s", sub.get("repo"), exc)
                    continue
                for message in messages:
                    chain = MessageChain()
                    mention_qq = message.get("mention_qq")
                    text = render_text_message(
                        self.normalized_config,
                        sub,
                        message["template_name"],
                        message["variables"],
                    )
                    if mention_qq:
                        chain.chain.append(Comp.At(qq=str(mention_qq)))
                    chain.message(text)
                    await self.context.send_message(sub["target_umo"], chain)
                    await asyncio.sleep(self.normalized_config["message_limits"]["message_send_delay_seconds"])
                self.state.save()
```

如果 `MessageChain().chain.append(...)` 在当前 AstrBot 版本不可用，改为构造 `list[Comp.At, Comp.Plain]` 并使用支持的消息链 API。以 AstrBot 文档中的 `Comp.At(qq=...)` 和 `MessageChain().message(...)` 为准。

- [ ] **步骤 4：运行测试**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest -q
```

预期：所有单元测试 PASS。

## 任务 12：完善初始化 baseline

**文件：**
- 修改：`/home/junie/astrbot_plugin_github_subscriber/github_subscriber/poller.py`
- 修改：`/home/junie/astrbot_plugin_github_subscriber/tests/test_poller.py`

- [ ] **步骤 1：添加 baseline 测试**

追加到 `tests/test_poller.py`：

```python
from github_subscriber.poller import initialize_baseline


def test_initialize_baseline_records_existing_items_without_messages():
    state = {}
    initialize_baseline(
        state,
        stargazers=[{"user": {"login": "alice"}}],
        releases=[{"id": 1}],
        issues=[{"number": 2}, {"number": 3, "pull_request": {}}],
        open_prs=[{"number": 4}],
        closed_prs=[{"number": 5, "merged_at": "2026-06-01T00:00:00Z"}],
        now="2026-06-29T00:00:00Z",
    )

    assert state["initialized_at"] == "2026-06-29T00:00:00Z"
    assert state["known_star_users"] == ["alice"]
    assert state["notified_release_ids"] == [1]
    assert state["notified_issue_numbers"] == [2]
    assert state["notified_pr_numbers"] == [4]
    assert state["notified_merged_pr_numbers"] == [5]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_poller.py::test_initialize_baseline_records_existing_items_without_messages -q
```

预期：FAIL，提示 `initialize_baseline` 不存在。

- [ ] **步骤 3：实现 initialize_baseline**

在 `github_subscriber/poller.py` 增加：

```python
def initialize_baseline(
    state: dict[str, Any],
    *,
    stargazers: list[dict[str, Any]],
    releases: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    open_prs: list[dict[str, Any]],
    closed_prs: list[dict[str, Any]],
    now: str,
) -> None:
    state["initialized_at"] = now
    state["known_star_users"] = [
        (item.get("user") or {}).get("login", "")
        for item in stargazers
        if (item.get("user") or {}).get("login")
    ]
    state["notified_release_ids"] = [item["id"] for item in releases if "id" in item]
    state["notified_issue_numbers"] = [
        item["number"]
        for item in issues
        if "pull_request" not in item and "number" in item
    ]
    state["notified_pr_numbers"] = [
        item["number"]
        for item in open_prs
        if "number" in item
    ]
    state["notified_merged_pr_numbers"] = [
        item["number"]
        for item in closed_prs
        if item.get("merged_at") and "number" in item
    ]
```

- [ ] **步骤 4：运行 poller 测试验证通过**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest tests/test_poller.py -q
```

预期：所有 poller 测试 PASS。

## 任务 13：文档补充与最终验证

**文件：**
- 修改：`/home/junie/astrbot_plugin_github_subscriber/docs/design.md`
- 创建：`/home/junie/astrbot_plugin_github_subscriber/README.md`

- [ ] **步骤 1：创建 README**

写入 `README.md`：

```markdown
# astrbot_plugin_github_subscriber

通用 GitHub 仓库订阅提醒插件。插件通过轮询 GitHub REST API，把 Star、Release、Issue、PR 新建和 PR 合并事件推送到 AstrBot 的群聊或私聊。

## 功能

- 支持公开 GitHub 仓库订阅。
- 支持群聊和私聊目标。
- 支持 Star、Release、Issue、新 PR、PR 合并提醒。
- 支持全局可选 GitHub Token。
- 支持 GitHub 用户名到 QQ UID 映射，PR 合并时 @ PR 作者。
- 支持全局默认模板和单条订阅模板覆盖。

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

命令默认作用于当前会话。群聊中执行管理当前群；私聊中执行管理当前私聊。

## 默认事件

命令新增订阅时默认开启 Release、Issue、PR，默认关闭 Star。
```

- [ ] **步骤 2：运行完整单元测试**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m pytest -q
```

预期：所有测试 PASS。

- [ ] **步骤 3：验证 JSON 配置 schema**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
python -m json.tool _conf_schema.json >/tmp/github_subscriber_schema.json
```

预期：退出码 0。

- [ ] **步骤 4：检查文件结构**

运行：

```bash
cd /home/junie/astrbot_plugin_github_subscriber
find . -maxdepth 3 -type f | sort
```

预期至少包含：

```text
./_conf_schema.json
./README.md
./github_subscriber/config.py
./github_subscriber/github_client.py
./github_subscriber/messages.py
./github_subscriber/models.py
./github_subscriber/poller.py
./github_subscriber/repo_parser.py
./github_subscriber/state.py
./main.py
./metadata.yaml
./requirements.txt
```

## 自检

- 规格覆盖：计划覆盖 GitHub Token 可选、目标 UMO 隔离、默认事件开关、管理员命令、命令持久写回配置、Star 聚合、Release 最新一条、Issue 新建、PR 新建和合并、PR 作者 @、模板占位符、摘要截断、发送节流、初始化 baseline、状态与配置分离。
- 占位符扫描：计划中没有空泛占位步骤。任务 11 中 `poll_subscription_once` 要求填完整实现，不能保留空列表伪实现。
- 类型一致性：事件 key 使用 `star/release/issue/pr`；模板 key 使用 `star/release/issue/pr_opened/pr_merged`；状态字段使用 `known_star_users/notified_release_ids/notified_issue_numbers/notified_pr_numbers/notified_merged_pr_numbers`。
