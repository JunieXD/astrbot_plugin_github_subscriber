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
