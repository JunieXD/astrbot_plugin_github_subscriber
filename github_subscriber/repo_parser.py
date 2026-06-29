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
