"""Minimal Telegram Bot API terminal chat client."""

from __future__ import annotations

import json
import msvcrt
import os
import queue
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API = "https://api.telegram.org/bot{token}/{method}"
HERE = Path(__file__).resolve().parent
TOKEN_FILE = HERE / "token.txt"


def get_token() -> str:
    """Load a bot token from the environment, ignored local file, or prompt."""
    token = os.environ.get("TG_BOT_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        token = input("Bot token: ").strip()
        if token:
            TOKEN_FILE.write_text(token, encoding="utf-8")
            try:
                os.chmod(TOKEN_FILE, 0o600)
            except OSError:
                pass
            print(f"(saved to {TOKEN_FILE})")
    if not token:
        raise SystemExit("No token.")
    return token


def call(token: str, method: str, **params: Any) -> Any:
    """Call a Telegram Bot API method and return its result."""
    url = API.format(token=token, method=method)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=45) as response:
        data = json.load(response)
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data}")
    return data.get("result")


def fmt_update(update: dict[str, Any]) -> str | None:
    """Format a supported Telegram update for terminal output."""
    message = (
        update.get("message")
        or update.get("edited_message")
        or update.get("channel_post")
    )
    if not message:
        return None

    chat = message.get("chat", {})
    sender = message.get("from", {})
    name = (
        sender.get("first_name")
        or chat.get("title")
        or chat.get("username")
        or str(chat.get("id"))
    )
    parts = [f"[{name} | chat {chat.get('id')}]" ]
    if "text" in message:
        parts.append(message["text"])
    elif "caption" in message:
        parts.append(f"(caption) {message['caption']}")
    else:
        parts.append(f"(<{message.get('content_type', 'unknown')}>)")
    return " ".join(parts)


def poll_loop(token: str, updates: queue.Queue[dict[str, Any]], offset: list[int]) -> None:
    """Poll for updates in a background thread."""
    while True:
        try:
            received = call(
                token,
                "getUpdates",
                offset=offset[0],
                timeout=30,
                allowed_updates="message,edited_message,channel_post",
            )
            for update in received:
                offset[0] = update["update_id"] + 1
                updates.put(update)
        except Exception as error:  # keep the terminal client alive after network errors
            updates.put({"__error__": str(error)})
            time.sleep(3)


def main() -> None:
    token = get_token()
    me = call(token, "getMe")
    print(f"Connected as @{me['username']}  (Ctrl+C to quit)")
    print("Commands: /chats  /chat <id>  /exit")

    updates: queue.Queue[dict[str, Any]] = queue.Queue()
    offset = [0]
    thread = threading.Thread(
        target=poll_loop,
        args=(token, updates, offset),
        daemon=True,
    )
    thread.start()

    active_chat: int | None = None
    seen_chats: list[int] = []

    while True:
        try:
            while True:
                try:
                    update = updates.get_nowait()
                except queue.Empty:
                    break

                if "__error__" in update:
                    print(f"!! poll error: {update['__error__']}")
                    continue

                line = fmt_update(update)
                if not line:
                    continue
                print(line)

                message = (
                    update.get("message")
                    or update.get("edited_message")
                    or update.get("channel_post")
                )
                chat_id = message["chat"]["id"]
                if chat_id not in seen_chats:
                    seen_chats.append(chat_id)
                if active_chat is None:
                    active_chat = chat_id
                    print(f"-> now chatting with chat {chat_id}")

            time.sleep(0.1)

            if msvcrt.kbhit():
                line = input().strip()
                if not line:
                    continue
                if line == "/exit":
                    break
                if line == "/chats":
                    for chat_id in seen_chats:
                        marker = "*" if chat_id == active_chat else " "
                        print(f" {marker} {chat_id}")
                    continue
                if line.startswith("/chat "):
                    active_chat = int(line.split()[1])
                    print(f"-> active chat {active_chat}")
                    continue
                if active_chat is None:
                    print("No chat yet - send the bot a message in Telegram first.")
                    continue
                call(token, "sendMessage", chat_id=active_chat, text=line)
        except KeyboardInterrupt:
            break

    print("Bye.")


if __name__ == "__main__":
    main()
