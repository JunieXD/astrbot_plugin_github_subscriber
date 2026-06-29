from __future__ import annotations

from typing import Any


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


def normalize_github_login(login: str) -> str:
    return login.strip().lower()
