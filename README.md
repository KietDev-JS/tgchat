# tgchat

Small Windows-friendly Telegram terminal clients for personal automation and local use.

This repository contains three entry points built from the same original `tools\tgchat` utility:

| Command | Transport | Account type | UI |
| --- | --- | --- | --- |
| `tgchat-bot` | Telegram Bot API | Bot token | Minimal terminal loop |
| `tgchat-user` | Telethon MTProto client | Personal Telegram account | Minimal terminal loop |
| `tgchat-tui` | Telethon MTProto client | Personal Telegram account | Textual/Rich TUI |

The project is deliberately small. It is useful when you want a local terminal client for a bot or a personal Telegram account without running a full desktop application.

> **Status:** early personal utility. It is not a production-grade Telegram client. Expect limited media support, limited chat management, and rough edges around terminal input and reconnect behavior.

## Features

- Bot API polling client using only Python's standard library.
- Personal-account client using Telethon.
- Textual/Rich terminal UI with:
  - Chat picker on `F2`.
  - Conversation history loading.
  - Incoming and outgoing message styling.
  - `Ctrl+C`/`Ctrl+Q` exit handling.
  - Custom dark `strelitzia` theme.
- Environment variables for non-interactive configuration.
- Ignored local credential/session files.
- Windows-friendly launch instructions and PowerShell examples.

## Security First

Never commit any of the following:

- Bot tokens.
- Telegram `api_id` or `api_hash`.
- Telethon `.session` files.
- Login codes, two-factor passwords, or exported Telegram data.
- Logs containing message text or account identifiers.

The repository ignores `token.txt`, `api-creds.txt`, `*.session`, session journals, and runtime logs. This protects against accidental commits, but it does not protect a value that has already been printed, copied, or committed elsewhere. Rotate a credential immediately if it was exposed.

The code stores local credentials for convenience when prompted. For shared machines or automated environments, prefer environment variables and a secret manager.

## Requirements

- Python `3.10` or newer. Tested on Python `3.13` on Windows.
- A Telegram bot token for `tgchat-bot`, or Telegram API credentials for the user clients.
- A terminal with standard input support. Windows Terminal is recommended for the TUI.
- Internet access to Telegram's API endpoints.

The current development machine used:

- Python `3.13.1`.
- Telethon `1.45.0`.
- Textual `8.0.0`.
- Rich `14.3.3`.

## Installation

### PowerShell, recommended virtual environment

```powershell
git clone https://github.com/KietDev-JS/tgchat.git
Set-Location tgchat

py -3 -m venv .venv
\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the venv's Python directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Alternatively, install the project in editable mode:

```powershell
python -m pip install -e .
```

### Bot-only installation

The Bot API client uses only the Python standard library:

```powershell
py -3 tgchat.py
```

You do not need `requirements.txt` for this entry point.

## Telegram Credentials

### Bot API token

1. Open Telegram and message `@BotFather`.
2. Create or select a bot and copy its token.
3. Start the bot client:

```powershell
$env:TG_BOT_TOKEN = '123456789:replace-this-value'
python .\tgchat.py
```

The client also accepts an ignored local file at `token.txt` containing only the token:

```text
123456789:replace-this-value
```

If neither the environment variable nor the file exists, the client prompts and writes the entered token to `token.txt`.

### User API credentials

For `tguser.py` and `tguser_tui.py`, create Telegram API credentials at:

<https://my.telegram.org>

Open **API development tools** and obtain:

- `api_id`: numeric application ID.
- `api_hash`: application hash.

Use environment variables for the current PowerShell process:

```powershell
$env:TG_API_ID = '123456'
$env:TG_API_HASH = 'replace-this-value'
```

Or create the ignored local file `api-creds.txt` containing one comma-separated line:

```text
123456,replace-this-value
```

The first user-client login may ask for your phone number, Telegram login code, and two-factor password. Telethon then creates `user.session`. That file is an authenticated account session and must remain private.

## Running

### Bot API client

```powershell
python .\tgchat.py
```

The bot must receive a message before the client knows a chat to use. Send the bot a message in Telegram, then use:

| Command | Action |
| --- | --- |
| `/chats` | List chats seen during this process |
| `/chat <id>` | Select a chat by numeric ID |
| `/exit` | Exit |
| Any other text | Send it to the active chat |

The Bot API client uses long polling through `getUpdates`. It tracks the update offset in memory only, so restarting the process can replay updates depending on Telegram's pending-update state.

### User terminal client

```powershell
python .\tguser.py
```

This uses Telethon with a personal account session. Once logged in:

| Command | Action |
| --- | --- |
| `/chats` | Fetch and list up to 30 dialogs |
| `/chat <id>` | Select a dialog by numeric ID |
| `/exit` | Disconnect and exit |
| Any other text | Send it to the active chat |

The client displays incoming messages and automatically selects the first chat that sends an incoming message. Use `/chats` and `/chat <id>` to select another conversation.

### Textual/Rich TUI

```powershell
python .\tguser_tui.py
```

Controls:

| Key / input | Action |
| --- | --- |
| `F2` | Open the chat picker |
| `Enter` in picker | Select the highlighted chat |
| `Esc` in picker | Close the picker |
| `Enter` in composer | Send the message or execute a slash command |
| `Ctrl+Q` | Quit |
| `Ctrl+C` | Quit |
| `/chats` | Open the chat picker from the composer |
| `/chat <id>` | Select a chat by ID |
| `/exit` | Quit |

The TUI loads up to 50 recent messages for a selected chat and displays incoming/outgoing messages with the built-in `strelitzia` theme.

## Console Scripts

After `python -m pip install -e .`, the project exposes:

```powershell
tgchat-bot
tgchat-user
```

These map to `tgchat.py`, `tguser.py`, and `tguser_tui.py` respectively. Running the files directly is also supported and is often clearer while developing.

## Configuration Precedence

### Bot client

1. `TG_BOT_TOKEN` environment variable.
2. Local ignored `token.txt`.
3. Interactive prompt, followed by writing `token.txt`.

### User clients

1. `TG_API_ID` and `TG_API_HASH` environment variables together.
2. Local ignored `api-creds.txt`.
3. Interactive prompts, followed by writing `api-creds.txt`.

The session path is always local to the repository directory by default:

```text
user.session
```

## Architecture

### `tgchat.py`

- Uses `urllib.request` against `https://api.telegram.org/bot<TOKEN>/<METHOD>`.
- Runs `getUpdates` in a daemon thread.
- Sends text messages with `sendMessage`.
- Formats text, captions, and basic non-text update markers.
- Keeps the active chat and update offset in memory.

