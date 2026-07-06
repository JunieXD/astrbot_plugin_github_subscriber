from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


def install_astrbot_stub_modules(monkeypatch, plugin_data_path: Path | None = None):
    plugin_data_path = plugin_data_path or Path("stub-plugin-data")
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    core = types.ModuleType("astrbot.core")
    core_utils = types.ModuleType("astrbot.core.utils")
    astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
    event_module = types.ModuleType("astrbot.api.event")
    components_module = types.ModuleType("astrbot.api.message_components")
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
            self.warnings: list[tuple[Any, ...]] = []

        def info(self, message: str) -> None:
            self.infos.append(message)

        def debug(self, message: str) -> None:
            self.debugs.append(message)

        def warning(self, *args: Any) -> None:
            self.warnings.append(args)

    class AstrMessageEvent:
        pass

    class MessageChain:
        def __init__(self, chain: list[Any] | None = None) -> None:
            self.chain = list(chain or [])

        def message(self, text: str):
            self.chain.append(text)
            return self

    class At:
        def __init__(self, qq: str) -> None:
            self.qq = qq

    class Plain:
        def __init__(self, text: str) -> None:
            self.text = text

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

        def on_plugin_loaded(self):
            def decorator(func):
                func.__on_plugin_loaded__ = True
                return func

            return decorator

    class Context:
        def __init__(self) -> None:
            self.sent_messages: list[tuple[str, Any]] = []
            self.fail_send = False

        async def send_message(self, target_umo: str, chain: Any) -> None:
            if self.fail_send:
                raise RuntimeError("send failed")
            self.sent_messages.append((target_umo, chain))

    class Star:
        def __init__(self, context: Context) -> None:
            self.context = context

    def get_astrbot_plugin_data_path() -> str:
        return str(plugin_data_path)

    api.AstrBotConfig = AstrBotConfig
    api.logger = Logger()
    astrbot_path.get_astrbot_plugin_data_path = get_astrbot_plugin_data_path
    event_module.AstrMessageEvent = AstrMessageEvent
    event_module.MessageChain = MessageChain
    event_module.filter = Filter()
    components_module.At = At
    components_module.Plain = Plain
    star_module.Context = Context
    star_module.Star = Star

    monkeypatch.setitem(sys.modules, "astrbot", astrbot)
    monkeypatch.setitem(sys.modules, "astrbot.api", api)
    monkeypatch.setitem(sys.modules, "astrbot.core", core)
    monkeypatch.setitem(sys.modules, "astrbot.core.utils", core_utils)
    monkeypatch.setitem(sys.modules, "astrbot.core.utils.astrbot_path", astrbot_path)
    monkeypatch.setitem(sys.modules, "astrbot.api.event", event_module)
    monkeypatch.setitem(sys.modules, "astrbot.api.message_components", components_module)
    monkeypatch.setitem(sys.modules, "astrbot.api.star", star_module)

    sys.modules.pop("main", None)
    return api, star_module


def install_astrbot_stubs(monkeypatch, plugin_data_path: Path | None = None):
    install_astrbot_stub_modules(monkeypatch, plugin_data_path)
    return importlib.import_module("main")


def install_astrbot_stubs_only(monkeypatch, plugin_data_path: Path | None = None):
    module = install_astrbot_stub_modules(monkeypatch, plugin_data_path)
    sys.modules.pop("main", None)
    return module


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


