from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_SUBSCRIPTION_STATE = {
    "initialized_at": "",
    "known_star_users": [],
    "known_star_count": 0,
    "notified_release_ids": [],
    "notified_issue_numbers": [],
    "notified_pr_numbers": [],
    "notified_merged_pr_numbers": [],
    "event_enabled": {"star": False, "release": False, "issue": False, "pr": False},
    "last_checked_at": {"star": "", "release": "", "issue": "", "pr": ""},
    "etag": {"star": "", "release": "", "issue": "", "pr": ""},
}


def subscription_state_key(target_umo: str, repo: str) -> str:
    normalized = f"{target_umo}:{repo.lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class JsonStateStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def get_subscription_state(self, target_umo: str, repo: str) -> dict[str, Any]:
        key = subscription_state_key(target_umo, repo)
        subscriptions = self.data.setdefault("subscriptions", {})
        if key not in subscriptions:
            subscriptions[key] = deepcopy(DEFAULT_SUBSCRIPTION_STATE)
            subscriptions[key]["target_umo"] = target_umo
            subscriptions[key]["repo"] = repo
        return subscriptions[key]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"subscriptions": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))
