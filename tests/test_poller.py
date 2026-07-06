from github_subscriber.poller import (
    collect_new_issues,
    collect_new_prs,
    collect_new_releases,
    collect_new_stars,
    initialize_baseline,
)
from datetime import datetime, timezone


class FakeGitHubClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.stargazers: list[dict] = []
        self.repo_meta: dict = {"stargazers_count": 0}
        self.releases: list[dict] = []
        self.release_error: Exception | None = None
        self.issues: list[dict] = []
        self.pulls: dict[str, list[dict]] = {"open": [], "closed": []}
        self.pull_errors: dict[str, Exception] = {}

    async def get_stargazers(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("get_stargazers", owner, repo))
        return self.stargazers

    async def get_repo(self, owner: str, repo: str) -> dict:
        self.calls.append(("get_repo", owner, repo))
        return self.repo_meta

    async def get_releases(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("get_releases", owner, repo))
        if self.release_error is not None:
            raise self.release_error
        return self.releases

    async def get_issues(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("get_issues", owner, repo))
        return self.issues

    async def get_pulls(self, owner: str, repo: str, state: str) -> list[dict]:
        self.calls.append(("get_pulls", owner, repo, state))
        if state in self.pull_errors:
            raise self.pull_errors[state]
        return self.pulls[state]


def poller_config(**overrides):
    config = {
        "message_limits": {
            "issue_body_summary_chars": 300,
            "pr_body_summary_chars": 300,
            "release_notes_max_chars": 1500,
            "max_items_per_event_cycle": 2,
        },
        "github_to_qq": {},
    }
    config.update(overrides)
    return config


def subscription(events: dict[str, bool] | None = None) -> dict:
    return {
        "target_umo": "aiocqhttp:GroupMessage:100",
        "repo": "Owner/Repo",
        "events": events or {"star": False, "release": False, "issue": False, "pr": False},
        "intervals": {
            "star_minutes": 1,
            "release_minutes": 5,
            "issue_minutes": 2,
            "pr_minutes": 2,
        },
    }


def initialized_state(**overrides) -> dict:
    state = {"initialized_at": "2026-06-28T00:00:00Z"}
    state.update(overrides)
    return state


def test_initialize_baseline_records_existing_items_without_messages():
    state = {}
    initialize_baseline(
        state,
        stargazers=[{"user": {"login": "alice"}}],
        releases=[{"id": 1}, {"id": None}],
        issues=[
            {"number": 2},
            {"number": 3, "pull_request": {}},
            {"number": None},
        ],
        open_prs=[{"number": 4}, {"number": None}],
        closed_prs=[
            {"number": 5, "merged_at": "2026-06-01T00:00:00Z"},
            {"number": None, "merged_at": "2026-06-02T00:00:00Z"},
        ],
        now="2026-06-29T00:00:00Z",
    )

    assert state["initialized_at"] == "2026-06-29T00:00:00Z"
    assert state["known_star_users"] == ["alice"]
    assert state["notified_release_ids"] == [1]
    assert state["notified_issue_numbers"] == [2]
    assert state["notified_pr_numbers"] == [4]
    assert state["notified_merged_pr_numbers"] == [5]


def test_collect_new_stars_updates_known_users_and_limits_message():
    state = {"known_star_users": ["alice"]}
    new_users = collect_new_stars(
        state,
        stargazers=[
            {"user": {"login": "alice"}, "starred_at": "2026-06-01T00:00:00Z"},
            {"user": {"login": "bob"}, "starred_at": "2026-06-02T00:00:00Z"},
        ],
    )

    assert new_users == ["bob"]
    assert state["known_star_users"] == ["alice", "bob"]


def test_collect_new_stars_ignores_known_users_case_insensitively():
    state = {"known_star_users": ["Alice"]}
    new_users = collect_new_stars(
        state,
        stargazers=[
            {"user": {"login": "alice"}, "starred_at": "2026-06-01T00:00:00Z"},
            {"user": {"login": "Bob"}, "starred_at": "2026-06-02T00:00:00Z"},
        ],
    )

    assert new_users == ["Bob"]
    assert state["known_star_users"] == ["Alice", "Bob"]


