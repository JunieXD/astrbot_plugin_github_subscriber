import json
from pathlib import Path


SUPPORTED_SCHEMA_TYPES = {
    "int",
    "float",
    "bool",
    "string",
    "text",
    "list",
    "file",
    "object",
    "template_list",
}


def iter_schema_nodes(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from iter_schema_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_schema_nodes(item)


def test_conf_schema_uses_only_astrbot_supported_types():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))
    types = {
        node["type"]
        for node in iter_schema_nodes(schema)
        if isinstance(node, dict) and "type" in node
    }

    assert types <= SUPPORTED_SCHEMA_TYPES


def test_github_to_qq_schema_is_template_list():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))

    assert schema["github_to_qq"]["type"] == "template_list"
    mapping_template = schema["github_to_qq"]["templates"]["mapping"]
    assert mapping_template["items"]["github_login"]["type"] == "string"
    assert mapping_template["items"]["qq_uid"]["type"] == "string"


def test_subscription_schema_splits_pr_switches_and_supports_admin_mention():
    schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))
    items = schema["subscriptions"]["templates"]["subscription"]["items"]

    assert items["admin_qq_uid"]["type"] == "string"
    assert "{admin_mention}" in items["admin_qq_uid"]["hint"]
    event_items = items["events"]["items"]
    assert "pr" not in event_items
    assert event_items["pr_opened"]["default"] is True
    assert event_items["pr_merged"]["default"] is True