def test_imports_when_loaded_as_plugin_package(monkeypatch):
    install_astrbot_stubs_only(monkeypatch)
    module_name = "astrbot_plugin_github_subscriber.main"
    plugin_dir = Path(__file__).resolve().parents[1]
    sanitized_path = [
        entry
        for entry in sys.path
        if entry and Path(entry).resolve() != plugin_dir
    ]
    monkeypatch.setattr(sys, "path", sanitized_path)
    for name in list(sys.modules):
        if name == "github_subscriber" or name.startswith("github_subscriber."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location(module_name, plugin_dir / "main.py")
    module = importlib.util.module_from_spec(spec)
    package = types.ModuleType("astrbot_plugin_github_subscriber")
    package.__path__ = [str(plugin_dir)]
    monkeypatch.setitem(sys.modules, "astrbot_plugin_github_subscriber", package)
    monkeypatch.setitem(sys.modules, module_name, module)

    spec.loader.exec_module(module)

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


def test_plugin_migrates_legacy_github_to_qq_dict_for_webui(monkeypatch, tmp_path):
    plugin_data_path = tmp_path / "plugin_data"
    module = install_astrbot_stubs(monkeypatch, plugin_data_path)
    monkeypatch.chdir(tmp_path)
    config = module.AstrBotConfig({"github_to_qq": {"alice": "10001"}})

    plugin = module.GitHubSubscriberPlugin(module.Context(), config)

    expected = [
        {
            "__template_key": "mapping",
            "github_login": "alice",
            "qq_uid": "10001",
        }
    ]
    assert plugin.normalized_config["github_to_qq"] == expected
    assert config["github_to_qq"] == expected
    assert config.save_count == 1


async def test_ghsub_add_persists_subscription_and_reports_defaults(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    github_to_qq = [
        {
            "__template_key": "mapping",
            "github_login": "alice",
            "qq_uid": "10001",
        }
    ]
    config = module.AstrBotConfig({"github_to_qq": github_to_qq})
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
    assert config["github_to_qq"] == github_to_qq
    assert replies == [
        "已订阅 JunieXD/AutoEmailSender\n"
        "已开启：Release、Issue、PR\n"
        "未开启：Star\n"
        "可使用 /ghsub enable JunieXD/AutoEmailSender star 开启 Star 提醒"
    ]


async def test_ghsub_add_starts_poller_when_plugin_is_hot_loaded(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    plugin = module.GitHubSubscriberPlugin(module.Context(), module.AstrBotConfig({}))
    created_coroutines: list[Any] = []

    class FakeTask:
        def __init__(self, coroutine: Any) -> None:
            self.coroutine = coroutine
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True
            self.coroutine.close()

        def done(self) -> bool:
            return False

    def fake_create_task(coroutine: Any) -> FakeTask:
        created_coroutines.append(coroutine)
        return FakeTask(coroutine)

    monkeypatch.setattr(module.asyncio, "create_task", fake_create_task)

    await collect_plain_result(plugin.ghsub_add(FakeEvent("umo-a"), "Owner/Repo"))

    assert len(created_coroutines) == 1
    assert plugin._poller_task is not None
    plugin._poller_task.cancel()


async def test_on_plugin_loaded_starts_poller_for_existing_subscriptions(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch)
    monkeypatch.chdir(tmp_path)
    config = module.AstrBotConfig(
        {
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Repo",
                    "enabled": True,
                    "events": {"star": True},
                }
            ],
        }
    )
    plugin = module.GitHubSubscriberPlugin(module.Context(), config)
    created_coroutines: list[Any] = []

    class FakeTask:
        def __init__(self, coroutine: Any) -> None:
            self.coroutine = coroutine
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True
            self.coroutine.close()

        def done(self) -> bool:
            return False

    def fake_create_task(coroutine: Any) -> FakeTask:
        created_coroutines.append(coroutine)
        return FakeTask(coroutine)

    monkeypatch.setattr(module.asyncio, "create_task", fake_create_task)

    await plugin.on_plugin_loaded(object())

    assert len(created_coroutines) == 1
    assert plugin._poller_task is not None
    plugin._poller_task.cancel()


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


async def test_poll_loop_sends_rendered_subscription_messages(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    context = module.Context()
    config = module.AstrBotConfig(
        {
            "message_limits": {"message_send_delay_seconds": 0},
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Repo",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {"issue": "Issue {number}: {title}"},
                }
            ],
        }
    )
    plugin = module.GitHubSubscriberPlugin(context, config)
    save_count = 0

    async def fake_poll_subscription_once(client, normalized_config, sub, state, **_kwargs):
        assert sub["repo"] == "Owner/Repo"
        state["touched"] = True
        return [
            {
                "target_umo": "umo-a",
                "template_name": "issue",
                "variables": {"number": 7, "title": "Hello"},
                "mention_qq": "10001",
            }
        ]

    async def one_tick_sleep(_seconds: float):
        raise asyncio.CancelledError

    def fake_save() -> None:
        nonlocal save_count
        save_count += 1

    monkeypatch.setattr(module, "poll_subscription_once", fake_poll_subscription_once)
    monkeypatch.setattr(module.asyncio, "sleep", one_tick_sleep)
    monkeypatch.setattr(plugin.state, "save", fake_save)

    try:
        await plugin._poll_loop()
    except asyncio.CancelledError:
        pass

    assert save_count == 1
    assert len(context.sent_messages) == 1
    target_umo, chain = context.sent_messages[0]
    assert target_umo == "umo-a"
    assert chain.chain[0].qq == "10001"
    assert chain.chain[1].text == "Issue 7: Hello"
    sub_state = plugin.state.get_subscription_state("umo-a", "Owner/Repo")
    assert sub_state["touched"] is True


async def test_poll_loop_polls_once_before_first_sleep(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    context = module.Context()
    config = module.AstrBotConfig(
        {
            "message_limits": {"message_send_delay_seconds": 0},
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Repo",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {"issue": "{title}"},
                }
            ],
        }
    )
    plugin = module.GitHubSubscriberPlugin(context, config)
    sleep_calls: list[float] = []

    async def fake_poll_subscription_once(client, normalized_config, sub, state, **_kwargs):
        state["touched_before_sleep"] = True
        raise asyncio.CancelledError

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)
        raise AssertionError("poll loop should poll once before sleeping")

    monkeypatch.setattr(module, "poll_subscription_once", fake_poll_subscription_once)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    try:
        await plugin._poll_loop()
    except asyncio.CancelledError:
        pass

    sub_state = plugin.state.get_subscription_state("umo-a", "Owner/Repo")
    assert sub_state["touched_before_sleep"] is True
    assert sleep_calls == []