def test_collect_new_releases_returns_latest_only_and_marks_all_seen():
    state = {"notified_release_ids": []}
    releases = [
        {"id": 1, "published_at": "2026-06-01T00:00:00Z"},
        {"id": 2, "published_at": "2026-06-02T00:00:00Z"},
    ]

    selected, skipped_count = collect_new_releases(state, releases)

    assert selected["id"] == 2
    assert skipped_count == 1
    assert state["notified_release_ids"] == [1, 2]


def test_collect_new_releases_skips_missing_ids():
    state = {"notified_release_ids": []}
    releases = [
        {"published_at": "2026-06-03T00:00:00Z"},
        {"id": None, "published_at": "2026-06-02T00:00:00Z"},
        {"id": 1, "published_at": "2026-06-01T00:00:00Z"},
    ]

    selected, skipped_count = collect_new_releases(state, releases)

    assert selected["id"] == 1
    assert skipped_count == 0
    assert state["notified_release_ids"] == [1]


def test_collect_new_issues_filters_prs_and_limits_to_five():
    state = {"notified_issue_numbers": []}
    issues = [
        {"number": i, "created_at": f"2026-06-{i:02d}T00:00:00Z"}
        for i in range(1, 8)
    ]
    issues.append({"number": 99, "pull_request": {}})

    selected, skipped_count = collect_new_issues(state, issues, limit=5)

    assert [item["number"] for item in selected] == [7, 6, 5, 4, 3]
    assert skipped_count == 2
    assert set(state["notified_issue_numbers"]) == set(range(1, 8))


def test_collect_new_issues_skips_missing_numbers():
    state = {"notified_issue_numbers": []}
    issues = [
        {"created_at": "2026-06-03T00:00:00Z"},
        {"number": None, "created_at": "2026-06-02T00:00:00Z"},
        {"number": 1, "created_at": "2026-06-01T00:00:00Z"},
    ]

    selected, skipped_count = collect_new_issues(state, issues, limit=5)

    assert [item["number"] for item in selected] == [1]
    assert skipped_count == 0
    assert state["notified_issue_numbers"] == [1]
    assert None not in state["notified_issue_numbers"]


def test_collect_new_prs_splits_opened_and_merged():
    state = {"notified_pr_numbers": [], "notified_merged_pr_numbers": []}
    open_prs = [{"number": 1, "created_at": "2026-06-01T00:00:00Z"}]
    closed_prs = [
        {"number": 2, "merged_at": "2026-06-02T00:00:00Z"},
        {"number": 3, "merged_at": None},
    ]

    opened, merged = collect_new_prs(
        state, open_prs=open_prs, closed_prs=closed_prs, limit=5
    )

    assert [item["number"] for item in opened] == [1]
    assert [item["number"] for item in merged] == [2]
    assert state["notified_pr_numbers"] == [1]
    assert state["notified_merged_pr_numbers"] == [2]


def test_collect_new_prs_limits_each_kind_and_marks_all_seen():
    state = {"notified_pr_numbers": [], "notified_merged_pr_numbers": []}
    open_prs = [
        {"number": i, "created_at": f"2026-06-{i:02d}T00:00:00Z"}
        for i in range(1, 5)
    ]
    closed_prs = [
        {"number": i, "merged_at": f"2026-06-{i:02d}T00:00:00Z"}
        for i in range(5, 9)
    ]

    opened, merged = collect_new_prs(
        state, open_prs=open_prs, closed_prs=closed_prs, limit=2
    )

    assert [item["number"] for item in opened] == [4, 3]
    assert [item["number"] for item in merged] == [8, 7]
    assert set(state["notified_pr_numbers"]) == {1, 2, 3, 4}
    assert set(state["notified_merged_pr_numbers"]) == {5, 6, 7, 8}


