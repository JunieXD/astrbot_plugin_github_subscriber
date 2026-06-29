from github_subscriber.poller import (
    collect_new_issues,
    collect_new_prs,
    collect_new_releases,
    collect_new_stars,
)


class FakeGitHubClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.stargazers: list[dict] = []
        self.repo_meta: dict = {"stargazers_count": 0}
        self.releases: list[dict] = []
        self.issues: list[dict] = []
        self.pulls: dict[str, list[dict]] = {"open": [], "closed": []}

    async def get_stargazers(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("get_stargazers", owner, repo))
        return self.stargazers

    async def get_repo(self, owner: str, repo: str) -> dict:
        self.calls.append(("get_repo", owner, repo))
        return self.repo_meta

    async def get_releases(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("get_releases", owner, repo))
        return self.releases

    async def get_issues(self, owner: str, repo: str) -> list[dict]:
        self.calls.append(("get_issues", owner, repo))
        return self.issues

    async def get_pulls(self, owner: str, repo: str, state: str) -> list[dict]:
        self.calls.append(("get_pulls", owner, repo, state))
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
    }


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
        {"notified_issue_numbers": []},
    )

    assert [message["template_name"] for message in messages] == ["issue", "issue", "_raw"]
    assert [message["variables"].get("number") for message in messages[:2]] == [4, 3]
    assert messages[2]["variables"]["text"] == (
        "本轮 Owner/Repo 新增 Issue 较多，已展示 2 条，还有 2 条未展示。"
    )
    assert messages[2]["mention_qq"] == ""
    assert client.calls == [("get_issues", "Owner", "Repo")]


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
    state = {"notified_release_ids": []}

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
        {"notified_pr_numbers": [], "notified_merged_pr_numbers": []},
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
    assert client.calls == []
