"""Textual/Rich Telegram user-account TUI."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from rich.text import Text
from telethon import TelegramClient, events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Footer, Input, ListItem, ListView, Static


HERE = Path(__file__).resolve().parent
SESSION = HERE / "user.session"
CFG = HERE / "api-creds.txt"

STRELITZIA = Theme(
    name="strelitzia",
    primary="#D05050",
    secondary="#708090",
    accent="#F0A040",
    warning="#F0A040",
    error="#D05050",
    success="#A0A0C0",
    foreground="#F0F0E0",
    background="#0B0B12",
    surface="#191924",
    panel="#232332",
    dark=True,
    variables={
        "border": "#708090",
        "border-blurred": "#34344A",
        "block-cursor-background": "#F0A040",
        "block-cursor-foreground": "#0B0B12",
        "footer-background": "#191924",
    },
)


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


class ChatsScreen(ModalScreen[None]):
    """Modal dialog for choosing a Telegram chat."""

    BINDINGS = [("escape", "close", "close"), ("enter", "pick", "select")]

    def __init__(self, app: "TgChatApp") -> None:
        super().__init__()
        self.app_ref = app
        self.dialogs = []

    def compose(self) -> ComposeResult:
        yield Static("◤ SELECT LINK ◢  (Enter = lock on, Esc = abort)", id="chats-title")
        yield ListView(id="chats-list")

    def on_mount(self) -> None:
        self.query_one("#chats-list", ListView).focus()
        self.run_worker(self._fill(), exclusive=False)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if 0 <= event.index < len(self.dialogs):
            self.app_ref.set_active(self.dialogs[event.index].id)
        self.dismiss()

    async def _fill(self) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self.app_ref.client.get_dialogs(limit=50), self.app_ref.client_loop
        )
        self.dialogs = list(await asyncio.wait_for(asyncio.wrap_future(future), 20))
        chat_list = self.query_one("#chats-list", ListView)
        for dialog in self.dialogs:
            marker = "*" if dialog.id == self.app_ref.active else " "
            chat_list.append(ListItem(Static(f"{marker} {dialog.id}  {dialog.name}")))

    def action_pick(self) -> None:
        chat_list = self.query_one("#chats-list", ListView)
        index = chat_list.index if chat_list.index is not None else 0
        if 0 <= index < len(self.dialogs):
            self.app_ref.set_active(self.dialogs[index].id)
        self.pop_screen()


class TgChatApp(App[None]):
    """Terminal UI for receiving, browsing, and sending Telegram messages."""

    CSS = """
    #hazard { width: 100%; height: 1; background: $warning; color: $background; text-style: bold; }
    #titlebar { padding: 0 1; text-style: bold; color: $accent;
                 background: $panel; border-bottom: solid $error; }
    #chatbar { padding: 0 1; text-style: bold; background: $surface;
               border-bottom: solid $error; }
    #msgs { height: 1fr; }
    Static.bubble { width: auto; max-width: 75%; padding: 0 1; }
    Static.them { border: round $secondary; background: $surface; }
    Static.me { border: round $warning; background: $error; color: $background; }
    ListItem.item-me { align-horizontal: right; }
    ListItem.item-sys { align-horizontal: center; }
    #bottom { height: auto; }
    #composer { margin: 0 1; border: heavy $secondary; }
    Footer { dock: bottom; }
    #chats-title { height: 1; padding: 0 1; text-style: bold; color: $accent; }
    """
    BINDINGS = [
        Binding("ctrl+q", "quit", "quit"),
        Binding("ctrl+c", "quit", "quit"),
        Binding("f2", "chats", "chats"),
    ]

    def __init__(self, client: TelegramClient, client_loop, me) -> None:
        super().__init__()
        self.register_theme(STRELITZIA)
        self.theme = "strelitzia"
        self.client = client
        self.client_loop = client_loop
        self.me = me
        self.active = None
        self._loaded: set[int] = set()

    def compose(self) -> ComposeResult:
        yield Static("▚▞" * 256, id="hazard")
        yield Static(
            f"STRELITZIA // COMMS LINK  ⚠  {self.me.first_name} (@{self.me.username})",
            id="titlebar",
        )
        yield Static("◤ NO LINK ◢  awaiting signal", id="chatbar")
        yield ListView(id="msgs")
        with Vertical(id="bottom"):
            yield Input(
                placeholder="▸ transmit...  [Enter] send  /chats  /exit",
                id="composer",
            )
            yield Footer()

    def on_mount(self) -> None:
        self.query_one("#composer", Input).focus()
        self.add_system("F2 = switch chat, /chat <id>, /exit, Ctrl+C to quit")

    def set_active(self, chat_id: int) -> None:
        if self.active == chat_id:
            return
        self.active = chat_id
        self.query_one("#chatbar", Static).update(
            f"◤ LINK: {chat_id} ◢  [F2 = SWITCH]"
        )
        if chat_id not in self._loaded:
            self._loaded.add(chat_id)
            self.run_worker(self._load_history(chat_id), exclusive=False)

    async def _load_history(self, chat_id: int) -> None:
        async def fetch():
            chat = await self.client.get_entity(chat_id)
            who = (
                getattr(chat, "title", None)
                or getattr(chat, "first_name", None)
                or str(chat_id)
            )
            messages = [message async for message in self.client.iter_messages(chat_id, limit=50)]
            return who, list(reversed(messages))

        future = asyncio.run_coroutine_threadsafe(fetch(), self.client_loop)
        try:
            who, messages = await asyncio.wait_for(asyncio.wrap_future(future), 20)
        except Exception as error:
            self.add_system(f"history failed: {error}")
            return
        if chat_id != self.active:
            return
        for message in messages:
            header = Text()
            if message.date:
                header.append(message.date.strftime("%m-%d %H:%M"), style="dim")
            if message.out:
                header.append("  you", style="bold")
                self.add_msg("me", header, message.message or "<media>")
            else:
                header.append(f"  {who}", style="bold cyan")
                self.add_msg("them", header, message.message or "<media>")

    def add_msg(self, kind: str, header: Text, body: str) -> None:
        content = Text()
        content.append_text(header)
        content.append("\n" + body)
        messages = self.query_one("#msgs", ListView)
        messages.append(ListItem(Static(content, classes=f"bubble {kind}"), classes=f"item-{kind}"))
        messages.scroll_end()

    def add_incoming(self, chat_id: int, who: str, text: str) -> None:
        if self.active is None:
            self.set_active(chat_id)
        header = Text()
        header.append(datetime.now().strftime("%H:%M"), style="dim")
        header.append(f"  {who}", style="bold cyan")
        self.add_msg("them", header, str(text))

    def add_outgoing(self, text: str) -> None:
        header = Text()
        header.append(datetime.now().strftime("%H:%M"), style="dim")
        header.append("  you", style="bold")
        self.add_msg("me", header, str(text))

    def add_system(self, text: str) -> None:
        header = Text(datetime.now().strftime("%H:%M") + "  ⚠ SYSTEM", style="bold #F0A040")
        self.add_msg("sys", header, str(text))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.control.value = ""
        if not text:
            return
        if text == "/exit":
            self.exit()
        elif text == "/chats":
            self.push_screen(ChatsScreen(self))
        elif text.startswith("/chat "):
            try:
                self.set_active(int(text.split()[1]))
            except ValueError:
                self.add_system("usage: /chat <id>")
        else:
            self.send(text)

    def action_chats(self) -> None:
        self.push_screen(ChatsScreen(self))

    def action_quit(self) -> None:
        self.exit()

    def send(self, text: str) -> None:
        if self.active is None:
            self.add_system("No active chat - receive a message first, or F2 to pick one.")
            return
        self.add_outgoing(text)
        future = asyncio.run_coroutine_threadsafe(
            self.client.send_message(self.active, text), self.client_loop
        )

        def done(done_future) -> None:
            try:
                done_future.result()
            except Exception as error:
                self.call_from_thread(self.add_system, f"send failed: {error}")

        future.add_done_callback(done)


def main() -> None:
    api_id, api_hash = load_creds()
    client = TelegramClient(str(SESSION), api_id, api_hash)
    holder = {}

    @client.on(events.NewMessage(incoming=True))
    async def on_message(event: events.NewMessage.Event) -> None:
        try:
            chat = await event.get_chat()
            who = (
                getattr(chat, "title", None)
                or getattr(chat, "first_name", None)
                or str(event.chat_id)
            )
        except Exception:
            who = str(event.chat_id)
        text = (event.message.message if event.message else None) or "<media>"
        app = holder.get("app")
        if app is not None:
            app.call_from_thread(app.add_incoming, event.chat_id, who, text)

    async def connect() -> None:
        await client.start()
        holder["me"] = await client.get_me()
        holder["loop"] = asyncio.get_running_loop()
        await client.run_until_disconnected()

    thread = threading.Thread(target=lambda: asyncio.run(connect()), daemon=True)
    thread.start()
    print("logging in...", flush=True)

    for _ in range(300):
        if "me" in holder:
            break
        if not thread.is_alive():
            raise SystemExit("Login failed or was cancelled.")
        time.sleep(0.2)
    else:
        raise SystemExit("Login timed out.")

    app = TgChatApp(client, holder["loop"], holder["me"])
    holder["app"] = app
    try:
        app.run()
    except Exception:
        error_log = HERE / "tui-error.log"
        with error_log.open("w", encoding="utf-8") as handle:
            import traceback

            traceback.print_exc(file=handle)
        print(f"UI failed - see {error_log}")
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