def test_collect_new_prs_skips_missing_numbers_and_reports_skipped_counts():
    state = {"notified_pr_numbers": [], "notified_merged_pr_numbers": []}
    open_prs = [
        {"created_at": "2026-06-06T00:00:00Z"},
        {"number": None, "created_at": "2026-06-05T00:00:00Z"},
        {"number": 1, "created_at": "2026-06-01T00:00:00Z"},
        {"number": 2, "created_at": "2026-06-02T00:00:00Z"},
        {"number": 3, "created_at": "2026-06-03T00:00:00Z"},
    ]
    closed_prs = [
        {"merged_at": "2026-06-08T00:00:00Z"},
        {"number": None, "merged_at": "2026-06-07T00:00:00Z"},
        {"number": 4, "merged_at": "2026-06-04T00:00:00Z"},
        {"number": 5, "merged_at": "2026-06-05T00:00:00Z"},
        {"number": 6, "merged_at": "2026-06-06T00:00:00Z"},
    ]

    result = collect_new_prs(state, open_prs=open_prs, closed_prs=closed_prs, limit=2)
    opened, merged = result

    assert [item["number"] for item in opened] == [3, 2]
    assert [item["number"] for item in merged] == [6, 5]
    assert result.skipped_opened_count == 1
    assert result.skipped_merged_count == 1
    assert set(state["notified_pr_numbers"]) == {1, 2, 3}
    assert set(state["notified_merged_pr_numbers"]) == {4, 5, 6}
    assert None not in state["notified_pr_numbers"]
    assert None not in state["notified_merged_pr_numbers"]


async def test_poll_subscription_once_adds_issue_limit_summary():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.issues = [
        {
            "number": number,
            "title": f"Issue {number}",
            "user": {"login": "alice"},
            "created_at": f"2026-06-0{number}T00:00:00Z",
            "html_url": f"https://github.com/Owner/Repo/issues/{number}",
            "body": "body",
        }
        for number in range(1, 5)
    ]

    assert hasattr(poller, "poll_subscription_once")
    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"issue": True}),
        initialized_state(notified_issue_numbers=[]),
    )

    assert [message["template_name"] for message in messages] == ["issue", "issue", "_raw"]
    assert [message["variables"].get("number") for message in messages[:2]] == [4, 3]
    assert messages[2]["variables"]["text"] == (
        "本轮 Owner/Repo 新增 Issue 较多，已展示 2 条，还有 2 条未展示。"
    )
    assert messages[2]["mention_qq"] == ""
    assert client.calls == [("get_issues", "Owner", "Repo")]


async def test_poll_subscription_once_respects_per_event_intervals():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.releases = [
        {
            "id": 10,
            "tag_name": "v1.0.0",
            "published_at": "2026-06-29T00:01:00Z",
        }
    ]
    state = initialized_state(
        notified_release_ids=[],
        last_checked_at={"release": "2026-06-29T00:00:00+00:00"},
        event_enabled={"release": True},
    )

    messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        subscription({"release": True}),
        state,
        now=datetime(2026, 6, 29, 0, 1, tzinfo=timezone.utc),
    )

    assert messages == []
    assert client.calls == []
    assert state["notified_release_ids"] == []


async def test_poll_subscription_once_marks_checked_when_interval_elapsed():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.releases = [
        {
            "id": 10,
            "tag_name": "v1.0.0",
            "published_at": "2026-06-29T00:05:00Z",
        }
    ]
    state = initialized_state(
        notified_release_ids=[],
        last_checked_at={"release": "2026-06-29T00:00:00+00:00"},
        event_enabled={"release": True},
    )
    now = datetime(2026, 6, 29, 0, 5, 1, tzinfo=timezone.utc)

    messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        subscription({"release": True}),
        state,
        now=now,
    )

    assert [message["template_name"] for message in messages] == ["release"]
    assert client.calls == [("get_releases", "Owner", "Repo")]
    assert state["last_checked_at"]["release"] == now.isoformat()


