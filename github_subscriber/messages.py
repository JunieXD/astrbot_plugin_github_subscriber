from __future__ import annotations

from typing import Any

from .templates import render_template, truncate_text


def resolve_template(config: dict[str, Any], sub: dict[str, Any], template_name: str) -> str:
    override = (sub.get("template_overrides") or {}).get(template_name) or ""
    if override.strip():
        return override
    return (config.get("global_templates") or {}).get(template_name, "")


def build_star_variables(
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


def build_issue_variables(
    repo: str,
    item: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    owner, repo_name = repo.split("/", 1)
    return {
        "repo": repo,
        "repo_url": f"https://github.com/{repo}",
        "owner": owner,
        "repo_name": repo_name,
        "number": item.get("number", ""),
        "title": item.get("title", ""),
        "author": (item.get("user") or {}).get("login", ""),
        "created_at": item.get("created_at", ""),
        "url": item.get("html_url", ""),
        "body_summary": truncate_text(item.get("body") or "", max_chars),
    }


def render_text_message(
    config: dict[str, Any],
    sub: dict[str, Any],
    template_name: str,
    variables: dict[str, Any],
) -> str:
    if template_name == "_raw":
        return str(variables.get("text", ""))
    return render_template(resolve_template(config, sub, template_name), variables)


def normalize_github_login(login: str) -> str:
    return login.strip().lower()
