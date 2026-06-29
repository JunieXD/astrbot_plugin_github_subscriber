from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any


def install_astrbot_stubs(monkeypatch, plugin_data_path: Path | None = None):
    plugin_data_path = plugin_data_path or Path("stub-plugin-data")
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    core = types.ModuleType("astrbot.core")
    core_utils = types.ModuleType("astrbot.core.utils")
    astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
    event_module = types.ModuleType("astrbot.api.event")
    star_module = types.ModuleType("astrbot.api.star")

    class AstrBotConfig(dict):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, **kwargs)
            self.save_count = 0

        def save_config(self) -> None:
            self.save_count += 1

    class Logger:
        def __init__(self) -> None:
            self.infos: list[str] = []
            self.debugs: list[str] = []

        def info(self, message: str) -> None:
            self.infos.append(message)

        def debug(self, message: str) -> None:
            self.debugs.append(message)

    class AstrMessageEvent:
        pass

    class CommandGroup:
        def __init__(self, name: str) -> None:
            self.name = name

        def __call__(self, func):
            func.__command_group__ = self.name
            return self

        def command(self, name: str):
            def decorator(func):
                func.__command_name__ = name
                return func

            return decorator

    class Filter:
        class PermissionType:
            ADMIN = "admin"

        def __init__(self) -> None:
            self.groups: list[CommandGroup] = []

        def command_group(self, name: str):
            group = CommandGroup(name)
            self.groups.append(group)
            return group

        def permission_type(self, permission_type: str):
            def decorator(func):
                func.__permission_type__ = permission_type
                return func

            return decorator

        def on_astrbot_loaded(self):
            def decorator(func):
                func.__on_astrbot_loaded__ = True
                return func

            return decorator

    class Context:
        pass

    class Star:
        def __init__(self, context: Context) -> None:
            self.context = context

    def get_astrbot_plugin_data_path() -> str:
        return str(plugin_data_path)

    api.AstrBotConfig = AstrBotConfig
    api.logger = Logger()
    astrbot_path.get_astrbot_plugin_data_path = get_astrbot_plugin_data_path
    event_module.AstrMessageEvent = AstrMessageEvent
    event_module.filter = Filter()
    star_module.Context = Context
    star_module.Star = Star

    monkeypatch.setitem(sys.modules, "astrbot", astrbot)
    monkeypatch.setitem(sys.modules, "astrbot.api", api)
    monkeypatch.setitem(sys.modules, "astrbot.core", core)
    monkeypatch.setitem(sys.modules, "astrbot.core.utils", core_utils)
    monkeypatch.setitem(sys.modules, "astrbot.core.utils.astrbot_path", astrbot_path)
    monkeypatch.setitem(sys.modules, "astrbot.api.event", event_module)
    monkeypatch.setitem(sys.modules, "astrbot.api.star", star_module)

    sys.modules.pop("main", None)
    return importlib.import_module("main")


class FakeEvent:
    def __init__(self, umo: str, group_name: str = "测试群") -> None:
        self.unified_msg_origin = umo
        self.group_name = group_name

    def get_group_name(self) -> str:
        return self.group_name

    def plain_result(self, message: str) -> str:
        return message


async def collect_plain_result(async_iterable) -> list[str]:
    return [item async for item in async_iterable]


def test_imports_with_stubbed_astrbot_modules(monkeypatch):
    module = install_astrbot_stubs(monkeypatch)

    assert module.ghsub.name == "ghsub"
    assert hasattr(module, "GitHubSubscriberPlugin")


def test_plugin_initializes_normalized_config_and_state_store(monkeypatch, tmp_path):
    plugin_data_path = tmp_path / "plugin_data"
    module = install_astrbot_stubs(monkeypatch, plugin_data_path)
    monkeypatch.chdir(tmp_path)
    config = module.AstrBotConfig({"github_token": "token"})

    plugin = module.GitHubSubscriberPlugin(module.Context(), config)

    assert plugin.normalized_config["github_token"] == "token"
    assert plugin.normalized_config["default_intervals"]["release_minutes"] == 5
    assert plugin.state.path == plugin_data_path / "astrbot_plugin_github_subscriber" / "state.json"


