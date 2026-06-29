import pytest

from github_subscriber.repo_parser import RepoParseError, parse_repo_ref


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("github.com/owner/repo", "owner/repo"),
        ("owner/repo", "owner/repo"),
        ("Owner-Name/repo.name", "Owner-Name/repo.name"),
    ],
)
def test_parse_supported_repo_refs(value: str, expected: str):
    assert parse_repo_ref(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/releases/tag/v1.0.0",
        "https://gitlab.com/owner/repo",
        "https://owner/repo",
        "owner/repo.git",
        "http://github.com/owner/repo",
        "owner",
        "",
    ],
)
def test_reject_invalid_or_subpage_refs(value: str):
    with pytest.raises(RepoParseError):
        parse_repo_ref(value)
