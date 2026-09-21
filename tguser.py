"""Minimal Telegram user-account terminal chat client using Telethon."""

from __future__ import annotations

import asyncio
import msvcrt
import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events


HERE = Path(__file__).resolve().parent
SESSION = HERE / "user.session"
CFG = HERE / "api-creds.txt"


def load_creds() -> tuple[int, str]:
    """Load Telegram API credentials from env vars, ignored file, or prompts."""
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if api_id and api_hash:
        return int(api_id), api_hash

    if CFG.exists():
        values = CFG.read_text(encoding="utf-8").strip().split(",", 1)
        if len(values) == 2:
            return int(values[0]), values[1]

    print(
        "First run: get api_id and api_hash at "
        "https://my.telegram.org (API development tools)"
    )
    api_id = input("api_id: ").strip()
    api_hash = input("api_hash: ").strip()
    CFG.write_text(f"{api_id},{api_hash}", encoding="utf-8")
    try:
        os.chmod(CFG, 0o600)
    except OSError:
        pass
    return int(api_id), api_hash


def main() -> None:
    api_id, api_hash = load_creds()
    messages: queue.Queue[dict[str, Any]] = queue.Queue()
    client = TelegramClient(str(SESSION), api_id, api_hash)

    @client.on(events.NewMessage(incoming=True))
    async def on_message(event: events.NewMessage.Event) -> None:
        try:
            chat = await event.get_chat()
            who = (
                getattr(chat, "title", None)
                or getattr(event.sender, "first_name", None)
                or str(event.chat_id)
            )
        except Exception:
            who = str(event.chat_id)
        text = event.message or f"(<{'media' if event.raw_text else 'unknown'}>)"
        messages.put({"chat_id": event.chat_id, "who": who, "text": text})

    async def connect() -> None:
        await client.start()
        me = await client.get_me()
        print(f"Logged in as {me.first_name} (@{me.username})  (Ctrl+C to quit)")
        print("Commands: /chats  /chat <id>  /exit")
        await client.run_until_disconnected()

    thread = threading.Thread(target=lambda: asyncio.run(connect()), daemon=True)
    thread.start()

    for _ in range(300):
        if client.is_connected() and getattr(client, "_me", None) is not None:
            break
        if not thread.is_alive():
            raise SystemExit("Login failed or was cancelled.")
        time.sleep(0.2)

    active: int | None = None
    seen: list[int] = []
    print("> ", end="", flush=True)

    while True:
        try:
            while True:
                try:
                    message = messages.get_nowait()
                except queue.Empty:
                    break
                print(f"[{message['who']} | {message['chat_id']}] {message['text']}")
                if message["chat_id"] not in seen:
                    seen.append(message["chat_id"])
                if active is None:
                    active = message["chat_id"]
                    print(f"-> now chatting with {active}")

            time.sleep(0.1)
            if not msvcrt.kbhit():
                continue

            line = input().strip()
            print("> ", end="", flush=True)
            if not line:
                continue
            if line == "/exit":
                break
            if line == "/chats":
                dialogs = asyncio.run_coroutine_threadsafe(
                    client.get_dialogs(limit=30), client.loop
                ).result()
                for dialog in dialogs:
                    marker = "*" if dialog.id == active else " "
                    print(f" {marker} {dialog.id}  {dialog.name}")
                continue
            if line.startswith("/chat "):
                active = int(line.split()[1])
                print(f"-> active chat {active}")
                continue
            if active is None:
                print("No active chat - receive a message first, or use /chats + /chat <id>.")
                continue
            asyncio.run_coroutine_threadsafe(
                client.send_message(active, line), client.loop
            ).result()
        except KeyboardInterrupt:
            break

    try:
        client.disconnect()
    except Exception:
        pass
    print("Bye.")


if __name__ == "__main__":
    main()
