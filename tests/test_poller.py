from github_subscriber.poller import (
    collect_new_issues,
    collect_new_prs,
    collect_new_releases,
    collect_new_stars,
)


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
