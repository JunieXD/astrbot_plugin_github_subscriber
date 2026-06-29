from __future__ import annotations

from dataclasses import dataclass


EVENT_KEYS = ("star", "release", "issue", "pr")


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @classmethod
    def from_full_name(cls, full_name: str) -> "RepoRef":
        owner, name = full_name.split("/", 1)
        return cls(owner=owner, name=name)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full_name}"
