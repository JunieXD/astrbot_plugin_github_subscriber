import pytest
from datetime import datetime, timezone

from github_subscriber.config import (
    DEFAULT_GLOBAL_TEMPLATES,
    add_subscription,
    disable_event,
    enable_event,
    get_subscriptions_for_target,
    normalize_github_to_qq,
    normalize_config,
    remove_subscription,
)


def test_normalize_config_adds_defaults():
    config = normalize_config({})

    assert config["github_token"] == ""
    assert config["github_to_qq"] == []
    assert config["default_intervals"]["star_minutes"] == 1
    assert config["default_intervals"]["release_minutes"] == 5
    assert config["default_intervals"]["issue_minutes"] == 2
    assert config["default_intervals"]["pr_minutes"] == 2
    assert config["message_limits"]["max_items_per_event_cycle"] == 5
    assert config["global_templates"] == DEFAULT_GLOBAL_TEMPLATES
    assert config["subscriptions"] == []


def test_normalize_config_accepts_github_to_qq_template_list():
    config = normalize_config(
        {
            "github_to_qq": [
                {
                    "__template_key": "mapping",
                    "github_login": "Alice",
                    "qq_uid": "10001",
                },
                {
                    "github_login": "bob",
                    "qq_uid": 10002,
                },
                {
                    "github_login": "",
                    "qq_uid": "ignored",
                },
            ]
        }
    )

    assert config["github_to_qq"] == [
        {
            "__template_key": "mapping",
            "github_login": "Alice",
            "qq_uid": "10001",
        },
        {
            "github_login": "bob",
            "qq_uid": 10002,
        },
        {
            "github_login": "",
            "qq_uid": "ignored",
        },
    ]
    assert normalize_github_to_qq(config["github_to_qq"]) == {
        "Alice": "10001",
        "bob": "10002",
    }


def test_normalize_config_migrates_legacy_github_to_qq_dict_to_template_list():
    config = normalize_config({"github_to_qq": {"Alice": 10001}})

    assert config["github_to_qq"] == [
        {
            "__template_key": "mapping",
            "github_login": "Alice",
            "qq_uid": "10001",
        }
    ]


def test_add_subscription_defaults_events_and_target():
    config = normalize_config({})
    sub = add_subscription(
        config,
        target_umo="aiocqhttp:GroupMessage:123",
        target_name="群 123",
        repo="Owner/Repo",
    )

    assert sub["repo"] == "Owner/Repo"
    assert sub["__template_key"] == "subscription"
    assert sub["target_umo"] == "aiocqhttp:GroupMessage:123"
    assert sub["admin_qq_uid"] == ""
    assert datetime.fromisoformat(sub["created_at"]).tzinfo == timezone.utc
    assert sub["enabled"] is True
    assert sub["events"] == {
        "star": False,
        "release": True,
        "issue": True,
        "pr_opened": True,
        "pr_merged": True,
    }
    assert get_subscriptions_for_target(config, "aiocqhttp:GroupMessage:123") == [sub]


def test_add_subscription_is_idempotent_per_target_and_repo():
    config = normalize_config({})
    first = add_subscription(config, "umo-a", "A", "Owner/Repo")
    second = add_subscription(config, "umo-a", "A", "owner/repo")
    third = add_subscription(config, "umo-b", "B", "Owner/Repo")

    assert first is second
    assert len(config["subscriptions"]) == 2
    assert third["target_umo"] == "umo-b"


def test_enable_disable_and_remove_subscription():
    config = normalize_config({})
    add_subscription(config, "umo-a", "A", "Owner/Repo")

    assert enable_event(config, "umo-a", "Owner/Repo", "star") is True
    assert config["subscriptions"][0]["events"]["star"] is True

    assert enable_event(config, "umo-missing", "Owner/Repo", "star") is False

    assert disable_event(config, "umo-a", "Owner/Repo", "pr_opened") is True
    assert config["subscriptions"][0]["events"]["pr_opened"] is False
    assert config["subscriptions"][0]["events"]["pr_merged"] is True

    assert disable_event(config, "umo-a", "Owner/Repo", "pr") is True
    assert config["subscriptions"][0]["events"]["pr_opened"] is False
    assert config["subscriptions"][0]["events"]["pr_merged"] is False

    assert disable_event(config, "umo-a", "Owner/Repo", "all") is True
    assert config["subscriptions"][0]["events"] == {
        "star": False,
        "release": False,
        "issue": False,
        "pr_opened": False,
        "pr_merged": False,
    }

    assert disable_event(config, "umo-missing", "Owner/Repo", "all") is False

    with pytest.raises(ValueError):
        enable_event(config, "umo-a", "Owner/Repo", "unknown")
    with pytest.raises(ValueError):
        disable_event(config, "umo-a", "Owner/Repo", "unknown")

    assert remove_subscription(config, "umo-missing", "Owner/Repo") is False
    assert remove_subscription(config, "umo-a", "Owner/Repo") is True
    assert config["subscriptions"] == []


def test_normalize_config_does_not_share_subscription_list():
    first = normalize_config({})
    second = normalize_config({})

    first["subscriptions"].append({"repo": "Owner/Repo"})

    assert second["subscriptions"] == []


def test_normalize_config_coerces_subscriptions_to_list():
    config = normalize_config({"subscriptions": None})

    assert config["subscriptions"] == []

    add_subscription(config, "umo", "name", "Owner/Repo")
    assert len(config["subscriptions"]) == 1


def test_normalize_config_migrates_legacy_pr_switch_and_admin_qq():
    config = normalize_config(
        {
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Repo",
                    "events": {"issue": True, "pr": False},
                },
                {
                    "target_umo": "umo-b",
                    "repo": "Other/Repo",
                    "admin_qq_uid": 10001,
                    "events": {
                        "pr": False,
                        "pr_opened": True,
                    },
                },
            ]
        }
    )

    first, second = config["subscriptions"]
    assert first["events"] == {
        "issue": True,
        "pr_opened": False,
        "pr_merged": False,
    }
    assert first["admin_qq_uid"] == ""
    assert second["events"] == {
        "pr_opened": True,
        "pr_merged": False,
    }
    assert second["admin_qq_uid"] == "10001"


def test_normalize_config_copies_mutable_defaults():
    first = normalize_config({})
    second = normalize_config({})

    first["github_to_qq"].append(
        {
            "__template_key": "mapping",
            "github_login": "alice",
            "qq_uid": "10001",
        }
    )
    first["global_templates"]["issue"] = "changed"
    first["default_intervals"]["issue_minutes"] = 9

    assert second["github_to_qq"] == []
    assert second["global_templates"] == DEFAULT_GLOBAL_TEMPLATES
    assert second["default_intervals"]["issue_minutes"] == 2


def test_add_subscription_does_not_share_mutable_defaults_between_subscriptions():
    config = normalize_config({})
    first = add_subscription(config, "umo-a", "A", "Owner/Repo")
    second = add_subscription(config, "umo-b", "B", "Owner/Repo")

    first["events"]["star"] = True
    first["template_overrides"]["issue"] = "custom"

    assert second["events"]["star"] is False
    assert second["template_overrides"]["issue"] == ""
