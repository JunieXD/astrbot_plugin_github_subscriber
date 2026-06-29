from typing import Any

import aiohttp


API_BASE_URL = "https://api.github.com"
DEFAULT_ACCEPT = "application/vnd.github+json"
STAR_ACCEPT = "application/vnd.github.star+json"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "astrbot-plugin-github-subscriber"
REQUEST_TIMEOUT_SECONDS = 20


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"GitHub API error {status}: {message}")


class GitHubClient:
    def __init__(
        self,
        token: str = "",
        session: aiohttp.ClientSession | None = None,
    ):
        self.token = token.strip()
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self):
        self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def get_stargazers(self, owner: str, repo: str) -> list[Any]:
        return await self._get_paginated(
            f"{API_BASE_URL}/repos/{owner}/{repo}/stargazers",
            accept=STAR_ACCEPT,
        )

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._get_json(f"{API_BASE_URL}/repos/{owner}/{repo}")

    async def get_releases(self, owner: str, repo: str) -> list[Any]:
        return await self._get_paginated(
            f"{API_BASE_URL}/repos/{owner}/{repo}/releases"
        )

    async def get_issues(self, owner: str, repo: str) -> list[Any]:
        return await self._get_paginated(
            f"{API_BASE_URL}/repos/{owner}/{repo}/issues",
            params={
                "state": "open",
                "sort": "created",
                "direction": "desc",
            },
        )

    async def get_pulls(self, owner: str, repo: str, state: str) -> list[Any]:
        sort = "updated" if state == "closed" else "created"
        return await self._get_paginated(
            f"{API_BASE_URL}/repos/{owner}/{repo}/pulls",
            params={
                "state": state,
                "sort": sort,
                "direction": "desc",
            },
        )

    async def _get_paginated(
        self,
        url: str,
        *,
        accept: str = DEFAULT_ACCEPT,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 3,
    ) -> list[Any]:
        merged_params = {**(params or {}), "per_page": per_page}
        next_url: str | None = url
        items: list[Any] = []

        for page_index in range(max_pages):
            page_params = merged_params if page_index == 0 else None
            payload, links = await self._request_json(
                next_url,
                accept=accept,
                params=page_params,
            )
            if not isinstance(payload, list):
                raise GitHubApiError(500, "Expected list response")

            items.extend(payload)
            next_url = self._next_link_url(links)
            if not next_url:
                break

        return items

    async def _get_json(
        self,
        url: str,
        *,
        accept: str = DEFAULT_ACCEPT,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload, _links = await self._request_json(
            url,
            accept=accept,
            params=params,
        )
        if not isinstance(payload, dict):
            raise GitHubApiError(500, "Expected object response")
        return payload

    async def _request_json(
        self,
        url: str | None,
        *,
        accept: str = DEFAULT_ACCEPT,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, Any]:
        if url is None:
            raise GitHubApiError(500, "Missing request URL")

        session = self._ensure_session()
        try:
            async with session.get(
                url,
                headers=self._headers(accept),
                params=params,
            ) as response:
                if response.status >= 400:
                    message = await response.text()
                    raise GitHubApiError(response.status, message[:500])
                return await response.json(), response.links
        except GitHubApiError:
            raise
        except Exception as exc:
            raise GitHubApiError(0, str(exc) or exc.__class__.__name__) from exc

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            )
            self._owns_session = True
        return self._session

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _next_link_url(self, links: Any) -> str | None:
        next_link = links.get("next") if hasattr(links, "get") else None
        if next_link is None:
            return None

        if hasattr(next_link, "get"):
            url = next_link.get("url")
        else:
            url = getattr(next_link, "url", None)

        return str(url) if url else None
