# Osslik - Remote Access Tool

**Osslik** is a Python-based Remote Access Tool (RAT) that provides extensive control over a target Windows machine via Discord. It includes surveillance, system control, data exfiltration, and persistence features.

---

## Features

### 🖥️ **Remote Control**
- **Screenshot Capture**: Take and send screenshots of the target machine.
- **Camera Access**: Capture images from all connected cameras.
- **Keyboard Control**:
  - Press single keys (`key` command).
  - Press hotkey combinations (`hotkey` command).
  - Type arbitrary text (`type` command).
- **Mouse Control**:
  - Move cursor to specific coordinates (`move` command).
  - Click left, right, or middle mouse buttons (`click` command).
  - Scroll up or down (`scroll` command).

### 🔍 **System Monitoring & Data Exfiltration**
- **Check User Activity**: Detect last keyboard/mouse activity time (`lastactive` command).
- **List Open Windows**: Retrieve a list of all visible application windows with their process names (`listwindows` command).
- **Chrome Data Theft**: Extract sensitive Chrome files (`chromedata` command):
  - Bookmarks
  - Login Data (potentially containing saved passwords)
  - Browsing History

### ⚡ **Command Execution**
- **Non-Admin Command Execution**: Run commands in CMD or PowerShell (`runcmd` command).
- **Admin Command Execution**: Execute commands with elevated privileges (`admincmd` command) via a background service.

### 📂 **File Operations**
- **Download Files**: Fetch files from URLs and save them to the target machine (`sendfile` command).
- **Send Files to Attacker**: Upload files from the victim's machine to Telegram (via `send_file_once` function).

### 🛡️ **Persistence & Evasion**
- **Auto-Start Registry Entry**: Adds itself to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` for persistence.
- **Windows Defender Exclusion**: Adds itself to Windows Defender’s exclusion list to avoid detection.
- **Elevation Service**: Runs a privileged background service (on port `58473`) for admin command execution.

### 🔒 **Security & Access Control**
- **Authorization Check**: Only allows predefined user IDs (in `AUTHORIZED_USER_IDS`) to execute commands.
- **Stealth Notifications**: Logs camera access attempts with timestamps and user info.

### 🌐 **Network Communication**
- **Discord Bot Integration**: Uses Discord as a C2 (Command & Control) channel for remote interaction.
- **Telegram Integration**: Optionally sends stolen files to a Telegram bot (if `TG_BOT_TOKEN` and `TG_USER_ID` are configured).

### ⚙️ **Utility Functions**
- **Process Management**: Tracks active processes (`ACTIVE_PROCESSES` dictionary).
- **Error Handling**: Graceful error messages for failed operations.
- **Multi-threading**: Uses background threads for long-running tasks (e.g., elevation service).
