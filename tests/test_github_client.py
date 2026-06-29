import pytest

from github_subscriber.github_client import GitHubApiError, GitHubClient


class FakeResponse:
    def __init__(self, payload, *, status=200, links=None, text=""):
        self._payload = payload
        self.status = status
        self.links = links or {}
        self._text = text

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class FakeRequestContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeRequestContext(self.responses.pop(0))

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_get_stargazers_uses_star_accept_token_and_merges_pages():
    session = FakeSession(
        [
            FakeResponse(
                [{"user": {"login": "alice"}}],
                links={"next": {"url": "https://api.github.com/page-2"}},
            ),
            FakeResponse([{"user": {"login": "bob"}}]),
        ]
    )

    async with GitHubClient(token="secret", session=session) as client:
        stargazers = await client.get_stargazers("Owner", "Repo")

    assert stargazers == [
        {"user": {"login": "alice"}},
        {"user": {"login": "bob"}},
    ]
    assert session.closed is False
    assert [call["url"] for call in session.calls] == [
        "https://api.github.com/repos/Owner/Repo/stargazers",
        "https://api.github.com/page-2",
    ]
    assert session.calls[0]["params"] == {"per_page": 100}
    assert session.calls[0]["headers"]["Accept"] == "application/vnd.github.star+json"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret"
    assert (
        session.calls[0]["headers"]["X-GitHub-Api-Version"]
        == "2022-11-28"
    )
    assert (
        session.calls[0]["headers"]["User-Agent"]
        == "astrbot-plugin-github-subscriber"
    )


@pytest.mark.asyncio
async def test_get_issues_and_pulls_send_expected_params_without_token():
    session = FakeSession([FakeResponse([]), FakeResponse([])])
    client = GitHubClient(session=session)

    assert await client.get_issues("Owner", "Repo") == []
    assert await client.get_pulls("Owner", "Repo", "closed") == []

    assert session.calls[0]["url"] == "https://api.github.com/repos/Owner/Repo/issues"
    assert session.calls[0]["params"] == {
        "state": "open",
        "sort": "created",
        "direction": "desc",
        "per_page": 100,
    }
    assert "Authorization" not in session.calls[0]["headers"]
    assert session.calls[1]["url"] == "https://api.github.com/repos/Owner/Repo/pulls"
    assert session.calls[1]["params"] == {
        "state": "closed",
        "sort": "created",
        "direction": "desc",
        "per_page": 100,
    }


@pytest.mark.asyncio
async def test_token_is_stripped_before_authorization_header():
    session = FakeSession([FakeResponse({"full_name": "Owner/Repo"})])
    client = GitHubClient(token=" secret ", session=session)

    assert await client.get_repo("Owner", "Repo") == {"full_name": "Owner/Repo"}

    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret"


@pytest.mark.asyncio
async def test_blank_token_does_not_send_authorization_header():
    session = FakeSession([FakeResponse({"full_name": "Owner/Repo"})])
    client = GitHubClient(token="   ", session=session)

    assert await client.get_repo("Owner", "Repo") == {"full_name": "Owner/Repo"}

    assert "Authorization" not in session.calls[0]["headers"]


@pytest.mark.asyncio
async def test_get_repo_returns_dict_and_rejects_non_dict_payload():
    ok_session = FakeSession([FakeResponse({"full_name": "Owner/Repo"})])
    ok_client = GitHubClient(session=ok_session)

    assert await ok_client.get_repo("Owner", "Repo") == {"full_name": "Owner/Repo"}

    bad_session = FakeSession([FakeResponse([{"full_name": "Owner/Repo"}])])
    bad_client = GitHubClient(session=bad_session)

    with pytest.raises(GitHubApiError) as exc_info:
        await bad_client.get_repo("Owner", "Repo")

    assert exc_info.value.status == 500
    assert exc_info.value.message == "Expected object response"
    assert str(exc_info.value) == "GitHub API error 500: Expected object response"


@pytest.mark.asyncio
async def test_http_error_raises_github_api_error_with_status_and_message():
    text = "x" * 600
    session = FakeSession([FakeResponse({}, status=403, text=text)])
    client = GitHubClient(session=session)

    with pytest.raises(GitHubApiError) as exc_info:
        await client.get_repo("Owner", "Repo")

    assert exc_info.value.status == 403
    assert exc_info.value.message == "x" * 500
    assert str(exc_info.value) == f"GitHub API error 403: {'x' * 500}"


@pytest.mark.asyncio
async def test_paginated_endpoint_rejects_non_list_payload():
    session = FakeSession([FakeResponse({"not": "a list"})])
    client = GitHubClient(session=session)

    with pytest.raises(GitHubApiError) as exc_info:
        await client.get_releases("Owner", "Repo")

    assert exc_info.value.status == 500
    assert exc_info.value.message == "Expected list response"