async def test_poll_subscription_once_baselines_reenabled_event_without_backlog():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.issues = [
        {
            "number": 10,
            "title": "Issue while disabled",
            "user": {"login": "alice"},
            "created_at": "2026-06-29T00:03:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/10",
            "body": "body",
        }
    ]
    state = initialized_state(
        notified_issue_numbers=[],
        last_checked_at={"issue": "2026-06-29T00:00:00+00:00"},
        event_enabled={"issue": False},
    )

    messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        subscription({"issue": True}),
        state,
        now=datetime(2026, 6, 29, 0, 10, tzinfo=timezone.utc),
    )

    assert messages == []
    assert client.calls == [("get_issues", "Owner", "Repo")]
    assert state["notified_issue_numbers"] == [10]
    assert state["event_enabled"]["issue"] is True


async def test_initial_baseline_records_current_event_switches():
    from github_subscriber import poller

    client = FakeGitHubClient()
    state = {}

    messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        subscription({"star": False, "release": True, "issue": True, "pr": True}),
        state,
        now=datetime(2026, 6, 29, 0, 0, tzinfo=timezone.utc),
    )

    assert messages == []
    assert state["event_enabled"] == {
        "star": False,
        "release": True,
        "issue": True,
        "pr": True,
    }


async def test_initial_baseline_keeps_post_subscription_issue_for_notification():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.issues = [
        {
            "number": 1,
            "title": "old issue",
            "user": {"login": "alice"},
            "created_at": "2026-06-29T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/1",
            "body": "old",
        },
        {
            "number": 2,
            "title": "new issue",
            "user": {"login": "bob"},
            "created_at": "2026-06-29T00:02:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/2",
            "body": "new",
        },
    ]
    state = {}
    sub = subscription({"issue": True})
    sub["created_at"] = "2026-06-29T00:01:00+00:00"

    baseline_messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        sub,
        state,
        now=datetime(2026, 6, 29, 0, 3, tzinfo=timezone.utc),
    )

    assert baseline_messages == []
    assert state["notified_issue_numbers"] == [1]

    messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        sub,
        state,
        now=datetime(2026, 6, 29, 0, 5, tzinfo=timezone.utc),
    )

    assert [message["template_name"] for message in messages] == ["issue"]
    assert messages[0]["variables"]["number"] == 2
    assert state["notified_issue_numbers"] == [1, 2]


async def test_poll_subscription_once_keeps_successful_events_when_later_api_fails():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.issues = [
        {
            "number": 10,
            "title": "Issue before failure",
            "user": {"login": "alice"},
            "created_at": "2026-06-01T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/10",
            "body": "body",
        }
    ]
    client.pull_errors["open"] = RuntimeError("pulls failed")
    state = {
        "initialized_at": "2026-06-28T00:00:00Z",
        "notified_issue_numbers": [],
        "notified_pr_numbers": [],
        "notified_merged_pr_numbers": [],
    }
    event_errors = []

    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"issue": True, "pr": True}),
        state,
        on_event_error=lambda event_name, exc: event_errors.append(
            (event_name, str(exc))
        ),
    )

    assert [message["template_name"] for message in messages] == ["issue"]
    assert state["notified_issue_numbers"] == [10]
    assert state["notified_pr_numbers"] == []
    assert state["notified_merged_pr_numbers"] == []
    assert event_errors == [("pr", "pulls failed")]
    assert client.calls == [
        ("get_issues", "Owner", "Repo"),
        ("get_pulls", "Owner", "Repo", "open"),
    ]


