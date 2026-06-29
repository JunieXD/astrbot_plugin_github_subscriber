from pathlib import Path

from github_subscriber.state import JsonStateStore, subscription_state_key


def test_subscription_state_key_is_stable_and_target_scoped():
    a = subscription_state_key("umo-a", "Owner/Repo")
    b = subscription_state_key("umo-a", "owner/repo")
    c = subscription_state_key("umo-b", "Owner/Repo")

    assert a == b
    assert a != c


def test_state_store_creates_and_persists_subscription_state(tmp_path: Path):
    store = JsonStateStore(tmp_path / "state.json")
    state = store.get_subscription_state("umo-a", "Owner/Repo")
    state["known_star_users"].append("alice")
    state["notified_issue_numbers"].append(1)
    store.save()

    reloaded = JsonStateStore(tmp_path / "state.json")
    loaded = reloaded.get_subscription_state("umo-a", "Owner/Repo")

    assert loaded["known_star_users"] == ["alice"]
    assert loaded["notified_issue_numbers"] == [1]