### `tguser.py`

- Creates a Telethon `TelegramClient` backed by `user.session`.
- Runs Telethon's asyncio loop in a background thread.
- Uses a synchronous terminal loop for input.
- Supports receiving messages, listing dialogs, selecting a chat, and sending text.

### `tguser_tui.py`

- Shares the Telethon background-loop pattern with the CLI.
- Runs Textual on the main thread.
- Bridges Telegram events into Textual using `call_from_thread`.
- Loads recent history asynchronously when selecting a chat.
- Uses a modal `ChatsScreen` for chat selection.

## Development

Create the environment and install development dependencies:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Syntax-check all modules without logging into Telegram:

```powershell
python -m compileall .\tgchat.py .\tguser.py .\tguser_tui.py
```

Check the working tree for accidentally tracked secrets:

```powershell
git status --short
git ls-files | Select-String 'token|secret|credential|session|\.env'
```

The second command should return no credential or session files.

## Troubleshooting

### `ModuleNotFoundError: No module named 'telethon'`

Activate the virtual environment and install dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'textual'`

The TUI dependencies are in `requirements.txt`; reinstall them in the active environment.

### The bot receives no messages

- Confirm that the bot token is correct.
- Send the bot a new message in Telegram.
- Check that the bot is not blocked or restricted.
- Stop other consumers of the same bot's update queue if long polling is being used elsewhere.

### The user client asks for login repeatedly

- Make sure `user.session` is in the directory from which the script is running.
- Do not delete or replace the session file between runs.
- Ensure the same `api_id` and `api_hash` are being used.
- Keep the session private; do not move it into Git.

### The TUI fails to start

- Try `python .\tguser.py` first to isolate Telegram authentication from UI issues.
- Check `tui-error.log` if the application creates it.
- Use a modern terminal such as Windows Terminal.
- Verify that the terminal window is large enough for the layout.

### Windows PowerShell blocks virtual-environment activation

Use the environment's Python executable directly, or verify the effective policy:

```powershell
Get-ExecutionPolicy -List
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Do not weaken machine-wide policy just to run this project.

## Limitations

- Text-first interaction; media sending and media download are not implemented.
- No persistent local chat database.
- No message search, editing, deletion, reactions, forwarding, or attachments.
- No automatic reconnect strategy beyond the basic Telethon/long-polling loops.
- The Bot API client only knows chats that appear in its current update stream.
- The user clients use numeric Telegram IDs for explicit chat selection.
- Terminal input uses Windows-oriented `msvcrt` behavior and is not currently portable to Unix-like systems.
- This project has not been audited for multi-user or production deployment.

## Privacy and Data Handling

The clients communicate directly with Telegram. Message content is displayed locally and is not intentionally sent to any third-party service. However:

- Telegram receives normal API traffic.
- Telethon creates a local authenticated session.
- The terminal history, shell transcripts, crash logs, and screen capture tools may retain sensitive content outside this project.
- Do not run the clients in shared terminal sessions.
- Review and delete local runtime files before handing a machine to another user.

## License

MIT. See `LICENSE`.
