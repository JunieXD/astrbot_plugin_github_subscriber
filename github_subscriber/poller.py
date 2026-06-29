from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from .messages import normalize_github_login


@dataclass(frozen=True)
class PrCollectionResult:
    opened: list[dict[str, Any]]
    merged: list[dict[str, Any]]
    skipped_opened_count: int
    skipped_merged_count: int

    def __iter__(self) -> Iterator[list[dict[str, Any]]]:
        yield self.opened
        yield self.merged


def collect_new_stars(
    state: dict[str, Any], stargazers: list[dict[str, Any]]
) -> list[str]:
    known = {
        normalize_github_login(login) for login in state.setdefault("known_star_users", [])
    }
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
    state: dict[str, Any], releases: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, int]:
    seen = set(state.setdefault("notified_release_ids", []))
    new_releases = [
        item
        for item in releases
        if item.get("id") is not None and item.get("id") not in seen
    ]
    if not new_releases:
        return None, 0
    selected = sorted(
        new_releases,
        key=lambda row: row.get("published_at") or row.get("created_at") or "",
        reverse=True,
    )[0]
    for item in new_releases:
        state["notified_release_ids"].append(item["id"])
    return selected, max(0, len(new_releases) - 1)


def collect_new_issues(
    state: dict[str, Any], issues: list[dict[str, Any]], *, limit: int
) -> tuple[list[dict[str, Any]], int]:
    seen = set(state.setdefault("notified_issue_numbers", []))
    candidates = [
        item
        for item in issues
        if "pull_request" not in item
        and item.get("number") is not None
        and item.get("number") not in seen
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
) -> PrCollectionResult:
    seen_opened = set(state.setdefault("notified_pr_numbers", []))
    seen_merged = set(state.setdefault("notified_merged_pr_numbers", []))

    opened = [
        item
        for item in open_prs
        if item.get("number") is not None and item.get("number") not in seen_opened
    ]
    opened.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    for item in opened:
        state["notified_pr_numbers"].append(item["number"])

    merged = [
        item
        for item in closed_prs
        if item.get("merged_at")
        and item.get("number") is not None
        and item.get("number") not in seen_merged
    ]
    merged.sort(key=lambda row: row.get("merged_at") or "", reverse=True)
    for item in merged:
        state["notified_merged_pr_numbers"].append(item["number"])

    return PrCollectionResult(
        opened=opened[:limit],
        merged=merged[:limit],
        skipped_opened_count=max(0, len(opened) - limit),
        skipped_merged_count=max(0, len(merged) - limit),
    )
