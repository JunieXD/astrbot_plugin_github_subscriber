from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from .config import normalize_github_to_qq
from .messages import (
    build_issue_variables,
    build_star_variables,
    format_github_datetime,
    normalize_github_login,
)
from .models import EVENT_KEYS
from .templates import truncate_text


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
    _remember_star_count(
        state,
        max(_remembered_star_count(state), len(state["known_star_users"])),
    )
    return new_users


def collect_new_star_count(state: dict[str, Any], star_count: int) -> int:
    previous_count = _remembered_star_count(state)
    _remember_star_count(state, star_count)
    return max(0, star_count - previous_count)


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


def initialize_baseline(
    state: dict[str, Any],
    *,
    stargazers: list[dict[str, Any]],
    star_count: int | None = None,
    releases: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    open_prs: list[dict[str, Any]],
    closed_prs: list[dict[str, Any]],
    events: dict[str, bool] | None = None,
    threshold: datetime | None = None,
    now: str,
) -> None:
    state["initialized_at"] = now
    state["known_star_users"] = [
        (item.get("user") or {}).get("login", "")
        for item in stargazers
        if (item.get("user") or {}).get("login")
    ]
    _remember_star_count(
        state,
        star_count if star_count is not None else len(state["known_star_users"]),
    )
    state["notified_release_ids"] = [
        item["id"]
        for item in releases
        if item.get("id") is not None
        and _item_is_not_after_threshold(
            item,
            threshold,
            "published_at",
            "created_at",
        )
    ]
    state["notified_issue_numbers"] = [
        item["number"]
        for item in issues
        if "pull_request" not in item
        and item.get("number") is not None
        and _item_is_not_after_threshold(item, threshold, "created_at")
    ]
    state["notified_pr_numbers"] = [
        item["number"]
        for item in open_prs
        if item.get("number") is not None
        and _item_is_not_after_threshold(item, threshold, "created_at")
    ]
    state["notified_merged_pr_numbers"] = [
        item["number"]
        for item in closed_prs
        if item.get("merged_at")
        and item.get("number") is not None
        and _item_is_not_after_threshold(item, threshold, "merged_at")
    ]
    events = events or {}
    state["event_enabled"] = {key: bool(events.get(key)) for key in EVENT_KEYS}


def _repo_parts(repo: str) -> tuple[str, str]:
    return repo.split("/", 1)


def _base_variables(repo: str) -> dict[str, Any]:
    owner, repo_name = _repo_parts(repo)
    return {
        "repo": repo,
        "repo_url": f"https://github.com/{repo}",
        "owner": owner,
        "repo_name": repo_name,
    }


