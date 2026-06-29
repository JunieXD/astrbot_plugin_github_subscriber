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
    "global_templates": DEFAULT_GLOBAL_TEMPLATES,
    "github_to_qq": {},
    "subscriptions": [],
}

DEFAULT_SUBSCRIPTION_EVENTS = {
    "star": False,
    "release": True,
    "issue": True,
    "pr": True,
}

DEFAULT_TEMPLATE_OVERRIDES = {
    "star": "",
    "release": "",
    "issue": "",
    "pr_opened": "",
    "pr_merged": "",
}


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    raw = raw or {}

    for key, value in raw.items():
        if isinstance(config.get(key), dict) and isinstance(value, dict):
            config[key].update(value)
        else:
            config[key] = deepcopy(value)

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
        "events": deepcopy(DEFAULT_SUBSCRIPTION_EVENTS),
        "intervals": deepcopy(config.get("default_intervals") or DEFAULT_CONFIG["default_intervals"]),
        "template_overrides": deepcopy(DEFAULT_TEMPLATE_OVERRIDES),
    }
    config.setdefault("subscriptions", []).append(sub)
    return sub


def find_subscription(
    config: dict[str, Any],
    target_umo: str,
    repo: str,
) -> dict[str, Any] | None:
    normalized_repo = repo.lower()
    for sub in config.get("subscriptions") or []:
        if sub.get("target_umo") == target_umo and str(sub.get("repo", "")).lower() == normalized_repo:
            return sub
    return None


def get_subscriptions_for_target(config: dict[str, Any], target_umo: str) -> list[dict[str, Any]]:
    return [
        sub
        for sub in config.get("subscriptions") or []
        if sub.get("target_umo") == target_umo
    ]


def remove_subscription(config: dict[str, Any], target_umo: str, repo: str) -> bool:
    subscriptions = config.get("subscriptions") or []
    for index, sub in enumerate(subscriptions):
        if sub.get("target_umo") == target_umo and str(sub.get("repo", "")).lower() == repo.lower():
            del subscriptions[index]
            return True
    return False


def enable_event(config: dict[str, Any], target_umo: str, repo: str, event_name: str) -> bool:
    return _set_event_enabled(config, target_umo, repo, event_name, True)


def disable_event(config: dict[str, Any], target_umo: str, repo: str, event_name: str) -> bool:
    return _set_event_enabled(config, target_umo, repo, event_name, False)


def _set_event_enabled(
    config: dict[str, Any],
    target_umo: str,
    repo: str,
    event_name: str,
    enabled: bool,
) -> bool:
    if event_name != "all" and event_name not in EVENT_KEYS:
        raise ValueError(f"Unknown event: {event_name}")

    sub = find_subscription(config, target_umo, repo)
    if sub is None:
        return False

    events = sub.setdefault("events", deepcopy(DEFAULT_SUBSCRIPTION_EVENTS))
    keys = EVENT_KEYS if event_name == "all" else (event_name,)
    for key in keys:
        events[key] = enabled
    return True
