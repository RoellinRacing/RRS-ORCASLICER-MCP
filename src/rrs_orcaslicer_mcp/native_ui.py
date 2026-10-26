"""Version-sensitive native GUI controls with semantic locators, never caller coordinates."""

import io
import csv
import os
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from .desktop import Desktop
from .storage import atomic_bytes


def tokens(text):
    return re.findall(r"[\w]+", text.casefold())


class NativeControls:
    def __init__(self, desktop: Desktop, evidence: Path):
        self.desktop, self.evidence = desktop, evidence
        self.main_bounds = None

    def bounds(self):
        # Also checks the owning process, including native Orca dialogs.
        self.desktop._api()
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            rectangle = wintypes.RECT()
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rectangle))
            return rectangle.left, rectangle.top, rectangle.right, rectangle.bottom
        if sys.platform == "darwin":
            raw = subprocess.check_output(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to tell first application process whose frontmost is true to get {position, size} of front window',
                ],
                text=True,
            )
            x, y, width, height = [int(x) for x in re.findall(r"-?\d+", raw)]
            return x, y, x + width, y + height
        raw = subprocess.check_output(
            ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"], text=True
        )
        data = dict(s.split("=", 1) for s in raw.splitlines() if "=" in s)
        x, y, width, height = [int(data[k]) for k in ("X", "Y", "WIDTH", "HEIGHT")]
        return x, y, x + width, y + height

    def words(self, region=None):

        api = self.desktop._api()
        left, top, right, bottom = self.bounds()
        image = api.screenshot()
        left, top = max(left, 0), max(top, 0)
        right, bottom = min(right, image.width), min(bottom, image.height)
        if region is None and self.main_bounds == (left, top, right, bottom):
            region = (left + (right - left) * 0.36, top + 110, right, bottom)
        if region:
            left, top = max(left, int(region[0])), max(top, int(region[1]))
            right, bottom = min(right, int(region[2])), min(bottom, int(region[3]))
        crop = image.crop((left, top, right, bottom)).convert("RGB")
        stream = io.BytesIO()
        crop.resize((crop.width * 2, crop.height * 2)).save(stream, format="PNG")
        # Bound OCR wall time and use a per-child OpenMP setting. Full-screen
        # Tesseract can otherwise spend minutes on a dense GL/UI composition.
        try:
            response = subprocess.run(
                ["tesseract", "stdin", "stdout", "--psm", "11", "tsv"],
                input=stream.getvalue(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                timeout=12,
                check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(
                "Native OCR did not complete; check system Tesseract and visible controls"
            ) from None
        rows = csv.DictReader(io.StringIO(response.stdout.decode("utf-8")), delimiter="\t")
        result = []
        for row in rows:
            text = row.get("text", "")
            if tokens(text):
                result.append(
                    {
                        "text": text,
                        "tokens": tokens(text),
                        "x": left + int(row["left"]) / 2,
                        "y": top + int(row["top"]) / 2,
                        "w": int(row["width"]) / 2,
                        "h": int(row["height"]) / 2,
                    }
                )
        return result

    @staticmethod
    def locate(words, phrase, region=None, all_matches=False):
        desired = tokens(phrase)
        candidates = []
        for first in words:
            if region and not (
                region[0] <= first["x"] <= region[2] and region[1] <= first["y"] <= region[3]
            ):
                continue
            row = sorted(
                (
                    w
                    for w in words
                    if abs((w["y"] + w["h"] / 2) - (first["y"] + first["h"] / 2)) <= 8
                ),
                key=lambda w: w["x"],
            )
            start = row.index(first)
            found, chosen = [], []
            for item in row[start:]:
                found.extend(item["tokens"])
                chosen.append(item)
                if found == desired:
                    candidates.append(
                        {
                            "x": first["x"],
                            "y": min(w["y"] for w in chosen),
                            "w": chosen[-1]["x"] + chosen[-1]["w"] - first["x"],
                            "h": max(w["h"] for w in chosen),
                        }
                    )
                    break
                if desired[: len(found)] != found:
                    break
        if all_matches:
            return candidates
        if len(candidates) != 1:
            raise ValueError(
                f"Native control {phrase!r} missing or ambiguous ({len(candidates)} matches)"
            )
        return candidates[0]

    def label(self, phrase, region=None):
        return self.locate(self.words(region), phrase, region)

    def click(self, phrase, region=None):
        box = self.label(phrase, region)
        self.desktop._api().click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)
        time.sleep(0.3)

    def key(self, *keys):
        self.desktop._api().hotkey(*keys)
        time.sleep(0.2)

    def paste(self, value):
        api = self.desktop._api()
        import pyperclip

        previous = pyperclip.paste()
        try:
            pyperclip.copy(str(value))
            api.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
            time.sleep(0.15)
        finally:
            pyperclip.copy(previous)

    def read_numeric(self, label, region=None, index=0, columns=None, required_unit=None):
        words = self.words(region)
        rows = []
        for anchor in self.locate(words, label, region, all_matches=True):
            mid = anchor["y"] + anchor["h"] / 2
            numbers = sorted(
                [
                    w
                    for w in words
                    if w["x"] > anchor["x"] + anchor["w"] + 5
                    and abs(w["y"] + w["h"] / 2 - mid) <= 10
                    and re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?(?:%|mm|°)?", w["text"])
                ],
                key=lambda w: w["x"],
            )
            if required_unit and not any(
                w["text"] == required_unit and abs(w["y"] + w["h"] / 2 - mid) <= 10 for w in words
            ):
                continue
            if len(numbers) > index and (columns is None or len(numbers) == columns):
                rows.append(numbers)
        if len(rows) != 1:
            raise ValueError(f"Numeric row next to {label!r} missing or ambiguous")
        box = rows[0][index]
        observed = float(re.sub(r"[^0-9.,+-]", "", box["text"]).replace(",", "."))
        return box, observed

    def numeric(
        self,
        label,
        value=None,
        delta=None,
        region=None,
        index=0,
        columns=None,
        commit="tab",
        required_unit=None,
        verify=False,
    ):
        box, old = self.read_numeric(label, region, index, columns, required_unit)
        target = old + delta if delta is not None else value
        if type(target) not in (int, float) or not math.isfinite(target):
            raise ValueError("Native numeric value must be finite")
        self.desktop._api().click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)
        self.key("command" if sys.platform == "darwin" else "ctrl", "a")
        # Numeric fields accept ASCII directly; this avoids clipboard ownership
        # races between X11/wx and the native ImGui canvas.
        self.desktop._api().write(format(target, ".10g"), interval=0.05)
        self.key(commit)
        time.sleep(0.3)
        result = {"before": old, "requested": target}
        if verify:
            _, observed = self.read_numeric(label, region, index, columns, required_unit)
            if not math.isclose(observed, target, rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError(f"Native field {label!r} did not retain the requested value")
            result["observed"] = observed
        return result

    def capture(self, phase):
        self.evidence.mkdir(parents=True, exist_ok=True)
        image = self.desktop._api().screenshot()
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        destination = self.evidence / (phase + ".png")
        atomic_bytes(destination, stream.getvalue())
        return str(destination)

    def main(self):
        left, top, right, _ = self.bounds()
        # Dialogs/bridge panels do not satisfy the native MainFrame toolbar check.
        self.label("Prepare", (left, top, right, top + 110))
        self.label("Project", (left, top, right, top + 110))
        self.main_bounds = self.bounds()
        return left, top, right

    def park_bridge(self):
        api = self.desktop._api()
        _, screen_height = api.size()
        if sys.platform == "win32":
            import pygetwindow

            windows = [
                w
                for w in pygetwindow.getWindowsWithTitle("RRS MCP Bridge")
                if w.title == "RRS MCP Bridge"
            ]
            if len(windows) != 1:
                raise ValueError("Expected one modeless RRS MCP Bridge window")
            windows[0].resizeTo(350, 180)
            windows[0].moveTo(0, screen_height - 200)
        elif sys.platform == "darwin":
            raise ValueError("Native window parking on macOS needs separate acceptance")
        else:
            pid = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowpid"], text=True
            ).strip()
            windows = subprocess.check_output(
                [
                    "xdotool",
                    "search",
                    "--all",
                    "--onlyvisible",
                    "--pid",
                    pid,
                    "--name",
                    "^RRS MCP Bridge$",
                ],
                text=True,
            ).splitlines()
            if len(windows) != 1:
                raise ValueError("Expected one modeless RRS MCP Bridge window in this Orca process")
            subprocess.run(["xdotool", "windowsize", windows[0], "350", "180"], check=True)
            subprocess.run(
                ["xdotool", "windowmove", windows[0], "0", str(screen_height - 200)], check=True
            )
        time.sleep(0.3)
        return {"title": "RRS MCP Bridge", "placement": "compact_bottom_left", "kept_running": True}

    def canvas(self):
        left, top, right = self.main()
        self.click("Prepare", (left, top + 25, right, top + 110))
        # The supported Prepare layout places the viewport below the right toolbar.
        # Focus it before shortcuts so Ctrl+A/Z cannot target a settings text box.
        self.desktop._api().click(right - 100, top + 160)
        time.sleep(0.2)