async def test_ghsub_add_persists_subscription_and_reports_defaults(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    config = module.AstrBotConfig({})
    plugin = module.GitHubSubscriberPlugin(module.Context(), config)
    event = FakeEvent("aiocqhttp:GroupMessage:100")

    replies = await collect_plain_result(
        plugin.ghsub_add(event, "https://github.com/JunieXD/AutoEmailSender")
    )

    assert config.save_count == 1
    assert plugin.normalized_config["subscriptions"][0]["target_umo"] == event.unified_msg_origin
    assert plugin.normalized_config["subscriptions"][0]["target_name"] == "测试群"
    assert plugin.normalized_config["subscriptions"][0]["repo"] == "JunieXD/AutoEmailSender"
    assert plugin.normalized_config["subscriptions"][0]["events"] == {
        "star": False,
        "release": True,
        "issue": True,
        "pr": True,
    }
    assert config["subscriptions"] == plugin.normalized_config["subscriptions"]
    assert replies == [
        "已订阅 JunieXD/AutoEmailSender\n"
        "已开启：Release、Issue、PR\n"
        "未开启：Star\n"
        "可使用 /ghsub enable JunieXD/AutoEmailSender star 开启 Star 提醒"
    ]


async def test_ghsub_list_only_lists_current_target(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    config = module.AstrBotConfig({})
    plugin = module.GitHubSubscriberPlugin(module.Context(), config)

    await collect_plain_result(plugin.ghsub_add(FakeEvent("umo-a"), "Owner/Repo"))
    await collect_plain_result(plugin.ghsub_add(FakeEvent("umo-b"), "Other/Repo"))

    replies = await collect_plain_result(plugin.ghsub_list(FakeEvent("umo-a")))

    assert replies == ["当前 GitHub 订阅：\n- Owner/Repo：release, issue, pr"]


async def test_ghsub_enable_and_disable_persist_config(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    config = module.AstrBotConfig({})
    plugin = module.GitHubSubscriberPlugin(module.Context(), config)
    event = FakeEvent("umo-a")
    await collect_plain_result(plugin.ghsub_add(event, "Owner/Repo"))

    enabled = await collect_plain_result(plugin.ghsub_enable(event, "Owner/Repo", "star"))
    disabled = await collect_plain_result(plugin.ghsub_disable(event, "Owner/Repo", "issue"))

    sub = plugin.normalized_config["subscriptions"][0]
    assert sub["events"]["star"] is True
    assert sub["events"]["issue"] is False
    assert config.save_count == 3
    assert enabled == ["已开启 Owner/Repo 的 star 提醒"]
    assert disabled == ["已关闭 Owner/Repo 的 issue 提醒"]


async def test_repo_ref_errors_are_reported_by_all_repo_commands(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    config = module.AstrBotConfig({})
    plugin = module.GitHubSubscriberPlugin(module.Context(), config)
    event = FakeEvent("umo-a")
    expected = "请提供仓库主页链接，例如：https://github.com/owner/repo"

    commands = [
        plugin.ghsub_status(event, "not-a-repo"),
        plugin.ghsub_remove(event, "not-a-repo"),
        plugin.ghsub_enable(event, "not-a-repo", "star"),
        plugin.ghsub_disable(event, "not-a-repo", "star"),
    ]

    for command in commands:
        assert await collect_plain_result(command) == [expected]

    assert config.save_count == 0


async def test_unknown_event_errors_are_reported_without_persisting(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    config = module.AstrBotConfig({})
    plugin = module.GitHubSubscriberPlugin(module.Context(), config)
    event = FakeEvent("umo-a")
    await collect_plain_result(plugin.ghsub_add(event, "Owner/Repo"))
    config.save_count = 0

    enabled = await collect_plain_result(plugin.ghsub_enable(event, "Owner/Repo", "fork"))
    disabled = await collect_plain_result(plugin.ghsub_disable(event, "Owner/Repo", "fork"))

    expected = "未知事件类型：fork。支持：star、release、issue、pr、all"
    assert enabled == [expected]
    assert disabled == [expected]
    assert config.save_count == 0