async def test_poll_subscription_once_keeps_star_message_when_release_fails():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.stargazers = [
        {"user": {"login": "alice"}, "starred_at": "2026-06-01T00:00:00Z"},
        {"user": {"login": "bob"}, "starred_at": "2026-06-02T00:00:00Z"},
    ]
    client.repo_meta = {"stargazers_count": 2}
    client.release_error = RuntimeError("releases failed")
    state = initialized_state(
        known_star_users=["alice"],
        notified_release_ids=[],
        last_checked_at={
            "star": "2026-06-29T00:00:00+00:00",
            "release": "2026-06-29T00:00:00+00:00",
        },
        event_enabled={"star": True, "release": True},
    )
    event_errors = []

    messages = await poller.poll_subscription_once(
        client,
        poller_config(default_intervals={"min_interval_seconds": 60}),
        subscription({"star": True, "release": True}),
        state,
        now=datetime(2026, 6, 29, 0, 10, tzinfo=timezone.utc),
        on_event_error=lambda event_name, exc: event_errors.append(
            (event_name, str(exc))
        ),
    )

    assert [message["template_name"] for message in messages] == ["star"]
    assert messages[0]["variables"]["new_star_count"] == 1
    assert messages[0]["variables"]["star_users"] == "bob"
    assert state["known_star_users"] == ["alice", "bob"]
    assert state["notified_release_ids"] == []
    assert event_errors == [("release", "releases failed")]
    assert client.calls == [
        ("get_stargazers", "Owner", "Repo"),
        ("get_repo", "Owner", "Repo"),
        ("get_releases", "Owner", "Repo"),
    ]


async def test_poll_subscription_once_does_not_mutate_state_when_baseline_api_fails():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.issues = [
        {
            "number": 10,
            "title": "Existing issue before failure",
            "user": {"login": "alice"},
            "created_at": "2026-06-01T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/10",
            "body": "body",
        }
    ]
    client.pull_errors["open"] = RuntimeError("pulls failed")
    state = {
        "initialized_at": "",
        "known_star_users": [],
        "notified_release_ids": [],
        "notified_issue_numbers": [],
        "notified_pr_numbers": [],
        "notified_merged_pr_numbers": [],
    }
    before = {
        "initialized_at": "",
        "known_star_users": [],
        "notified_release_ids": [],
        "notified_issue_numbers": [],
        "notified_pr_numbers": [],
        "notified_merged_pr_numbers": [],
    }

    try:
        await poller.poll_subscription_once(
            client,
            poller_config(),
            subscription({"issue": True, "pr": True}),
            state,
        )
    except RuntimeError as exc:
        assert str(exc) == "pulls failed"
    else:
        raise AssertionError("poll_subscription_once should re-raise API failures")

    assert state == before
    assert client.calls == [
        ("get_stargazers", "Owner", "Repo"),
        ("get_releases", "Owner", "Repo"),
        ("get_issues", "Owner", "Repo"),
        ("get_pulls", "Owner", "Repo", "open"),
    ]


async def test_poll_subscription_once_release_sends_latest_only():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.releases = [
        {
            "id": 1,
            "tag_name": "v1",
            "name": "Version 1",
            "author": {"login": "alice"},
            "published_at": "2026-06-01T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/releases/tag/v1",
            "body": "old notes",
        },
        {
            "id": 2,
            "tag_name": "v2",
            "name": "Version 2",
            "author": {"login": "bob"},
            "published_at": "2026-06-02T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/releases/tag/v2",
            "body": "new notes",
        },
    ]
    state = initialized_state(notified_release_ids=[])

    assert hasattr(poller, "poll_subscription_once")
    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"release": True}),
        state,
    )

    assert len(messages) == 1
    assert messages[0]["template_name"] == "release"
    assert messages[0]["variables"]["tag_name"] == "v2"
    assert messages[0]["variables"]["release_notes"] == "new notes"
    assert state["notified_release_ids"] == [1, 2]
    assert client.calls == [("get_releases", "Owner", "Repo")]


