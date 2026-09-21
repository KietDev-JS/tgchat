# tgchat Setup Guide

This guide is the operational setup path for Windows PowerShell. It assumes a clean checkout and keeps Telegram secrets outside Git.

## 1. Install Python

Install Python 3.10 or newer and verify:

```powershell
py --version
python --version
```

Python 3.13 is known to work with the current development dependencies.

## 2. Clone and enter the repository

```powershell
git clone https://github.com/KietDev-JS/tgchat.git
Set-Location tgchat
```

## 3. Create an isolated environment

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use the venv interpreter explicitly if PowerShell activation is unavailable. This avoids accidentally installing packages into the global Python installation.

## 4. Choose an account mode

### Bot mode

Use this for a bot created through `@BotFather`.

```powershell
$env:TG_BOT_TOKEN = 'paste-the-token-for-this-session-only'
.\.venv\Scripts\python.exe .\tgchat.py
```

The client can save a token to the ignored `token.txt` file after prompting. Environment variables are preferable for CI or temporary sessions because they avoid writing the token to disk.

### Personal user mode

Use this for a personal Telegram account through Telethon.

1. Visit <https://my.telegram.org>.
2. Open **API development tools**.
3. Create an application if necessary.
4. Copy `api_id` and `api_hash`.
5. Set them for the current PowerShell process:

```powershell
$env:TG_API_ID = '123456'
$env:TG_API_HASH = 'paste-the-api-hash-for-this-session-only'
```

Run:

```powershell
.\.venv\Scripts\python.exe .\tguser.py
```

During the first login, Telethon may ask for your phone number, login code, and two-factor password. The generated `user.session` file is equivalent to a remembered login and must be protected like a password.

## 5. Run the TUI

```powershell
.\.venv\Scripts\python.exe .\tguser_tui.py
```

Use `F2` to choose a chat. Enter messages in the bottom composer. Use `/exit` or `Ctrl+Q` to leave.

## 6. Optional local config files

Copy the examples only if you want file-based local configuration:

```powershell
Copy-Item .\.env.example .\.env
```

The current Python clients read environment variables and their own ignored files; they do not parse `.env` automatically. Do not assume that creating `.env` alone configures the application. Either export the variables in PowerShell or create the exact ignored files:

```powershell
Set-Content -NoNewline .\token.txt '123456789:replace-this-value'
Set-Content -NoNewline .\api-creds.txt '123456,replace-this-value'
```

The files above must remain untracked. Confirm:

```powershell
git status --short
```

## 7. Validate without logging in

```powershell
.\.venv\Scripts\python.exe -m compileall .\tgchat.py .\tguser.py .\tguser_tui.py
```

Check dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip show telethon textual rich
```

## 8. Verify no secrets are tracked

```powershell
git status --short
git ls-files | Select-String 'token|secret|credential|session|\.env'
```

The second command should produce no output. If it does, stop and remove the file from Git before pushing.

## 9. Credential rotation and cleanup

If a bot token is exposed, revoke it through `@BotFather` and create a replacement. If a Telethon session is exposed, terminate active sessions through Telegram's account security settings and delete the exposed `.session` file.

To remove local account state from a checkout:

```powershell
Remove-Item .\user.session -ErrorAction SilentlyContinue
Remove-Item .\api-creds.txt -ErrorAction SilentlyContinue
Remove-Item .\token.txt -ErrorAction SilentlyContinue
```

## 10. Common operational issues

### Login succeeds but no chats appear

Use `/chats` in the CLI or `F2` in the TUI. A chat must be available to the authenticated account, and the numeric ID must be selected before sending.

### Bot mode appears idle

Send the bot a new message. The Bot API client uses polling and does not query a full dialog list like a personal account client.

### TUI crash

Run the plain user CLI first. If authentication works but the TUI fails, inspect `tui-error.log`. That file is ignored and may contain exception details or account identifiers.

### Wrong Python environment

Always compare:

```powershell
Get-Command python
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip --version
```

The `pip` path should point inside `.venv`.

## 11. Updating

Pull source changes and reinstall pinned-range dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
```

Review changes to Telegram protocol code before running with an existing authenticated session.