def _release_variables(
    repo: str,
    item: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    variables = _base_variables(repo)
    variables.update(
        {
            "tag_name": item.get("tag_name", ""),
            "release_name": item.get("name") or item.get("tag_name", ""),
            "release_author": (item.get("author") or {}).get("login", ""),
            "release_time": format_github_datetime(
                item.get("published_at") or item.get("created_at") or ""
            ),
            "release_url": item.get("html_url", ""),
            "release_notes": truncate_text(item.get("body") or "", max_chars),
        }
    )
    return variables


def _pr_variables(
    repo: str,
    item: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    variables = build_issue_variables(repo, item, max_chars)
    variables.update(
        {
            "merged_by": (item.get("merged_by") or {}).get("login", ""),
            "merged_at": format_github_datetime(item.get("merged_at") or ""),
            "mention": "",
        }
    )
    return variables


def _summary_message(
    target_umo: str,
    repo: str,
    event_label: str,
    max_items: int,
    skipped_count: int,
) -> dict[str, Any]:
    return {
        "target_umo": target_umo,
        "template_name": "_raw",
        "variables": {
            "text": (
                f"本轮 {repo} 新增 {event_label} 较多，"
                f"已展示 {max_items} 条，还有 {skipped_count} 条未展示。"
            )
        },
        "mention_qq": "",
    }


def _parse_checked_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        checked_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if checked_at.tzinfo is None:
        return checked_at.replace(tzinfo=timezone.utc)
    return checked_at.astimezone(timezone.utc)


def _item_is_not_after_threshold(
    item: dict[str, Any],
    threshold: datetime | None,
    *field_names: str,
) -> bool:
    if threshold is None:
        return True

    for field_name in field_names:
        item_time = _parse_checked_at(str(item.get(field_name) or ""))
        if item_time is not None:
            return item_time <= threshold

    return True


def _event_interval_seconds(
    config: dict[str, Any],
    sub: dict[str, Any],
    event_name: str,
) -> int:
    defaults = config.get("default_intervals") or {}
    intervals = {**defaults, **(sub.get("intervals") or {})}
    min_seconds = int(defaults.get("min_interval_seconds", 60) or 60)
    minutes = int(intervals.get(f"{event_name}_minutes", 1) or 1)
    return max(minutes * 60, min_seconds)


def _event_is_due(
    working_state: dict[str, Any],
    config: dict[str, Any],
    sub: dict[str, Any],
    event_name: str,
    now: datetime,
) -> bool:
    last_checked = (working_state.get("last_checked_at") or {}).get(event_name)
    checked_at = _parse_checked_at(last_checked)
    if checked_at is None:
        return True
    elapsed = (now - checked_at).total_seconds()
    return elapsed >= _event_interval_seconds(config, sub, event_name)


def _mark_checked(working_state: dict[str, Any], event_name: str, now: datetime) -> None:
    working_state.setdefault("last_checked_at", {})[event_name] = now.isoformat()


def _previously_enabled(working_state: dict[str, Any], event_name: str) -> bool:
    event_enabled = working_state.get("event_enabled")
    if not isinstance(event_enabled, dict):
        return True
    return bool(event_enabled.get(event_name, True))


def _mark_event_enabled(working_state: dict[str, Any], event_name: str, enabled: bool) -> None:
    working_state.setdefault("event_enabled", {})[event_name] = enabled


def _coerce_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback


def _remembered_star_count(working_state: dict[str, Any]) -> int:
    users_count = len(working_state.get("known_star_users") or [])
    if "known_star_count" not in working_state:
        return users_count
    return max(
        _coerce_non_negative_int(working_state.get("known_star_count")),
        users_count,
    )


def _remember_star_count(working_state: dict[str, Any], star_count: int) -> None:
    working_state["known_star_count"] = _coerce_non_negative_int(star_count)


def _has_complete_star_users(working_state: dict[str, Any]) -> bool:
    if "known_star_count" not in working_state:
        return True
    return len(working_state.get("known_star_users") or []) >= _remembered_star_count(
        working_state
    )


def _repo_star_count(repo_meta: dict[str, Any], fallback: int = 0) -> int:
    return _coerce_non_negative_int(repo_meta.get("stargazers_count"), fallback)


def _baseline_stars(
    working_state: dict[str, Any],
    stargazers: list[dict[str, Any]],
    star_count: int | None = None,
) -> None:
    working_state["known_star_users"] = [
        (item.get("user") or {}).get("login", "")
        for item in stargazers
        if (item.get("user") or {}).get("login")
    ]
    _remember_star_count(
        working_state,
        star_count
        if star_count is not None
        else len(working_state["known_star_users"]),
    )


def _baseline_releases(working_state: dict[str, Any], releases: list[dict[str, Any]]) -> None:
    working_state["notified_release_ids"] = [
        item["id"] for item in releases if item.get("id") is not None
    ]


def _baseline_issues(working_state: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    working_state["notified_issue_numbers"] = [
        item["number"]
        for item in issues
        if "pull_request" not in item and item.get("number") is not None
    ]


def _baseline_prs(
    working_state: dict[str, Any],
    *,
    open_prs: list[dict[str, Any]],
    closed_prs: list[dict[str, Any]],
) -> None:
    working_state["notified_pr_numbers"] = [
        item["number"] for item in open_prs if item.get("number") is not None
    ]
    working_state["notified_merged_pr_numbers"] = [
        item["number"]
        for item in closed_prs
        if item.get("merged_at") and item.get("number") is not None
    ]


async def poll_subscription_once(
    client: Any,
    config: dict[str, Any],
    sub: dict[str, Any],
    state: dict[str, Any],
    *,
    now: datetime | None = None,
    on_event_error: Callable[[str, Exception], None] | None = None,
) -> list[dict[str, Any]]:
    repo = sub["repo"]
    owner, name = _repo_parts(repo)
    target_umo = sub["target_umo"]
    events = sub.get("events") or {}
    now = now or datetime.now(timezone.utc)
    limits = config.get("message_limits") or {}
    max_items = int(limits.get("max_items_per_event_cycle", 5))
    issue_chars = int(limits.get("issue_body_summary_chars", 300))
    pr_chars = int(limits.get("pr_body_summary_chars", 300))
    release_chars = int(limits.get("release_notes_max_chars", 1500))
    working_state = deepcopy(state)
    messages: list[dict[str, Any]] = []
    subscription_created_at = _parse_checked_at(str(sub.get("created_at") or ""))

    def rollback_event(
        event_name: str,
        exc: Exception,
        snapshot: dict[str, Any],
        message_count: int,
    ) -> None:
        working_state.clear()
        working_state.update(snapshot)
        del messages[message_count:]
        if on_event_error is not None:
            on_event_error(event_name, exc)

    if not working_state.get("initialized_at"):
        star_count: int | None = None
        try:
            stargazers = await client.get_stargazers(owner, name)
        except Exception:
            repo_meta = await client.get_repo(owner, name)
            star_count = _repo_star_count(
                repo_meta,
                _remembered_star_count(working_state),
            )
            stargazers = []
        releases = await client.get_releases(owner, name)
        issues = await client.get_issues(owner, name)
        open_prs = await client.get_pulls(owner, name, "open")
        closed_prs = await client.get_pulls(owner, name, "closed")
        initialize_baseline(
            working_state,
            stargazers=stargazers,
            star_count=star_count,
            releases=releases,
            issues=issues,
            open_prs=open_prs,
            closed_prs=closed_prs,
            events=events,
            threshold=subscription_created_at,
            now=now.isoformat(),
        )
        state.clear()
        state.update(working_state)
        return []

    if events.get("star"):
        event_snapshot = deepcopy(working_state)
        event_message_count = len(messages)
        try:
            if not _event_is_due(working_state, config, sub, "star", now):
                _mark_event_enabled(working_state, "star", True)
            elif not _previously_enabled(working_state, "star"):
                try:
                    stargazers = await client.get_stargazers(owner, name)
                except Exception:
                    repo_meta = await client.get_repo(owner, name)
                    _remember_star_count(
                        working_state,
                        _repo_star_count(
                            repo_meta,
                            _remembered_star_count(working_state),
                        ),
                    )
                else:
                    repo_meta = await client.get_repo(owner, name)
                    _baseline_stars(
                        working_state,
                        stargazers,
                        _repo_star_count(repo_meta, len(stargazers)),
                    )
                _mark_checked(working_state, "star", now)
                _mark_event_enabled(working_state, "star", True)
            else:
                try:
                    stargazers = await client.get_stargazers(owner, name)
                except Exception:
                    repo_meta = await client.get_repo(owner, name)
                    star_count = _repo_star_count(
                        repo_meta,
                        _remembered_star_count(working_state),
                    )
                    new_star_count = collect_new_star_count(working_state, star_count)
                    if new_star_count:
                        messages.append(
                            {
                                "target_umo": target_umo,
                                "template_name": "star",
                                "variables": build_star_variables(
                                    repo=repo,
                                    repo_url=f"https://github.com/{repo}",
                                    star_count=star_count,
                                    new_users=[],
                                    new_star_count=new_star_count,
                                ),
                                "mention_qq": "",
                            }
                        )
                else:
                    repo_meta = await client.get_repo(owner, name)
                    star_count = _repo_star_count(repo_meta, len(stargazers))
                    if _has_complete_star_users(working_state):
                        new_users = collect_new_stars(working_state, stargazers)
                        _remember_star_count(working_state, star_count)
                        new_star_count = len(new_users)
                    else:
                        new_star_count = collect_new_star_count(
                            working_state, star_count
                        )
                        new_users = []
                        _baseline_stars(working_state, stargazers, star_count)
                    if new_star_count:
                        messages.append(
                            {
                                "target_umo": target_umo,
                                "template_name": "star",
                                "variables": build_star_variables(
                                    repo=repo,
                                    repo_url=f"https://github.com/{repo}",
                                    star_count=star_count,
                                    new_users=new_users,
                                    new_star_count=new_star_count,
                                ),
                                "mention_qq": "",
                            }
                        )
                _mark_checked(working_state, "star", now)
                _mark_event_enabled(working_state, "star", True)
        except Exception as exc:
            rollback_event("star", exc, event_snapshot, event_message_count)
    else:
        _mark_event_enabled(working_state, "star", False)

    if events.get("release"):
        event_snapshot = deepcopy(working_state)
        event_message_count = len(messages)
        try:
            if not _event_is_due(working_state, config, sub, "release", now):
                _mark_event_enabled(working_state, "release", True)
            elif not _previously_enabled(working_state, "release"):
                releases = await client.get_releases(owner, name)
                _baseline_releases(working_state, releases)
                _mark_checked(working_state, "release", now)
                _mark_event_enabled(working_state, "release", True)
            else:
                releases = await client.get_releases(owner, name)
                selected_release, _skipped_count = collect_new_releases(
                    working_state,
                    releases,
                )
                if selected_release:
                    messages.append(
                        {
                            "target_umo": target_umo,
                            "template_name": "release",
                            "variables": _release_variables(
                                repo,
                                selected_release,
                                release_chars,
                            ),
                            "mention_qq": "",
                        }
                    )
                _mark_checked(working_state, "release", now)
                _mark_event_enabled(working_state, "release", True)
        except Exception as exc:
            rollback_event("release", exc, event_snapshot, event_message_count)
    else:
        _mark_event_enabled(working_state, "release", False)

    if events.get("issue"):
        event_snapshot = deepcopy(working_state)
        event_message_count = len(messages)
        try:
            if not _event_is_due(working_state, config, sub, "issue", now):
                _mark_event_enabled(working_state, "issue", True)
            elif not _previously_enabled(working_state, "issue"):
                issues = await client.get_issues(owner, name)
                _baseline_issues(working_state, issues)
                _mark_checked(working_state, "issue", now)
                _mark_event_enabled(working_state, "issue", True)
            else:
                issues = await client.get_issues(owner, name)
                selected_issues, skipped_count = collect_new_issues(
                    working_state,
                    issues,
                    limit=max_items,
                )
                for item in selected_issues:
                    messages.append(
                        {
                            "target_umo": target_umo,
                            "template_name": "issue",
                            "variables": build_issue_variables(repo, item, issue_chars),
                            "mention_qq": "",
                        }
                    )
                if skipped_count:
                    messages.append(
                        _summary_message(
                            target_umo,
                            repo,
                            "Issue",
                            max_items,
                            skipped_count,
                        )
                    )
                _mark_checked(working_state, "issue", now)
                _mark_event_enabled(working_state, "issue", True)
        except Exception as exc:
            rollback_event("issue", exc, event_snapshot, event_message_count)
    else:
        _mark_event_enabled(working_state, "issue", False)

    if events.get("pr"):
        event_snapshot = deepcopy(working_state)
        event_message_count = len(messages)
        try:
            if not _event_is_due(working_state, config, sub, "pr", now):
                _mark_event_enabled(working_state, "pr", True)
            elif not _previously_enabled(working_state, "pr"):
                open_prs = await client.get_pulls(owner, name, "open")
                closed_prs = await client.get_pulls(owner, name, "closed")
                _baseline_prs(working_state, open_prs=open_prs, closed_prs=closed_prs)
                _mark_checked(working_state, "pr", now)
                _mark_event_enabled(working_state, "pr", True)
            else:
                open_prs = await client.get_pulls(owner, name, "open")
                closed_prs = await client.get_pulls(owner, name, "closed")
                result = collect_new_prs(
                    working_state,
                    open_prs=open_prs,
                    closed_prs=closed_prs,
                    limit=max_items,
                )

                for item in result.opened:
                    messages.append(
                        {
                            "target_umo": target_umo,
                            "template_name": "pr_opened",
                            "variables": _pr_variables(repo, item, pr_chars),
                            "mention_qq": "",
                        }
                    )
                if result.skipped_opened_count:
                    messages.append(
                        _summary_message(
                            target_umo,
                            repo,
                            "PR",
                            max_items,
                            result.skipped_opened_count,
                        )
                    )

                github_to_qq = {
                    normalize_github_login(login): str(qq)
                    for login, qq in normalize_github_to_qq(
                        config.get("github_to_qq")
                    ).items()
                }
                for item in result.merged:
                    variables = _pr_variables(repo, item, pr_chars)
                    author_login = normalize_github_login(variables.get("author", ""))
                    mention_qq = github_to_qq.get(author_login, "")
                    variables["mention"] = " " if mention_qq else ""
                    messages.append(
                        {
                            "target_umo": target_umo,
                            "template_name": "pr_merged",
                            "variables": variables,
                            "mention_qq": mention_qq,
                        }
                    )
                if result.skipped_merged_count:
                    messages.append(
                        _summary_message(
                            target_umo,
                            repo,
                            "已合并 PR",
                            max_items,
                            result.skipped_merged_count,
                        )
                    )
                _mark_checked(working_state, "pr", now)
                _mark_event_enabled(working_state, "pr", True)
        except Exception as exc:
            rollback_event("pr", exc, event_snapshot, event_message_count)
    else:
        _mark_event_enabled(working_state, "pr", False)

    state.clear()
    state.update(working_state)
    return messages
