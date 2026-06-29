from __future__ import annotations

import re


class RepoParseError(ValueError):
    """Raised when a user-provided value is not a repository reference."""


_OWNER = r"(?P<owner>[A-Za-z0-9_.-]+)"
_REPO = r"(?P<repo>[A-Za-z0-9_.-]+)"
_REPO_WITHOUT_GIT_SUFFIX = r"(?P<repo>(?![A-Za-z0-9_.-]*\.git/?$)[A-Za-z0-9_.-]+)"
_HTTPS_GITHUB_REPO_PATTERN = re.compile(
    rf"^https://github\.com/{_OWNER}/{_REPO_WITHOUT_GIT_SUFFIX}/?$"
)
_HTTPS_GITHUB_GIT_REPO_PATTERN = re.compile(
    rf"^https://github\.com/{_OWNER}/{_REPO}\.git$"
)
_GITHUB_REPO_PATTERN = re.compile(rf"^github\.com/{_OWNER}/{_REPO_WITHOUT_GIT_SUFFIX}$")
_BARE_REPO_PATTERN = re.compile(rf"^{_OWNER}/{_REPO_WITHOUT_GIT_SUFFIX}$")


def parse_repo_ref(value: str) -> str:
    raw = value.strip()
    match = (
        _HTTPS_GITHUB_REPO_PATTERN.match(raw)
        or _HTTPS_GITHUB_GIT_REPO_PATTERN.match(raw)
        or _GITHUB_REPO_PATTERN.match(raw)
        or _BARE_REPO_PATTERN.match(raw)
    )
    if not match:
        raise RepoParseError("请提供仓库主页链接，例如：https://github.com/owner/repo")

    owner = match.group("owner")
    repo = match.group("repo")
    if raw.startswith("https://github.com/") and repo.endswith(".git"):
        repo = repo.removesuffix(".git")

    if not owner or not repo:
        raise RepoParseError("请提供仓库主页链接，例如：https://github.com/owner/repo")

    return f"{owner}/{repo}"
