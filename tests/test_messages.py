import github_subscriber.messages as messages
from github_subscriber.config import normalize_config
from github_subscriber.messages import (
    build_star_variables,
    normalize_github_login,
    resolve_template,
)


def test_resolve_template_uses_subscription_override_first():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": "override {title}"}}

    assert resolve_template(config, sub, "issue") == "override {title}"


def test_resolve_template_falls_back_to_global():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": ""}}

    assert resolve_template(config, sub, "issue") == "global {title}"


def test_resolve_template_falls_back_when_override_is_whitespace():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": "   "}}

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


def test_build_star_variables_accepts_positional_arguments():
    variables = build_star_variables(
        "Owner/Repo",
        "https://github.com/Owner/Repo",
        1,
        ["alice"],
    )

    assert variables["repo"] == "Owner/Repo"
    assert variables["repo_url"] == "https://github.com/Owner/Repo"
    assert variables["owner"] == "Owner"
    assert variables["repo_name"] == "Repo"
    assert variables["new_star_count"] == 1
    assert variables["star_count"] == 1
    assert variables["star_users"] == "alice"


def test_build_star_variables_uses_all_names_when_five_or_fewer():
    variables = build_star_variables(
        repo="Owner/Repo",
        repo_url="https://github.com/Owner/Repo",
        star_count=42,
        new_users=["a", "b", "c", "d", "e"],
    )

    assert variables["star_users"] == "a、b、c、d、e"


def test_normalize_github_login_strips_and_lowercases():
    assert normalize_github_login(" Alice ") == "alice"


def test_build_issue_variables_truncates_body_summary():
    assert hasattr(messages, "build_issue_variables")
    variables = messages.build_issue_variables(
        "Owner/Repo",
        {
            "number": 12,
            "title": "Bug title",
            "user": {"login": "alice"},
            "created_at": "2026-06-01T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/12",
            "body": "abcdef",
        },
        max_chars=3,
    )

    assert variables == {
        "repo": "Owner/Repo",
        "repo_url": "https://github.com/Owner/Repo",
        "owner": "Owner",
        "repo_name": "Repo",
        "number": 12,
        "title": "Bug title",
        "author": "alice",
        "created_at": "2026-06-01T00:00:00Z",
        "url": "https://github.com/Owner/Repo/issues/12",
        "body_summary": "abc...",
    }


def test_render_text_message_uses_subscription_override():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": "override {title}"}}

    assert hasattr(messages, "render_text_message")
    assert (
        messages.render_text_message(config, sub, "issue", {"title": "Hello"})
        == "override Hello"
    )


def test_render_text_message_uses_global_template():
    config = normalize_config({"global_templates": {"issue": "global {title}"}})
    sub = {"template_overrides": {"issue": ""}}

    assert hasattr(messages, "render_text_message")
    assert (
        messages.render_text_message(config, sub, "issue", {"title": "Hello"})
        == "global Hello"
    )


def test_render_text_message_raw_returns_text_variable():
    config = normalize_config({})

    assert hasattr(messages, "render_text_message")
    assert (
        messages.render_text_message(config, {}, "_raw", {"text": "本轮摘要", "title": "ignored"})
        == "本轮摘要"
    )
