"""Optional visual control for features with no public CLI/API, always on a local desktop."""

import io
import os
import subprocess
import sys


class Desktop:
    def __init__(self):
        self.enabled = os.environ.get("ORCA_MCP_DESKTOP", "0") == "1"

    def status(self) -> dict:
        return {"enabled": self.enabled, "platform": sys.platform, "method": "foreground-window-checked visual interaction", "notice": "Requires [desktop] extra and unlocked local desktop. GUI workflows depend on version, dialogs and layout; no semantic API is claimed."}

    def _api(self, check_focus: bool = True):
        if not self.enabled:
            raise ValueError("Enable ORCA_MCP_DESKTOP=1 and install the [desktop] extra")
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.15
        if check_focus:
            if sys.platform == "win32":
                import pygetwindow
                title = pygetwindow.getActiveWindowTitle() or ""
            elif sys.platform == "darwin":
                title = subprocess.check_output(["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'], text=True)
            else:
                title = subprocess.check_output(["xdotool", "getactivewindow", "getwindowname"], text=True)
            if "orca" not in title.lower():
                raise ValueError("OrcaSlicer must be the foreground window; focus it first")
        return pyautogui

    def screenshot(self) -> bytes:
        api = self._api()
        out = io.BytesIO()
        api.screenshot().save(out, format="PNG")
        return out.getvalue()

    def focus(self) -> dict:
        self._api(check_focus=False)
        if sys.platform == "win32":
            import pygetwindow
            windows = pygetwindow.getWindowsWithTitle("OrcaSlicer")
            if len(windows) != 1:
                raise ValueError("Expected exactly one OrcaSlicer window; select it locally")
            if windows[0].isMinimized:
                windows[0].restore()
            windows[0].activate()
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", 'tell application "OrcaSlicer" to activate'], check=True)
        else:
            windows = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--class", "(?i)orca"], text=True).split()
            if len(windows) != 1:
                raise ValueError("Expected exactly one OrcaSlicer window; select it locally")
            subprocess.run(["xdotool", "windowactivate", "--sync", windows[0]], check=True)
        return {"focused": True}

    def action(self, action: str, x: int = 0, y: int = 0, text: str = "", keys: list[str] | None = None, amount: int = 0) -> dict:
        api = self._api()
        if action in ("click", "double_click", "right_click", "move", "drag"):
            width, height = api.size()
            if not 0 <= x < width or not 0 <= y < height:
                raise ValueError("Coordinates outside screen")
        if action == "click":
            api.click(x, y)
        elif action == "double_click":
            api.doubleClick(x, y, interval=0.15)
        elif action == "right_click":
            api.click(x, y, button="right")
        elif action == "move":
            api.moveTo(x, y)
        elif action == "drag":
            api.dragTo(x, y, duration=0.5)
        elif action == "scroll":
            if abs(amount) > 100:
                raise ValueError("Scroll range is -100..100")
            api.scroll(amount)
        elif action == "keys":
            if not keys or len(keys) > 5 or any(k not in api.KEYBOARD_KEYS for k in keys):
                raise ValueError("Provide 1..5 valid PyAutoGUI key names")
            api.hotkey(*keys)
        elif action == "text":
            if len(text) > 10000:
                raise ValueError("Text exceeds 10000 characters")
            # Clipboard paste preserves Unicode; restore previous text afterwards.
            import pyperclip
            old = pyperclip.paste()
            try:
                pyperclip.copy(text)
                api.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
                import time
                time.sleep(0.2)
            finally:
                pyperclip.copy(old)
        else:
            raise ValueError("Unknown action")
        return {"action": action, "performed": True, "next": "Inspect a new screenshot before the next action"}

