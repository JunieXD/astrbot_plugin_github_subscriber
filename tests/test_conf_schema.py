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
