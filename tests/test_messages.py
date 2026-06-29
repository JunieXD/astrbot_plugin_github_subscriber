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