async def test_poll_loop_warns_and_continues_after_github_api_error(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    context = module.Context()
    config = module.AstrBotConfig(
        {
            "message_limits": {"message_send_delay_seconds": 0},
            "global_templates": {"issue": "{title}"},
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Fail",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {},
                },
                {
                    "target_umo": "umo-b",
                    "repo": "Owner/Ok",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {},
                },
            ],
        }
    )
    plugin = module.GitHubSubscriberPlugin(context, config)

    async def fake_poll_subscription_once(client, normalized_config, sub, state, **_kwargs):
        if sub["repo"] == "Owner/Fail":
            state["notified_issue_numbers"] = [99]
            raise module.GitHubApiError(500, "boom")
        return [
            {
                "target_umo": sub["target_umo"],
                "template_name": "_raw",
                "variables": {"text": f"{sub['repo']} ok"},
                "mention_qq": "",
            }
        ]

    async def one_tick_sleep(_seconds: float):
        if not hasattr(one_tick_sleep, "called"):
            one_tick_sleep.called = True
            return
        raise asyncio.CancelledError

    monkeypatch.setattr(module, "poll_subscription_once", fake_poll_subscription_once)
    monkeypatch.setattr(module.asyncio, "sleep", one_tick_sleep)

    try:
        await plugin._poll_loop()
    except asyncio.CancelledError:
        pass

    assert context.sent_messages[0][0] == "umo-b"
    assert context.sent_messages[0][1].chain == ["Owner/Ok ok"]
    assert module.logger.warnings
    assert "Owner/Fail" in module.logger.warnings[0][1]
    failed_state = plugin.state.get_subscription_state("umo-a", "Owner/Fail")
    assert failed_state["notified_issue_numbers"] == []


async def test_poll_loop_rolls_back_state_when_send_fails(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    context = module.Context()
    context.fail_send = True
    config = module.AstrBotConfig(
        {
            "message_limits": {"message_send_delay_seconds": 0},
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Repo",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {},
                }
            ],
        }
    )
    plugin = module.GitHubSubscriberPlugin(context, config)
    save_count = 0

    async def fake_poll_subscription_once(client, normalized_config, sub, state, **_kwargs):
        state["notified_issue_numbers"] = [99]
        return [
            {
                "target_umo": sub["target_umo"],
                "template_name": "_raw",
                "variables": {"text": "should send"},
                "mention_qq": "",
            }
        ]

    async def one_tick_sleep(_seconds: float):
        if not hasattr(one_tick_sleep, "called"):
            one_tick_sleep.called = True
            return
        raise asyncio.CancelledError

    def fake_save() -> None:
        nonlocal save_count
        save_count += 1

    monkeypatch.setattr(module, "poll_subscription_once", fake_poll_subscription_once)
    monkeypatch.setattr(module.asyncio, "sleep", one_tick_sleep)
    monkeypatch.setattr(plugin.state, "save", fake_save)

    try:
        await plugin._poll_loop()
    except asyncio.CancelledError:
        pass

    assert save_count == 0
    assert module.logger.warnings
    assert "send failed" in str(module.logger.warnings[0])
    sub_state = plugin.state.get_subscription_state("umo-a", "Owner/Repo")
    assert sub_state["notified_issue_numbers"] == []


async def test_poll_loop_treats_unexpected_poll_errors_as_recoverable(monkeypatch, tmp_path):
    module = install_astrbot_stubs(monkeypatch, tmp_path / "plugin_data")
    context = module.Context()
    config = module.AstrBotConfig(
        {
            "message_limits": {"message_send_delay_seconds": 0},
            "global_templates": {"issue": "{title}"},
            "subscriptions": [
                {
                    "target_umo": "umo-a",
                    "repo": "Owner/Fail",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {},
                },
                {
                    "target_umo": "umo-b",
                    "repo": "Owner/Ok",
                    "enabled": True,
                    "events": {"issue": True},
                    "template_overrides": {},
                },
            ],
        }
    )
    plugin = module.GitHubSubscriberPlugin(context, config)

    async def fake_poll_subscription_once(client, normalized_config, sub, state, **_kwargs):
        if sub["repo"] == "Owner/Fail":
            state["notified_issue_numbers"] = [99]
            raise RuntimeError("network reset")
        return [
            {
                "target_umo": sub["target_umo"],
                "template_name": "_raw",
                "variables": {"text": f"{sub['repo']} ok"},
                "mention_qq": "",
            }
        ]

    async def one_tick_sleep(_seconds: float):
        if not hasattr(one_tick_sleep, "called"):
            one_tick_sleep.called = True
            return
        raise asyncio.CancelledError

    monkeypatch.setattr(module, "poll_subscription_once", fake_poll_subscription_once)
    monkeypatch.setattr(module.asyncio, "sleep", one_tick_sleep)

    try:
        await plugin._poll_loop()
    except asyncio.CancelledError:
        pass

    assert context.sent_messages[0][0] == "umo-b"
    assert context.sent_messages[0][1].chain == ["Owner/Ok ok"]
    assert module.logger.warnings
    assert "Owner/Fail" in module.logger.warnings[0][1]
    failed_state = plugin.state.get_subscription_state("umo-a", "Owner/Fail")
    assert failed_state["notified_issue_numbers"] == []