async def test_poll_subscription_once_initializes_baseline_without_messages_then_reports_new_items():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.stargazers = [{"user": {"login": "alice"}}]
    client.repo_meta = {"stargazers_count": 2}
    client.releases = [{"id": 1}]
    client.issues = [
        {
            "number": 2,
            "title": "Existing issue",
            "user": {"login": "alice"},
            "created_at": "2026-06-01T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/2",
            "body": "old issue",
        },
        {"number": 3, "pull_request": {}},
    ]
    client.pulls["open"] = [
        {
            "number": 4,
            "title": "Existing PR",
            "user": {"login": "bob"},
            "created_at": "2026-06-02T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/pull/4",
            "body": "old pr",
        }
    ]
    client.pulls["closed"] = [
        {
            "number": 5,
            "title": "Existing merged PR",
            "user": {"login": "carol"},
            "created_at": "2026-06-03T00:00:00Z",
            "merged_at": "2026-06-04T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/pull/5",
            "body": "old merged pr",
        }
    ]
    state = {"initialized_at": ""}

    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"issue": True, "pr": True}),
        state,
    )

    assert messages == []
    assert state["initialized_at"]
    assert state["known_star_users"] == ["alice"]
    assert state["notified_release_ids"] == [1]
    assert state["notified_issue_numbers"] == [2]
    assert state["notified_pr_numbers"] == [4]
    assert state["notified_merged_pr_numbers"] == [5]
    assert client.calls == [
        ("get_stargazers", "Owner", "Repo"),
        ("get_releases", "Owner", "Repo"),
        ("get_issues", "Owner", "Repo"),
        ("get_pulls", "Owner", "Repo", "open"),
        ("get_pulls", "Owner", "Repo", "closed"),
    ]

    client.calls.clear()
    client.issues.append(
        {
            "number": 6,
            "title": "New issue",
            "user": {"login": "dave"},
            "created_at": "2026-06-29T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/issues/6",
            "body": "new issue",
        }
    )
    client.pulls["open"].append(
        {
            "number": 7,
            "title": "New PR",
            "user": {"login": "erin"},
            "created_at": "2026-06-29T00:00:00Z",
            "html_url": "https://github.com/Owner/Repo/pull/7",
            "body": "new pr",
        }
    )
    client.pulls["closed"].append(
        {
            "number": 8,
            "title": "New merged PR",
            "user": {"login": "frank"},
            "created_at": "2026-06-28T00:00:00Z",
            "merged_at": "2026-06-29T00:00:00Z",
            "merged_by": {"login": "maintainer"},
            "html_url": "https://github.com/Owner/Repo/pull/8",
            "body": "new merged pr",
        }
    )

    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"issue": True, "pr": True}),
        state,
    )

    assert [message["template_name"] for message in messages] == [
        "issue",
        "pr_opened",
        "pr_merged",
    ]
    assert [message["variables"]["number"] for message in messages] == [6, 7, 8]
    assert state["notified_issue_numbers"] == [2, 6]
    assert state["notified_pr_numbers"] == [4, 7]
    assert state["notified_merged_pr_numbers"] == [5, 8]
    assert client.calls == [
        ("get_issues", "Owner", "Repo"),
        ("get_pulls", "Owner", "Repo", "open"),
        ("get_pulls", "Owner", "Repo", "closed"),
    ]


