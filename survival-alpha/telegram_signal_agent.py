from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from telegram_parser import TelegramCall, parse_telegram_message

log = logging.getLogger("survival-alpha.telegram-signal-agent")


class TelegramSignalAgent:
    """
    Optional MTProto listener for Telegram signal channels.

    It intentionally uses a pre-authenticated StringSession supplied via an
    environment secret. It never prompts for OTP in the cloud and never persists
    the session to disk.
    """

    def __init__(self, on_call: Callable[[TelegramCall], Awaitable[None]]):
        self.on_call = on_call
        self.api_id = int(os.getenv("TG_API_ID", "0") or 0)
        self.api_hash = os.getenv("TG_API_HASH", "").strip()
        self.session_string = os.getenv("TG_SESSION_STRING", "").strip()
        self.channels = [
            x.strip() for x in os.getenv("TG_SIGNAL_CHANNELS", "").split(",") if x.strip()
        ]
        self.enabled = bool(self.api_id and self.api_hash and self.session_string and self.channels)
        self._client = None

    async def run(self) -> None:
        if not self.enabled:
            log.info("Telegram MTProto signal agent disabled")
            return

        try:
            from telethon import TelegramClient, events
            from telethon.sessions import StringSession
        except Exception:
            log.exception("Telethon unavailable")
            return

        client = TelegramClient(
            StringSession(self.session_string),
            self.api_id,
            self.api_hash,
            sequential_updates=False,
        )
        self._client = client

        try:
            await client.connect()
            if not await client.is_user_authorized():
                log.error("TG_SESSION_STRING is not authorized; refusing interactive login")
                return

            entities = []
            for ref in self.channels:
                try:
                    entities.append(await client.get_entity(ref))
                except Exception:
                    log.exception("Cannot resolve Telegram signal source %s", ref)

            allowed_ids = {getattr(e, "id", None) for e in entities}
            allowed_ids.discard(None)

            @client.on(events.NewMessage(chats=entities))
            async def _handler(event):
                try:
                    chat = await event.get_chat()
                    cid = getattr(chat, "id", None)
                    if allowed_ids and cid not in allowed_ids:
                        return
                    username = getattr(chat, "username", None)
                    title = getattr(chat, "title", None)
                    channel = f"@{username}" if username else f"id_{cid}"
                    source_url = (
                        f"https://t.me/{username}/{event.id}" if username else ""
                    )
                    calls = parse_telegram_message(
                        channel=channel or title or "telegram",
                        message_id=event.id,
                        published_at=event.date,
                        text=event.raw_text or "",
                        source_url=source_url,
                    )
                    for call in calls:
                        await self.on_call(call)
                except Exception:
                    log.exception("Telegram signal handler failed")

            log.info("Telegram MTProto signal agent listening to %d channels", len(entities))
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Telegram MTProto signal agent crashed")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
