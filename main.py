from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star
try:
    from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path
except ImportError:  # pragma: no cover - used only outside AstrBot.
    def get_astrbot_plugin_data_path() -> str:
        return str(Path("data") / "plugin_data")

try:
    from .github_subscriber.config import (
        add_subscription,
        disable_event,
        enable_event,
        find_subscription,
        get_subscriptions_for_target,
        normalize_config,
        remove_subscription,
    )
    from .github_subscriber.github_client import GitHubClient
    from .github_subscriber.messages import render_text_message
    from .github_subscriber.models import EVENT_KEYS
    from .github_subscriber.poller import poll_subscription_once
    from .github_subscriber.repo_parser import RepoParseError, parse_repo_ref
    from .github_subscriber.state import JsonStateStore
except ImportError:  # pragma: no cover - supports direct local imports in tests/dev.
    from github_subscriber.config import (
        add_subscription,
        disable_event,
        enable_event,
        find_subscription,
        get_subscriptions_for_target,
        normalize_config,
        remove_subscription,
    )
    from github_subscriber.github_client import GitHubClient
    from github_subscriber.messages import render_text_message
    from github_subscriber.models import EVENT_KEYS
    from github_subscriber.poller import poll_subscription_once
    from github_subscriber.repo_parser import RepoParseError, parse_repo_ref
    from github_subscriber.state import JsonStateStore

SUPPORTED_EVENT_NAMES = (*EVENT_KEYS, "all")


@filter.command_group("ghsub")
def ghsub():
    pass


class GitHubSubscriberPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.normalized_config: dict[str, Any] = normalize_config(dict(config))
        self._poller_task: asyncio.Task | None = None
        self.state = JsonStateStore(self._state_path())

    async def terminate(self):
        if self._poller_task is not None:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                pass
        self.state.save()

    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        if self._poller_task is None:
            self._poller_task = asyncio.create_task(self._poll_loop())
            logger.info("GitHub subscriber poller started.")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("help")
    async def ghsub_help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "GitHub 订阅命令：\n"
            "/ghsub add https://github.com/JunieXD/AutoEmailSender\n"
            "/ghsub list\n"
            "/ghsub status JunieXD/AutoEmailSender\n"
            "/ghsub enable JunieXD/AutoEmailSender star\n"
            "/ghsub disable JunieXD/AutoEmailSender issue\n"
            "/ghsub remove JunieXD/AutoEmailSender\n\n"
            "默认开启：Release、Issue、PR\n"
            "默认关闭：Star\n"
            "所有命令仅管理员可用。"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("add")
    async def ghsub_add(self, event: AstrMessageEvent, repo_ref: str):
        try:
            repo = parse_repo_ref(repo_ref)
        except RepoParseError as exc:
            yield event.plain_result(str(exc))
            return

        sub = add_subscription(
            self.normalized_config,
            target_umo=event.unified_msg_origin,
            target_name=event.get_group_name() if hasattr(event, "get_group_name") else "",
            repo=repo,
        )
        self._persist_config()
        yield event.plain_result(
            f"已订阅 {sub['repo']}\n"
            "已开启：Release、Issue、PR\n"
            "未开启：Star\n"
            f"可使用 /ghsub enable {sub['repo']} star 开启 Star 提醒"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("list")
    async def ghsub_list(self, event: AstrMessageEvent):
        subs = get_subscriptions_for_target(self.normalized_config, event.unified_msg_origin)
        if not subs:
            yield event.plain_result("当前会话还没有 GitHub 订阅。")
            return
        lines = ["当前 GitHub 订阅："]
        for sub in subs:
            enabled = [name for name, ok in sub.get("events", {}).items() if ok]
            lines.append(f"- {sub['repo']}：{', '.join(enabled) or '未开启事件'}")
        yield event.plain_result("\n".join(lines))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("status")
    async def ghsub_status(self, event: AstrMessageEvent, repo_ref: str):
        repo, error = self._parse_repo_ref(repo_ref)
        if error is not None:
            yield event.plain_result(error)
            return
        sub = find_subscription(self.normalized_config, event.unified_msg_origin, repo)
        if sub is None:
            yield event.plain_result(f"当前会话未订阅 {repo}")
            return
        enabled = [name for name, ok in sub.get("events", {}).items() if ok]
        yield event.plain_result(f"{repo}\n开启事件：{', '.join(enabled) or '无'}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("remove")
    async def ghsub_remove(self, event: AstrMessageEvent, repo_ref: str):
        repo, error = self._parse_repo_ref(repo_ref)
        if error is not None:
            yield event.plain_result(error)
            return
        if remove_subscription(self.normalized_config, event.unified_msg_origin, repo):
            self._persist_config()
            yield event.plain_result(f"已移除订阅 {repo}")
        else:
            yield event.plain_result(f"当前会话未订阅 {repo}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("enable")
    async def ghsub_enable(self, event: AstrMessageEvent, repo_ref: str, event_name: str):
        repo, error = self._parse_repo_ref(repo_ref)
        if error is not None:
            yield event.plain_result(error)
            return
        try:
            changed = enable_event(self.normalized_config, event.unified_msg_origin, repo, event_name)
        except ValueError:
            yield event.plain_result(self._unknown_event_message(event_name))
            return

        if changed:
            self._persist_config()
            yield event.plain_result(f"已开启 {repo} 的 {event_name} 提醒")
        else:
            yield event.plain_result(f"当前会话未订阅 {repo}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @ghsub.command("disable")
    async def ghsub_disable(self, event: AstrMessageEvent, repo_ref: str, event_name: str):
        repo, error = self._parse_repo_ref(repo_ref)
        if error is not None:
            yield event.plain_result(error)
            return
        try:
            changed = disable_event(self.normalized_config, event.unified_msg_origin, repo, event_name)
        except ValueError:
            yield event.plain_result(self._unknown_event_message(event_name))
            return

        if changed:
            self._persist_config()
            yield event.plain_result(f"已关闭 {repo} 的 {event_name} 提醒")
        else:
            yield event.plain_result(f"当前会话未订阅 {repo}")

    async def _poll_loop(self):
        while True:
            await asyncio.sleep(60)
            async with GitHubClient(self.normalized_config.get("github_token", "")) as client:
                for sub in list(self.normalized_config.get("subscriptions", [])):
                    if not sub.get("enabled", True):
                        continue
                    sub_state = self.state.get_subscription_state(
                        sub["target_umo"],
                        sub["repo"],
                    )
                    state_before_poll = deepcopy(sub_state)
                    try:
                        messages = await poll_subscription_once(
                            client,
                            self.normalized_config,
                            sub,
                            sub_state,
                        )
                        await self._send_subscription_messages(sub, messages)
                    except Exception as exc:
                        sub_state.clear()
                        sub_state.update(state_before_poll)
                        logger.warning(
                            "GitHub subscriber failed for %s: %s",
                            sub.get("repo"),
                            exc,
                        )
                        continue

                    self.state.save()

    async def _send_subscription_messages(
        self,
        sub: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> None:
        delay_seconds = (self.normalized_config.get("message_limits") or {}).get(
            "message_send_delay_seconds",
            1,
        )
        for index, message in enumerate(messages):
            text = render_text_message(
                self.normalized_config,
                sub,
                message["template_name"],
                message["variables"],
            )
            chain = _build_message_chain(text, message.get("mention_qq", ""))
            await self.context.send_message(message["target_umo"], chain)
            if index < len(messages) - 1:
                await asyncio.sleep(delay_seconds)

    def _persist_config(self) -> None:
        self.config.clear()
        self.config.update(self.normalized_config)
        self.config.save_config()

    def _state_path(self) -> Path:
        return Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_github_subscriber" / "state.json"

    def _parse_repo_ref(self, repo_ref: str) -> tuple[str | None, str | None]:
        try:
            return parse_repo_ref(repo_ref), None
        except RepoParseError as exc:
            return None, str(exc)

    def _unknown_event_message(self, event_name: str) -> str:
        return f"未知事件类型：{event_name}。支持：{self._supported_event_names_text()}"

    def _supported_event_names_text(self) -> str:
        return "、".join(SUPPORTED_EVENT_NAMES)


def _build_message_chain(text: str, mention_qq: str | None = "") -> MessageChain:
    if mention_qq:
        try:
            return MessageChain([Comp.At(qq=str(mention_qq)), Comp.Plain(text)])
        except TypeError:
            chain = MessageChain()
            chain.message(text)
            return chain

    chain = MessageChain()
    if hasattr(chain, "message"):
        chain.message(text)
    elif hasattr(chain, "chain"):
        chain.chain.append(Comp.Plain(text))
    else:
        chain = MessageChain([Comp.Plain(text)])
    return chain