async def test_poll_subscription_once_baselines_disabled_events_before_star_is_enabled():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.stargazers = [{"user": {"login": "alice"}}]
    client.repo_meta = {"stargazers_count": 2}
    client.releases = [{"id": 1}]
    client.issues = [{"number": 2}]
    client.pulls["open"] = [{"number": 3}]
    client.pulls["closed"] = [
        {"number": 4, "merged_at": "2026-06-01T00:00:00Z"}
    ]
    state = {"initialized_at": ""}

    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"star": False, "release": True, "issue": False, "pr": False}),
        state,
    )

    assert messages == []
    assert state["known_star_users"] == ["alice"]
    assert state["notified_release_ids"] == [1]
    assert state["notified_issue_numbers"] == [2]
    assert state["notified_pr_numbers"] == [3]
    assert state["notified_merged_pr_numbers"] == [4]
    assert client.calls == [
        ("get_stargazers", "Owner", "Repo"),
        ("get_releases", "Owner", "Repo"),
        ("get_issues", "Owner", "Repo"),
        ("get_pulls", "Owner", "Repo", "open"),
        ("get_pulls", "Owner", "Repo", "closed"),
    ]

    client.calls.clear()
    client.stargazers = [
        {"user": {"login": "alice"}, "starred_at": "2026-06-01T00:00:00Z"},
        {"user": {"login": "bob"}, "starred_at": "2026-06-29T00:00:00Z"},
    ]

    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"star": True, "release": False, "issue": False, "pr": False}),
        state,
    )

    assert messages == []
    assert state["known_star_users"] == ["alice", "bob"]
    assert client.calls == [("get_stargazers", "Owner", "Repo")]


async def test_poll_subscription_once_pr_merged_mentions_mapped_author():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.pulls["closed"] = [
        {
            "number": 8,
            "title": "Merged PR",
            "user": {"login": "Alice"},
            "created_at": "2026-06-01T00:00:00Z",
            "merged_at": "2026-06-02T00:00:00Z",
            "merged_by": {"login": "maintainer"},
            "html_url": "https://github.com/Owner/Repo/pull/8",
            "body": "body",
        }
    ]

    assert hasattr(poller, "poll_subscription_once")
    messages = await poller.poll_subscription_once(
        client,
        poller_config(github_to_qq={"alice": "10001"}),
        subscription({"pr": True}),
        initialized_state(notified_pr_numbers=[], notified_merged_pr_numbers=[]),
    )

    assert [message["template_name"] for message in messages] == ["pr_merged"]
    assert messages[0]["mention_qq"] == "10001"
    assert messages[0]["variables"]["mention"] == " "
    assert messages[0]["variables"]["author"] == "Alice"
    assert messages[0]["variables"]["merged_by"] == "maintainer"
    assert client.calls == [
        ("get_pulls", "Owner", "Repo", "open"),
        ("get_pulls", "Owner", "Repo", "closed"),
    ]


async def test_poll_subscription_once_pr_merged_mentions_template_list_mapping():
    from github_subscriber import poller

    client = FakeGitHubClient()
    client.pulls["closed"] = [
        {
            "number": 8,
            "title": "Merged PR",
            "user": {"login": "Alice"},
            "created_at": "2026-06-01T00:00:00Z",
            "merged_at": "2026-06-02T00:00:00Z",
            "merged_by": {"login": "maintainer"},
            "html_url": "https://github.com/Owner/Repo/pull/8",
            "body": "body",
        }
    ]

    messages = await poller.poll_subscription_once(
        client,
        poller_config(
            github_to_qq=[
                {
                    "__template_key": "mapping",
                    "github_login": "alice",
                    "qq_uid": "10001",
                }
            ]
        ),
        subscription({"pr": True}),
        initialized_state(notified_pr_numbers=[], notified_merged_pr_numbers=[]),
    )

    assert [message["template_name"] for message in messages] == ["pr_merged"]
    assert messages[0]["mention_qq"] == "10001"


async def test_poll_subscription_once_skips_disabled_event_apis():
    from github_subscriber import poller

    client = FakeGitHubClient()

    assert hasattr(poller, "poll_subscription_once")
    messages = await poller.poll_subscription_once(
        client,
        poller_config(),
        subscription({"star": False, "release": False, "issue": False, "pr": False}),
        {},
    )

    assert messages == []
    assert client.calls == [
        ("get_stargazers", "Owner", "Repo"),
        ("get_releases", "Owner", "Repo"),
        ("get_issues", "Owner", "Repo"),
        ("get_pulls", "Owner", "Repo", "open"),
        ("get_pulls", "Owner", "Repo", "closed"),
    ]
